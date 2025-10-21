"""
Email Service for sending emails via SMTP.

Supports Gmail, Office365, and other SMTP providers.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from config.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending emails."""
    
    def __init__(self):
        """Initialize email service with settings."""
        self.enabled = settings.email_enabled
        self.backend = settings.email_backend
        self.host = settings.email_host
        self.port = settings.email_port
        self.use_tls = settings.email_use_tls
        self.use_ssl = settings.email_use_ssl
        self.username = settings.email_host_user
        self.password = settings.email_host_password
        self.from_address = settings.email_from_address
        self.from_name = settings.email_from_name
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        to_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text fallback content
            to_emails: List of additional recipient emails
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("📧 Email sending is disabled. Enable in settings.")
            logger.info(f"📧 Would send email to {to_email}: {subject}")
            if self.backend == "console":
                logger.info(f"📧 Subject: {subject}")
                logger.info(f"📧 To: {to_email}")
                logger.info(f"📧 Content: {text_content or html_content[:200]}...")
            return True  # Return True in dev mode
        
        if not self.username or not self.password:
            logger.error("❌ Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_address}>"
            msg['To'] = to_email
            
            # Add plain text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)
            
            # Connect to SMTP server
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
            
            # Use TLS if specified
            if self.use_tls and not self.use_ssl:
                server.starttls()
            
            # Login and send
            server.login(self.username, self.password)
            
            # Send to primary recipient and any additional recipients
            recipients = [to_email]
            if to_emails:
                recipients.extend(to_emails)
            
            server.sendmail(self.from_address, recipients, msg.as_string())
            server.quit()
            
            logger.info(f"✅ Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False
    
    def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """
        Send password reset email with reset link.
        
        Args:
            to_email: Recipient email address
            username: User's username
            reset_token: Password reset token
        
        Returns:
            True if email sent successfully
        """
        reset_url = f"{settings.password_reset_url}?token={reset_token}&email={to_email}"
        
        subject = "Reset Your Password - LearnivaAI"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 5px 5px 0 0;
                }}
                .content {{
                    background-color: #f9f9f9;
                    padding: 30px;
                    border-radius: 0 0 5px 5px;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background-color: #4CAF50;
                    color: white !important;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hi {username},</p>
                    <p>We received a request to reset your password for your LearnivaAI account.</p>
                    <p>Click the button below to reset your password:</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset My Password</a>
                    </p>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #4CAF50;">{reset_url}</p>
                    <p><strong>This link will expire in {settings.password_reset_token_expire_hours} hour(s).</strong></p>
                    <p>If you didn't request this password reset, please ignore this email or contact support if you have concerns.</p>
                    <p>Best regards,<br>The LearnivaAI Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 LearnivaAI. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        Hi {username},
        
        We received a request to reset your password for your LearnivaAI account.
        
        Click the link below to reset your password:
        {reset_url}
        
        This link will expire in {settings.password_reset_token_expire_hours} hour(s).
        
        If you didn't request this password reset, please ignore this email or contact support.
        
        Best regards,
        The LearnivaAI Team
        
        © 2025 LearnivaAI. All rights reserved.
        """
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )


# Global email service instance
email_service = EmailService()


__all__ = ['EmailService', 'email_service']

