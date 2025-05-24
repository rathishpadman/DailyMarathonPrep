import logging
from datetime import datetime, timedelta
from typing import Dict, List
from models import Athlete, DailySummary, PlannedWorkout
from data_processor import DataProcessor

logger = logging.getLogger(__name__)

class DashboardBuilder:
    """Class for building dashboard content and reports"""
    
    def __init__(self):
        self.data_processor = DataProcessor()
    
    def build_daily_dashboard(self, target_date: datetime) -> Dict:
        """Build complete daily dashboard data"""
        try:
            # Get team summary for previous day
            team_summary = self.data_processor.calculate_team_summary(target_date)
            
            # Get individual athlete summaries for previous day
            athlete_summaries = self._get_athlete_summaries(target_date)
            
            # Get today's planned workouts
            today_workouts = self._get_todays_workouts(datetime.now())
            
            dashboard_data = {
                'report_date': target_date.strftime('%Y-%m-%d'),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'team_summary': team_summary,
                'athlete_summaries': athlete_summaries,
                'todays_workouts': today_workouts
            }
            
            logger.info(f"Built dashboard for {target_date.strftime('%Y-%m-%d')}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Failed to build daily dashboard: {e}")
            return {}
    
    def _get_athlete_summaries(self, target_date: datetime) -> List[Dict]:
        """Get individual athlete performance summaries"""
        try:
            # Get all daily summaries for the date
            daily_summaries = DailySummary.query.filter_by(
                summary_date=target_date.date()
            ).all()
            
            athlete_summaries = []
            for summary in daily_summaries:
                athlete = Athlete.query.get(summary.athlete_id)
                if not athlete:
                    continue
                
                athlete_summary = {
                    'athlete_name': athlete.name,
                    'status': summary.status,
                    'planned_distance': self.data_processor.format_distance(summary.planned_distance_km or 0),
                    'actual_distance': self.data_processor.format_distance(summary.actual_distance_km or 0),
                    'planned_pace': self.data_processor.format_pace(summary.planned_pace_min_per_km or 0),
                    'actual_pace': self.data_processor.format_pace(summary.actual_pace_min_per_km or 0),
                    'distance_variance': f"{summary.distance_variance_percent or 0:+.1f}%",
                    'pace_variance': f"{summary.pace_variance_percent or 0:+.1f}%",
                    'notes': summary.notes or ''
                }
                athlete_summaries.append(athlete_summary)
            
            # Sort by athlete name
            athlete_summaries.sort(key=lambda x: x['athlete_name'])
            
            return athlete_summaries
            
        except Exception as e:
            logger.error(f"Failed to get athlete summaries: {e}")
            return []
    
    def _get_todays_workouts(self, target_date: datetime) -> List[Dict]:
        """Get planned workouts for today"""
        try:
            # Get all planned workouts for today
            planned_workouts = PlannedWorkout.query.filter_by(
                workout_date=target_date.date()
            ).all()
            
            todays_workouts = []
            for workout in planned_workouts:
                athlete = Athlete.query.get(workout.athlete_id)
                if not athlete:
                    continue
                
                workout_info = {
                    'athlete_name': athlete.name,
                    'planned_distance': self.data_processor.format_distance(workout.planned_distance_km),
                    'planned_pace': self.data_processor.format_pace(workout.planned_pace_min_per_km),
                    'workout_type': workout.workout_type or 'Regular Run',
                    'notes': workout.notes or ''
                }
                todays_workouts.append(workout_info)
            
            # Sort by athlete name
            todays_workouts.sort(key=lambda x: x['athlete_name'])
            
            return todays_workouts
            
        except Exception as e:
            logger.error(f"Failed to get today's workouts: {e}")
            return []
    
    def build_markdown_report(self, dashboard_data: Dict) -> str:
        """Build markdown formatted daily report"""
        try:
            markdown_content = []
            
            # Header
            markdown_content.append(f"# Marathon Training Dashboard")
            markdown_content.append(f"**Report Date:** {dashboard_data['report_date']}")
            markdown_content.append(f"**Generated:** {dashboard_data['generated_at']}")
            markdown_content.append("")
            
            # Team Summary
            team_summary = dashboard_data.get('team_summary', {})
            markdown_content.append("## Team Performance Summary")
            markdown_content.append(f"- **Total Athletes:** {team_summary.get('total_athletes', 0)}")
            markdown_content.append(f"- **Completed Workouts:** {team_summary.get('completed_workouts', 0)}")
            markdown_content.append(f"- **Completion Rate:** {team_summary.get('completion_rate', 0)}%")
            markdown_content.append(f"- **Avg Distance Variance:** {team_summary.get('average_distance_variance', 0):+.1f}%")
            markdown_content.append(f"- **Avg Pace Variance:** {team_summary.get('average_pace_variance', 0):+.1f}%")
            markdown_content.append("")
            
            # Status Breakdown
            status_breakdown = team_summary.get('status_breakdown', {})
            if status_breakdown:
                markdown_content.append("### Status Breakdown")
                for status, count in status_breakdown.items():
                    markdown_content.append(f"- **{status}:** {count}")
                markdown_content.append("")
            
            # Individual Performance
            athlete_summaries = dashboard_data.get('athlete_summaries', [])
            if athlete_summaries:
                markdown_content.append("## Individual Performance")
                markdown_content.append("| Athlete | Status | Planned Distance | Actual Distance | Distance Var | Planned Pace | Actual Pace | Pace Var |")
                markdown_content.append("|---------|--------|------------------|-----------------|--------------|--------------|-------------|----------|")
                
                for summary in athlete_summaries:
                    row = f"| {summary['athlete_name']} | {summary['status']} | {summary['planned_distance']} | {summary['actual_distance']} | {summary['distance_variance']} | {summary['planned_pace']} | {summary['actual_pace']} | {summary['pace_variance']} |"
                    markdown_content.append(row)
                markdown_content.append("")
            
            # Today's Workouts
            todays_workouts = dashboard_data.get('todays_workouts', [])
            if todays_workouts:
                markdown_content.append("## Today's Planned Workouts")
                markdown_content.append("| Athlete | Distance | Pace | Workout Type | Notes |")
                markdown_content.append("|---------|----------|------|--------------|-------|")
                
                for workout in todays_workouts:
                    notes = workout['notes'][:50] + "..." if len(workout['notes']) > 50 else workout['notes']
                    row = f"| {workout['athlete_name']} | {workout['planned_distance']} | {workout['planned_pace']} | {workout['workout_type']} | {notes} |"
                    markdown_content.append(row)
                markdown_content.append("")
            
            return "\n".join(markdown_content)
            
        except Exception as e:
            logger.error(f"Failed to build markdown report: {e}")
            return "Failed to generate report"
    
    def build_whatsapp_summary(self, dashboard_data: Dict) -> str:
        """Build concise WhatsApp summary message"""
        try:
            team_summary = dashboard_data.get('team_summary', {})
            athlete_summaries = dashboard_data.get('athlete_summaries', [])
            
            # Build concise message
            message_parts = []
            
            # Header
            message_parts.append(f"🏃‍♂️ Marathon Training Update")
            message_parts.append(f"📅 {dashboard_data['report_date']}")
            message_parts.append("")
            
            # Team stats
            completion_rate = team_summary.get('completion_rate', 0)
            total_athletes = team_summary.get('total_athletes', 0)
            completed = team_summary.get('completed_workouts', 0)
            
            if completion_rate >= 80:
                emoji = "🎯"
            elif completion_rate >= 60:
                emoji = "⚠️"
            else:
                emoji = "🚨"
            
            message_parts.append(f"{emoji} Team: {completed}/{total_athletes} completed ({completion_rate}%)")
            message_parts.append("")
            
            # Individual status (abbreviated)
            status_emoji = {
                'On Track': '✅',
                'Over-performed': '💪',
                'Under-performed': '⚠️',
                'Missed Workout': '❌',
                'Extra Activity': '➕',
                'Partially Completed': '🔄'
            }
            
            for summary in athlete_summaries[:4]:  # Limit to first 4 athletes
                emoji = status_emoji.get(summary['status'], '❓')
                name = summary['athlete_name'].split()[0]  # First name only
                message_parts.append(f"{emoji} {name}: {summary['actual_distance']}")
            
            # Today's focus
            todays_workouts = dashboard_data.get('todays_workouts', [])
            if todays_workouts:
                message_parts.append("")
                message_parts.append("🎯 Today's Focus:")
                total_planned_distance = sum(
                    float(w['planned_distance'].replace(' km', '')) 
                    for w in todays_workouts 
                    if w['planned_distance'] != 'N/A'
                )
                message_parts.append(f"Team target: {total_planned_distance:.1f} km")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Failed to build WhatsApp summary: {e}")
            return f"Training Update {dashboard_data.get('report_date', 'Today')}: Dashboard generation failed"
    
    def get_weekly_trends(self, end_date: datetime, weeks: int = 4) -> Dict:
        """Get weekly performance trends for the team"""
        try:
            trends_data = {
                'weeks': [],
                'completion_rates': [],
                'avg_distance_variances': [],
                'total_distances': []
            }
            
            for week_offset in range(weeks):
                week_end = end_date - timedelta(weeks=week_offset)
                week_start = week_end - timedelta(days=6)
                
                # Get summaries for the week
                weekly_summaries = DailySummary.query.filter(
                    DailySummary.summary_date >= week_start.date(),
                    DailySummary.summary_date <= week_end.date()
                ).all()
                
                if weekly_summaries:
                    # Calculate weekly metrics
                    completed = len([s for s in weekly_summaries if s.status in ['On Track', 'Over-performed', 'Partially Completed']])
                    total = len(weekly_summaries)
                    completion_rate = (completed / total) * 100 if total > 0 else 0
                    
                    distance_variances = [s.distance_variance_percent for s in weekly_summaries if s.distance_variance_percent is not None]
                    avg_distance_variance = sum(distance_variances) / len(distance_variances) if distance_variances else 0
                    
                    total_distance = sum(s.actual_distance_km for s in weekly_summaries if s.actual_distance_km)
                    
                    trends_data['weeks'].append(week_start.strftime('%m/%d'))
                    trends_data['completion_rates'].append(round(completion_rate, 1))
                    trends_data['avg_distance_variances'].append(round(avg_distance_variance, 2))
                    trends_data['total_distances'].append(round(total_distance, 1))
            
            # Reverse to show chronological order
            for key in trends_data:
                trends_data[key].reverse()
            
            return trends_data
            
        except Exception as e:
            logger.error(f"Failed to get weekly trends: {e}")
            return {'weeks': [], 'completion_rates': [], 'avg_distance_variances': [], 'total_distances': []}
