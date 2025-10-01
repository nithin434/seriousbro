#!/usr/bin/env python3
"""
Simple Email Test Script for SYNTEXA
Tests the email functionality with professional templates
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email configuration
FROM_EMAIL = os.getenv("SMTP_EMAIL", "nithinjambula89@gmail.com")
FROM_PASSWORD = os.getenv("SMTP_PASSWORD", "qyum bzzh dmxn yivo")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

def create_professional_email_template(otp, purpose="verification"):
    """Create a professional SYNTEXA email template"""
    
    if purpose == "welcome":
        title = "Welcome to SYNTEXA"
        message = "Thank you for joining SYNTEXA! We're excited to help you advance your career with our AI-powered tools."
        extra_content = """
        <p>Once verified, you'll have access to:</p>
        <ul style="color: #475569; padding-left: 20px; margin: 20px 0;">
            <li>AI-powered resume optimization</li>
            <li>Professional cover letter generation</li>
            <li>Interview preparation tools</li>
            <li>Job matching algorithms</li>
        </ul>
        """
    elif purpose == "forgot_password":
        title = "Password Reset Request"
        message = "We received a request to reset your SYNTEXA account password."
        extra_content = """
        <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 15px; margin: 20px 0;">
            <p style="color: #92400e; font-size: 13px; margin: 0; font-weight: 500;">
                If you didn't request a password reset, please ignore this email and consider updating your password for security.
            </p>
        </div>
        """
    else:
        title = "Email Verification Required"
        message = "Please verify your email address to continue using SYNTEXA."
        extra_content = ""
    
    # Create the HTML template
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
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
                <h1>{title}</h1>
                <p>{message}</p>
                <p>Enter the following verification code to proceed:</p>
                
                <div class="otp-container">
                    <div class="otp-label">Verification Code</div>
                    <div class="otp-code">{otp}</div>
                </div>
                
                {extra_content}
                
                <div class="info-box">
                    <p><strong>Code expires in:</strong> 10 minutes</p>
                    <p><strong>Security tip:</strong> Never share this code with anyone.</p>
                    <p><strong>For your security:</strong> Only use this code on the official SYNTEXA website</p>
                </div>
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
    
    return html_template

def send_test_email(to_email, otp="123456", purpose="verification"):
    """Send a test email with professional SYNTEXA template"""
    try:
        print(f"📧 Sending test email to: {to_email}")
        print(f"📊 Using SMTP: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"📤 From: {FROM_EMAIL}")
        print(f"🔑 OTP: {otp}")
        print("-" * 50)
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"SYNTEXA <{FROM_EMAIL}>"
        msg['To'] = to_email
        
        if purpose == "welcome":
            msg['Subject'] = "Welcome to SYNTEXA - Verify Your Email"
        elif purpose == "forgot_password":
            msg['Subject'] = "SYNTEXA - Password Reset Code"
        else:
            msg['Subject'] = "SYNTEXA - Email Verification Code"
        
        # Create HTML content
        html_body = create_professional_email_template(otp, purpose)
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Send email
        print("🔄 Connecting to SMTP server...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            print("🔐 Starting TLS...")
            server.starttls()
            print("🔑 Logging in...")
            server.login(FROM_EMAIL, FROM_PASSWORD)
            print("📨 Sending email...")
            server.send_message(msg)
        
        print("✅ Email sent successfully!")
        print(f"📬 Check {to_email} for the verification code: {otp}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentication failed: {e}")
        print("💡 Please check your email credentials in .env file")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def main():
    """Test the email system"""
    print("=" * 60)
    print("🚀 SYNTEXA Email System Test")
    print("=" * 60)
    
    # Check environment variables
    print("🔧 Checking configuration...")
    print(f"📧 SMTP Email: {FROM_EMAIL}")
    print(f"🔐 Password: {'*' * len(FROM_PASSWORD) if FROM_PASSWORD else 'NOT SET'}")
    print(f"🌐 SMTP Server: {SMTP_SERVER}:{SMTP_PORT}")
    print()
    
    if not FROM_EMAIL or not FROM_PASSWORD:
        print("❌ Email configuration missing!")
        print("💡 Please set SMTP_EMAIL and SMTP_PASSWORD in .env file")
        return
    
    # Test email
    test_email = input("📧 Enter test email address: ").strip()
    if not test_email:
        test_email = "nithinjambula44@gmail.com"  # Default test email
    
    print(f"🎯 Sending test email to: {test_email}")
    print()
    
    # Test different email types
    print("📧 Testing Welcome Email...")
    send_test_email(test_email, "123456", "welcome")
    print()
    
    print("📧 Testing Verification Email...")
    send_test_email(test_email, "654321", "verification")
    print()
    
    print("📧 Testing Password Reset Email...")
    send_test_email(test_email, "789012", "forgot_password")
    print()
    
    print("=" * 60)
    print("✅ Email test completed!")
    print("📬 Check your email inbox for the test messages")
    print("=" * 60)

if __name__ == "__main__":
    main()
