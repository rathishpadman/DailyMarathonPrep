
#!/usr/bin/env python3
"""
Script to remove duplicate planned workouts from the database.
Keeps the most recent record (highest ID) for each athlete_id + workout_date combination.
"""

import logging
from datetime import datetime
from sqlalchemy import text, func
from app import app, db
from models import PlannedWorkout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_duplicate_workouts():
    """Find and return duplicate workout information"""
    try:
        # Query to find duplicates
        duplicates_query = db.session.query(
            PlannedWorkout.athlete_id,
            func.date(PlannedWorkout.workout_date).label('workout_date'),
            func.count(PlannedWorkout.id).label('count'),
            func.group_concat(PlannedWorkout.id.op('ORDER BY')(PlannedWorkout.id)).label('all_ids')
        ).group_by(
            PlannedWorkout.athlete_id,
            func.date(PlannedWorkout.workout_date)
        ).having(func.count(PlannedWorkout.id) > 1).all()

        logger.info(f"Found {len(duplicates_query)} groups with duplicates")
        
        for dup in duplicates_query:
            logger.info(f"Athlete {dup.athlete_id}, Date {dup.workout_date}: {dup.count} records (IDs: {dup.all_ids})")
        
        return duplicates_query
    
    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        return []

def remove_duplicate_workouts():
    """Remove duplicate planned workouts, keeping the most recent one"""
    try:
        with app.app_context():
            # Find duplicates first
            duplicates = find_duplicate_workouts()
            
            if not duplicates:
                logger.info("No duplicate workouts found")
                return 0
            
            total_removed = 0
            
            # Process each group of duplicates
            for dup in duplicates:
                athlete_id = dup.athlete_id
                workout_date = dup.workout_date
                
                # Get all records for this athlete/date combination
                duplicate_records = db.session.query(PlannedWorkout).filter(
                    PlannedWorkout.athlete_id == athlete_id,
                    func.date(PlannedWorkout.workout_date) == workout_date
                ).order_by(PlannedWorkout.id.desc()).all()
                
                if len(duplicate_records) > 1:
                    # Keep the first one (highest ID), delete the rest
                    records_to_delete = duplicate_records[1:]
                    
                    logger.info(f"Keeping workout ID {duplicate_records[0].id} for athlete {athlete_id} on {workout_date}")
                    logger.info(f"Deleting {len(records_to_delete)} duplicate records")
                    
                    for record in records_to_delete:
                        logger.info(f"Deleting workout ID {record.id}")
                        db.session.delete(record)
                        total_removed += 1
            
            # Commit all changes
            db.session.commit()
            logger.info(f"Successfully removed {total_removed} duplicate workout records")
            
            # Verify cleanup
            remaining_duplicates = find_duplicate_workouts()
            if not remaining_duplicates:
                logger.info("Cleanup successful - no duplicates remaining")
            else:
                logger.warning(f"Warning: {len(remaining_duplicates)} duplicate groups still exist")
            
            return total_removed
            
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        db.session.rollback()
        return 0

def show_workout_summary():
    """Show summary of planned workouts after cleanup"""
    try:
        with app.app_context():
            total_workouts = db.session.query(PlannedWorkout).count()
            unique_athletes = db.session.query(PlannedWorkout.athlete_id).distinct().count()
            unique_dates = db.session.query(func.date(PlannedWorkout.workout_date)).distinct().count()
            
            logger.info(f"Summary after cleanup:")
            logger.info(f"  Total planned workouts: {total_workouts}")
            logger.info(f"  Unique athletes: {unique_athletes}")
            logger.info(f"  Unique workout dates: {unique_dates}")
            
            return {
                'total_workouts': total_workouts,
                'unique_athletes': unique_athletes,
                'unique_dates': unique_dates
            }
    
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return None

if __name__ == "__main__":
    logger.info("Starting duplicate workout cleanup process...")
    
    # Show current state
    logger.info("=== BEFORE CLEANUP ===")
    find_duplicate_workouts()
    show_workout_summary()
    
    # Remove duplicates
    logger.info("=== PERFORMING CLEANUP ===")
    removed_count = remove_duplicate_workouts()
    
    # Show final state
    logger.info("=== AFTER CLEANUP ===")
    show_workout_summary()
    
    logger.info(f"Cleanup complete. Removed {removed_count} duplicate records.")
