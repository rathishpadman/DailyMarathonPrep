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
    """Simplified home page with 4 tiles, athlete management, and summary table"""
    try:
        # Get the 4 main tiles data
        total_athletes = db.session.query(func.count(distinct(Athlete.id))).filter_by(is_active=True).scalar() or 0

        # Weekly stats (last 7 days) - only count activities from active athletes
        week_ago = datetime.now() - timedelta(days=7)
        weekly_activities = db.session.query(func.count(distinct(Activity.id))).join(Athlete).filter(
            Activity.start_date >= week_ago,
            Activity.start_date <= datetime.now(),
            Athlete.is_active == True
        ).scalar() or 0

        # Monthly stats (last 30 days) - only count activities from active athletes  
        month_ago = datetime.now() - timedelta(days=30)
        monthly_activities = db.session.query(func.count(distinct(Activity.id))).join(Athlete).filter(
            Activity.start_date >= month_ago,
            Activity.start_date <= datetime.now(),
            Athlete.is_active == True
        ).scalar() or 0

        # Total planned vs actual distance this week - only include active athletes
        weekly_summaries = db.session.query(DailySummary).join(Athlete).filter(
            DailySummary.summary_date >= week_ago.date(),
            DailySummary.summary_date <= datetime.now().date(),
            Athlete.is_active == True
        ).all()

        # Remove duplicates and calculate proper totals
        unique_summaries = {}
        for summary in weekly_summaries:
            key = f"{summary.athlete_id}_{summary.summary_date}"
            if key not in unique_summaries:
                unique_summaries[key] = summary

        weekly_planned = sum(s.planned_distance_km or 0 for s in unique_summaries.values())
        weekly_actual = sum(s.actual_distance_km or 0 for s in unique_summaries.values())

        # Get all athletes for management
        all_athletes = db.session.query(Athlete).order_by(Athlete.name).all()

        # Get unified summary data with filtering support
        filter_period = request.args.get('period', 'week')  # day, week, month
        summary_data = get_filtered_summary_data(filter_period)

        return render_template('index.html',
                               total_athletes=total_athletes,
                               weekly_activities=weekly_activities,
                               monthly_activities=monthly_activities,
                               weekly_planned=weekly_planned,
                               weekly_actual=weekly_actual,
                               all_athletes=all_athletes,
                               summary_data=summary_data,
                               current_period=filter_period)

    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        flash(f"Error loading dashboard: {e}", "error")
        return render_template('index.html',
                               total_athletes=0,
                               weekly_activities=0,
                               monthly_activities=0,
                               weekly_planned=0,
                               weekly_actual=0,
                               all_athletes=[],
                               summary_data=[],
                               current_period='week')


