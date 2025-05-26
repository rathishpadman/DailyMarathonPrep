from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, distinct
from app import app, db
from models import Athlete, Activity, PlannedWorkout, DailySummary, SystemLog
from strava_client import StravaClient
from excel_reader import ExcelReader
from dashboard_builder import DashboardBuilder
from scheduler import run_manual_task
from config import Config
import logging
import os

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Home page with overview and quick stats"""
    try:
        # Get basic stats - only count distinct active athletes
        total_athletes = db.session.query(func.count(distinct(
            Athlete.id))).filter_by(is_active=True).scalar()

        # Get recent activities (last 7 days) - avoid duplicates
        week_ago = datetime.now() - timedelta(days=7)
        recent_activities = db.session.query(func.count(distinct(
            Activity.id))).filter(Activity.start_date >= week_ago).scalar()

        # Get latest system log
        latest_log = SystemLog.query.order_by(
            SystemLog.created_at.desc()).first()

        # Get recent daily summaries - avoid duplicates by athlete and date
        recent_summaries = db.session.query(DailySummary).filter(
            DailySummary.summary_date >= week_ago.date()).order_by(
                DailySummary.summary_date.desc(),
                DailySummary.athlete_id).limit(10).all()

        return render_template('index.html',
                               total_athletes=total_athletes,
                               recent_activities=recent_activities,
                               latest_log=latest_log,
                               recent_summaries=recent_summaries)

    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        flash(f"Error loading dashboard: {e}", "error")
        return render_template('index.html',
                               total_athletes=0,
                               recent_activities=0,
                               latest_log=None,
                               recent_summaries=[])


@app.route('/dashboard')
@app.route('/dashboard/<date>')
def dashboard(date=None):
    """Main dashboard view for a specific date"""
    try:
        # Parse target date - FIX: Use current date instead of yesterday as default
        if date:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            target_date = datetime.now().replace(
                hour=0, minute=0, second=0,
                microsecond=0)  # Today, not yesterday

        # Build dashboard data
        dashboard_builder = DashboardBuilder()
        dashboard_data = dashboard_builder.build_daily_dashboard(target_date)

        # Get weekly trends
        weekly_trends = dashboard_builder.get_weekly_trends(target_date)

        # FIX: Trigger sync for current date if it's today
        if target_date.date() == datetime.now().date():
            try:
                # Auto-sync current day activities
                success = run_manual_task(target_date)
                if success:
                    logger.info(
                        f"Auto-synced activities for {target_date.date()}")
                    # Rebuild dashboard data after sync
                    dashboard_data = dashboard_builder.build_daily_dashboard(
                        target_date)
            except Exception as sync_error:
                logger.warning(f"Auto-sync failed: {sync_error}")

        return render_template('dashboard.html',
                               dashboard_data=dashboard_data,
                               weekly_trends=weekly_trends,
                               target_date=target_date)

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f"Error loading dashboard: {e}", "error")
        return redirect(url_for('index'))


@app.route('/athletes')
def athletes():
    """Athletes management page"""
    try:
        # FIX: Order by name and ensure distinct athletes
        athletes_list = db.session.query(Athlete).order_by(
            Athlete.name).distinct().all()

        # Get athlete stats
        athlete_stats = []
        for athlete in athletes_list:
            # FIX: Use count with distinct to avoid duplicates
            total_activities = db.session.query(
                func.count(distinct(
                    Activity.id))).filter_by(athlete_id=athlete.id).scalar()

            # Get recent activity (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            recent_activities = db.session.query(
                func.count(distinct(Activity.id))).filter(
                    Activity.athlete_id == athlete.id, Activity.start_date
                    >= week_ago).scalar()

            # Get latest summary - ensure only one per athlete
            latest_summary = db.session.query(DailySummary).filter_by(
                athlete_id=athlete.id).order_by(
                    DailySummary.summary_date.desc()).first()

            athlete_stats.append({
                'athlete': athlete,
                'total_activities': total_activities or 0,  # Handle None case
                'recent_activities': recent_activities or 0,
                'latest_summary': latest_summary
            })

        return render_template('athletes.html', athlete_stats=athlete_stats)

    except Exception as e:
        logger.error(f"Error loading athletes page: {e}")
        flash(f"Error loading athletes: {e}", "error")
        return redirect(url_for('index'))


@app.route('/training-plan')
def training_plan():
    """Training plan management page"""
    try:
        excel_reader = ExcelReader()

        # Validate Excel file
        validation_results = excel_reader.validate_excel_format()

        # FIX: Get recent planned workouts with distinct constraint
        week_ago = datetime.now() - timedelta(days=7)
        recent_workouts = db.session.query(PlannedWorkout).filter(
            PlannedWorkout.workout_date >= week_ago.date()).order_by(
                PlannedWorkout.workout_date.desc(),
                PlannedWorkout.athlete_id).distinct().limit(20).all()

        # Get upcoming workouts
        today = datetime.now().date()
        upcoming_workouts = db.session.query(PlannedWorkout).filter(
            PlannedWorkout.workout_date >= today).order_by(
                PlannedWorkout.workout_date,
                PlannedWorkout.athlete_id).distinct().limit(20).all()

        return render_template('training_plan.html',
                               validation_results=validation_results,
                               recent_workouts=recent_workouts,
                               upcoming_workouts=upcoming_workouts,
                               training_plan_file=Config.TRAINING_PLAN_FILE)

    except Exception as e:
        logger.error(f"Error loading training plan page: {e}")
        flash(f"Error loading training plan: {e}", "error")
        return redirect(url_for('index'))


@app.route('/upload-training-plan', methods=['POST'])
def upload_training_plan():
    """Handle training plan file upload"""
    try:
        if 'training_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('training_plan'))

        file = request.files['training_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('training_plan'))

        if file and file.filename and file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            filename = 'uploaded_training_plan' + (
                '.xlsx' if file.filename.lower().endswith(
                    ('.xlsx', '.xls')) else '.csv')
            file_path = os.path.join(os.getcwd(), filename)
            file.save(file_path)

            # Validate the uploaded file first before updating config
            excel_reader = ExcelReader(file_path)
            validation_results = excel_reader.validate_excel_format()

            if validation_results.get('file_exists', False):
                # Update config to use the uploaded file only if validation passes
                Config.TRAINING_PLAN_FILE = filename

            if validation_results.get('file_exists',
                                      False) and validation_results.get(
                                          'required_columns', False):
                # Trigger manual task to process the new file
                success = run_manual_task()

                if success:
                    flash('Training plan uploaded and processed successfully!',
                          'success')
                else:
                    flash(
                        'Training plan uploaded but processing had some issues. Check the logs for details.',
                        'warning')
            else:
                flash(
                    'Uploaded file format is invalid. Please check the required columns and data format.',
                    'error')
        else:
            flash('Please upload a valid Excel file (.xlsx, .xls) or CSV file (.csv)', 'error')

    except Exception as e:
        logger.error(f"Error uploading training plan: {e}")
        flash(f'Error uploading file: {e}', 'error')

    return redirect(url_for('training_plan'))


@app.route('/api/manual-run', methods=['POST'])
def manual_run():
    """API endpoint to manually trigger daily tasks"""
    try:
        # Get target date from request
        target_date_str = request.json.get(
            'date') if request.is_json else request.form.get('date')

        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        else:
            # FIX: Default to current date for syncing, not yesterday
            target_date = datetime.now().replace(hour=0,
                                                 minute=0,
                                                 second=0,
                                                 microsecond=0)

        # Run manual task
        success = run_manual_task(target_date)

        if success:
            message = f"Manual task execution completed successfully for {target_date.strftime('%Y-%m-%d')}"
            flash(message, "success")
            return jsonify({"success": True, "message": message})
        else:
            message = f"Manual task execution failed for {target_date.strftime('%Y-%m-%d')}"
            flash(message, "error")
            return jsonify({"success": False, "message": message})

    except Exception as e:
        error_msg = f"Error during manual execution: {e}"
        logger.error(error_msg)
        flash(error_msg, "error")
        return jsonify({"success": False, "message": error_msg})


@app.route('/auth/strava')
def strava_auth():
    """Initiate Strava OAuth flow"""
    try:
        strava_client = StravaClient()
        auth_url = strava_client.get_authorization_url()
        logger.info(f"Generated Strava auth URL: {auth_url}")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating Strava auth: {e}")
        flash(f"Error connecting to Strava: {e}", "error")
        return redirect(url_for('athletes'))


@app.route('/auth/strava/callback')
def strava_callback():
    """Handle Strava OAuth callback"""
    try:
        code = request.args.get('code')
        error = request.args.get('error')

        if error:
            flash(f"Strava authorization failed: {error}", "error")
            return redirect(url_for('athletes'))

        if not code:
            flash("No authorization code received from Strava", "error")
            return redirect(url_for('athletes'))

        # Exchange code for token
        strava_client = StravaClient()
        token_data = strava_client.exchange_code_for_token(code)

        if not token_data:
            flash("Failed to exchange authorization code for token", "error")
            return redirect(url_for('athletes'))

        # Get or create athlete
        athlete_info = token_data.get('athlete', {})
        strava_athlete_id = athlete_info.get('id')
        athlete_name = f"{athlete_info.get('firstname', '')} {athlete_info.get('lastname', '')}".strip(
        )

        # FIX: Use get_or_404 pattern or proper existence check
        athlete = db.session.query(Athlete).filter_by(
            strava_athlete_id=strava_athlete_id).first()

        if not athlete:
            # Create new athlete
            athlete = Athlete(name=athlete_name
                              or f"Athlete {strava_athlete_id}",
                              strava_athlete_id=strava_athlete_id,
                              is_active=True)
            db.session.add(athlete)
        else:
            # Update existing athlete info
            if athlete_name:
                athlete.name = athlete_name
            athlete.is_active = True

        # Update token data
        athlete.access_token = token_data['access_token']
        athlete.refresh_token = token_data['refresh_token']
        athlete.token_expires_at = datetime.fromtimestamp(
            token_data['expires_at'])

        db.session.commit()

        # FIX: Trigger immediate sync for new/updated athlete
        try:
            current_date = datetime.now().replace(hour=0,
                                                  minute=0,
                                                  second=0,
                                                  microsecond=0)
            run_manual_task(current_date)
            logger.info(
                f"Auto-synced activities for newly connected athlete: {athlete.name}"
            )
        except Exception as sync_error:
            logger.warning(f"Auto-sync failed for new athlete: {sync_error}")

        flash(f"Successfully connected Strava account for {athlete.name}",
              "success")
        return redirect(url_for('athletes'))

    except Exception as e:
        logger.error(f"Error in Strava callback: {e}")
        db.session.rollback()  # FIX: Add rollback on error
        flash(f"Error processing Strava authorization: {e}", "error")
        return redirect(url_for('athletes'))


@app.route('/api/athlete/<int:athlete_id>/toggle', methods=['POST'])
def toggle_athlete(athlete_id):
    """Toggle athlete active status"""
    try:
        athlete = Athlete.query.get_or_404(athlete_id)
        athlete.is_active = not athlete.is_active
        db.session.commit()

        status = "activated" if athlete.is_active else "deactivated"
        flash(f"Athlete {athlete.name} {status}", "success")

        return jsonify({"success": True, "active": athlete.is_active})

    except Exception as e:
        logger.error(f"Error toggling athlete status: {e}")
        db.session.rollback()  # FIX: Add rollback on error
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/dashboard-data/<date>')
def api_dashboard_data(date):
    """API endpoint to get dashboard data for AJAX requests"""
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d')

        dashboard_builder = DashboardBuilder()
        dashboard_data = dashboard_builder.build_daily_dashboard(target_date)

        return jsonify(dashboard_data)

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)})


@app.route('/api/system-logs')
def api_system_logs():
    """API endpoint to get recent system logs"""
    try:
        limit = request.args.get('limit', 20, type=int)

        # FIX: Add distinct to avoid duplicate logs
        logs = db.session.query(SystemLog).order_by(
            SystemLog.created_at.desc()).distinct().limit(limit).all()

        logs_data = []
        for log in logs:
            logs_data.append({
                'id':
                log.id,
                'log_date':
                log.log_date.strftime('%Y-%m-%d %H:%M:%S'),
                'log_type':
                log.log_type,
                'message':
                log.message,
                'details':
                log.details,
                'created_at':
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify(logs_data)

    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        return jsonify({"error": str(e)})


# FIX: Add new endpoint for immediate sync
@app.route('/api/sync-current', methods=['POST'])
def sync_current():
    """API endpoint to sync current day activities immediately"""
    try:
        current_date = datetime.now().replace(hour=0,
                                              minute=0,
                                              second=0,
                                              microsecond=0)
        success = run_manual_task(current_date)

        if success:
            message = f"Successfully synced activities for {current_date.strftime('%Y-%m-%d')}"
            return jsonify({"success": True, "message": message})
        else:
            message = f"Sync failed for {current_date.strftime('%Y-%m-%d')}"
            return jsonify({"success": False, "message": message})

    except Exception as e:
        error_msg = f"Error during sync: {e}"
        logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg})


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('base.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    logger.error(f"Internal server error: {error}")
    return render_template('base.html'), 500
