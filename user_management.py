import os
import jwt
import bcrypt
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional
from pymongo import MongoClient
from bson import ObjectId
import logging
from dotenv import load_dotenv
from send_mail import send_welcome_email, send_verification_email, send_password_reset_email

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        """Initialize the user management system"""
        try:
            # MongoDB connection
            self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
            self.db = self.mongo_client["resumeDB"]
            self.users_collection = self.db["users"]
            self.otps_collection = self.db["otps"]
            
            # JWT secret key
            self.jwt_secret = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
            
            # Create indexes for better performance
            self.users_collection.create_index("email", unique=True)
            self.otps_collection.create_index("email")
            self.otps_collection.create_index("expires_at", expireAfterSeconds=0)
            
            logger.info("User management system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize user management: {str(e)}")
            raise

    def generate_otp(self) -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def generate_jwt_token(self, user_id: str, email: str) -> Dict[str, str]:
        """Generate JWT access and refresh tokens for user"""
        # Access token (short-lived)
        access_payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=1),  # Access token expires in 1 hour
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        access_token = jwt.encode(access_payload, self.jwt_secret, algorithm='HS256')
        
        # Refresh token (long-lived)
        refresh_payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(days=30),  # Refresh token expires in 30 days
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        refresh_token = jwt.encode(refresh_payload, self.jwt_secret, algorithm='HS256')
        
        # Store refresh token in database
        try:
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'refresh_token': refresh_token,
                        'last_login': datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to store refresh token: {str(e)}")
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token
        }

    def verify_jwt_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Generate new access token using refresh token"""
        try:
            # Verify refresh token
            payload = jwt.decode(refresh_token, self.jwt_secret, algorithms=['HS256'])
            
            # Check if it's a refresh token
            if payload.get('type') != 'refresh':
                return None
            
            user_id = payload['user_id']
            email = payload['email']
            
            # Verify refresh token exists in database
            user = self.users_collection.find_one({
                '_id': ObjectId(user_id),
                'refresh_token': refresh_token
            })
            
            if not user:
                return None
            
            # Generate new access token
            new_access_payload = {
                'user_id': user_id,
                'email': email,
                'exp': datetime.utcnow() + timedelta(hours=1),
                'iat': datetime.utcnow(),
                'type': 'access'
            }
            new_access_token = jwt.encode(new_access_payload, self.jwt_secret, algorithm='HS256')
            
            return {
                'access_token': new_access_token,
                'refresh_token': refresh_token  # Keep same refresh token
            }
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return None

    def revoke_refresh_token(self, user_id: str) -> bool:
        """Revoke refresh token for user logout"""
        try:
            result = self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$unset': {'refresh_token': ''}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {str(e)}")
            return False

    def send_otp_email(self, email: str, otp: str, purpose: str = "verification") -> bool:
        """Send OTP via email using professional templates"""
        try:
            if purpose == "signup":
                return send_welcome_email(email, otp)
            elif purpose == "forgot_password":
                return send_password_reset_email(email, otp)
            else:
                return send_verification_email(email, otp)
                
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return False

    def send_otp(self, email: str, purpose: str = "verification") -> Dict:
        """Generate and send OTP to email"""
        try:
            # Generate OTP
            otp = self.generate_otp()
            
            # Store OTP in database with expiration
            otp_data = {
                'email': email,
                'otp': otp,
                'purpose': purpose,
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(minutes=10),
                'verified': False
            }
            
            # Remove any existing OTPs for this email and purpose
            self.otps_collection.delete_many({
                'email': email,
                'purpose': purpose,
                'verified': False
            })
            
            # Insert new OTP
            self.otps_collection.insert_one(otp_data)
            
            # Send email
            if self.send_otp_email(email, otp, purpose):
                return {
                    'success': True,
                    'message': 'OTP sent successfully',
                    'expires_in': 600  # 10 minutes in seconds
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to send OTP email'
                }
                
        except Exception as e:
            logger.error(f"Failed to send OTP: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def verify_otp(self, email: str, otp: str, purpose: str = "verification") -> Dict:
        """Verify OTP for email"""
        try:
            # Find OTP in database
            otp_record = self.otps_collection.find_one({
                'email': email,
                'otp': otp,
                'purpose': purpose,
                'verified': False,
                'expires_at': {'$gt': datetime.utcnow()}
            })
            
            if not otp_record:
                return {
                    'success': False,
                    'error': 'Invalid or expired OTP'
                }
            
            # Mark OTP as verified
            self.otps_collection.update_one(
                {'_id': otp_record['_id']},
                {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
            )
            
            return {
                'success': True,
                'message': 'OTP verified successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to verify OTP: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def signup(self, first_name: str, last_name: str, email: str, password: str) -> Dict:
        """Register a new user"""
        try:
            # Check if user already exists
            existing_user = self.users_collection.find_one({'email': email})
            if existing_user:
                return {
                    'success': False,
                    'error': 'User with this email already exists'
                }
            
            # Hash password
            hashed_password = self.hash_password(password)
            
            # Create user document
            user_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'password': hashed_password,
                'email_verified': False,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_active': True,
                'profile': {
                    'full_name': f"{first_name} {last_name}",
                    'avatar_url': None,
                    'bio': None,
                    'phone': None,
                    'location': None
                }
            }
            
            # Insert user
            result = self.users_collection.insert_one(user_data)
            user_id = str(result.inserted_id)
            
            # Send verification OTP
            otp_result = self.send_otp(email, "signup")
            
            return {
                'success': True,
                'message': 'User registered successfully. Please verify your email.',
                'user_id': user_id,
                'otp_sent': otp_result.get('success', False),
                'requires_verification': True
            }
            
        except Exception as e:
            logger.error(f"Signup failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def verify_email(self, email: str, otp: str) -> Dict:
        """Verify user email with OTP"""
        try:
            # Verify OTP
            otp_result = self.verify_otp(email, otp, "signup")
            if not otp_result['success']:
                return otp_result
            
            # Update user email verification status
            result = self.users_collection.update_one(
                {'email': email},
                {
                    '$set': {
                        'email_verified': True,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Get user data for token generation
            user = self.users_collection.find_one({'email': email})
            user_id = str(user['_id'])
            
            # Generate JWT tokens
            tokens = self.generate_jwt_token(user_id, email)
            
            return {
                'success': True,
                'message': 'Email verified successfully',
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'user': {
                    'id': user_id,
                    'email': email,
                    'first_name': user['first_name'],
                    'last_name': user['last_name'],
                    'full_name': user['profile']['full_name']
                }
                }
            
            
        except Exception as e:
            logger.error(f"Email verification failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def login(self, email: str, password: str) -> Dict:
        """Authenticate user login"""
        try:
            # Find user
            user = self.users_collection.find_one({'email': email})
            if not user:
                return {
                    'success': False,
                    'error': 'Invalid email or password'
                }
            
            # Check if user is deleted
            if user.get('deleted', False):
                return {
                    'success': False,
                    'error': 'Account has been deleted'
                }
            
            # Check if user is active
            if not user.get('is_active', True):
                return {
                    'success': False,
                    'error': 'Account is deactivated'
                }
            
            # Verify password
            if not self.verify_password(password, user['password']):
                return {
                    'success': False,
                    'error': 'Invalid email or password'
                }
            
            # Check if email is verified
            if not user.get('email_verified', False):
                return {
                    'success': False,
                    'error': 'Please verify your email first',
                    'requires_verification': True
                }
            
            # Generate JWT tokens
            user_id = str(user['_id'])
            tokens = self.generate_jwt_token(user_id, email)
            
            # Update last login
            self.users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            
            return {
                'success': True,
                'message': 'Login successful',
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'user': {
                    'id': user_id,
                    'email': email,
                    'first_name': user['first_name'],
                    'last_name': user['last_name'],
                    'full_name': user['profile']['full_name'],
                    'email_verified': user.get('email_verified', False)
                }
            }
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def forgot_password(self, email: str) -> Dict:
        """Send password reset OTP"""
        try:
            # Check if user exists
            user = self.users_collection.find_one({'email': email})
            if not user:
                return {
                    'success': False,
                    'error': 'No account found with this email'
                }
            
            # Send OTP
            otp_result = self.send_otp(email, "forgot_password")
            
            return {
                'success': True,
                'message': 'Password reset code sent to your email',
                'otp_sent': otp_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"Forgot password failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def reset_password(self, email: str, otp: str, new_password: str) -> Dict:
        """Reset password with OTP"""
        try:
            # Verify OTP
            otp_result = self.verify_otp(email, otp, "forgot_password")
            if not otp_result['success']:
                return otp_result
            
            # Hash new password
            hashed_password = self.hash_password(new_password)
            
            # Update password
            result = self.users_collection.update_one(
                {'email': email},
                {
                    '$set': {
                        'password': hashed_password,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            return {
                'success': True,
                'message': 'Password reset successfully'
            }
            
        except Exception as e:
            logger.error(f"Password reset failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def change_password(self, user_id: str, current_password: str, new_password: str) -> Dict:
        """Change user password"""
        try:
            # Find user
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Verify current password
            if not self.verify_password(current_password, user['password']):
                return {
                    'success': False,
                    'error': 'Current password is incorrect'
                }
            
            # Hash new password
            hashed_password = self.hash_password(new_password)
            
            # Update password
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'password': hashed_password,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return {
                'success': True,
                'message': 'Password changed successfully'
            }
            
        except Exception as e:
            logger.error(f"Change password failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_user_profile(self, user_id: str) -> Dict:
        """Get user profile"""
        try:
            user = self.users_collection.find_one(
                {'_id': ObjectId(user_id)},
                {'password': 0}  # Exclude password
            )
            
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Convert ObjectId to string
            user['_id'] = str(user['_id'])
            
            return {
                'success': True,
                'user': user
            }
            
        except Exception as e:
            logger.error(f"Get user profile failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def update_profile(self, user_id: str, profile_data: Dict) -> Dict:
        """Update user profile"""
        try:
            # Prepare update data
            update_data = {
                'updated_at': datetime.utcnow()
            }
            
            # Update allowed fields
            allowed_fields = ['first_name', 'last_name']
            for field in allowed_fields:
                if field in profile_data:
                    update_data[field] = profile_data[field]
            
            # Update profile fields
            profile_fields = ['bio', 'phone', 'location', 'avatar_url']
            profile_updates = {}
            for field in profile_fields:
                if field in profile_data:
                    profile_updates[f'profile.{field}'] = profile_data[field]
            
            # Update full name if first or last name changed
            if 'first_name' in profile_data or 'last_name' in profile_data:
                user = self.users_collection.find_one({'_id': ObjectId(user_id)})
                first_name = profile_data.get('first_name', user['first_name'])
                last_name = profile_data.get('last_name', user['last_name'])
                profile_updates['profile.full_name'] = f"{first_name} {last_name}"
            
            update_data.update(profile_updates)
            
            # Update user
            result = self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            if result.modified_count == 0:
                return {
                    'success': False,
                    'error': 'No changes made or user not found'
                }
            
            return {
                'success': True,
                'message': 'Profile updated successfully'
            }
            
        except Exception as e:
            logger.error(f"Update profile failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_account(self, user_id: str, password: str) -> Dict:
        """Delete user account"""
        try:
            # Find user
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Verify password
            if not self.verify_password(password, user['password']):
                return {
                    'success': False,
                    'error': 'Incorrect password'
                }
            
            # Delete user data from related collections
            # Delete resumes
            self.db.resumes.delete_many({'user_id': user_id})
            
            # Delete cover letters
            self.db.cover_letters.delete_many({'user_id': user_id})
            
            # Delete emails
            self.db.emails.delete_many({'user_id': user_id})
            
            # Delete ATS resumes
            self.db.ats_resumes.delete_many({'user_id': user_id})
            
            # Delete OTPs
            self.otps_collection.delete_many({'email': user['email']})
            
            # Delete user
            self.users_collection.delete_one({'_id': ObjectId(user_id)})
            
            return {
                'success': True,
                'message': 'Account deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Delete account failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def soft_delete_account(self, user_id: str, password: str) -> Dict:
        """Soft delete user account (mark as deleted instead of removing)"""
        try:
            # Find user
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Check if already deleted
            if user.get('deleted', False):
                return {
                    'success': False,
                    'error': 'Account is already deleted'
                }
            
            # Verify password
            if not self.verify_password(password, user['password']):
                return {
                    'success': False,
                    'error': 'Incorrect password'
                }
            
            # Mark user as deleted
            result = self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'deleted': True,
                        'deleted_at': datetime.utcnow(),
                        'is_active': False,
                        'updated_at': datetime.utcnow()
                    },
                    '$unset': {
                        'refresh_token': ''  # Revoke refresh token
                    }
                }
            )
            
            if result.modified_count == 0:
                return {
                    'success': False,
                    'error': 'Failed to delete account'
                }
            
            logger.info(f"Account soft deleted for user: {user['email']} (ID: {user_id})")
            
            return {
                'success': True,
                'message': 'Account deleted successfully. Your data has been deactivated and will be removed after 30 days.'
            }
            
        except Exception as e:
            logger.error(f"Soft delete account failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def resend_verification_otp(self, email: str) -> Dict:
        """Resend email verification OTP"""
        try:
            # Check if user exists
            user = self.users_collection.find_one({'email': email})
            if not user:
                return {
                    'success': False,
                    'error': 'No account found with this email'
                }
            
            # Check if already verified
            if user.get('email_verified', False):
                return {
                    'success': False,
                    'error': 'Email is already verified'
                }
            
            # Send OTP
            otp_result = self.send_otp(email, "signup")
            
            return {
                'success': True,
                'message': 'Verification code sent to your email',
                'otp_sent': otp_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"Resend verification OTP failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