def get_filtered_summary_data(period='week'):
    """Get summary data filtered by period with aggregated planned vs actual"""
    try:
        end_date = datetime.now()
        
        if period == 'day':
            # Get latest 10 days with distinct athlete summaries
            summaries = db.session.query(DailySummary).join(Athlete).filter(
                DailySummary.summary_date <= end_date.date(),
                Athlete.is_active == True
            ).order_by(DailySummary.summary_date.desc()).all()
            
            # Group by individual dates with unique athletes
            date_groups = {}
            for summary in summaries:
                # Convert summary_date to proper date if it's datetime
                if hasattr(summary.summary_date, 'date'):
                    summary_date = summary.summary_date.date()
                else:
                    summary_date = summary.summary_date
                    
                date_key = summary_date.strftime('%Y-%m-%d')
                if date_key not in date_groups:
                    date_groups[date_key] = {
                        'date': summary_date,
                        'period_label': summary_date.strftime('%d %b %Y'),
                        'athletes': [],
                        'athlete_ids': set(),  # Track unique athlete IDs
                        'total_planned': 0,
                        'total_actual': 0,
                        'completion_rate': 0
                    }

                # Only add if athlete hasn't been added for this date
                if summary.athlete_id not in date_groups[date_key]['athlete_ids']:
                    athlete = Athlete.query.get(summary.athlete_id)
                    date_groups[date_key]['athletes'].append({
                        'name': athlete.name if athlete else 'Unknown',
                        'planned': summary.planned_distance_km or 0,
                        'actual': summary.actual_distance_km or 0,
                        'status': summary.status
                    })
                    date_groups[date_key]['athlete_ids'].add(summary.athlete_id)
                    date_groups[date_key]['total_planned'] += summary.planned_distance_km or 0
                    date_groups[date_key]['total_actual'] += summary.actual_distance_km or 0
            
            # Clean up athlete_ids from final data and get latest 10 unique dates
            sorted_dates = sorted(date_groups.keys(), reverse=True)[:10]
            result_data = []
            for date in sorted_dates:
                data = date_groups[date]
                data.pop('athlete_ids', None)  # Remove tracking set
                result_data.append(data)
            
        elif period == 'week':
            # Define week start as May 19, 2025 (Week 1)
            base_date = datetime(2025, 5, 19).date()  # Week 1 starts May 19
            
            # Calculate current week number
            current_date = end_date.date()
            days_since_base = (current_date - base_date).days
            weeks_since_base = days_since_base // 7
            
            week_groups = {}
            # Get latest 10 weeks
            start_week = max(0, weeks_since_base - 9)
            end_week = weeks_since_base + 1
            
            for week_num in range(start_week, end_week):
                week_start = base_date + timedelta(weeks=week_num)
                week_end = week_start + timedelta(days=6)
                
                # Get summaries for this week
                week_summaries = db.session.query(DailySummary).join(Athlete).filter(
                    DailySummary.summary_date >= week_start,
                    DailySummary.summary_date <= week_end,
                    Athlete.is_active == True
                ).all()
                
                week_key = f"week-{week_num + 1}"
                week_groups[week_key] = {
                    'date': week_start,
                    'period_label': f"Week {week_num + 1} ({week_start.strftime('%d %b')} - {week_end.strftime('%d %b')})",
                    'athletes': [],
                    'total_planned': 0,
                    'total_actual': 0,
                    'completion_rate': 0
                }
                
                # Aggregate weekly data
                athlete_weekly_data = {}
                for summary in week_summaries:
                    athlete_id = summary.athlete_id
                    if athlete_id not in athlete_weekly_data:
                        athlete = Athlete.query.get(athlete_id)
                        athlete_weekly_data[athlete_id] = {
                            'name': athlete.name if athlete else 'Unknown',
                            'planned': 0,
                            'actual': 0,
                            'completed_days': 0,
                            'total_days': 0
                        }
                    
                    athlete_weekly_data[athlete_id]['planned'] += summary.planned_distance_km or 0
                    athlete_weekly_data[athlete_id]['actual'] += summary.actual_distance_km or 0
                    athlete_weekly_data[athlete_id]['total_days'] += 1
                    if summary.status in ['On Track', 'Over-performed']:
                        athlete_weekly_data[athlete_id]['completed_days'] += 1
                
                # Calculate totals and completion rates
                for athlete_data in athlete_weekly_data.values():
                    week_groups[week_key]['total_planned'] += athlete_data['planned']
                    week_groups[week_key]['total_actual'] += athlete_data['actual']
                    completion_rate = (athlete_data['completed_days'] / athlete_data['total_days'] * 100) if athlete_data['total_days'] > 0 else 0
                    athlete_data['status'] = 'On Track' if completion_rate >= 80 else 'Needs Improvement'
                    week_groups[week_key]['athletes'].append(athlete_data)
            
            result_data = [week_groups[key] for key in sorted(week_groups.keys()) if week_groups[key]['athletes']][-10:]
            
        else:  # month
            # Get monthly data with May-25 format
            month_groups = {}
            current_year = end_date.year
            current_month = end_date.month
            
            for i in range(10):  # Latest 10 months
                month_year = current_year
                month_num = current_month - i
                
                if month_num <= 0:
                    month_num += 12
                    month_year -= 1
                
                month_start = datetime(month_year, month_num, 1).date()
                if month_num == 12:
                    month_end = datetime(month_year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    month_end = datetime(month_year, month_num + 1, 1).date() - timedelta(days=1)
                
                # Get summaries for this month (only active athletes)
                month_summaries = db.session.query(DailySummary).join(Athlete).filter(
                    DailySummary.summary_date >= month_start,
                    DailySummary.summary_date <= month_end,
                    Athlete.is_active == True
                ).all()
                
                # Format month as May-25, Jun-25, etc.
                month_label = f"{month_start.strftime('%b')}-{str(month_year)[2:]}"
                month_key = f"{month_year}-{month_num:02d}"
                
                month_groups[month_key] = {
                    'date': month_start,
                    'period_label': month_label,
                    'athletes': [],
                    'total_planned': 0,
                    'total_actual': 0,
                    'completion_rate': 0
                }
                
                # Aggregate monthly data by athlete
                athlete_monthly_data = {}
                for summary in month_summaries:
                    athlete_id = summary.athlete_id
                    if athlete_id not in athlete_monthly_data:
                        athlete = Athlete.query.get(athlete_id)
                        athlete_monthly_data[athlete_id] = {
                            'name': athlete.name if athlete else 'Unknown',
                            'planned': 0,
                            'actual': 0,
                            'completed_days': 0,
                            'total_days': 0
                        }
                    
                    athlete_monthly_data[athlete_id]['planned'] += summary.planned_distance_km or 0
                    athlete_monthly_data[athlete_id]['actual'] += summary.actual_distance_km or 0
                    athlete_monthly_data[athlete_id]['total_days'] += 1
                    if summary.status in ['On Track', 'Over-performed']:
                        athlete_monthly_data[athlete_id]['completed_days'] += 1
                
                # Calculate totals and completion rates
                for athlete_data in athlete_monthly_data.values():
                    month_groups[month_key]['total_planned'] += athlete_data['planned']
                    month_groups[month_key]['total_actual'] += athlete_data['actual']
                    completion_rate = (athlete_data['completed_days'] / athlete_data['total_days'] * 100) if athlete_data['total_days'] > 0 else 0
                    athlete_data['status'] = 'On Track' if completion_rate >= 80 else 'Needs Improvement'
                    month_groups[month_key]['athletes'].append(athlete_data)
            
            result_data = [month_groups[key] for key in sorted(month_groups.keys()) if month_groups[key]['athletes']][-10:]

        # Calculate completion rates for all periods
        for period_data in result_data:
            if period_data['athletes']:
                completed = len([a for a in period_data['athletes'] if a['status'] in ['On Track', 'Over-performed']])
                total = len(period_data['athletes'])
                period_data['completion_rate'] = (completed / total * 100) if total > 0 else 0

        return result_data

    except Exception as e:
        logger.error(f"Error getting filtered summary data: {e}")
        return []


@app.route('/dashboard')
def dashboard():
    """Enhanced dashboard with comprehensive filtering and manual update capabilities"""
    try:
        # Get filter parameters
        athlete_filter = request.args.get('athlete_id', type=int)
        date_filter = request.args.get('date')
        period_filter = request.args.get('period', 'week')  # Default to week view
        activity_filter = request.args.get('activity_type', 'all')
        week_filter = request.args.get('week')
        month_filter = request.args.get('month')
        start_date_filter = request.args.get('start_date')
        end_date_filter = request.args.get('end_date')

        # Calculate current week based on May 19, 2025 as Week 1 start
        base_date = datetime(2025, 5, 19)  # Week 1 starts May 19
        current_date = datetime.now()
        days_since_base = (current_date.date() - base_date.date()).days
        current_week_num = (days_since_base // 7) + 1

        # Parse target date based on period and filters
        if period_filter == 'day':
            if start_date_filter:
                target_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
            else:
                target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif period_filter == 'week':
            if week_filter:
                week_num = int(week_filter.split('-')[1]) - 1
                target_date = base_date + timedelta(weeks=week_num)
            else:
                # Default to current week
                target_date = base_date + timedelta(weeks=current_week_num - 1)
                week_filter = f"week-{current_week_num}"
        elif period_filter == 'month' and month_filter:
            # Parse month (e.g., "may-25" -> May 2025)
            month_name, year_suffix = month_filter.split('-')
            month_num = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }.get(month_name.lower(), 5)
            year = 2000 + int(year_suffix)
            target_date = datetime(year, month_num, 1)
        else:
            target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get all athletes for filter dropdown
        all_athletes = db.session.query(Athlete).filter_by(is_active=True).order_by(Athlete.name).all()

        # Build filtered dashboard data
        dashboard_data = get_enhanced_dashboard_data(
            target_date, athlete_filter, period_filter, activity_filter,
            start_date_filter, end_date_filter
        )

        # Get weekly trends
        dashboard_builder = DashboardBuilder()
        weekly_trends = dashboard_builder.get_weekly_trends(target_date)

        return render_template('dashboard.html',
                               dashboard_data=dashboard_data,
                               weekly_trends=weekly_trends,
                               target_date=target_date,
                               all_athletes=all_athletes,
                               filters={
                                   'athlete_id': athlete_filter,
                                   'date': date_filter,
                                   'period': period_filter,
                                   'activity_type': activity_filter,
                                   'week': week_filter,
                                   'month': month_filter,
                                   'start_date': start_date_filter,
                                   'end_date': end_date_filter
                               })

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f"Error loading dashboard: {e}", "error")
        return redirect(url_for('index'))


