
from app import app, db
from models import Activity

def migrate_activity_fields():
    """Add new fields to Activity table"""
    with app.app_context():
        try:
            # Check if fields already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('activity')]
            
            new_fields = ['average_speed', 'average_heartrate', 'max_heartrate', 'total_elevation_gain']
            
            for field in new_fields:
                if field not in columns:
                    if field == 'average_speed':
                        db.engine.execute(f'ALTER TABLE activity ADD COLUMN {field} FLOAT')
                    elif 'heartrate' in field:
                        db.engine.execute(f'ALTER TABLE activity ADD COLUMN {field} FLOAT')
                    else:
                        db.engine.execute(f'ALTER TABLE activity ADD COLUMN {field} FLOAT')
                    print(f"Added column: {field}")
                else:
                    print(f"Column {field} already exists")
            
            # Create optimal_values table
            db.create_all()
            print("Migration completed successfully")
            
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    migrate_activity_fields()
