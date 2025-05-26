import schedule
import time
import logging
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import Config
from strava_client import StravaClient
from excel_reader import ExcelReader
from data_processor import DataProcessor
from dashboard_builder import DashboardBuilder
from notifier import NotificationManager
from models import Athlete, Activity, PlannedWorkout, SystemLog
from app import app, db

logger = logging.getLogger(__name__)

class DailyTaskScheduler:
    """Class for scheduling and executing daily marathon dashboard tasks"""

    def __init__(self):
        self.strava_client = StravaClient()
        self.excel_reader = ExcelReader(Config.TRAINING_PLAN_FILE)
        self.data_processor = DataProcessor()
        self.dashboard_builder = DashboardBuilder()
        self.notification_manager = NotificationManager()
        self.is_running = False  # Prevent concurrent executions

    def execute_daily_tasks(self, target_date: datetime = None) -> bool:
        """Execute the complete daily task workflow"""
        if self.is_running:
            logger.warning("Daily tasks already running, skipping execution")
            return False

        self.is_running = True

        try:
            if target_date is None:
                target_date = datetime.now()

            logger.info(f"Starting daily task execution for {target_date.strftime('%Y-%m-%d')}")

            with app.app_context():
                # Step 1: Update training plan from Excel
                plan_updated = self._update_training_plan()
                if not plan_updated:
                    self._log_system_event("WARNING", "Training plan update failed, continuing with existing data")

                # Step 2: Fetch and process Strava data for all athletes
                strava_success = self._fetch_and_process_strava_data(target_date)
                if not strava_success:
                    self._log_system_event("ERROR", "Strava data fetch failed")
                    return False

                # Step 3: Generate dashboard
                dashboard_data = self.dashboard_builder.build_daily_dashboard(target_date)

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
        finally:
            self.is_running = False

    def _update_training_plan(self) -> bool:
        """Update training plan from Excel file"""
        try:
            # Use the current training plan file from config
            self.excel_reader = ExcelReader(Config.TRAINING_PLAN_FILE)
            
            # Validate Excel file format
            validation_results = self.excel_reader.validate_excel_format()

            if not all(validation_results.values()):
                logger.error(f"Excel file validation failed: {validation_results}")
                return False

            # Read training plan
            training_df = self.excel_reader.read_training_plan()
            if training_df is None or training_df.empty:
                logger.error("Failed to read training plan or training plan is empty")
                return False

            # Get athletes from training plan
            athletes_in_plan = self.excel_reader.get_athletes_list()
            if not athletes_in_plan:
                logger.error("No athletes found in training plan")
                return False

            # Ensure athletes exist in database
            for athlete_name in athletes_in_plan:
                try:
                    athlete = Athlete.query.filter_by(name=athlete_name).first()
                    if not athlete:
                        # Create new athlete record
                        athlete = Athlete(name=athlete_name, is_active=True)
                        db.session.add(athlete)
                        logger.info(f"Created new athlete record: {athlete_name}")
                except Exception as e:
                    logger.error(f"Failed to create athlete {athlete_name}: {e}")
                    continue

            # Commit athlete changes first
            try:
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to commit athlete changes: {e}")
                db.session.rollback()
                return False

            # Update planned workouts
            workouts_updated = self._update_planned_workouts(training_df)

            if workouts_updated:
                logger.info("Training plan updated successfully")
                return True
            else:
                logger.error("Failed to update planned workouts")
                return False

        except Exception as e:
            logger.error(f"Failed to update training plan: {e}")
            db.session.rollback()
            return False

    def _update_planned_workouts(self, training_df) -> bool:
        """Update planned workouts in database from training plan"""
        try:
            updated_count = 0
            created_count = 0

            for _, row in training_df.iterrows():
                try:
                    athlete = Athlete.query.filter_by(name=row['AthleteName']).first()
                    if not athlete:
                        logger.warning(f"Athlete not found: {row['AthleteName']}")
                        continue

                    # Validate required fields
                    if not row.get('Date') or not row.get('PlannedDistanceKM'):
                        logger.warning(f"Missing required fields for workout: {row}")
                        continue

                    workout_date = row['Date'].date() if hasattr(row['Date'], 'date') else row['Date']

                    # Check if workout already exists
                    existing_workout = PlannedWorkout.query.filter_by(
                        athlete_id=athlete.id,
                        workout_date=workout_date
                    ).first()

                    if existing_workout:
                        # Update existing workout
                        existing_workout.planned_distance_km = row.get('PlannedDistanceKM', 0)
                        existing_workout.planned_pace_min_per_km = row.get('PlannedPaceMinPerKM')
                        existing_workout.workout_type = row.get('WorkoutType', 'General')
                        existing_workout.notes = row.get('Notes', '')
                        updated_count += 1
                    else:
                        # Create new workout
                        new_workout = PlannedWorkout(
                            athlete_id=athlete.id,
                            workout_date=workout_date,
                            planned_distance_km=row.get('PlannedDistanceKM', 0),
                            planned_pace_min_per_km=row.get('PlannedPaceMinPerKM'),
                            workout_type=row.get('WorkoutType', 'General'),
                            notes=row.get('Notes', '')
                        )
                        db.session.add(new_workout)
                        created_count += 1

                except Exception as e:
                    logger.error(f"Failed to process workout row {row}: {e}")
                    continue

            # Commit all changes
            db.session.commit()
            logger.info(f"Planned workouts updated: {updated_count} updated, {created_count} created")
            return True

        except Exception as e:
            logger.error(f"Failed to update planned workouts: {e}")
            db.session.rollback()
            return False

    def _fetch_and_process_strava_data(self, target_date: datetime) -> bool:
        """Fetch and process Strava data for all athletes"""
        try:
            athletes = Athlete.query.filter_by(is_active=True).all()

            if not athletes:
                logger.warning("No active athletes found")
                return True  # Not an error, just no data to process

            successful_athletes = 0

            for athlete in athletes:
                try:
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

                    # Commit token updates immediately
                    db.session.commit()

                    # Fetch activities for target date
                    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_day = start_of_day + timedelta(days=1)

                    activities = self.strava_client.get_athlete_activities(
                        athlete.access_token, start_of_day, end_of_day
                    )

                    if not activities:
                        logger.info(f"No activities found for athlete {athlete.name} on {target_date.strftime('%Y-%m-%d')}")
                        successful_athletes += 1
                        continue

                    # Process and save activities
                    saved_activities = 0
                    for activity_data in activities:
                        try:
                            processed_activity = self.strava_client.process_activity_data(activity_data)
                            if processed_activity:
                                if self._save_activity(athlete.id, processed_activity):
                                    saved_activities += 1
                        except Exception as e:
                            logger.error(f"Failed to process activity for athlete {athlete.name}: {e}")
                            continue

                    logger.info(f"Processed {saved_activities} activities for athlete {athlete.name}")

                    # Process daily performance
                    try:
                        performance_summary = self.data_processor.process_athlete_daily_performance(
                            athlete.id, target_date
                        )

                        if performance_summary:
                            self.data_processor.save_daily_summary(performance_summary)
                    except Exception as e:
                        logger.error(f"Failed to process daily performance for athlete {athlete.name}: {e}")

                    successful_athletes += 1

                except Exception as e:
                    logger.error(f"Failed to process athlete {athlete.name}: {e}")
                    db.session.rollback()
                    continue

            logger.info(f"Successfully processed {successful_athletes}/{len(athletes)} athletes")
            return successful_athletes > 0

        except Exception as e:
            logger.error(f"Failed to fetch and process Strava data: {e}")
            db.session.rollback()
            return False

    def _save_activity(self, athlete_id: int, activity_data: dict) -> bool:
        """Save activity to database with comprehensive duplicate prevention"""
        if not activity_data or not activity_data.get('strava_activity_id'):
            logger.warning("Invalid activity data provided")
            return False

        try:
            # Check for duplicates by Strava ID first (most reliable)
            existing_by_strava_id = Activity.query.filter_by(
                strava_activity_id=activity_data['strava_activity_id']
            ).first()

            if existing_by_strava_id:
                logger.debug(f"Activity {activity_data['strava_activity_id']} already exists (by Strava ID)")
                return True

            # Secondary check: athlete + date + name combination
            if activity_data.get('start_date') and activity_data.get('name'):
                existing_by_combination = Activity.query.filter_by(
                    athlete_id=athlete_id,
                    start_date=activity_data['start_date'],
                    name=activity_data['name']
                ).first()

                if existing_by_combination:
                    logger.debug(f"Similar activity already exists for athlete {athlete_id} on {activity_data['start_date']}")
                    return True

            # Create new activity with validation
            activity = Activity(
                strava_activity_id=activity_data['strava_activity_id'],
                athlete_id=athlete_id,
                name=activity_data.get('name', 'Unknown Activity'),
                activity_type=activity_data.get('activity_type', 'Unknown'),
                start_date=activity_data.get('start_date'),
                distance_km=activity_data.get('distance_km', 0.0),
                moving_time_seconds=activity_data.get('moving_time_seconds', 0),
                pace_min_per_km=activity_data.get('pace_min_per_km', 0.0)
            )

            db.session.add(activity)
            db.session.commit()

            logger.info(f"Saved activity {activity_data['strava_activity_id']} for athlete {athlete_id}")
            return True

        except IntegrityError as e:
            # Handle database constraint violations (duplicate keys)
            db.session.rollback()
            logger.info(f"Activity {activity_data['strava_activity_id']} already exists (integrity constraint)")
            return True
        except SQLAlchemyError as e:
            # Handle other database errors
            db.session.rollback()
            logger.error(f"Database error saving activity {activity_data.get('strava_activity_id')}: {e}")
            return False
        except Exception as e:
            # Handle any other errors
            db.session.rollback()
            logger.error(f"Unexpected error saving activity {activity_data.get('strava_activity_id')}: {e}")
            return False

    def _log_system_event(self, log_type: str, message: str, details: str = None):
        """Log system events to database with error handling"""
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
            db.session.rollback()

    def schedule_daily_execution(self):
        """Schedule the daily task execution - 3 times per day"""
        try:
            # Clear any existing scheduled jobs
            schedule.clear()

            # Schedule 3 syncs per day: 9 AM, 5 PM, and 10 PM
            schedule.every().day.at("09:00").do(self._safe_execute_daily_tasks)
            schedule.every().day.at("17:00").do(self._safe_execute_daily_tasks)  # 5 PM
            schedule.every().day.at("22:00").do(self._safe_execute_daily_tasks)  # 10 PM

            logger.info("Scheduled daily Strava syncs at 9:00 AM, 5:00 PM, and 10:00 PM")

            # Keep the scheduler running
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def _safe_execute_daily_tasks(self):
        """Wrapper for execute_daily_tasks with additional error handling"""
        try:
            return self.execute_daily_tasks()
        except Exception as e:
            logger.error(f"Unexpected error in scheduled task execution: {e}")
            self.is_running = False  # Reset the running flag
            return False

    def start_scheduler_thread(self):
        """Start the scheduler in a separate thread"""
        try:
            scheduler_thread = Thread(target=self.schedule_daily_execution, daemon=True)
            scheduler_thread.start()
            logger.info("Scheduler thread started")
        except Exception as e:
            logger.error(f"Failed to start scheduler thread: {e}")

    def manual_execution(self, target_date: Optional[datetime] = None) -> bool:
        """Manually execute tasks for a specific date (for testing/debugging)"""
        if target_date is None:
            target_date = datetime.now()

        logger.info(f"Manual execution for {target_date.strftime('%Y-%m-%d')}")
        return self.execute_daily_tasks(target_date)

    def health_check(self) -> dict:
        """Perform a health check of the scheduler system"""
        try:
            with app.app_context():
                health_status = {
                    'scheduler_running': not self.is_running,  # Available for new runs
                    'database_connection': False,
                    'active_athletes': 0,
                    'recent_activities': 0,
                    'last_successful_run': None
                }

                # Test database connection
                try:
                    health_status['active_athletes'] = Athlete.query.filter_by(is_active=True).count()
                    health_status['database_connection'] = True
                except Exception as e:
                    logger.error(f"Database connection failed: {e}")

                # Check recent activities
                try:
                    yesterday = datetime.now() - timedelta(days=1)
                    health_status['recent_activities'] = Activity.query.filter(
                        Activity.start_date >= yesterday
                    ).count()
                except Exception as e:
                    logger.error(f"Failed to count recent activities: {e}")

                # Check last successful run
                try:
                    last_success = SystemLog.query.filter_by(
                        log_type='SUCCESS'
                    ).order_by(SystemLog.log_date.desc()).first()

                    if last_success:
                        health_status['last_successful_run'] = last_success.log_date.isoformat()
                except Exception as e:
                    logger.error(f"Failed to get last successful run: {e}")

                return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'error': str(e)}


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

def get_scheduler_health() -> dict:
    """Get scheduler health status"""
    return daily_scheduler.health_check()