def get_enhanced_dashboard_data(target_date, athlete_filter=None, period_filter='week', activity_filter='all', 
                                       start_date_filter=None, end_date_filter=None):
    """Get enhanced dashboard data with comprehensive filtering"""
    try:
        # Calculate current week based on May 19, 2025 as Week 1 start
        base_date = datetime(2025, 5, 19)
        
        # Determine date range based on period
        if period_filter == 'day':
            if start_date_filter and end_date_filter:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d')
            else:
                start_date = target_date
                end_date = target_date
        elif period_filter == 'month':
            start_date = target_date.replace(day=1)
            if target_date.month == 12:
                next_month = start_date.replace(year=start_date.year + 1, month=1)
            else:
                next_month = start_date.replace(month=start_date.month + 1)
            end_date = next_month - timedelta(days=1)
        else:  # week
            # Use proper week calculation based on May 19 base date
            days_since_base = (target_date.date() - base_date.date()).days
            week_offset = days_since_base // 7
            start_date = base_date + timedelta(weeks=week_offset)
            end_date = start_date + timedelta(days=6)

        # Build query with filters - join with Athlete to ensure active athletes only
        query = db.session.query(DailySummary).join(Athlete).filter(
            DailySummary.summary_date >= start_date.date(),
            DailySummary.summary_date <= end_date.date(),
            Athlete.is_active == True
        )

        if athlete_filter:
            query = query.filter(DailySummary.athlete_id == athlete_filter)

        summaries = query.order_by(DailySummary.summary_date.desc()).all()

        # Remove duplicates by creating unique key
        unique_summaries = {}
        for summary in summaries:
            key = f"{summary.athlete_id}_{summary.summary_date}"
            if key not in unique_summaries:
                unique_summaries[key] = summary
        
        summaries = list(unique_summaries.values())

        # Process summaries with athlete information
        enhanced_summaries = []
        total_planned = 0
        total_actual = 0

        for summary in summaries:
            athlete = Athlete.query.get(summary.athlete_id)
            if not athlete:
                continue

            # Apply activity filter if needed (for future enhancement)
            summary_data = {
                'athlete_id': summary.athlete_id,
                'athlete_name': athlete.name,
                'date': summary.summary_date,
                'planned_distance': summary.planned_distance_km or 0,
                'actual_distance': summary.actual_distance_km or 0,
                'planned_pace': summary.planned_pace_min_per_km or 0,
                'actual_pace': summary.actual_pace_min_per_km or 0,
                'distance_variance': summary.distance_variance_percent or 0,
                'pace_variance': summary.pace_variance_percent or 0,
                'status': summary.status,
                'notes': summary.notes
            }
            enhanced_summaries.append(summary_data)
            total_planned += summary.planned_distance_km or 0
            total_actual += summary.actual_distance_km or 0

        # Calculate aggregate statistics
        variance = ((total_actual - total_planned) / total_planned * 100) if total_planned > 0 else 0
        completion_rate = len([s for s in enhanced_summaries if s['status'] in ['On Track', 'Over-performed']]) / len(enhanced_summaries) * 100 if enhanced_summaries else 0

        return {
            'summaries': enhanced_summaries,
            'period_stats': {
                'start_date': start_date.date(),
                'end_date': end_date.date(),
                'total_planned': total_planned,
                'total_actual': total_actual,
                'variance_percent': variance,
                'completion_rate': completion_rate,
                'total_athletes': len(set(s['athlete_id'] for s in enhanced_summaries)),
                'period_type': period_filter
            }
        }

    except Exception as e:
        logger.error(f"Error getting enhanced dashboard data: {e}")
        return {'summaries': [], 'period_stats': {}}


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
                               training_plan_file=Config.TRAINING_PLAN_FILE,
                               today=today)

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
        # Get target date from request with better error handling
        target_date_str = None
        sync_type = 'range'  # Default to range sync
        
        if request.is_json and request.json:
            target_date_str = request.json.get('date')
            sync_type = request.json.get('type', 'range')
        elif request.form:
            target_date_str = request.form.get('date')
            sync_type = request.form.get('type', 'range')

        if target_date_str and sync_type == 'single':
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
                success = run_manual_task(target_date)
                message = f"Manual task execution completed for {target_date.strftime('%Y-%m-%d')}"
            except ValueError as ve:
                error_msg = f"Invalid date format: {target_date_str}. Use YYYY-MM-DD format."
                logger.error(error_msg)
                return jsonify({"success": False, "message": error_msg}), 400
        else:
            # Default: sync from May 19, 2025 to current date
            success = run_manual_task()  # This will trigger date range sync
            start_date = datetime(2025, 5, 19)
            end_date = datetime.now()
            message = f"Date range sync completed from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": f"Sync failed: {message}"}), 500

    except Exception as e:
        error_msg = f"Error during manual execution: {str(e)}"
        logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 500


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
    """API endpoint to sync all activities from May 19th to current date"""
    try:
        # Sync full date range from May 19, 2025 to current date
        success = run_manual_task()  # This will trigger date range sync
        
        start_date = datetime(2025, 5, 19)
        end_date = datetime.now()

        if success:
            message = f"Successfully synced all activities from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            return jsonify({"success": True, "message": message})
        else:
            message = f"Sync failed for date range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            return jsonify({"success": False, "message": message})

    except Exception as e:
        error_msg = f"Error during sync: {e}"
        logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg})


@app.route('/api/summary-stats/<period>')
def api_summary_stats(period):
    """API endpoint for real-time summary statistics"""
    try:
        summary_data = get_filtered_summary_data(period)

        # Calculate totals
        total_planned = sum(day['total_planned'] for day in summary_data)
        total_actual = sum(day['total_actual'] for day in summary_data)
        avg_completion = sum(day['completion_rate'] for day in summary_data) / len(summary_data) if summary_data else 0

        return jsonify({
            'period': period,
            'total_planned': total_planned,
            'total_actual': total_actual,
            'variance_percent': ((total_actual - total_planned) / total_planned * 100) if total_planned > 0 else 0,
            'avg_completion_rate': avg_completion,
            'data_points': len(summary_data),
            'summary_data': summary_data
        })

    except Exception as e:
        logger.error(f"Error getting summary stats: {e}")
        return jsonify({'error': str(e)}), 500


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