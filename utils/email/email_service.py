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
    
    def send_account_linked_email(
        self,
        to_email: str,
        username: str,
        linked_service: str = "Google"
    ) -> bool:
        """
        Send notification email when a third-party account is linked.
        
        Args:
            to_email: Recipient email address
            username: User's username
            linked_service: Name of the linked service (e.g., "Google")
        
        Returns:
            True if email sent successfully
        """
        subject = f"🔗 {linked_service} Account Linked - LearnivaAI"
        
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
                    background-color: #4285f4;
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
                .info-box {{
                    background-color: #e3f2fd;
                    border-left: 4px solid #2196F3;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .warning-box {{
                    background-color: #fff3e0;
                    border-left: 4px solid #ff9800;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                    font-size: 12px;
                }}
                .icon {{
                    font-size: 48px;
                    text-align: center;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔗 Account Successfully Linked</h1>
                </div>
                <div class="content">
                    <div class="icon">✅</div>
                    <p>Hi {username},</p>
                    <p>Your LearnivaAI account has been successfully linked with your <strong>{linked_service}</strong> account.</p>
                    
                    <div class="info-box">
                        <p><strong>📧 Email:</strong> {to_email}</p>
                        <p><strong>🔗 Linked Service:</strong> {linked_service}</p>
                        <p><strong>📅 Date:</strong> {self._get_current_datetime()}</p>
                    </div>
                    
                    <h3>What This Means:</h3>
                    <ul>
                        <li>You can now sign in using either your email/password or your {linked_service} account</li>
                        <li>Your profile information has been updated with your {linked_service} profile picture</li>
                        <li>All your existing data and settings remain unchanged</li>
                        <li>You have the convenience of using both sign-in methods</li>
                    </ul>
                    
                    <div class="warning-box">
                        <p><strong>⚠️ Security Notice:</strong></p>
                        <p>If you did not authorize this account linking, please take immediate action:</p>
                        <ol>
                            <li>Change your password immediately</li>
                            <li>Review your account security settings</li>
                            <li>Contact our support team at support@learniva.ai</li>
                        </ol>
                    </div>
                    
                    <p>You can manage your connected accounts and security settings in your account preferences.</p>
                    
                    <p>Best regards,<br>The LearnivaAI Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 LearnivaAI. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>If you have questions, contact us at support@learniva.ai</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Account Successfully Linked - LearnivaAI
        
        Hi {username},
        
        Your LearnivaAI account has been successfully linked with your {linked_service} account.
        
        Account Details:
        - Email: {to_email}
        - Linked Service: {linked_service}
        - Date: {self._get_current_datetime()}
        
        What This Means:
        • You can now sign in using either your email/password or your {linked_service} account
        • Your profile information has been updated with your {linked_service} profile picture
        • All your existing data and settings remain unchanged
        • You have the convenience of using both sign-in methods
        
        SECURITY NOTICE:
        If you did not authorize this account linking, please take immediate action:
        1. Change your password immediately
        2. Review your account security settings
        3. Contact our support team at support@learniva.ai
        
        You can manage your connected accounts and security settings in your account preferences.
        
        Best regards,
        The LearnivaAI Team
        
        © 2025 LearnivaAI. All rights reserved.
        If you have questions, contact us at support@learniva.ai
        """
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    def _get_current_datetime(self) -> str:
        """Get current datetime formatted string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")


# Global email service instance
email_service = EmailService()


__all__ = ['EmailService', 'email_service']

