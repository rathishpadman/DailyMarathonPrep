import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, func
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
            return {
                'total_distance_km': 0,
                'total_time_seconds': 0,
                'overall_pace_min_per_km': 0,
                'activity_count': 0,
                'activity_names': []
            }

        # FIX: Remove potential duplicates by using set of activity IDs
        unique_activities = []
        seen_ids = set()
        for activity in activities:
            if activity.id not in seen_ids:
                unique_activities.append(activity)
                seen_ids.add(activity.id)

        # Use unique activities for calculations
        total_distance = sum(activity.distance_km or 0 for activity in unique_activities)
        total_time_seconds = sum(activity.moving_time_seconds or 0 for activity in unique_activities)

        # Calculate overall pace
        overall_pace = 0
        if total_distance > 0 and total_time_seconds > 0:
            total_time_minutes = total_time_seconds / 60
            overall_pace = total_time_minutes / total_distance

        aggregated_data = {
            'total_distance_km': round(total_distance, 2),
            'total_time_seconds': total_time_seconds,
            'overall_pace_min_per_km': round(overall_pace, 2) if overall_pace else 0,
            'activity_count': len(unique_activities),
            'activity_names': [activity.name for activity in unique_activities if activity.name]
        }

        return aggregated_data

    def calculate_variance(self, planned: float, actual: float) -> float:
        """Calculate percentage variance between planned and actual values"""
        if not planned or planned == 0:
            return 0.0

        variance = ((actual - planned) / planned) * 100
        return round(variance, 2)

    def determine_workout_status(self, distance_variance: float, pace_variance: float, 
                               planned_distance: float, actual_distance: float) -> str:
        """Determine the status of a workout based on performance metrics"""

        # If no actual activity recorded
        if not actual_distance or actual_distance == 0:
            return "Missed Workout"

        # If no planned workout but activity recorded
        if not planned_distance or planned_distance == 0:
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
            # FIX: Use explicit date filtering to prevent timezone issues
            target_date_only = target_date.date() if isinstance(target_date, datetime) else target_date

            # Get planned workout for the date - FIX: Use .first() to ensure single result
            # Handle both date and datetime objects in workout_date
            planned_workout = db.session.query(PlannedWorkout).filter(
                and_(
                    PlannedWorkout.athlete_id == athlete_id,
                    func.date(PlannedWorkout.workout_date) == target_date_only
                )
            ).first()

            # Debug logging for planned workout matching
            if planned_workout:
                logger.debug(f"Found planned workout: Distance: {planned_workout.planned_distance_km}, Date: {planned_workout.workout_date}")
            else:
                logger.debug(f"No planned workout found for athlete {athlete_id} on {target_date_only}")

            # Get actual activities for the date - FIX: Use date-only comparison
            # Convert activity start_date to date for comparison
            activities = db.session.query(Activity).filter(
                and_(
                    Activity.athlete_id == athlete_id,
                    func.date(Activity.start_date) == target_date_only
                )
            ).distinct().all()

            # Debug logging for activity matching
            logger.debug(f"Looking for activities on date {target_date_only}")

            # Log found activities for debugging
            for activity in activities:
                logger.debug(f"Found activity: {activity.name}, Date: {activity.start_date}, Distance: {activity.distance_km}")

            # Debug logging for date comparison
            logger.debug(f"Processing athlete {athlete_id} for date {target_date_only}")
            logger.debug(f"Planned workout found: {planned_workout is not None}")
            if planned_workout:
                logger.debug(f"Planned distance: {planned_workout.planned_distance_km}")
            logger.debug(f"Activities found: {len(activities)}")

            # FIX: Log the number of activities found for debugging
            logger.debug(f"Found {len(activities)} activities for athlete {athlete_id} on {target_date_only}")

            # Aggregate activities
            aggregated_activities = self.aggregate_daily_activities(activities)

            # Extract values with proper null handling
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
                'summary_date': target_date_only,
                'planned_distance_km': round(planned_distance, 2) if planned_distance else 0,
                'actual_distance_km': round(actual_distance, 2) if actual_distance else 0,
                'planned_pace_min_per_km': round(planned_pace, 2) if planned_pace else 0,
                'actual_pace_min_per_km': round(actual_pace, 2) if actual_pace else 0,
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
            logger.error(f"Failed to process athlete daily performance for athlete {athlete_id}: {e}")
            return None

    def save_daily_summary(self, performance_summary: Dict) -> bool:
        """Save daily performance summary to database"""
        try:
            # Update last sync time in Strava API usage
            self._update_last_sync_time()
            
            # FIX: Ensure we're working with date objects consistently
            summary_date = performance_summary['summary_date']
            if isinstance(summary_date, datetime):
                summary_date = summary_date.date()

            athlete_id = performance_summary['athlete_id']

            # FIX: Use session.merge or explicit upsert pattern to prevent duplicates
            existing_summary = db.session.query(DailySummary).filter_by(
                athlete_id=athlete_id,
                summary_date=summary_date
            ).first()

            if existing_summary:
                # Update existing summary - FIX: Update all fields explicitly
                existing_summary.actual_distance_km = performance_summary.get('actual_distance_km', 0)
                existing_summary.planned_distance_km = performance_summary.get('planned_distance_km', 0)
                existing_summary.actual_pace_min_per_km = performance_summary.get('actual_pace_min_per_km', 0)
                existing_summary.planned_pace_min_per_km = performance_summary.get('planned_pace_min_per_km', 0)
                existing_summary.distance_variance_percent = performance_summary.get('distance_variance_percent', 0)
                existing_summary.pace_variance_percent = performance_summary.get('pace_variance_percent', 0)
                existing_summary.status = performance_summary.get('status', 'Unknown')
                existing_summary.notes = f"Activities: {', '.join(performance_summary.get('activity_names', []))}"
                existing_summary.updated_at = datetime.now()  # Add timestamp if column exists

                logger.info(f"Updated existing daily summary for athlete {athlete_id} on {summary_date}")
            else:
                # Create new summary
                daily_summary = DailySummary(
                    athlete_id=athlete_id,
                    summary_date=summary_date,
                    actual_distance_km=performance_summary.get('actual_distance_km', 0),
                    planned_distance_km=performance_summary.get('planned_distance_km', 0),
                    actual_pace_min_per_km=performance_summary.get('actual_pace_min_per_km', 0),
                    planned_pace_min_per_km=performance_summary.get('planned_pace_min_per_km', 0),
                    distance_variance_percent=performance_summary.get('distance_variance_percent', 0),
                    pace_variance_percent=performance_summary.get('pace_variance_percent', 0),
                    status=performance_summary.get('status', 'Unknown'),
                    notes=f"Activities: {', '.join(performance_summary.get('activity_names', []))}"
                )
                db.session.add(daily_summary)
                logger.info(f"Created new daily summary for athlete {athlete_id} on {summary_date}")

            # FIX: Flush before commit to catch constraint violations early
            db.session.flush()
            db.session.commit()

            logger.info(f"Successfully saved daily summary for athlete {athlete_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save daily summary for athlete {performance_summary.get('athlete_id')}: {e}")
            db.session.rollback()
            return False

    def calculate_team_summary(self, target_date: datetime) -> Dict:
        """Calculate team-wide performance summary for a given date"""
        try:
            # FIX: Ensure consistent date handling
            target_date_only = target_date.date() if isinstance(target_date, datetime) else target_date

            # Get all daily summaries for the date - FIX: Use distinct to prevent duplicates
            daily_summaries = db.session.query(DailySummary).filter_by(
                summary_date=target_date_only
            ).distinct().all()

            # FIX: Remove any potential duplicates by athlete_id
            unique_summaries = {}
            for summary in daily_summaries:
                key = f"{summary.athlete_id}_{summary.summary_date}"
                if key not in unique_summaries:
                    unique_summaries[key] = summary

            daily_summaries = list(unique_summaries.values())

            if not daily_summaries:
                return {
                    'summary_date': target_date_only,
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

            # Average variances - FIX: Handle None values properly
            distance_variances = [s.distance_variance_percent for s in daily_summaries 
                                if s.distance_variance_percent is not None and s.distance_variance_percent != 0]
            pace_variances = [s.pace_variance_percent for s in daily_summaries 
                            if s.pace_variance_percent is not None and s.pace_variance_percent != 0]

            avg_distance_variance = sum(distance_variances) / len(distance_variances) if distance_variances else 0
            avg_pace_variance = sum(pace_variances) / len(pace_variances) if pace_variances else 0

            team_summary = {
                'summary_date': target_date_only,
                'total_athletes': total_athletes,
                'completed_workouts': completed_workouts,
                'completion_rate': round(completion_rate, 1),
                'status_breakdown': status_breakdown,
                'average_distance_variance': round(avg_distance_variance, 2),
                'average_pace_variance': round(avg_pace_variance, 2)
            }

            logger.info(f"Calculated team summary for {target_date_only}: {completion_rate}% completion rate")
            return team_summary

        except Exception as e:
            logger.error(f"Failed to calculate team summary for {target_date}: {e}")
            return {
                'summary_date': target_date.date() if isinstance(target_date, datetime) else target_date,
                'total_athletes': 0,
                'completed_workouts': 0,
                'completion_rate': 0,
                'status_breakdown': {},
                'average_distance_variance': 0,
                'average_pace_variance': 0
            }

    # FIX: Add method to clean up duplicate summaries
    def cleanup_duplicate_workouts(self) -> int:
        """Remove duplicate planned workouts, keeping the most recent one"""
        try:
            from sqlalchemy import func
            
            # Find all duplicate groups
            duplicates_query = db.session.query(
                PlannedWorkout.athlete_id,
                func.date(PlannedWorkout.workout_date).label('workout_date'),
                func.count(PlannedWorkout.id).label('count')
            ).group_by(
                PlannedWorkout.athlete_id,
                func.date(PlannedWorkout.workout_date)
            ).having(func.count(PlannedWorkout.id) > 1).all()

            total_removed = 0
            
            for dup in duplicates_query:
                # Get all records for this athlete/date combination
                duplicate_records = db.session.query(PlannedWorkout).filter(
                    PlannedWorkout.athlete_id == dup.athlete_id,
                    func.date(PlannedWorkout.workout_date) == dup.workout_date
                ).order_by(PlannedWorkout.id.desc()).all()
                
                if len(duplicate_records) > 1:
                    # Keep the first one (highest ID), delete the rest
                    for record in duplicate_records[1:]:
                        db.session.delete(record)
                        total_removed += 1
            
            if total_removed > 0:
                db.session.commit()
                logger.info(f"Removed {total_removed} duplicate planned workouts")
            
            return total_removed
            
        except Exception as e:
            logger.error(f"Failed to cleanup duplicate workouts: {e}")
            db.session.rollback()
            return 0

    def cleanup_duplicate_summaries(self, target_date: datetime = None) -> int:
        """Remove duplicate daily summaries for a given date or all dates"""
        try:
            query = db.session.query(DailySummary)
            if target_date:
                target_date_only = target_date.date() if isinstance(target_date, datetime) else target_date
                query = query.filter_by(summary_date=target_date_only)

            all_summaries = query.all()

            # Group by athlete_id and summary_date
            grouped_summaries = {}
            for summary in all_summaries:
                key = f"{summary.athlete_id}_{summary.summary_date}"
                if key not in grouped_summaries:
                    grouped_summaries[key] = []
                grouped_summaries[key].append(summary)

            duplicates_removed = 0
            for key, summaries in grouped_summaries.items():
                if len(summaries) > 1:
                    # Keep the most recent one, delete others
                    summaries.sort(key=lambda x: x.id, reverse=True)
                    for duplicate in summaries[1:]:
                        db.session.delete(duplicate)
                        duplicates_removed += 1

            if duplicates_removed > 0:
                db.session.commit()
                logger.info(f"Removed {duplicates_removed} duplicate daily summaries")

            return duplicates_removed

        except Exception as e:
            logger.error(f"Failed to cleanup duplicate summaries: {e}")
            db.session.rollback()
            return 0

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
    
    def _update_last_sync_time(self):
        """Update the last sync time in Strava API usage tracking"""
        try:
            from models import StravaApiUsage
            from app import db
            
            today = datetime.now().date()
            usage = db.session.query(StravaApiUsage).filter_by(date=today).first()
            
            if not usage:
                usage = StravaApiUsage(date=today)
                db.session.add(usage)
            
            usage.last_sync_time = datetime.now()
            usage.updated_at = datetime.now()
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating last sync time: {e}")
            # Don't raise exception as this is not critical