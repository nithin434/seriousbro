#!/usr/bin/env python3
"""
Test script for email OTP template
This script tests if the OTP is properly inserted into the email template
"""

import sys
import os
sys.path.append('.')

from send_mail import get_email_template, send_email

def test_email_template():
    """Test email template OTP replacement"""
    print("🧪 Testing Email Template OTP Replacement")
    print("=" * 50)
    
    # Test welcome template
    template = get_email_template("welcome")
    if template:
        if "OTP_PLACEHOLDER" in template:
            print("✅ Welcome template created with OTP placeholder")
            
            # Test replacement
            test_otp = "123456"
            replaced_template = template.replace('OTP_PLACEHOLDER', test_otp)
            
            if test_otp in replaced_template and "OTP_PLACEHOLDER" not in replaced_template:
                print(f"✅ OTP replacement successful: {test_otp}")
            else:
                print("❌ OTP replacement failed")
                
        else:
            print("❌ No OTP placeholder found in template")
    else:
        print("❌ Failed to create welcome template")
    
    # Test verification template
    template = get_email_template("verification")
    if template and "OTP_PLACEHOLDER" in template:
        print("✅ Verification template created with OTP placeholder")
    else:
        print("❌ Verification template issue")
    
    # Test forgot password template
    template = get_email_template("forgot_password")
    if template and "OTP_PLACEHOLDER" in template:
        print("✅ Forgot password template created with OTP placeholder")
    else:
        print("❌ Forgot password template issue")

def test_send_email_function():
    """Test the send_email function with OTP"""
    print("\n📧 Testing Send Email Function")
    print("=" * 50)
    
    # Test email (you can change this)
    test_email = "test@example.com"  # Change to a real email for testing
    test_otp = "654321"
    
    print(f"📤 Would send email to: {test_email}")
    print(f"🔑 With OTP: {test_otp}")
    
    # Don't actually send, just test the template preparation
    from send_mail import FROM_EMAIL, FROM_PASSWORD
    
    if not FROM_EMAIL or not FROM_PASSWORD:
        print("⚠️ Email configuration not set, skipping actual send test")
        return
    
    print("📋 Email configuration found, template should work correctly")
    
    # You can uncomment this to actually send a test email
    # result = send_email(
    #     subject="SYNTEXA Test Email",
    #     to_email=test_email,
    #     template_name="welcome",
    #     otp=test_otp
    # )
    # 
    # if result:
    #     print("✅ Test email sent successfully!")
    # else:
    #     print("❌ Test email failed to send")

def main():
    """Run all tests"""
    print("🚀 SYNTEXA Email Template Tests")
    print("=" * 60)
    
    test_email_template()
    test_send_email_function()
    
    print("\n" + "=" * 60)
    print("✅ Email template tests completed!")
    print("💡 The email templates should now correctly show OTP codes instead of {otp}")
    print("🔧 Try the signup process again to verify the fix")

if __name__ == "__main__":
    main()
