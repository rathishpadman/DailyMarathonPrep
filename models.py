from app import db
from datetime import datetime
from sqlalchemy import Text, Float, Integer, String, DateTime, Boolean, UniqueConstraint


class Athlete(db.Model):
    """Model for storing athlete information and Strava credentials"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    strava_athlete_id = db.Column(db.Integer, unique=True, nullable=True)
    refresh_token = db.Column(db.String(255), nullable=True)
    access_token = db.Column(db.String(255), nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    activities = db.relationship('Activity', backref='athlete', lazy=True)
    planned_workouts = db.relationship('PlannedWorkout',
                                       backref='athlete',
                                       lazy=True)
    daily_summaries = db.relationship('DailySummary',
                                      backref='athlete',
                                      lazy=True)


class Activity(db.Model):
    """Model for storing Strava activity data"""
    id = db.Column(db.Integer, primary_key=True)
    strava_activity_id = db.Column(db.Integer, unique=True, nullable=False)
    athlete_id = db.Column(db.Integer,
                           db.ForeignKey('athlete.id'),
                           nullable=False)
    name = db.Column(db.String(200), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    moving_time_seconds = db.Column(db.Integer, nullable=False)
    pace_min_per_km = db.Column(db.Float, nullable=True)
    average_speed = db.Column(db.Float, nullable=True)  # m/s
    average_heartrate = db.Column(db.Float, nullable=True)  # bpm
    max_heartrate = db.Column(db.Float, nullable=True)  # bpm
    total_elevation_gain = db.Column(db.Float, nullable=True)  # meters
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('strava_activity_id',
                                          name='unique_strava_activity'), )


class PlannedWorkout(db.Model):
    """Model for storing planned workouts from Excel file"""
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer,
                           db.ForeignKey('athlete.id'),
                           nullable=False)
    workout_date = db.Column(db.DateTime, nullable=False)
    planned_distance_km = db.Column(db.Float, nullable=False)
    planned_pace_min_per_km = db.Column(db.Float, nullable=False)
    workout_type = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint(
        'athlete_id', 'workout_date', name='unique_athlete_workout_date'), )


class DailySummary(db.Model):
    """Model for storing daily performance summaries"""
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer,
                           db.ForeignKey('athlete.id'),
                           nullable=False)
    summary_date = db.Column(db.DateTime, nullable=False)
    actual_distance_km = db.Column(db.Float, nullable=True)
    planned_distance_km = db.Column(db.Float, nullable=True)
    actual_pace_min_per_km = db.Column(db.Float, nullable=True)
    planned_pace_min_per_km = db.Column(db.Float, nullable=True)
    distance_variance_percent = db.Column(db.Float, nullable=True)
    pace_variance_percent = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50),
                       nullable=True)  # On Track, Under-performed, etc.
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    # Add indexes for better query performance
    __table_args__ = (
        UniqueConstraint('athlete_id', 'summary_date', name='uq_daily_summary_athlete_date'),
        db.Index('idx_daily_summary_date', 'summary_date'),
        db.Index('idx_daily_summary_athlete', 'athlete_id'),
        db.Index('idx_daily_summary_status', 'status')
    )

    # This is the KEY change: Ensure only one summary per athlete per day
    __table_args__ = (UniqueConstraint('athlete_id', 'summary_date', name='uq_daily_summary_athlete_date'),)

class SystemLog(db.Model):
    """Model for storing system execution logs"""
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.DateTime, nullable=False)
    log_type = db.Column(db.String(50),
                         nullable=False)  # SUCCESS, ERROR, WARNING
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StravaApiUsage(db.Model):
    """Model for tracking Strava API usage"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    requests_made = db.Column(db.Integer, default=0)
    limit_reached = db.Column(db.Boolean, default=False)
    last_sync_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OptimalValues(db.Model):
    """Model for storing optimal performance values for athletes"""
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'), nullable=True)  # None for global defaults
    optimal_distance_km = db.Column(db.Float, default=10.0)
    optimal_pace_min_per_km = db.Column(db.Float, default=5.5)
    optimal_heart_rate_bpm = db.Column(db.Integer, default=150)
    max_heart_rate_bpm = db.Column(db.Integer, default=180)
    optimal_elevation_gain_m = db.Column(db.Float, default=100.0)
    weekly_distance_target_km = db.Column(db.Float, default=50.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    athlete = db.relationship('Athlete', backref='optimal_values', lazy=True)