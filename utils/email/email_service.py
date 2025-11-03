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
            logger.warning(" Email sending is disabled. Enable in settings.")
            logger.info(f" Would send email to {to_email}: {subject}")
            if self.backend == "console":
                logger.info(f" Subject: {subject}")
                logger.info(f" To: {to_email}")
                logger.info(f" Content: {text_content or html_content[:200]}...")
            return True  # Return True in dev mode
        
        if not self.username or not self.password:
            logger.error(" Email credentials not configured")
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
            
            logger.info(f" Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f" Failed to send email to {to_email}: {e}")
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
                    <h1> Password Reset Request</h1>
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
        subject = f" {linked_service} Account Linked - LearnivaAI"
        
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
                    <h1> Account Successfully Linked</h1>
                </div>
                <div class="content">
                    <div class="icon"></div>
                    <p>Hi {username},</p>
                    <p>Your LearnivaAI account has been successfully linked with your <strong>{linked_service}</strong> account.</p>
                    
                    <div class="info-box">
                        <p><strong> Email:</strong> {to_email}</p>
                        <p><strong> Linked Service:</strong> {linked_service}</p>
                        <p><strong> Date:</strong> {self._get_current_datetime()}</p>
                    </div>
                    
                    <h3>What This Means:</h3>
                    <ul>
                        <li>You can now sign in using either your email/password or your {linked_service} account</li>
                        <li>Your profile information has been updated with your {linked_service} profile picture</li>
                        <li>All your existing data and settings remain unchanged</li>
                        <li>You have the convenience of using both sign-in methods</li>
                    </ul>
                    
                    <div class="warning-box">
                        <p><strong> Security Notice:</strong></p>
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
    
    def send_welcome_email(
        self,
        to_email: str,
        username: str,
        first_name: Optional[str] = None
    ) -> bool:
        """
        Send a welcome email to newly registered users.
        
        Args:
            to_email: Recipient email address
            username: User's username
            first_name: User's first name (optional)
        
        Returns:
            True if email sent successfully
        """
        # Use first name if provided, otherwise use username
        greeting_name = first_name if first_name else username
        
        subject = f" Welcome to LearnivaAI, {greeting_name}!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.8;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px 0;
                }}
                .inner-container {{
                    background-color: white;
                    margin: 0 20px;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 32px;
                    font-weight: 600;
                }}
                .emoji-banner {{
                    font-size: 64px;
                    margin: 20px 0;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .welcome-text {{
                    font-size: 18px;
                    color: #4a5568;
                    margin-bottom: 25px;
                }}
                .highlight-box {{
                    background: linear-gradient(135deg, #f6f8fb 0%, #e9ecef 100%);
                    border-left: 5px solid #667eea;
                    padding: 20px;
                    margin: 25px 0;
                    border-radius: 5px;
                }}
                .features {{
                    margin: 30px 0;
                }}
                .feature-item {{
                    display: flex;
                    align-items: flex-start;
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    transition: transform 0.2s;
                }}
                .feature-item:hover {{
                    transform: translateX(5px);
                }}
                .feature-icon {{
                    font-size: 32px;
                    margin-right: 15px;
                    flex-shrink: 0;
                }}
                .feature-content h3 {{
                    margin: 0 0 8px 0;
                    color: #667eea;
                    font-size: 16px;
                }}
                .feature-content p {{
                    margin: 0;
                    color: #666;
                    font-size: 14px;
                }}
                .cta-button {{
                    display: inline-block;
                    padding: 16px 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white !important;
                    text-decoration: none;
                    border-radius: 30px;
                    margin: 25px 0;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                    transition: transform 0.2s;
                }}
                .cta-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
                }}
                .tips-section {{
                    background-color: #fff3e0;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 25px 0;
                }}
                .tips-section h3 {{
                    color: #f57c00;
                    margin-top: 0;
                }}
                .tip {{
                    margin: 12px 0;
                    padding-left: 25px;
                    position: relative;
                }}
                .tip:before {{
                    content: "";
                    position: absolute;
                    left: 0;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    text-align: center;
                    padding: 30px;
                    color: #666;
                    font-size: 13px;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .social-links {{
                    margin: 20px 0;
                }}
                .social-links a {{
                    display: inline-block;
                    margin: 0 10px;
                    color: #667eea;
                    text-decoration: none;
                }}
                .divider {{
                    height: 2px;
                    background: linear-gradient(90deg, transparent, #667eea, transparent);
                    margin: 30px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="inner-container">
                    <div class="header">
                        <div class="emoji-banner"></div>
                        <h1>Welcome to LearnivaAI!</h1>
                    </div>
                    
                    <div class="content">
                        <p class="welcome-text">
                            <strong>Hi {greeting_name},</strong>
                        </p>
                        
                        <p class="welcome-text">
                            We're absolutely thrilled to have you join the LearnivaAI community! 
                        </p>
                        
                        <div class="highlight-box">
                            <strong>You've just unlocked the power of AI-driven learning!</strong><br>
                            Your journey to smarter, more efficient studying starts right now.
                        </div>
                        
                        <div class="divider"></div>
                        
                        <h2 style="color: #667eea; text-align: center;"> What Can You Do Now?</h2>
                        
                        <div class="features">
                            <div class="feature-item">
                                <div class="feature-icon"></div>
                                <div class="feature-content">
                                    <h3>AI-Powered Study Assistant</h3>
                                    <p>Get instant help with homework, assignments, and research. Our intelligent study agent adapts to your learning style.</p>
                                </div>
                            </div>
                            
                            <div class="feature-item">
                                <div class="feature-icon"></div>
                                <div class="feature-content">
                                    <h3>Smart Grading & Feedback</h3>
                                    <p>Submit your work and receive detailed, constructive feedback powered by AI to help you improve.</p>
                                </div>
                            </div>
                            
                            <div class="feature-item">
                                <div class="feature-icon"></div>
                                <div class="feature-content">
                                    <h3>Visual Learning Animations</h3>
                                    <p>Complex concepts made simple with beautiful animations and visual explanations.</p>
                                </div>
                            </div>
                            
                            <div class="feature-item">
                                <div class="feature-icon"></div>
                                <div class="feature-content">
                                    <h3>Personalized Learning Path</h3>
                                    <p>Your study sessions are tracked and optimized to help you learn more effectively.</p>
                                </div>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin: 35px 0;">
                            <a href="{settings.frontend_url}" class="cta-button">
                                 Start Learning Now
                            </a>
                        </div>
                        
                        <div class="tips-section">
                            <h3> Quick Tips to Get Started:</h3>
                            <div class="tip">Complete your profile to personalize your experience</div>
                            <div class="tip">Try asking the study agent your first question</div>
                            <div class="tip">Explore different subjects and topics</div>
                            <div class="tip">Connect with Google for seamless access</div>
                            <div class="tip">Check out the help section for tutorials</div>
                        </div>
                        
                        <div class="divider"></div>
                        
                        <p style="color: #666; font-size: 15px;">
                            Need help getting started? Our support team is here for you! 
                            Just reply to this email or visit our help center.
                        </p>
                        
                        <p style="margin-top: 30px; color: #4a5568;">
                            Happy learning! <br>
                            <strong>The LearnivaAI Team</strong>
                        </p>
                    </div>
                    
                    <div class="footer">
                        <p><strong>Stay Connected</strong></p>
                        <div class="social-links">
                            <a href="#">Twitter</a> • 
                            <a href="#">Facebook</a> • 
                            <a href="#">LinkedIn</a>
                        </div>
                        <p>© 2025 LearnivaAI. All rights reserved.</p>
                        <p>You're receiving this because you just created a LearnivaAI account.</p>
                        <p style="margin-top: 15px;">
                            <a href="mailto:support@learniva.ai" style="color: #667eea;">support@learniva.ai</a>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
         WELCOME TO LEARNIVA AI! 
        
        Hi {greeting_name},
        
        We're absolutely thrilled to have you join the LearnivaAI community!
        
        You've just unlocked the power of AI-driven learning! Your journey to smarter, 
        more efficient studying starts right now.
        
         WHAT CAN YOU DO NOW?
        
         AI-Powered Study Assistant
           Get instant help with homework, assignments, and research. Our intelligent 
           study agent adapts to your learning style.
        
         Smart Grading & Feedback
           Submit your work and receive detailed, constructive feedback powered by AI 
           to help you improve.
        
         Visual Learning Animations
           Complex concepts made simple with beautiful animations and visual explanations.
        
         Personalized Learning Path
           Your study sessions are tracked and optimized to help you learn more effectively.
        
         QUICK TIPS TO GET STARTED:
        
        • Complete your profile to personalize your experience
        • Try asking the study agent your first question
        • Explore different subjects and topics
        • Connect with Google for seamless access
        • Check out the help section for tutorials
        
         Ready to start? Visit: {settings.frontend_url}
        
        Need help getting started? Our support team is here for you! Just reply to 
        this email or contact us at support@learniva.ai
        
        Happy learning! 
        The LearnivaAI Team
        
        ---
        © 2025 LearnivaAI. All rights reserved.
        You're receiving this because you just created a LearnivaAI account.
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

