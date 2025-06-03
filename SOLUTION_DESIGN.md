
# Marathon Training Dashboard - Solution Design Document

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Design](#component-design)
4. [Data Models](#data-models)
5. [API Design](#api-design)
6. [Security & Authentication](#security--authentication)
7. [Database Design](#database-design)
8. [External Integrations](#external-integrations)
9. [Processing Workflows](#processing-workflows)
10. [Deployment Architecture](#deployment-architecture)
11. [Performance Considerations](#performance-considerations)
12. [Error Handling & Logging](#error-handling--logging)

## Executive Summary

The Marathon Training Dashboard is a comprehensive web application built with Flask that helps marathon training teams track, analyze, and manage their training progress. The system integrates with Strava for activity data, processes training plans, and provides real-time performance analytics.

### Key Features
- Strava OAuth integration for automatic activity sync
- Excel-based training plan management
- Real-time performance analytics and variance tracking
- Team dashboard with individual athlete insights
- Automated daily performance processing
- WhatsApp notifications (configurable)
- RESTful API for data access

## System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   External      │
│   (Templates)   │◄──►│   (Flask App)   │◄──►│   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        │              ┌─────────────────┐                │
        │              │   Database      │                │
        └──────────────┤   (SQLite)      │                │
                       └─────────────────┘                │
                                                          │
                              ┌─────────────────────────────┘
                              │
                    ┌─────────────────┐
                    │ Strava API      │
                    │ WhatsApp API    │
                    └─────────────────┘
```

### Technology Stack
- **Backend**: Python 3.x, Flask, SQLAlchemy
- **Database**: SQLite (with provisions for PostgreSQL)
- **Frontend**: Bootstrap 5, Jinja2 templates, Chart.js
- **External APIs**: Strava API v3, WhatsApp Business API
- **Deployment**: Replit platform

## Component Design

### Core Components

#### 1. Application Core (`app.py`)
```python
# Responsibilities:
- Flask application initialization
- Database connection management
- CORS configuration
- Global error handling
- Health check endpoints
```

#### 2. Models Layer (`models.py`)
```python
# Core entities:
- Athlete: User profiles and Strava credentials
- Activity: Strava activity data
- PlannedWorkout: Training schedule from Excel
- DailySummary: Performance analysis results
- SystemLog: Application logging
- StravaApiUsage: Rate limiting tracking
- OptimalValues: Performance benchmarks
```

#### 3. Routes Layer (`routes.py`)
```python
# Route categories:
- Dashboard routes (/dashboard, /)
- API endpoints (/api/*)
- Authentication routes (/auth/strava/*)
- Management routes (/athletes, /training-plan)
- Debug routes (/debug/*)
```

#### 4. Data Processing (`data_processor.py`)
```python
# Core functions:
- aggregate_daily_activities()
- calculate_variance()
- determine_workout_status()
- process_athlete_daily_performance()
- save_daily_summary()
- calculate_team_summary()
```

#### 5. External Integrations
- **Strava Client** (`strava_client.py`): OAuth flow, activity fetching
- **Excel Reader** (`excel_reader.py`): Training plan import
- **Scheduler** (`scheduler.py`): Automated tasks
- **Notifier** (`notifier.py`): WhatsApp messaging

## Data Models

### Core Entities

#### Athlete Model
```python
class Athlete(db.Model):
    id: Integer (PK)
    name: String(100)
    strava_athlete_id: Integer (Unique)
    refresh_token: String(255)
    access_token: String(255)
    token_expires_at: DateTime
    is_active: Boolean
    created_at: DateTime
```

#### Activity Model
```python
class Activity(db.Model):
    id: Integer (PK)
    strava_activity_id: Integer (Unique)
    athlete_id: Integer (FK)
    name: String(200)
    activity_type: String(50)
    start_date: DateTime
    distance_km: Float
    moving_time_seconds: Integer
    pace_min_per_km: Float
    average_speed: Float
    average_heartrate: Float
    max_heartrate: Float
    total_elevation_gain: Float
    created_at: DateTime
```

#### PlannedWorkout Model
```python
class PlannedWorkout(db.Model):
    id: Integer (PK)
    athlete_id: Integer (FK)
    workout_date: DateTime
    planned_distance_km: Float
    planned_pace_min_per_km: Float
    workout_type: String(100)
    notes: Text
    created_at: DateTime
    
    # Unique constraint on (athlete_id, workout_date)
```

#### DailySummary Model
```python
class DailySummary(db.Model):
    id: Integer (PK)
    athlete_id: Integer (FK)
    summary_date: DateTime
    actual_distance_km: Float
    planned_distance_km: Float
    actual_pace_min_per_km: Float
    planned_pace_min_per_km: Float
    distance_variance_percent: Float
    pace_variance_percent: Float
    status: String(50)  # On Track, Under-performed, etc.
    notes: Text
    created_at: DateTime
    
    # Unique constraint on (athlete_id, summary_date)
```

### Data Relationships
```
Athlete (1) ──── (N) Activity
Athlete (1) ──── (N) PlannedWorkout
Athlete (1) ──── (N) DailySummary
Athlete (1) ──── (1) OptimalValues
```

## API Design

### RESTful Endpoints

#### Authentication Endpoints
```
GET  /auth/strava          - Initiate Strava OAuth
GET  /auth/strava/callback - Handle OAuth callback
```

#### Dashboard API
```
GET  /api/dashboard-data/<date>      - Get dashboard data for date
GET  /api/athlete-progress-data      - Get athlete progress metrics
GET  /api/summary-stats/<period>     - Get filtered summary statistics
```

#### Management API
```
POST /api/manual-run                 - Trigger manual sync
POST /api/sync-activities            - Filtered activity sync
POST /api/athlete/<id>/toggle        - Toggle athlete status
GET  /api/system-logs               - Get system logs
```

#### Training Plan API
```
GET  /api/training-plan-data        - Get training plan data
POST /api/save-training-plan        - Save edited training plan
GET  /api/athletes-list             - Get athletes for dropdowns
```

#### Configuration API
```
GET  /api/optimal-values            - Get optimal performance values
POST /api/optimal-values            - Save optimal values
POST /api/apply-global-defaults     - Apply global defaults
```

### API Response Format
```json
{
  "success": true|false,
  "message": "Human readable message",
  "data": { /* response payload */ },
  "error": "Error details if applicable"
}
```

## Security & Authentication

### Strava OAuth 2.0 Flow
```
1. User clicks "Connect Strava"
2. Redirect to Strava authorization URL
3. User grants permissions
4. Strava redirects with authorization code
5. Exchange code for access/refresh tokens
6. Store tokens securely in database
7. Use refresh token for token renewal
```

### Security Measures
- **Token Management**: Secure storage of OAuth tokens
- **Rate Limiting**: Strava API rate limit compliance
- **Input Validation**: Form data sanitization
- **CORS**: Cross-origin request handling
- **Session Security**: Flask session management
- **Environment Variables**: Sensitive config in environment

### Rate Limiting Strategy
```python
# Strava API Limits:
- 15-minute limit: 100 requests
- Daily limit: 1000 requests
- Tracking in StravaApiUsage model
- Automatic backoff on limit reached
```

## Database Design

### Schema Overview
```sql
-- Core tables with relationships
Athlete (id, name, strava_athlete_id, tokens, is_active)
Activity (id, strava_activity_id, athlete_id, metrics, dates)
PlannedWorkout (id, athlete_id, workout_date, planned_metrics)
DailySummary (id, athlete_id, summary_date, variances, status)
SystemLog (id, log_date, log_type, message, details)
StravaApiUsage (id, date, requests_count, limits)
OptimalValues (id, athlete_id, optimal_metrics)
```

### Indexing Strategy
```sql
-- Performance indexes
CREATE INDEX idx_activity_athlete_date ON Activity(athlete_id, start_date);
CREATE INDEX idx_planned_workout_athlete_date ON PlannedWorkout(athlete_id, workout_date);
CREATE INDEX idx_daily_summary_athlete_date ON DailySummary(athlete_id, summary_date);
CREATE INDEX idx_daily_summary_date ON DailySummary(summary_date);
CREATE INDEX idx_activity_strava_id ON Activity(strava_activity_id);
```

### Data Integrity
- **Unique Constraints**: Prevent duplicate records
- **Foreign Keys**: Maintain referential integrity
- **Duplicate Prevention**: Upsert patterns in data processing
- **Transaction Management**: Rollback on errors

## External Integrations

### Strava API Integration

#### Authentication Flow
```python
class StravaClient:
    def get_authorization_url() -> str
    def exchange_code_for_token(code: str) -> Dict
    def refresh_access_token(refresh_token: str) -> Dict
    def get_athlete_activities(token, start_date, end_date) -> List[Dict]
```

#### Rate Limiting Implementation
```python
def _check_rate_limits() -> bool:
    # Check 15-minute and daily limits
    # Return False if limits would be exceeded

def _record_request():
    # Update usage counters
    # Track request timestamps
```

#### Data Processing
```python
def process_activity_data(activity: Dict) -> Dict:
    # Convert Strava format to internal format
    # Calculate derived metrics (pace, etc.)
    # Handle missing/invalid data
```

### Excel Integration

#### Training Plan Import
```python
class ExcelReader:
    def validate_excel_format() -> Dict
    def read_training_data() -> List[Dict]
    def process_athlete_data(athlete_name: str) -> List[Dict]
```

#### Supported Formats
- Excel (.xlsx, .xls)
- CSV (.csv)
- Required columns: Athlete, Date, Distance, Pace, Type, Notes

### WhatsApp Integration

#### Notification System
```python
class WhatsAppNotifier:
    def send_daily_summary(summary_data: Dict) -> bool
    def send_team_update(team_data: Dict) -> bool
    def format_message(data: Dict) -> str
```

## Processing Workflows

### Daily Processing Pipeline

#### 1. Activity Sync Workflow
```python
def sync_athlete_activities(athlete: Athlete, date: datetime):
    # Check token validity
    # Refresh token if needed
    # Fetch activities from Strava
    # Process and store activities
    # Handle duplicates
    # Update sync timestamps
```

#### 2. Performance Analysis Workflow
```python
def process_daily_performance(athlete_id: int, date: datetime):
    # Get planned workout for date
    # Aggregate actual activities for date
    # Calculate variances
    # Determine performance status
    # Create/update daily summary
    # Clean up duplicates
```

#### 3. Team Summary Workflow
```python
def calculate_team_summary(date: datetime):
    # Aggregate all athlete summaries
    # Calculate team metrics
    # Generate status breakdown
    # Prepare dashboard data
```

### Automated Scheduling

#### Daily Tasks
```python
# Scheduled via scheduler.py
- Sync previous day activities
- Process performance analysis
- Generate team summaries
- Send notifications (if enabled)
- Cleanup duplicate records
```

#### Manual Triggers
```python
# API endpoints for manual execution
- Single date sync
- Date range sync
- Individual athlete sync
- Bulk data processing
```

## Deployment Architecture

### Replit Platform Deployment

#### Application Structure
```
├── main.py              # Application entry point
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── .replit            # Replit configuration
└── static/            # Static assets
    ├── css/
    ├── js/
    └── images/
```

#### Environment Configuration
```python
# Config management
class Config:
    STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
    STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///marathon_dashboard.db')
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret')
```

#### Port Configuration
```python
# app.py
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

### Database Deployment
```python
# SQLite for development/testing
# PostgreSQL for production (if needed)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", 
    "sqlite:///marathon_dashboard.db"
)
```

## Performance Considerations

### Database Optimization

#### Query Optimization
```python
# Use joins instead of multiple queries
activities = db.session.query(Activity, Athlete.name).join(
    Athlete, Activity.athlete_id == Athlete.id
).filter(Activity.start_date >= start_date).all()

# Use distinct() to prevent duplicates
summaries = db.session.query(DailySummary).filter_by(
    summary_date=date
).distinct().all()
```

#### Caching Strategy
```python
# Dashboard data caching
@app.route('/api/dashboard-data/<date>')
def api_dashboard_data(date):
    # Cache results for frequently accessed dates
    # Implement cache invalidation on data updates
```

### API Rate Limiting

#### Strava API Management
```python
# Respect Strava rate limits
STRAVA_RATE_LIMIT_15MIN = 100
STRAVA_RATE_LIMIT_DAILY = 1000

# Implement exponential backoff
# Queue requests during high-traffic periods
```

#### Application Rate Limiting
```python
# Prevent abuse of manual sync endpoints
# Implement request throttling
# Queue long-running operations
```

### Memory Management
```python
# Process large datasets in chunks
# Use generators for large result sets
# Implement pagination for API responses
```

## Error Handling & Logging

### Comprehensive Logging Strategy

#### Log Levels and Categories
```python
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Log categories:
- ERROR: System errors, API failures
- WARNING: Rate limits, data inconsistencies
- INFO: Successful operations, user actions
- DEBUG: Detailed processing information
```

#### Error Handling Patterns
```python
# Database operations
try:
    db.session.commit()
except Exception as e:
    logger.error(f"Database error: {e}")
    db.session.rollback()
    return jsonify({'error': str(e)}), 500

# API calls
try:
    response = requests.get(api_url)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    logger.error(f"API request failed: {e}")
    return []
```

#### System Log Model
```python
class SystemLog(db.Model):
    id: Integer (PK)
    log_date: DateTime
    log_type: String(50)  # SUCCESS, ERROR, WARNING
    message: Text
    details: Text
    created_at: DateTime
```

### Monitoring and Alerting

#### Health Checks
```python
@app.route('/health/scheduler')
def scheduler_health():
    # Check scheduler status
    # Verify database connectivity
    # Test external API access
```

#### Debug Endpoints
```python
# Debug routes for troubleshooting
@app.route('/debug/database-stats')
@app.route('/debug/duplicate-activities')
@app.route('/debug/system-logs')
```

## Security Considerations

### Data Protection
- **Token Encryption**: Store OAuth tokens securely
- **Input Sanitization**: Prevent SQL injection
- **Session Management**: Secure session handling
- **HTTPS**: Force SSL in production

### Privacy Compliance
- **Data Minimization**: Store only necessary data
- **User Consent**: Clear data usage policies
- **Data Retention**: Automated cleanup policies
- **Export/Delete**: User data management tools

## Future Enhancements

### Scalability Improvements
- **Database Migration**: PostgreSQL for larger datasets
- **Caching Layer**: Redis for session/data caching
- **API Optimization**: GraphQL for flexible queries
- **Microservices**: Split components for better scaling

### Feature Additions
- **Mobile App**: React Native or Flutter app
- **Advanced Analytics**: ML-based performance predictions
- **Social Features**: Team challenges and leaderboards
- **Integration Expansion**: Garmin, Fitbit, Apple Health

### Infrastructure Enhancements
- **CI/CD Pipeline**: Automated testing and deployment
- **Monitoring**: Application performance monitoring
- **Backup Strategy**: Automated database backups
- **Load Balancing**: Handle increased traffic

---

This solution design document provides a comprehensive overview of the Marathon Training Dashboard application architecture, covering all major components, integrations, and technical considerations for successful deployment and maintenance on the Replit platform.
