import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the marathon dashboard application"""

    # Strava API Configuration
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    # Use the actual Replit URL for redirect
    STRAVA_REDIRECT_URI = os.getenv('STRAVA_REDIRECT_URI', 'https://your-repl-name.your-username.repl.co/auth/strava/callback')

    # WhatsApp Business API Configuration
    WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    # File Paths
    TRAINING_PLAN_FILE = os.getenv("TRAINING_PLAN_FILE", "sample_training_plan.xlsx")

    # Scheduling Configuration
    DAILY_EXECUTION_TIME = os.getenv("DAILY_EXECUTION_TIME", "08:00")  # 24-hour format

    # Application Settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            'STRAVA_CLIENT_ID',
            'STRAVA_CLIENT_SECRET'
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True

    @classmethod
    def get_athlete_refresh_tokens(cls):
        """Get athlete refresh tokens from environment variables"""
        tokens = {}

        # Look for environment variables in format ATHLETE_1_REFRESH_TOKEN, etc.
        for i in range(1, 10):  # Support up to 10 athletes
            token_var = f"ATHLETE_{i}_REFRESH_TOKEN"
            name_var = f"ATHLETE_{i}_NAME"

            token = os.getenv(token_var)
            name = os.getenv(name_var, f"Athlete {i}")

            if token:
                tokens[name] = token

        return tokens