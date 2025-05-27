# Enhance WhatsApp notifier with configuration support
import requests
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class WhatsAppNotifier:
    """WhatsApp notification service using Twilio"""

    def __init__(self):
        # Try to load from config file first, then environment variables
        self.config = self._load_config()

        if self.config.get('enabled', False) and self.config.get('api_key'):
            try:
                # If using Twilio
                if 'twilio' in self.config.get('provider', 'twilio').lower():
                    from twilio.rest import Client
                    self.client = Client(self.config['api_key'], self.config.get('auth_token', ''))
                else:
                    self.client = None
                    logger.info("WhatsApp provider not yet implemented")
            except Exception as e:
                logger.error(f"Failed to initialize WhatsApp client: {e}")
                self.client = None
        else:
            self.client = None
            logger.info("WhatsApp notifications disabled or not configured")

    def _load_config(self):
        """Load WhatsApp configuration from file or environment"""
        try:
            import json
            with open('whatsapp_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback to environment variables
            return {
                'enabled': bool(getattr(Config, 'TWILIO_ACCOUNT_SID', None)),
                'api_key': getattr(Config, 'TWILIO_ACCOUNT_SID', None),
                'auth_token': getattr(Config, 'TWILIO_AUTH_TOKEN', None),
                'phone_number': getattr(Config, 'TWILIO_WHATSAPP_NUMBER', None),
                'provider': 'twilio'
            }

    def send_message(self, message: str, recipient: str = None) -> bool:
        """
        Send a message via WhatsApp Business API

        Note: This is a placeholder implementation for WhatsApp Business API.
        The actual implementation depends on your WhatsApp Business setup.

        For unofficial WhatsApp automation, consider these limitations:
        1. WhatsApp's Terms of Service restrict automated messaging
        2. Third-party APIs may be unreliable or against ToS
        3. Official WhatsApp Business API requires business verification
        4. Rate limits and message formatting restrictions apply

        Alternative approaches:
        - Use WhatsApp Business API (official, requires business account)
        - Use Twilio WhatsApp Business API (official integration)
        - Use email notifications as fallback
        - Use Slack/Discord webhooks for team notifications
        """

        if not self._validate_config():
            logger.error("WhatsApp configuration is incomplete")
            return False

        try:
            # Use group ID if no specific recipient provided
            target_recipient = recipient or self.group_id

            # Prepare the message payload (format varies by API provider)
            payload = {
                "messaging_product": "whatsapp",
                "to": target_recipient,
                "type": "text",
                "text": {
                    "body": message
                }
            }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            # Send the message
            response = requests.post(
                f"{self.api_url}/{self.phone_number_id}/messages",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                logger.info("WhatsApp message sent successfully")
                return True
            else:
                logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp message: {e}")
            return False

    def _validate_config(self) -> bool:
        """Validate WhatsApp configuration"""
        required_configs = [
            self.api_url,
            self.access_token,
            self.phone_number_id
        ]

        if not all(required_configs):
            missing_configs = []
            if not self.api_url:
                missing_configs.append("WHATSAPP_API_URL")
            if not self.access_token:
                missing_configs.append("WHATSAPP_ACCESS_TOKEN")
            if not self.phone_number_id:
                missing_configs.append("WHATSAPP_PHONE_NUMBER_ID")

            logger.warning(f"Missing WhatsApp configurations: {', '.join(missing_configs)}")
            return False

        return True

    def send_daily_summary(self, summary_message: str) -> bool:
        """Send the daily training summary to the configured group"""
        try:
            success = self.send_message(summary_message)

            if success:
                logger.info("Daily summary sent to WhatsApp group successfully")
            else:
                logger.error("Failed to send daily summary to WhatsApp group")
                # Fallback: Log the message for manual review
                logger.info(f"Daily summary message (for manual review):\n{summary_message}")

            return success

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
            return False

    def test_connection(self) -> bool:
        """Test WhatsApp API connection"""
        try:
            test_message = "🏃‍♂️ Marathon Dashboard - Connection Test"
            return self.send_message(test_message)

        except Exception as e:
            logger.error(f"WhatsApp connection test failed: {e}")
            return False


class EmailNotifier:
    """Alternative email notification system as fallback"""

    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER if hasattr(Config, 'SMTP_SERVER') else None
        self.smtp_port = Config.SMTP_PORT if hasattr(Config, 'SMTP_PORT') else 587
        self.email_user = Config.EMAIL_USER if hasattr(Config, 'EMAIL_USER') else None
        self.email_password = Config.EMAIL_PASSWORD if hasattr(Config, 'EMAIL_PASSWORD') else None
        self.recipient_emails = Config.RECIPIENT_EMAILS if hasattr(Config, 'RECIPIENT_EMAILS') else []

    def send_email_summary(self, subject: str, message: str) -> bool:
        """
        Send email notification as fallback
        This can be implemented if email credentials are provided
        """
        try:
            if not self._validate_email_config():
                logger.warning("Email configuration not available, skipping email notification")
                return False

            import smtplib
            from email.mime.text import MimeText
            from email.mime.multipart import MimeMultipart

            msg = MimeMultipart()
            msg['From'] = self.email_user
            msg['Subject'] = subject

            msg.attach(MimeText(message, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)

            for recipient in self.recipient_emails:
                msg['To'] = recipient
                server.send_message(msg)
                del msg['To']

            server.quit()
            logger.info("Email summary sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send email summary: {e}")
            return False

    def _validate_email_config(self) -> bool:
        """Validate email configuration"""
        return all([
            self.smtp_server,
            self.email_user,
            self.email_password,
            self.recipient_emails
        ])


class NotificationManager:
    """Manager class to handle multiple notification channels"""

    def __init__(self):
        self.whatsapp_notifier = WhatsAppNotifier()
        self.email_notifier = EmailNotifier()

    def send_daily_notification(self, summary_message: str) -> bool:
        """Send daily notification via available channels"""
        success = False

        # Try WhatsApp first
        if self.whatsapp_notifier.send_daily_summary(summary_message):
            success = True
        else:
            # Fallback to email if WhatsApp fails
            logger.info("WhatsApp notification failed, trying email fallback")
            if self.email_notifier.send_email_summary(
                "Marathon Training Daily Summary",
                summary_message
            ):
                success = True

        # Always log the summary for backup
        logger.info(f"Daily training summary:\n{summary_message}")

        return success