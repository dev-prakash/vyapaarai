"""
Email Service for VyaparAI
Handles sending emails via AWS SES or SMTP
"""

import os
import logging
import boto3
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        """Initialize email service with AWS SES or fallback to SMTP"""
        self.use_ses = os.getenv("USE_AWS_SES", "false").lower() == "true"
        self.from_email = os.getenv("FROM_EMAIL", "noreply@vyaparai.com")
        self.from_name = "VyaparAI"
        
        if self.use_ses:
            # Initialize AWS SES client
            self.ses_client = boto3.client(
                'ses',
                region_name=os.getenv("AWS_REGION", "ap-south-1")
            )
        else:
            # For development, we'll just log emails
            logger.info("Email service in development mode - emails will be logged only")
    
    async def send_passcode_email(self, to_email: str, passcode: str) -> bool:
        """
        Send passcode email to user
        
        Args:
            to_email: Recipient email address
            passcode: 6-digit passcode
            
        Returns:
            True if email sent successfully, False otherwise
        """
        subject = "Your VyapaarAI Login Passcode"
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .passcode-box {{ background: white; border: 2px solid #667eea; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
                .passcode {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #667eea; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 10px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>VyapaarAI</h1>
                    <p>Your Smart Store Assistant</p>
                </div>
                <div class="content">
                    <h2>Login Passcode</h2>
                    <p>You requested a login passcode for your VyapaarAI store account.</p>
                    
                    <div class="passcode-box">
                        <p>Your 6-digit passcode is:</p>
                        <div class="passcode">{passcode}</div>
                    </div>
                    
                    <p><strong>This passcode will expire in 15 minutes and can only be used once.</strong></p>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong><br>
                        • Never share this passcode with anyone<br>
                        • VyapaarAI staff will never ask for your passcode<br>
                        • If you didn't request this, please ignore this email
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated message from VyapaarAI. Please do not reply to this email.</p>
                        <p>© 2026 VyapaarAI. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text email body (fallback)
        text_body = f"""
        VyapaarAI Login Passcode

        You requested a login passcode for your VyapaarAI store account.
        
        Your 6-digit passcode is: {passcode}
        
        This passcode will expire in 15 minutes and can only be used once.
        
        Security Notice:
        - Never share this passcode with anyone
        - VyapaarAI staff will never ask for your passcode
        - If you didn't request this, please ignore this email
        
        This is an automated message from VyapaarAI.
        © 2026 VyapaarAI. All rights reserved.
        """
        
        return await self.send_email(to_email, subject, text_body, html_body)
    
    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        text_body: str, 
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using AWS SES or log in development
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            html_body: HTML email body (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if self.use_ses:
                # Send email via AWS SES
                message = {
                    'Subject': {'Data': subject},
                    'Body': {'Text': {'Data': text_body}}
                }
                
                if html_body:
                    message['Body']['Html'] = {'Data': html_body}
                
                response = self.ses_client.send_email(
                    Source=f"{self.from_name} <{self.from_email}>",
                    Destination={'ToAddresses': [to_email]},
                    Message=message
                )
                
                logger.info(f"Email sent successfully to {to_email}. MessageId: {response['MessageId']}")
                return True
                
            else:
                # Development mode - just log the email
                logger.info(f"""
                ========== EMAIL (DEVELOPMENT MODE) ==========
                TO: {to_email}
                FROM: {self.from_name} <{self.from_email}>
                SUBJECT: {subject}
                BODY: {text_body[:200]}...
                =============================================
                """)
                return True
                
        except ClientError as e:
            logger.error(f"Failed to send email to {to_email}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")
            return False

# Create singleton instance
email_service = EmailService()

# Export for easy access
send_passcode_email = email_service.send_passcode_email
send_email = email_service.send_email