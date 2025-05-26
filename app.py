import os
import logging
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Enable CORS for API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///marathon_dashboard.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models
    db.create_all()

# Import routes after app creation to avoid circular imports
from routes import *

# Health Check and Debug Routes
@app.route('/health/scheduler')
def scheduler_health():
    """Get scheduler health status"""
    try:
        from scheduler import get_scheduler_health
        return jsonify(get_scheduler_health())
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'unhealthy'}), 500

@app.route('/debug/database-stats')
def database_stats():
    """Get overall database statistics"""
    try:
        from models import Athlete, Activity, PlannedWorkout, SystemLog
        stats = {
            'athletes': Athlete.query.count(),
            'activities': Activity.query.count(),
            'planned_workouts': PlannedWorkout.query.count(),
            'system_logs': SystemLog.query.count(),
            'active_athletes': Athlete.query.filter_by(is_active=True).count()
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/duplicate-activities')
def find_duplicate_activities():
    """Find duplicate activities"""
    try:
        from models import Activity

        # Find duplicates by Strava activity ID
        strava_id_duplicates = db.session.query(
            Activity.strava_activity_id,
            func.count(Activity.id).label('count')
        ).group_by(Activity.strava_activity_id).having(func.count(Activity.id) > 1).all()

        # Find duplicates by athlete + date + name
        athlete_date_duplicates = db.session.query(
            Activity.athlete_id,
            Activity.start_date,
            Activity.name,
            func.count(Activity.id).label('count')
        ).group_by(
            Activity.athlete_id, 
            Activity.start_date, 
            Activity.name
        ).having(func.count(Activity.id) > 1).all()

        return jsonify({
            'strava_id_duplicates': [
                {'strava_activity_id': dup[0], 'count': dup[1]} 
                for dup in strava_id_duplicates
            ],
            'athlete_date_duplicates': [
                {
                    'athlete_id': dup[0], 
                    'start_date': dup[1].isoformat() if dup[1] else None,
                    'name': dup[2],
                    'count': dup[3]
                } 
                for dup in athlete_date_duplicates
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/duplicate-workouts')
def find_duplicate_workouts():
    """Find duplicate planned workouts"""
    try:
        from models import PlannedWorkout

        duplicates = db.session.query(
            PlannedWorkout.athlete_id,
            PlannedWorkout.workout_date,
            func.count(PlannedWorkout.id).label('count')
        ).group_by(
            PlannedWorkout.athlete_id, 
            PlannedWorkout.workout_date
        ).having(func.count(PlannedWorkout.id) > 1).all()

        return jsonify({
            'duplicate_workouts': [
                {
                    'athlete_id': dup[0], 
                    'workout_date': dup[1].isoformat() if dup[1] else None,
                    'count': dup[2]
                } 
                for dup in duplicates
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/activities/<int:athlete_id>')
def get_athlete_activities(athlete_id):
    """Get all activities for a specific athlete"""
    try:
        from models import Activity, Athlete

        athlete = Athlete.query.get(athlete_id)
        if not athlete:
            return jsonify({'error': 'Athlete not found'}), 404

        activities = Activity.query.filter_by(athlete_id=athlete_id).order_by(Activity.start_date.desc()).limit(50).all()

        return jsonify({
            'athlete_id': athlete_id,
            'athlete_name': athlete.name,
            'total_activities': Activity.query.filter_by(athlete_id=athlete_id).count(),
            'activities': [
                {
                    'id': act.id,
                    'strava_activity_id': act.strava_activity_id,
                    'name': act.name,
                    'start_date': act.start_date.isoformat() if act.start_date else None,
                    'distance_km': act.distance_km,
                    'activity_type': act.activity_type,
                    'pace_min_per_km': act.pace_min_per_km
                }
                for act in activities
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/recent-activities')
def recent_activities():
    """Get recent activities to check for duplicates"""
    try:
        from models import Activity, Athlete

        activities = db.session.query(Activity, Athlete.name).join(
            Athlete, Activity.athlete_id == Athlete.id
        ).order_by(Activity.start_date.desc()).limit(50).all()

        return jsonify({
            'activities': [
                {
                    'id': act.Activity.id,
                    'strava_activity_id': act.Activity.strava_activity_id,
                    'athlete_name': act.name,
                    'athlete_id': act.Activity.athlete_id,
                    'name': act.Activity.name,
                    'start_date': act.Activity.start_date.isoformat() if act.Activity.start_date else None,
                    'distance_km': act.Activity.distance_km,
                    'activity_type': act.Activity.activity_type
                }
                for act in activities
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/clean-duplicates', methods=['POST'])
def clean_duplicate_activities():
    """Remove duplicate activities (keep the first one created)"""
    try:
        from models import Activity

        # Find and remove Strava ID duplicates
        strava_duplicates = db.session.query(Activity.strava_activity_id).group_by(
            Activity.strava_activity_id
        ).having(func.count(Activity.id) > 1).all()

        removed_count = 0
        for (strava_id,) in strava_duplicates:
            # Get all activities with this Strava ID, ordered by ID (first created first)
            activities = Activity.query.filter_by(strava_activity_id=strava_id).order_by(Activity.id).all()

            # Keep the first one, remove the rest
            for activity in activities[1:]:
                db.session.delete(activity)
                removed_count += 1

        db.session.commit()

        return jsonify({
            'message': f'Removed {removed_count} duplicate activities',
            'removed_count': removed_count,
            'status': 'success'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e), 'status': 'failed'}), 500

@app.route('/debug/system-logs')
def get_system_logs():
    """Get recent system logs"""
    try:
        from models import SystemLog

        logs = SystemLog.query.order_by(SystemLog.log_date.desc()).limit(20).all()

        return jsonify({
            'logs': [
                {
                    'id': log.id,
                    'log_date': log.log_date.isoformat() if log.log_date else None,
                    'log_type': log.log_type,
                    'message': log.message,
                    'details': log.details
                }
                for log in logs
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/athletes')
def get_athletes():
    """Get all athletes information"""
    try:
        from models import Athlete

        athletes = Athlete.query.all()

        return jsonify({
            'athletes': [
                {
                    'id': athlete.id,
                    'name': athlete.name,
                    'is_active': athlete.is_active,
                    'has_refresh_token': bool(athlete.refresh_token),
                    'token_expires_at': athlete.token_expires_at.isoformat() if athlete.token_expires_at else None
                }
                for athlete in athletes
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)