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
        """Fetch athlete activities for a date range"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Convert dates to Unix timestamps
            after = int(start_date.timestamp())
            before = int(end_date.timestamp())
            
            params = {
                'after': after,
                'before': before,
                'per_page': 200
            }
            
            response = requests.get(
                f"{self.BASE_URL}/athlete/activities",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            activities = response.json()
            
            # Filter for running activities only
            running_activities = [
                activity for activity in activities 
                if activity.get('type', '').lower() in ['run', 'virtualrun']
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
        scopes = "read,activity:read_all"
        auth_url = (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={Config.STRAVA_REDIRECT_URI}"
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
