import schedule
import time
import logging
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

from strava_client import StravaClient
from excel_reader import ExcelReader
from data_processor import DataProcessor
from dashboard_builder import DashboardBuilder
from notifier import NotificationManager
from models import Athlete, Activity, PlannedWorkout, SystemLog
from app import app, db
from config import Config

logger = logging.getLogger(__name__)

class DailyTaskScheduler:
    """Class for scheduling and executing daily marathon dashboard tasks"""
    
    def __init__(self):
        self.strava_client = StravaClient()
        self.excel_reader = ExcelReader()
        self.data_processor = DataProcessor()
        self.dashboard_builder = DashboardBuilder()
        self.notification_manager = NotificationManager()
    
    def execute_daily_tasks(self) -> bool:
        """Execute the complete daily task workflow"""
        execution_date = datetime.now()
        yesterday = execution_date - timedelta(days=1)
        
        logger.info(f"Starting daily task execution for {yesterday.strftime('%Y-%m-%d')}")
        
        try:
            with app.app_context():
                # Step 1: Update training plan from Excel
                self._update_training_plan()
                
                # Step 2: Fetch and process Strava data for all athletes
                self._fetch_and_process_strava_data(yesterday)
                
                # Step 3: Generate dashboard
                dashboard_data = self.dashboard_builder.build_daily_dashboard(yesterday)
                
                # Step 4: Send notifications
                if dashboard_data:
                    whatsapp_summary = self.dashboard_builder.build_whatsapp_summary(dashboard_data)
                    notification_sent = self.notification_manager.send_daily_notification(whatsapp_summary)
                    
                    if notification_sent:
                        self._log_system_event("SUCCESS", "Daily tasks completed successfully")
                        logger.info("Daily tasks completed successfully")
                        return True
                    else:
                        self._log_system_event("WARNING", "Dashboard generated but notification failed")
                        logger.warning("Dashboard generated but notification failed")
                        return False
                else:
                    self._log_system_event("ERROR", "Failed to generate dashboard")
                    logger.error("Failed to generate dashboard")
                    return False
                
        except Exception as e:
            error_msg = f"Daily task execution failed: {e}"
            self._log_system_event("ERROR", error_msg)
            logger.error(error_msg)
            return False
    
    def _update_training_plan(self) -> bool:
        """Update training plan from Excel file"""
        try:
            # Validate Excel file format
            validation_results = self.excel_reader.validate_excel_format()
            
            if not all(validation_results.values()):
                logger.error(f"Excel file validation failed: {validation_results}")
                return False
            
            # Read training plan
            training_df = self.excel_reader.read_training_plan()
            if training_df is None:
                logger.error("Failed to read training plan")
                return False
            
            # Get athletes from training plan
            athletes_in_plan = self.excel_reader.get_athletes_list()
            
            # Ensure athletes exist in database
            for athlete_name in athletes_in_plan:
                athlete = Athlete.query.filter_by(name=athlete_name).first()
                if not athlete:
                    # Create new athlete record
                    athlete = Athlete(name=athlete_name, is_active=True)
                    db.session.add(athlete)
                    logger.info(f"Created new athlete record: {athlete_name}")
            
            db.session.commit()
            
            # Update planned workouts
            self._update_planned_workouts(training_df)
            
            logger.info("Training plan updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update training plan: {e}")
            return False
    
    def _update_planned_workouts(self, training_df) -> bool:
        """Update planned workouts in database from training plan"""
        try:
            for _, row in training_df.iterrows():
                athlete = Athlete.query.filter_by(name=row['AthleteName']).first()
                if not athlete:
                    continue
                
                # Check if workout already exists
                existing_workout = PlannedWorkout.query.filter_by(
                    athlete_id=athlete.id,
                    workout_date=row['Date'].date()
                ).first()
                
                if existing_workout:
                    # Update existing workout
                    existing_workout.planned_distance_km = row['PlannedDistanceKM']
                    existing_workout.planned_pace_min_per_km = row['PlannedPaceMinPerKM']
                    existing_workout.workout_type = row['WorkoutType']
                    existing_workout.notes = row['Notes']
                else:
                    # Create new workout
                    new_workout = PlannedWorkout(
                        athlete_id=athlete.id,
                        workout_date=row['Date'].date(),
                        planned_distance_km=row['PlannedDistanceKM'],
                        planned_pace_min_per_km=row['PlannedPaceMinPerKM'],
                        workout_type=row['WorkoutType'],
                        notes=row['Notes']
                    )
                    db.session.add(new_workout)
            
            db.session.commit()
            logger.info("Planned workouts updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update planned workouts: {e}")
            db.session.rollback()
            return False
    
    def _fetch_and_process_strava_data(self, target_date: datetime) -> bool:
        """Fetch and process Strava data for all athletes"""
        try:
            athletes = Athlete.query.filter_by(is_active=True).all()
            
            for athlete in athletes:
                if not athlete.refresh_token:
                    logger.warning(f"No refresh token for athlete {athlete.name}")
                    continue
                
                # Refresh access token
                token_data = self.strava_client.refresh_access_token(athlete.refresh_token)
                if not token_data:
                    logger.error(f"Failed to refresh token for athlete {athlete.name}")
                    continue
                
                # Update athlete token data
                athlete.access_token = token_data['access_token']
                athlete.token_expires_at = datetime.fromtimestamp(token_data['expires_at'])
                if 'refresh_token' in token_data:
                    athlete.refresh_token = token_data['refresh_token']
                
                # Fetch activities for target date
                start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = start_of_day + timedelta(days=1)
                
                activities = self.strava_client.get_athlete_activities(
                    athlete.access_token, start_of_day, end_of_day
                )
                
                # Process and save activities
                for activity_data in activities:
                    processed_activity = self.strava_client.process_activity_data(activity_data)
                    if processed_activity:
                        self._save_activity(athlete.id, processed_activity)
                
                # Process daily performance
                performance_summary = self.data_processor.process_athlete_daily_performance(
                    athlete.id, target_date
                )
                
                if performance_summary:
                    self.data_processor.save_daily_summary(performance_summary)
            
            db.session.commit()
            logger.info("Strava data fetched and processed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fetch and process Strava data: {e}")
            db.session.rollback()
            return False
    
    def _save_activity(self, athlete_id: int, activity_data: dict) -> bool:
        """Save activity to database"""
        try:
            # Check if activity already exists
            existing_activity = Activity.query.filter_by(
                strava_activity_id=activity_data['strava_activity_id']
            ).first()
            
            if existing_activity:
                logger.info(f"Activity {activity_data['strava_activity_id']} already exists")
                return True
            
            # Create new activity
            activity = Activity(
                strava_activity_id=activity_data['strava_activity_id'],
                athlete_id=athlete_id,
                name=activity_data['name'],
                activity_type=activity_data['activity_type'],
                start_date=activity_data['start_date'],
                distance_km=activity_data['distance_km'],
                moving_time_seconds=activity_data['moving_time_seconds'],
                pace_min_per_km=activity_data['pace_min_per_km']
            )
            
            db.session.add(activity)
            logger.info(f"Saved activity {activity_data['strava_activity_id']} for athlete {athlete_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save activity: {e}")
            return False
    
    def _log_system_event(self, log_type: str, message: str, details: str = None):
        """Log system events to database"""
        try:
            system_log = SystemLog(
                log_date=datetime.now(),
                log_type=log_type,
                message=message,
                details=details
            )
            db.session.add(system_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
    
    def schedule_daily_execution(self):
        """Schedule the daily task execution"""
        execution_time = Config.DAILY_EXECUTION_TIME
        schedule.every().day.at(execution_time).do(self.execute_daily_tasks)
        
        logger.info(f"Scheduled daily execution at {execution_time}")
        
        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def start_scheduler_thread(self):
        """Start the scheduler in a separate thread"""
        scheduler_thread = Thread(target=self.schedule_daily_execution, daemon=True)
        scheduler_thread.start()
        logger.info("Scheduler thread started")
    
    def manual_execution(self, target_date: Optional[datetime] = None) -> bool:
        """Manually execute tasks for a specific date (for testing/debugging)"""
        if target_date is None:
            target_date = datetime.now()
        
        logger.info(f"Manual execution for {target_date.strftime('%Y-%m-%d')}")
        return self.execute_daily_tasks(target_date)


# Global scheduler instance
daily_scheduler = DailyTaskScheduler()

def init_scheduler():
    """Initialize the scheduler (called from app startup)"""
    try:
        # Start the scheduler thread
        daily_scheduler.start_scheduler_thread()
        logger.info("Daily task scheduler initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")

def run_manual_task(target_date: Optional[datetime] = None) -> bool:
    """Function to manually trigger tasks (for testing)"""
    return daily_scheduler.manual_execution(target_date)
