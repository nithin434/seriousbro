import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Email configuration from environment variables
FROM_EMAIL = os.getenv("SMTP_EMAIL", "nithinjambula89@gmail.com")
FROM_PASSWORD = os.getenv("SMTP_PASSWORD", "qyum bzzh dmxn yivo")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

def get_email_template(template_name: str) -> str:
    """Get HTML email template with professional SYNTEXA branding"""
    
    def create_base_template(subject_text, content_html):
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject_text}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    margin: 0;
                    padding: 0;
                    background-color: #f8fafc;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                }}
                .header {{
                    background: linear-gradient(135deg, #059669 0%, #047857 100%);
                    padding: 40px 30px;
                    text-align: center;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: 700;
                    letter-spacing: -0.5px;
                    margin-bottom: 10px;
                }}
                .syn {{
                    color: #ffffff;
                }}
                .texa {{
                    color: #d1fae5;
                }}
                .tagline {{
                    color: #d1fae5;
                    font-size: 14px;
                    font-weight: 400;
                    letter-spacing: 0.5px;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .content h1 {{
                    color: #1e293b;
                    font-size: 24px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .content p {{
                    color: #475569;
                    font-size: 16px;
                    margin-bottom: 20px;
                    line-height: 1.6;
                }}
                .otp-container {{
                    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                    border: 2px solid #e2e8f0;
                    border-radius: 12px;
                    padding: 30px;
                    text-align: center;
                    margin: 30px 0;
                }}
                .otp-label {{
                    color: #64748b;
                    font-size: 14px;
                    font-weight: 500;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .otp-code {{
                    background: linear-gradient(135deg, #059669 0%, #047857 100%);
                    color: #ffffff;
                    font-size: 32px;
                    font-weight: 700;
                    padding: 20px 30px;
                    border-radius: 8px;
                    letter-spacing: 6px;
                    display: inline-block;
                    box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
                }}
                .info-box {{
                    background-color: #f8fafc;
                    border-left: 4px solid #059669;
                    padding: 20px;
                    border-radius: 0 8px 8px 0;
                    margin: 25px 0;
                }}
                .info-box p {{
                    margin: 8px 0;
                    font-size: 14px;
                    color: #475569;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 30px;
                    text-align: center;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{
                    color: #94a3b8;
                    font-size: 12px;
                    margin: 5px 0;
                }}
                .footer-links {{
                    margin-top: 20px;
                }}
                .footer-links a {{
                    color: #059669;
                    text-decoration: none;
                    margin: 0 15px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                .security-notice {{
                    background-color: #fef3c7;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .security-notice p {{
                    color: #92400e;
                    font-size: 13px;
                    margin: 0;
                    font-weight: 500;
                }}
                @media (max-width: 600px) {{
                    .container {{
                        margin: 0;
                        border-radius: 0;
                    }}
                    .header, .content, .footer {{
                        padding: 30px 20px;
                    }}
                    .otp-code {{
                        font-size: 28px;
                        letter-spacing: 4px;
                        padding: 18px 25px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">
                        <span class="syn">SYN</span><span class="texa">TEXA</span>
                    </div>
                    <div class="tagline">AI-Powered Career Solutions</div>
                </div>
                <div class="content">
                    {content_html}
                </div>
                <div class="footer">
                    <p>&copy; 2025 SYNTEXA. All rights reserved.</p>
                    <p>AI-powered tools for your career success.</p>
                    <div class="footer-links">
                        <a href="#">Privacy Policy</a>
                        <a href="#">Terms of Service</a>
                        <a href="#">Support</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    if template_name == "welcome":
        subject = "Welcome to SYNTEXA - Verify Your Email"
        content = """
            <h1>Welcome to SYNTEXA</h1>
            <p>Thank you for joining SYNTEXA! We're excited to help you advance your career with our AI-powered tools.</p>
            <p>To get started, please verify your email address using the code below:</p>
            
            <div class="otp-container">
                <div class="otp-label">Verification Code</div>
                <div class="otp-code">OTP_PLACEHOLDER</div>
            </div>
            
            <div class="info-box">
                <p><strong>Important:</strong> This code will expire in 10 minutes.</p>
                <p>If you didn't create an account with SYNTEXA, please ignore this email.</p>
            </div>
            
            <p>Once verified, you'll have access to:</p>
            <ul style="color: #475569; padding-left: 20px;">
                <li>AI-powered resume optimization</li>
                <li>Professional cover letter generation</li>
                <li>Interview preparation tools</li>
                <li>Job matching algorithms</li>
            </ul>
        """
        return create_base_template(subject, content)
        
    elif template_name == "verification":
        subject = "SYNTEXA - Email Verification Code"
        content = """
            <h1>Email Verification Required</h1>
            <p>Please verify your email address to continue using SYNTEXA.</p>
            <p>Enter the following verification code to proceed:</p>
            
            <div class="otp-container">
                <div class="otp-label">Verification Code</div>
                <div class="otp-code">OTP_PLACEHOLDER</div>
            </div>
            
            <div class="info-box">
                <p><strong>Code expires in:</strong> 10 minutes</p>
                <p><strong>Security tip:</strong> Never share this code with anyone.</p>
            </div>
        """
        return create_base_template(subject, content)
        
    elif template_name == "forgot_password":
        subject = "SYNTEXA - Password Reset Code"
        content = """
            <h1>Password Reset Request</h1>
            <p>We received a request to reset your SYNTEXA account password.</p>
            <p>Use the following code to reset your password:</p>
            
            <div class="otp-container">
                <div class="otp-label">Reset Code</div>
                <div class="otp-code">OTP_PLACEHOLDER</div>
            </div>
            
            <div class="security-notice">
                <p>If you didn't request a password reset, please ignore this email and consider updating your password for security.</p>
            </div>
            
            <div class="info-box">
                <p><strong>This code expires in:</strong> 10 minutes</p>
                <p><strong>For your security:</strong> Only use this code on the official SYNTEXA website</p>
            </div>
        """
        return create_base_template(subject, content)
    
    return None

def send_email(subject: str, to_email: str, template_name: str, custom_body: str = None, **kwargs) -> bool:
    """
    Send professional email using SYNTEXA templates
    
    Args:
        subject: Email subject
        to_email: Recipient email address
        template_name: Template name (welcome, verification, forgot_password, custom)
        custom_body: Custom HTML body (for template_name="custom")
        **kwargs: Template variables (e.g., otp)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate email configuration
        if not FROM_EMAIL or not FROM_PASSWORD:
            logger.error("Email configuration missing. Please set SMTP_EMAIL and SMTP_PASSWORD in .env file")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"SYNTEXA <{FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Get email body
        if template_name == "custom" and custom_body:
            html_body = custom_body
        else:
            html_template = get_email_template(template_name)
            if not html_template:
                logger.error(f"Template '{template_name}' not found")
                return False
            
            # Replace OTP placeholder with actual OTP
            html_body = html_template
            if 'otp' in kwargs:
                html_body = html_body.replace('OTP_PLACEHOLDER', str(kwargs['otp']))
            
            logger.info(f"Email template prepared for {template_name}, OTP replaced: {'otp' in kwargs}")
        
        # Create HTML part
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(FROM_EMAIL, FROM_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email} with template '{template_name}'")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Please check email credentials in .env file")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_welcome_email(to_email: str, otp: str) -> bool:
    """Send welcome email with verification OTP"""
    return send_email(
        subject="Welcome to SYNTEXA - Verify Your Email",
        to_email=to_email,
        template_name="welcome",
        otp=otp
    )

def send_verification_email(to_email: str, otp: str) -> bool:
    """Send email verification OTP"""
    return send_email(
        subject="SYNTEXA - Email Verification Code",
        to_email=to_email,
        template_name="verification",
        otp=otp
    )

def send_password_reset_email(to_email: str, otp: str) -> bool:
    """Send password reset OTP"""
    return send_email(
        subject="SYNTEXA - Password Reset Code",
        to_email=to_email,
        template_name="forgot_password",
        otp=otp
    )
