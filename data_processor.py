import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from models import Athlete, Activity, PlannedWorkout, DailySummary
from app import db

logger = logging.getLogger(__name__)

class DataProcessor:
    """Class for processing and benchmarking athlete performance data"""
    
    def __init__(self):
        pass
    
    def aggregate_daily_activities(self, activities: List[Activity]) -> Dict:
        """Aggregate multiple activities for a single day"""
        if not activities:
            return {}
        
        total_distance = sum(activity.distance_km for activity in activities)
        total_time_seconds = sum(activity.moving_time_seconds for activity in activities)
        
        # Calculate overall pace
        overall_pace = None
        if total_distance > 0:
            total_time_minutes = total_time_seconds / 60
            overall_pace = total_time_minutes / total_distance
        
        aggregated_data = {
            'total_distance_km': total_distance,
            'total_time_seconds': total_time_seconds,
            'overall_pace_min_per_km': overall_pace,
            'activity_count': len(activities),
            'activity_names': [activity.name for activity in activities]
        }
        
        return aggregated_data
    
    def calculate_variance(self, planned: float, actual: float) -> float:
        """Calculate percentage variance between planned and actual values"""
        if planned == 0:
            return 0.0
        
        variance = ((actual - planned) / planned) * 100
        return round(variance, 2)
    
    def determine_workout_status(self, distance_variance: float, pace_variance: float, 
                               planned_distance: float, actual_distance: float) -> str:
        """Determine the status of a workout based on performance metrics"""
        
        # If no actual activity recorded
        if actual_distance == 0:
            return "Missed Workout"
        
        # If no planned workout but activity recorded
        if planned_distance == 0:
            return "Extra Activity"
        
        # Define tolerance thresholds
        distance_tolerance = 10.0  # 10% tolerance
        pace_tolerance = 5.0       # 5% tolerance for pace
        
        distance_within_tolerance = abs(distance_variance) <= distance_tolerance
        pace_within_tolerance = abs(pace_variance) <= pace_tolerance
        
        if distance_within_tolerance and pace_within_tolerance:
            return "On Track"
        elif distance_variance < -distance_tolerance or pace_variance > pace_tolerance:
            return "Under-performed"
        elif distance_variance > distance_tolerance or pace_variance < -pace_tolerance:
            return "Over-performed"
        else:
            return "Partially Completed"
    
    def process_athlete_daily_performance(self, athlete_id: int, target_date: datetime) -> Optional[Dict]:
        """Process daily performance for a single athlete"""
        try:
            # Get planned workout for the date
            planned_workout = PlannedWorkout.query.filter_by(
                athlete_id=athlete_id,
                workout_date=target_date.date()
            ).first()
            
            # Get actual activities for the date
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            activities = Activity.query.filter(
                Activity.athlete_id == athlete_id,
                Activity.start_date >= start_of_day,
                Activity.start_date < end_of_day
            ).all()
            
            # Aggregate activities
            aggregated_activities = self.aggregate_daily_activities(activities)
            
            # Extract values
            planned_distance = planned_workout.planned_distance_km if planned_workout else 0
            planned_pace = planned_workout.planned_pace_min_per_km if planned_workout else 0
            actual_distance = aggregated_activities.get('total_distance_km', 0)
            actual_pace = aggregated_activities.get('overall_pace_min_per_km', 0)
            
            # Calculate variances
            distance_variance = self.calculate_variance(planned_distance, actual_distance)
            pace_variance = self.calculate_variance(planned_pace, actual_pace) if actual_pace else 0
            
            # Determine status
            status = self.determine_workout_status(
                distance_variance, pace_variance, planned_distance, actual_distance
            )
            
            # Prepare performance summary
            performance_summary = {
                'athlete_id': athlete_id,
                'summary_date': target_date.date(),
                'planned_distance_km': planned_distance,
                'actual_distance_km': actual_distance,
                'planned_pace_min_per_km': planned_pace,
                'actual_pace_min_per_km': actual_pace,
                'distance_variance_percent': distance_variance,
                'pace_variance_percent': pace_variance,
                'status': status,
                'activity_count': aggregated_activities.get('activity_count', 0),
                'activity_names': aggregated_activities.get('activity_names', []),
                'workout_type': planned_workout.workout_type if planned_workout else 'N/A',
                'planned_notes': planned_workout.notes if planned_workout else ''
            }
            
            logger.info(f"Processed daily performance for athlete {athlete_id}: {status}")
            return performance_summary
            
        except Exception as e:
            logger.error(f"Failed to process athlete daily performance: {e}")
            return None
    
    def save_daily_summary(self, performance_summary: Dict) -> bool:
        """Save daily performance summary to database"""
        try:
            # Check if summary already exists (using date only, not datetime)
            summary_date = performance_summary['summary_date']
            if isinstance(summary_date, datetime):
                summary_date = summary_date.date()
            
            existing_summary = DailySummary.query.filter_by(
                athlete_id=performance_summary['athlete_id'],
                summary_date=summary_date
            ).first()
            
            if existing_summary:
                # Update existing summary
                existing_summary.actual_distance_km = performance_summary['actual_distance_km']
                existing_summary.planned_distance_km = performance_summary['planned_distance_km']
                existing_summary.actual_pace_min_per_km = performance_summary['actual_pace_min_per_km']
                existing_summary.planned_pace_min_per_km = performance_summary['planned_pace_min_per_km']
                existing_summary.distance_variance_percent = performance_summary['distance_variance_percent']
                existing_summary.pace_variance_percent = performance_summary['pace_variance_percent']
                existing_summary.status = performance_summary['status']
                logger.info(f"Updated existing daily summary for athlete {performance_summary['athlete_id']}")
            else:
                # Create new summary
                daily_summary = DailySummary(
                    athlete_id=performance_summary['athlete_id'],
                    summary_date=performance_summary['summary_date'],
                    actual_distance_km=performance_summary['actual_distance_km'],
                    planned_distance_km=performance_summary['planned_distance_km'],
                    actual_pace_min_per_km=performance_summary['actual_pace_min_per_km'],
                    planned_pace_min_per_km=performance_summary['planned_pace_min_per_km'],
                    distance_variance_percent=performance_summary['distance_variance_percent'],
                    pace_variance_percent=performance_summary['pace_variance_percent'],
                    status=performance_summary['status'],
                    notes=f"Activities: {', '.join(performance_summary['activity_names'])}"
                )
                db.session.add(daily_summary)
            
            db.session.commit()
            logger.info(f"Saved daily summary for athlete {performance_summary['athlete_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save daily summary: {e}")
            db.session.rollback()
            return False
    
    def calculate_team_summary(self, target_date: datetime) -> Dict:
        """Calculate team-wide performance summary for a given date"""
        try:
            # Get all daily summaries for the date
            daily_summaries = DailySummary.query.filter_by(
                summary_date=target_date.date()
            ).all()
            
            if not daily_summaries:
                return {
                    'total_athletes': 0,
                    'completed_workouts': 0,
                    'completion_rate': 0,
                    'status_breakdown': {},
                    'average_distance_variance': 0,
                    'average_pace_variance': 0
                }
            
            # Calculate team metrics
            total_athletes = len(daily_summaries)
            completed_workouts = len([s for s in daily_summaries if s.status in ['On Track', 'Over-performed', 'Partially Completed']])
            completion_rate = (completed_workouts / total_athletes) * 100 if total_athletes > 0 else 0
            
            # Status breakdown
            status_breakdown = {}
            for summary in daily_summaries:
                status = summary.status or 'Unknown'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            # Average variances
            distance_variances = [s.distance_variance_percent for s in daily_summaries if s.distance_variance_percent is not None]
            pace_variances = [s.pace_variance_percent for s in daily_summaries if s.pace_variance_percent is not None]
            
            avg_distance_variance = sum(distance_variances) / len(distance_variances) if distance_variances else 0
            avg_pace_variance = sum(pace_variances) / len(pace_variances) if pace_variances else 0
            
            team_summary = {
                'summary_date': target_date.date(),
                'total_athletes': total_athletes,
                'completed_workouts': completed_workouts,
                'completion_rate': round(completion_rate, 1),
                'status_breakdown': status_breakdown,
                'average_distance_variance': round(avg_distance_variance, 2),
                'average_pace_variance': round(avg_pace_variance, 2)
            }
            
            logger.info(f"Calculated team summary: {completion_rate}% completion rate")
            return team_summary
            
        except Exception as e:
            logger.error(f"Failed to calculate team summary: {e}")
            return {}
    
    def format_pace(self, pace_min_per_km: float) -> str:
        """Format pace as MM:SS per km"""
        if not pace_min_per_km or pace_min_per_km <= 0:
            return "N/A"
        
        minutes = int(pace_min_per_km)
        seconds = int((pace_min_per_km - minutes) * 60)
        return f"{minutes}:{seconds:02d}"
    
    def format_distance(self, distance_km: float) -> str:
        """Format distance with appropriate decimal places"""
        if not distance_km:
            return "0.0 km"
        
        return f"{distance_km:.1f} km"
