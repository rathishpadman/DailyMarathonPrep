import os
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class StravaClient:
    """Client for interacting with Strava API"""

    BASE_URL = "https://www.strava.com/api/v3"
    TOKEN_URL = "https://www.strava.com/oauth/token"

    def __init__(self):
        self.client_id = Config.STRAVA_CLIENT_ID
        self.client_secret = Config.STRAVA_CLIENT_SECRET
        self.requests_made_15min = 0
        self.requests_made_daily = 0
        self.last_request_time = None

    def _check_rate_limits(self) -> bool:
        """Check if we can make a request without exceeding rate limits"""
        from models import StravaApiUsage
        from app import db
        
        try:
            today = datetime.now().date()
            usage = db.session.query(StravaApiUsage).filter_by(date=today).first()
            
            if not usage:
                usage = StravaApiUsage(date=today, requests_15min=0, requests_daily=0)
                db.session.add(usage)
                db.session.commit()
            
            # Check 15-minute limit
            if usage.last_request_time and usage.last_request_time > datetime.now() - timedelta(minutes=15):
                if usage.requests_15min >= Config.STRAVA_RATE_LIMIT_15MIN:
                    logger.warning("Strava 15-minute rate limit would be exceeded")
                    return False
            else:
                # Reset 15-minute counter
                usage.requests_15min = 0
            
            # Check daily limit
            if usage.requests_daily >= Config.STRAVA_RATE_LIMIT_DAILY:
                logger.warning("Strava daily rate limit would be exceeded")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limits: {e}")
            return True  # Allow request if we can't check limits
    
    def _record_request(self):
        """Record that we made a request"""
        from models import StravaApiUsage
        from app import db
        
        try:
            today = datetime.now().date()
            usage = db.session.query(StravaApiUsage).filter_by(date=today).first()
            
            if not usage:
                usage = StravaApiUsage(date=today)
                db.session.add(usage)
            
            # Reset 15-minute counter if needed
            if not usage.last_request_time or usage.last_request_time <= datetime.now() - timedelta(minutes=15):
                usage.requests_15min = 1
            else:
                usage.requests_15min += 1
            
            usage.requests_daily += 1
            usage.last_request_time = datetime.now()
            usage.updated_at = datetime.now()
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error recording request: {e}")

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh the access token using refresh token"""
        try:
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }

            response = requests.post(self.TOKEN_URL, data=payload)
            response.raise_for_status()

            token_data = response.json()
            logger.info("Successfully refreshed Strava access token")
            return token_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh Strava token: {e}")
            return None

    def get_athlete_activities(self, access_token: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch athlete activities for a date range with rate limiting"""
        try:
            if not self._check_rate_limits():
                logger.warning("Skipping activity fetch due to rate limits")
                return []
            
            headers = {'Authorization': f'Bearer {access_token}'}

            # Convert dates to Unix timestamps
            after = int(start_date.timestamp())
            before = int(end_date.timestamp())

            all_activities = []
            page = 1
            while True:
                if not self._check_rate_limits():
                    logger.warning("Rate limit reached during pagination")
                    break
                
                params = {
                    'after': after,
                    'before': before,
                    'per_page': 200,
                    'page': page
                }

                response = requests.get(
                    f"{self.BASE_URL}/athlete/activities",
                    headers=headers,
                    params=params
                )
                self._record_request()
                response.raise_for_status()

                activities = response.json()
                if not activities:
                    break

                all_activities.extend(activities)
                page += 1

            # Filter for running activities only
            running_activities = [
                activity for activity in all_activities
                if activity.get('type', '').lower() in ['run', 'virtualrun', 'trail_run']
            ]

            logger.info(f"Fetched {len(running_activities)} running activities")
            return running_activities

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Strava activities: {e}")
            return []

    def process_activity_data(self, activity: Dict) -> Dict:
        """Process raw Strava activity data into our format"""
        try:
            # Calculate pace (minutes per km)
            distance_km = activity.get('distance', 0) / 1000  # Convert meters to km
            moving_time_minutes = activity.get('moving_time', 0) / 60  # Convert seconds to minutes

            pace_min_per_km = None
            if distance_km > 0:
                pace_min_per_km = moving_time_minutes / distance_km

            processed_data = {
                'strava_activity_id': activity.get('id'),
                'name': activity.get('name', ''),
                'activity_type': activity.get('type', ''),
                'start_date': datetime.fromisoformat(activity.get('start_date_local', '').replace('Z', '+00:00')),
                'distance_km': distance_km,
                'moving_time_seconds': activity.get('moving_time', 0),
                'pace_min_per_km': pace_min_per_km
            }

            return processed_data

        except Exception as e:
            logger.error(f"Failed to process activity data: {e}")
            return {}

    def get_authorization_url(self) -> str:
        """Get Strava OAuth authorization URL"""
        from urllib.parse import quote

        scopes = "read,activity:read_all"
        redirect_uri = quote(Config.STRAVA_REDIRECT_URI, safe='')

        auth_url = (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&approval_prompt=force"
            f"&scope={scopes}"
        )
        return auth_url

    def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        try:
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code'
            }

            response = requests.post(self.TOKEN_URL, data=payload)
            response.raise_for_status()

            token_data = response.json()
            logger.info("Successfully exchanged code for Strava token")
            return token_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return None
