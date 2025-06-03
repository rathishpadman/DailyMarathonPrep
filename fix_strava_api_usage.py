
#!/usr/bin/env python3

import sqlite3
import logging
from pathlib import Path

def fix_strava_api_usage_table():
    """Fix the StravaApiUsage table schema"""
    db_path = Path('marathon_dashboard.db')
    if not db_path.exists():
        db_path = Path('instance/marathon_dashboard.db')
    
    if not db_path.exists():
        print("Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current table structure
        cursor.execute("PRAGMA table_info(strava_api_usage)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Check if we need to migrate
        if 'requests_made' in columns and 'requests_15min' not in columns:
            print("Migrating StravaApiUsage table...")
            
            # Create new table with correct structure
            cursor.execute('''
                CREATE TABLE strava_api_usage_new (
                    id INTEGER PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    requests_15min INTEGER DEFAULT 0,
                    requests_daily INTEGER DEFAULT 0,
                    limit_reached BOOLEAN DEFAULT 0,
                    last_sync_time DATETIME,
                    last_request_time DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Copy data from old table
            cursor.execute('''
                INSERT INTO strava_api_usage_new 
                (id, date, requests_daily, limit_reached, last_sync_time, created_at, updated_at)
                SELECT id, date, 
                       COALESCE(requests_made, 0) as requests_daily,
                       COALESCE(limit_reached, 0),
                       last_sync_time, created_at, updated_at
                FROM strava_api_usage
            ''')
            
            # Drop old table and rename new one
            cursor.execute('DROP TABLE strava_api_usage')
            cursor.execute('ALTER TABLE strava_api_usage_new RENAME TO strava_api_usage')
            
            conn.commit()
            print("StravaApiUsage table migration completed successfully")
            
        else:
            print("StravaApiUsage table already has correct structure")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error fixing StravaApiUsage table: {e}")
        return False

if __name__ == "__main__":
    fix_strava_api_usage_table()
