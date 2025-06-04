
import sqlite3
import os
from datetime import datetime

def fix_database_schema():
    """Fix database schema issues"""
    db_path = os.path.join('instance', 'marathon_dashboard.db')
    
    if not os.path.exists(db_path):
        print("Database not found, will be created with correct schema")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if strava_api_usage table exists and fix columns
        cursor.execute("PRAGMA table_info(strava_api_usage)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'requests_made' in columns:
            print("Fixing strava_api_usage table schema...")
            
            # Rename old table
            cursor.execute("ALTER TABLE strava_api_usage RENAME TO strava_api_usage_old")
            
            # Create new table with correct schema
            cursor.execute("""
                CREATE TABLE strava_api_usage (
                    id INTEGER NOT NULL PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    requests_15min INTEGER DEFAULT 0,
                    requests_daily INTEGER DEFAULT 0,
                    last_request_time DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Migrate data
            cursor.execute("""
                INSERT INTO strava_api_usage (id, date, requests_daily, created_at, updated_at)
                SELECT id, date, COALESCE(requests_made, 0), created_at, updated_at
                FROM strava_api_usage_old
            """)
            
            # Drop old table
            cursor.execute("DROP TABLE strava_api_usage_old")
            print("Fixed strava_api_usage table schema")
        
        # Fix daily_summary table if needed
        cursor.execute("PRAGMA table_info(daily_summary)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Check for duplicate daily summaries and remove them
        cursor.execute("""
            DELETE FROM daily_summary 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM daily_summary 
                GROUP BY athlete_id, date(summary_date)
            )
        """)
        
        duplicates_removed = cursor.rowcount
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate daily summary records")
        
        # Check for duplicate planned workouts and remove them
        cursor.execute("""
            DELETE FROM planned_workout 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM planned_workout 
                GROUP BY athlete_id, date(workout_date)
            )
        """)
        
        workout_duplicates_removed = cursor.rowcount
        if workout_duplicates_removed > 0:
            print(f"Removed {workout_duplicates_removed} duplicate planned workout records")
        
        conn.commit()
        print("Database schema fixed successfully")
        
    except Exception as e:
        print(f"Error fixing database schema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database_schema()
