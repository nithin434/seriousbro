from flask import Flask, request, jsonify, Blueprint, render_template, redirect, send_file
import os
import logging
import json
import io
from functools import wraps
from werkzeug.utils import secure_filename
from cover_letter_generator import CoverLetterGenerator
from cold_email_generator import ColdEmailGenerator
#from resume_generator import ResumeGenerator
from resume_parser import ResumeParser
from job_analyzer import JobAnalyzer
from resume_suggester import ResumeSuggester
from bson import ObjectId
from typing import List, Dict
from interview_preparation import InterviewPreparation
from flask_cors import CORS
# from collecter_data import ProfileDataCollector
from extractor import ProfileAnalyzer
from user_management import UserManager
import asyncio
import time
from datetime import datetime
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}

def is_api_request():
    """Check if request is asking for JSON response"""
    return (
        request.headers.get('Content-Type') == 'application/json' or
        request.headers.get('Accept') == 'application/json' or
        request.path.startswith('/api/') or
        request.args.get('format') == 'json'
    )

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def auth_required(f):
    """Decorator to require authentication for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401
        
        try:
            # Verify token using user manager
            user_manager = UserManager()
            payload = user_manager.verify_jwt_token(token)
            if payload is None:
                return jsonify({'success': False, 'error': 'Token is invalid or expired'}), 401
            
            # Add user info to request context
            request.user_id = payload['user_id']
            request.user_email = payload['email']
            
        except Exception as e:
            return jsonify({'success': False, 'error': 'Token verification failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    # Configure CORS with specific origins
    CORS(app, origins=[
        "https://syntexa.app",
        "https://syntexa.vercel.app",
        "http://35.200.140.65:5000",
        "http://localhost:3000",
        "http://localhost:5000",
        "*"  # Allow all for development
    ], 
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    # Add custom Jinja2 filter for pretty JSON
    @app.template_filter('tojsonpretty')
    def tojsonpretty_filter(obj):
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(obj)
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Initialize components without ChromaDB
    app.config['resume_parser'] = ResumeParser()
    # app.config['resume_gen'] = ResumeGenerator()
    app.config['cover_letter_gen'] = CoverLetterGenerator()
    app.config['email_gen'] = ColdEmailGenerator()
    app.config['job_analyzer'] = JobAnalyzer()
    app.config['interview_prep'] = InterviewPreparation()
    app.config['resume_suggester'] = ResumeSuggester()
    
    # Initialize Profile Analyzer with Gemini AI
    app.config['profile_analyzer'] = ProfileAnalyzer()
    
    # Initialize User Management
    app.config['user_manager'] = UserManager()
    
    # Check if Gemini API key is available
    if not os.getenv('GEMINI_API_KEY'):
        logger.warning("GEMINI_API_KEY not found. Profile analysis will use basic fallback methods.")
    
    return app

app = create_app()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for deployment"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'message': 'Resume AI API is running'
    })

# ===============================
# AUTHENTICATION ENDPOINTS
# ===============================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        # Basic email validation
        email = data['email'].strip().lower()
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Password validation
        password = data['password']
        if len(password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Register user
        result = app.config['user_manager'].signup(
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            email=email,
            password=password
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

@app.route('/api/auth/verify-email', methods=['POST'])
def verify_email():
    """Email verification endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('otp'):
            return jsonify({
                'success': False,
                'error': 'Email and OTP are required'
            }), 400
        
        # Verify email
        result = app.config['user_manager'].verify_email(
            email=data['email'].strip().lower(),
            otp=data['otp'].strip()
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Email verification failed. Please try again.'
        }), 500

@app.route('/api/auth/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification OTP endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('email'):
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
        
        # Resend verification OTP
        result = app.config['user_manager'].resend_verification_otp(
            email=data['email'].strip().lower()
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to resend verification code. Please try again.'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        # Login user
        result = app.config['user_manager'].login(
            email=data['email'].strip().lower(),
            password=data['password']
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 401 if 'Invalid email or password' in result.get('error', '') else 400
            return jsonify(result), status_code
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Login failed. Please try again.'
        }), 500

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Forgot password endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('email'):
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
        
        # Send password reset OTP
        result = app.config['user_manager'].forgot_password(
            email=data['email'].strip().lower()
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to send password reset code. Please try again.'
        }), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'otp', 'new_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        # Password validation
        if len(data['new_password']) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Reset password
        result = app.config['user_manager'].reset_password(
            email=data['email'].strip().lower(),
            otp=data['otp'].strip(),
            new_password=data['new_password']
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Password reset failed. Please try again.'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@auth_required
def change_password():
    """Change password endpoint (requires authentication)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['current_password', 'new_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        # Password validation
        if len(data['new_password']) < 8:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 8 characters long'
            }), 400
        
        # Change password
        result = app.config['user_manager'].change_password(
            user_id=request.user_id,
            current_password=data['current_password'],
            new_password=data['new_password']
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Password change failed. Please try again.'
        }), 500

@app.route('/api/auth/profile', methods=['GET'])
@auth_required
def get_profile():
    """Get user profile endpoint"""
    try:
        result = app.config['user_manager'].get_user_profile(request.user_id)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get profile. Please try again.'
        }), 500

@app.route('/api/auth/profile', methods=['PUT'])
@auth_required
def update_profile():
    """Update user profile endpoint"""
    try:
        data = request.get_json()
        
        # Update profile
        result = app.config['user_manager'].update_profile(
            user_id=request.user_id,
            profile_data=data
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Profile update failed. Please try again.'
        }), 500

@app.route('/api/auth/delete-account', methods=['DELETE'])
@auth_required
def delete_account():
    """Delete user account endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Password is required to delete account'
            }), 400
        
        # Delete account
        result = app.config['user_manager'].delete_account(
            user_id=request.user_id,
            password=data['password']
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Delete account error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Account deletion failed. Please try again.'
        }), 500

# ===============================
# END AUTHENTICATION ENDPOINTS
# ===============================

@app.route('/')
def index():
    try:
        if 'resume_parser' not in app.config:
            error_msg = "Application not properly initialized"
            logging.error("Resume parser not initialized")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
        resumes = app.config['resume_parser'].get_recent_resumes_sync(limit=3)
        
        # Serialize ObjectIds to strings
        serialized_resumes = serialize_resume_data(resumes)
        
        return jsonify({
            'success': True,
            'resumes': serialized_resumes,
            'count': len(serialized_resumes)
        })
        
    except Exception as e:
        error_msg = f"Unable to load resumes: {str(e)}"
        logging.error(f"Index error: {str(e)}")
        
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/resumes/recent')
def get_recent_resumes():
    """Get recent resumes - dedicated API endpoint"""
    try:
        limit = request.args.get('limit', 3, type=int)
        resumes = app.config['resume_parser'].get_recent_resumes_sync(limit=limit)
        
        # Serialize ObjectIds to strings
        serialized_resumes = serialize_resume_data(resumes)
        
        return jsonify({
            'success': True,
            'resumes': serialized_resumes,
            'count': len(serialized_resumes)
        })
        
    except Exception as e:
        logging.error(f"Recent resumes error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/my-resumes')
def my_resumes():
    """Show all resumes with proper error handling"""
    try:
        if 'resume_parser' not in app.config:
            logging.error("Resume parser not initialized")
            return render_template('error.html', 
                                error="Application not properly initialized"), 500
            
        # Add more detailed logging
        logging.info("Fetching all resumes...")
        resumes = app.config['resume_parser'].get_all_resumes_sync()
        
        # Debug the resumes data
        logging.info(f"Found {len(resumes)} resumes")
        for i, resume in enumerate(resumes):
            logging.info(f"Resume {i}: ID={resume.get('_id')}, filename={resume.get('original_filename')}")
        
        if not resumes:
            logging.warning("No resumes found in database")
            return render_template('my_resumes.html', 
                                resumes=[], 
                                message="No resumes found")
        
        # Ensure each resume has required fields for template
        for resume in resumes:
            # Add default values if missing
            if 'parsed_data' not in resume:
                resume['parsed_data'] = {}
            if 'personal_info' not in resume.get('parsed_data', {}):
                resume['parsed_data']['personal_info'] = {}
            if 'name' not in resume['parsed_data']['personal_info']:
                resume['parsed_data']['personal_info']['name'] = resume.get('original_filename', 'Unknown')
            
            # Handle skills structure - ensure it's properly formatted
            if 'skills' not in resume['parsed_data']:
                resume['parsed_data']['skills'] = {}
            
            # Convert old list format to new dict format if needed
            skills = resume['parsed_data']['skills']
            if isinstance(skills, list):
                resume['parsed_data']['skills'] = {
                    'technical_skills': skills[:5] if skills else [],
                    'programming_languages': [],
                    'frameworks': [],
                    'tools': [],
                    'soft_skills': []
                }
            elif not isinstance(skills, dict):
                resume['parsed_data']['skills'] = {
                    'technical_skills': [],
                    'programming_languages': [],
                    'frameworks': [],
                    'tools': [],
                    'soft_skills': []
                }
            
            # Ensure upload_date exists
            if 'upload_date' not in resume:
                resume['upload_date'] = 'Unknown'
            
            # Add any other missing fields your template expects
            resume.setdefault('file_size', 0)
            resume.setdefault('processing_status', 'completed')
            
        return render_template('my_resumes.html', resumes=resumes)
        
    except Exception as e:
        logging.error(f"My resumes error: {str(e)}")
        logging.error(f"Error type: {type(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return render_template('error.html', 
                             error="Unable to fetch resumes"), 500

@app.route('/dashboard/<resume_id>')
def dashboard(resume_id):
    """Dashboard for a specific resume"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.warning(f"No resume found with ID: {resume_id}")
            return render_template('404.html'), 404

        # Serialize the resume data to handle ObjectId conversion
        serialized_resume_data = serialize_resume_data(resume_data)

        # Get interview statistics
        try:
            interview_stats = app.config['interview_prep'].get_interview_statistics(resume_id)
        except Exception as e:
            logger.warning(f"Could not get interview stats: {str(e)}")
            interview_stats = {
                'total_interviews': 0,
                'success_rate': 0,
                'average_score': 0,
                'recent_sessions': []
            }

        # Get resume analytics from backend
        try:
            analytics_result = app.config['job_analyzer'].get_resume_analytics(resume_id)
            if analytics_result['success']:
                analytics = analytics_result['analytics']
                logger.info(f"Analytics loaded for resume {resume_id} (cached: {analytics_result.get('cached', False)})")
            else:
                logger.warning(f"Analytics calculation failed: {analytics_result.get('error')}")
                analytics = analytics_result.get('analytics', {})
        except Exception as e:
            logger.error(f"Error loading analytics: {str(e)}")
            analytics = app.config['job_analyzer']._get_default_analytics()
            
        return render_template('dash.html',
                             resume_data=serialized_resume_data,
                             interview_stats=interview_stats,
                             analytics=analytics,
                             resume_id=resume_id)
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/help')
def help_page():
    """Help page with FAQs and contact info"""
    try:
        # Initialize default resume data for sidebar
        resume_data = {
            'parsed_data': {
                'personal_info': {
                    'name': 'User',
                    'email': 'user@syntexa.ai',
                    'phone': '-',
                    'location': '-'
                }
            }
        }
        
        # Try to get the most recent resume data for sidebar
        try:
            if 'resume_parser' in app.config:
                recent_resumes = app.config['resume_parser'].get_recent_resumes_sync(limit=1)
                if recent_resumes:
                    latest_resume = recent_resumes[0]
                    if latest_resume.get('parsed_data', {}).get('personal_info'):
                        resume_data = latest_resume
                        logger.info("Using latest resume data for help page")
        except Exception as e:
            logger.warning(f"Could not load recent resume data: {str(e)}")
        
        # Load FAQs from JSON file
        faqs = []
        try:
            with open('static/faqs.json', 'r') as f:
                faqs = json.load(f)
        except FileNotFoundError:
            logger.warning("FAQs file not found, using default FAQs")
            faqs = [
                {
                    "question": "How do I upload a resume?",
                    "answer": "Click on the 'Upload Resume' button and select your PDF, DOC, or DOCX file."
                },
                {
                    "question": "What file formats are supported?",
                    "answer": "We support PDF, DOC, and DOCX file formats up to 16MB in size."
                },
                {
                    "question": "Is my data secure?",
                    "answer": "Yes, all data is encrypted and secure. We never sell your personal information."
                },
                {
                    "question": "How does ATS optimization work?",
                    "answer": "Our AI analyzes your resume against job requirements and suggests improvements to increase your chances of passing through Applicant Tracking Systems."
                },
                {
                    "question": "Can I delete my account?",
                    "answer": "Yes, you can request account deletion at any time. All your data will be permanently removed from our servers."
                }
            ]
        
        return render_template('help.html', faqs=faqs, resume_data=resume_data)
    except Exception as e:
        logger.error(f"Help page error: {str(e)}")
        # Return with minimal data instead of error template
        return render_template('help.html', 
                             faqs=[],
                             resume_data={'parsed_data': {'personal_info': {'name': 'User', 'email': 'user@syntexa.ai'}}})

@app.route('/settings')
def settings():
    """User settings page"""
    try:
        # Initialize default resume data
        resume_data = {
            'parsed_data': {
                'personal_info': {
                    'name': 'User',
                    'email': 'user@syntexa.ai',
                    'phone': '-',
                    'location': '-'
                }
            }
        }
        
        # Try to get user profile data if user management is available
        try:
            if 'user_manager' in app.config and hasattr(request, 'user_id'):
                user_profile = app.config['user_manager'].get_user_profile(request.user_id)
                if user_profile['success']:
                    # Use profile data if available
                    profile_data = user_profile['profile']
                    resume_data['parsed_data']['personal_info'].update({
                        'name': profile_data.get('name', 'User'),
                        'email': profile_data.get('email', 'user@syntexa.ai'),
                        'phone': profile_data.get('phone', '-'),
                        'location': profile_data.get('location', '-')
                    })
        except AttributeError:
            # No user_id in request (no authentication), use default data
            logger.info("No user authentication, using default profile data")
        except Exception as e:
            logger.warning(f"Could not load user profile: {str(e)}")
        
        # Try to get the most recent resume data as fallback
        try:
            if 'resume_parser' in app.config:
                recent_resumes = app.config['resume_parser'].get_recent_resumes_sync(limit=1)
                if recent_resumes:
                    latest_resume = recent_resumes[0]
                    if latest_resume.get('parsed_data', {}).get('personal_info'):
                        resume_data = latest_resume
                        logger.info("Using latest resume data for settings page")
        except Exception as e:
            logger.warning(f"Could not load recent resume data: {str(e)}")
        
        return render_template('settings.html', resume_data=resume_data)
    except Exception as e:
        logger.error(f"Settings error: {str(e)}")
        # Return with minimal data instead of error template
        return render_template('settings.html', 
                             resume_data={'parsed_data': {'personal_info': {'name': 'User', 'email': 'user@syntexa.ai'}}})
# @app.route('/dashboard_json/<resume_id>')
# def dashboard_json(resume_id):
#     """Dashboard for a specific resume - Returns JSON data"""
#     try:
#         # Get resume data
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.warning(f"No resume found with ID: {resume_id}")
#             return jsonify({
#                 'success': False,
#                 'error': 'Resume not found'
#             }), 404

#         # Get interview statistics
#         try:
#             interview_stats = app.config['interview_prep'].get_interview_statistics(resume_id)
#         except Exception as e:
#             logger.warning(f"Could not get interview stats: {str(e)}")
#             interview_stats = {
#                 'total_interviews': 0,
#                 'success_rate': 0,
#                 'average_score': 0,
#                 'recent_sessions': []
#             }

#         # Calculate additional analytics
#         analytics = {
#             'profile_completeness': _calculate_profile_completeness(resume_data),
#             'keyword_optimization': _analyze_keywords(resume_data),
#             'ats_score': 0  # Default value
#         }

#         # Try to get ATS score
#         try:
#             if hasattr(app.config['resume_gen'], 'calculate_ats_scores_sync'):
#                 ats_result = app.config['resume_gen'].calculate_ats_scores_sync(resume_data)
#                 analytics['ats_score'] = ats_result.get('overall', 0)
#         except Exception as e:
#             logger.warning(f"Could not calculate ATS score: {str(e)}")

#         # Get resume summary stats
#         parsed_data = resume_data.get('parsed_data', {})
#         summary_stats = {
#             'total_experience_years': len(parsed_data.get('experience', [])),
#             'total_skills': len(parsed_data.get('skills', [])),
#             'education_count': len(parsed_data.get('education', [])),
#             'projects_count': len(parsed_data.get('projects', [])),
#             'certifications_count': len(parsed_data.get('certifications', []))
#         }

#         # Serialize the resume data
#         serialized_resume = serialize_resume_data(resume_data)

#         # Return comprehensive dashboard data
#         dashboard_data = {
#             'success': True,
#             'resume_data': serialized_resume,
#             'interview_stats': interview_stats,
#             'analytics': analytics,
#             'summary_stats': summary_stats,
#             'personal_info': parsed_data.get('personal_info', {}),
#             'recent_activity': {
#                 'last_updated': resume_data.get('upload_date', 'Unknown'),
#                 'file_size': resume_data.get('file_size', 0),
#                 'processing_status': resume_data.get('processing_status', 'completed')
#             }
#         }

#         return jsonify(dashboard_data)

#     except Exception as e:
#         logger.error(f"Dashboard error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'message': 'Failed to load dashboard data'
#         }), 500
# @app.route('/api/resume/download/<resume_id>')
# def download_resume(resume_id):
#     """Download original PDF file from GridFS."""
#     try:
#         # Get resume data
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             return jsonify({'success': False, 'error': 'Resume not found'}), 404
        
#         # Check if file_id exists
#         if 'file_id' not in resume_data:
#             return jsonify({'success': False, 'error': 'Original file not found'}), 404
        
#         # Get original file from GridFS
#         file_data = app.config['resume_parser'].get_resume_file(resume_data['file_id'])
#         if not file_data:
#             return jsonify({'success': False, 'error': 'File data not found'}), 404
        
#         # Get file metadata
#         file_metadata = app.config['resume_parser'].get_file_metadata(resume_data['file_id'])
#         filename = file_metadata.get('filename', f"resume_{resume_id}.pdf") if file_metadata else f"resume_{resume_id}.pdf"
        
#         return send_file(
#             io.BytesIO(file_data),
#             mimetype='application/pdf',
#             as_attachment=True,
#             download_name=filename
#         )
        
#     except Exception as e:
#         logger.error(f"Resume download error: {str(e)}")
#         return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/cover-letter/<resume_id>', methods=['GET', 'POST'])
def generate_cover_letter(resume_id):
    """Generate cover letter using existing resume data"""
    try:
        logger.info(f"Found resume with ID: {resume_id}")
        
        # Get existing resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        if request.method == 'POST':
            try:
                data = request.json
                logger.info(f"Cover letter request data: {data}")
                
                # Log the structure of resume data for debugging
                parsed_data = resume_data.get('parsed_data', {})
                logger.info(f"Skills structure: {type(parsed_data.get('skills', []))}")
                logger.info(f"Experience structure: {type(parsed_data.get('experience', []))}")
                
                # Use synchronous method
                result = app.config['cover_letter_gen'].customize_cover_letter(
                    resume_data=resume_data,
                    company_name=data.get('company_name'),
                    position=data.get('job_title'),
                    job_description=data.get('job_description'),
                    additional_context=data.get('additional_context', '')
                )
                
                logger.info(f"Cover letter generation result: {result.get('success', False)}")
                return jsonify(result)
                
            except Exception as post_error:
                logger.error(f"POST request error: {str(post_error)}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'Cover letter generation failed: {str(post_error)}'
                }), 500

        # GET request - render form
        return render_template('cover_letter.html', 
                             resume_data=resume_data,
                             resume_id=resume_id)
                             
    except Exception as e:
        logger.error(f"Cover letter generation error: {str(e)}", exc_info=True)
        if request.method == 'POST':
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        return render_template('error.html', error=str(e))
@app.route('/api/resume/analyze-job', methods=['POST'])
def analyze_job():
    """Analyze job description and compare with resume if provided"""
    try:
        data = request.json
        if not data or not data.get('job_description'):
            return jsonify({
                'success': False,
                'error': 'Job description is required'
            }), 400

        # Get resume data if resume_id provided
        resume_data = None
        if data.get('resume_id'):
            resume_data = app.config['resume_parser'].get_resume_by_id_sync(data['resume_id'])
            if not resume_data:
                return jsonify({
                    'success': False,
                    'error': 'Resume not found'
                }), 404

        # Get job analysis
        analysis_result = app.config['job_analyzer'].analyze_job_sync(
            job_description=data['job_description'],
            resume_data=resume_data
        )

        if not analysis_result.get('success'):
            return jsonify({
                'success': False,
                'error': analysis_result.get('error', 'Analysis failed')
            }), 500

        # Get salary data
        salary_data = app.config['job_analyzer']._scrape_salary_data(
            analysis_result['analysis']['position']['title']
        )

        # Structure response
        response = {
            'success': True,
            'analysis': {
                'details': analysis_result['analysis'],
                'salary_data': salary_data,
                'match_analysis': analysis_result['analysis'].get('match_analysis', {})
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Job analysis error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@app.route('/api/resume/regenerate', methods=['POST'])
def regenerate_resume():
    try:
        data = request.json
        if not data.get('resume_id') or not data.get('feedback'):
            return jsonify({
                'success': False,
                'error': 'Resume ID and feedback are required'
            }), 400
            
        result = app.config['resume_gen'].regenerate_resume_sync(
            resume_id=data['resume_id'],
            feedback=data['feedback']
        )
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Resume regeneration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@app.route('/analyze-job/<resume_id>', methods=['GET', 'POST'])
def analyze_job_page(resume_id):
    """Job analysis page with comprehensive insights"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if request.method == 'POST':
            data = request.json
            
            # Extract job info from URL if provided
            job_url = data.get('job_url')
            if job_url:
                job_info = app.config['job_analyzer'].extract_job_from_url_sync(job_url)
                if job_info.get('success'):
                    data['job_description'] = job_info['description']
                    data['company_name'] = job_info['company']
                    data['job_title'] = job_info['title']
                    data['industry'] = job_info['industry']

            # Analyze job description
            analysis_result = app.config['job_analyzer'].analyze_job_sync(
                job_description=data.get('job_description', ''),
                resume_data=resume_data
            )

            # Research company
            company_insights = app.config['job_analyzer'].research_company_sync(
                company_name=data.get('company_name', ''),
                job_title=data.get('job_title', '')
            )

            # Get similar jobs from same company
            company_jobs = app.config['job_analyzer'].get_company_jobs_sync(
                company_name=data.get('company_name', ''),
                job_title=data.get('job_title', '')
            )

            # Get industry insights
            industry_data = app.config['job_analyzer'].get_industry_insights_sync(
                job_title=data.get('job_title', ''),
                industry=data.get('industry', '')
            )

            return jsonify({
                'success': True,
                'analysis': analysis_result,
                'company_insights': company_insights,
                'company_jobs': company_jobs,
                'industry_insights': industry_data
            })

        # GET request - render analysis form
        return render_template('analyze_job.html', 
                             resume_id=resume_id,
                             resume_data=resume_data)

    except Exception as e:
        logger.error(f"Job analysis error: {str(e)}")
        return render_template('error.html', error=str(e))
# @app.route('/job-recommendations/<resume_id>')
# def job_recommendations(resume_id):
#     """Show job recommendations based on resume"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")
            
#         # Get recommendations
#         result = app.config['job_analyzer'].get_job_recommendations_sync(resume_data)
        
#         if not result.get('success'):
#             logger.error(f"Failed to get recommendations: {result.get('error')}")
#             return render_template('error.html', 
#                                 error="Failed to generate recommendations")

#         return render_template('job_recommendations.html',
#                              resume_data=resume_data,
#                              recommendations=result.get('recommendations', {}),
#                              resume_id=resume_id)
                             
#     except Exception as e:
#         logger.error(f"Job recommendations error: {str(e)}")
#         return render_template('error.html', error=str(e))

@app.route('/api/resume/upload', methods=['POST'])
def upload_resume():
    """Handle resume upload with enhanced parsing and file storage."""
    try:
        logger.info(f"Resume upload started")
        
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']
        if not file or not allowed_file(file.filename):
            logger.error(f"Invalid file type: {file.filename if file else 'No filename'}")
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Allowed: PDF, DOC, DOCX'
            }), 400

        # Validate file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        logger.info(f"File size: {file_size} bytes")
        
        if file_size > app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            logger.error(f"File too large: {file_size}")
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size: 16MB'
            }), 400

        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"Saving file to: {temp_path}")
        file.save(temp_path)

        try:
            # Parse resume (this will store file in GridFS and parse content)
            logger.info(f"Starting resume parsing for: {filename}")
            result = app.config['resume_parser'].parse_resume(temp_path)
            logger.info(f"Parse result: {result.get('success', 'Unknown')} - {result.get('error', 'No error info')}")
            
            if result.get('success'):
                resume_id = result['resume_id']
                logger.info(f"Resume parsing successful, ID: {resume_id}")
                
                # Serialize the parsed data to handle ObjectIds
                serialized_result = {
                    'success': True,
                    'resume_id': resume_id,
                    'file_id': str(result['file_id']) if result.get('file_id') else None,
                    'parsed_data': serialize_resume_data(result.get('parsed_data', {})),
                    'metadata': serialize_resume_data(result.get('metadata', {})),
                    'message': 'Resume uploaded and processed successfully',
                    'redirect_url': f'/dashboard/{resume_id}'
                }
                
                return jsonify(serialized_result), 200
            else:
                logger.error(f"Resume parsing failed: {result.get('error', 'Unknown error')}")
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Resume parsing failed')
                }), 400
                
        except Exception as parse_error:
            logger.error(f"Exception during parsing: {str(parse_error)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Parsing failed: {str(parse_error)}'
            }), 500
                
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500

@app.route('/api/resume/complete-analysis', methods=['POST'])
async def complete_resume_analysis():
    try:
        data = request.json
        resume_id = data.get('resume_id')
        job_description = data.get('job_description')

        if not all([resume_id, job_description]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400

        # Get comprehensive analysis
        analysis_result = await app.config['resume_gen'].get_complete_analysis(
            resume_id,
            job_description
        )

        return jsonify({
            'success': True,
            'analysis': analysis_result
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resume/improvement-plan', methods=['POST'])
async def get_improvement_plan():
    try:
        data = request.json
        resume_id = data.get('resume_id')
        target_job = data.get('target_job')

        improvement_plan = await app.config['resume_gen'].generate_improvement_plan(
            resume_id,
            target_job
        )

        return jsonify({
            'success': True,
            'improvement_plan': improvement_plan
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/resume/generate-optimized', methods=['POST'])
def generate_optimized_resume():
    """Generate optimized resume using existing data and job description"""
    try:
        data = request.json
        resume_id = data.get('resume_id')
        job_description = data.get('job_description')
        
        if not resume_id or not job_description:
            return jsonify({
                'success': False,
                'error': 'Resume ID and job description are required'
            }), 400

        # Get existing resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return jsonify({
                'success': False,
                'error': 'Resume not found'
            }), 404

        # Generate optimized resume
        result = app.config['resume_gen'].generate_optimized_resume(
            resume_data,
            job_description,
            optimization_options=data.get('optimization_options', {})
        )

        return jsonify({
            'success': True,
            'optimized_resume': result['resume'],
            'improvements': result['improvements'],
            'ats_score': result['ats_score']
        })

    except Exception as e:
        logger.error(f"Resume generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _calculate_profile_completeness(resume_data):
    """Calculate profile completeness score"""
    sections = {
        'personal_info': ['name', 'email', 'phone', 'location'],
        'skills': [],
        'experience': ['title', 'company', 'duration', 'responsibilities'],
        'education': ['degree', 'institution', 'year']
    }
    
    scores = {}
    for section, fields in sections.items():
        if section in resume_data['parsed_data']:
            section_data = resume_data['parsed_data'][section]
            if fields:
                filled_fields = sum(1 for field in fields 
                                  if field in section_data and section_data[field])
                scores[section] = (filled_fields / len(fields)) * 100
            else:
                scores[section] = 100 if section_data else 0

    return {
        'scores': scores,
        'overall': sum(scores.values()) / len(scores)
    }

def _analyze_keywords(resume_data):
    """Analyze keyword usage and optimization"""
    common_keywords = {
        'technical': ['python', 'java', 'sql', 'aws', 'cloud'],
        'soft_skills': ['leadership', 'communication', 'teamwork'],
        'metrics': ['improved', 'increased', 'reduced', 'managed']
    }
    
    text = json.dumps(resume_data['parsed_data']).lower()
    analysis = {}
    
    for category, keywords in common_keywords.items():
        found = [word for word in keywords if word in text]
        analysis[category] = {
            'found': found,
            'missing': list(set(keywords) - set(found))
        }
    
    return analysis
@app.route('/email/<resume_id>', methods=['GET', 'POST'])
def generate_email(resume_id):
    """Generate cold email using existing resume data"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            if request.method == 'POST':
                return jsonify({
                    'success': False,
                    'error': 'Resume not found'
                }), 404
            return render_template('error.html', error="Resume not found")

        # Ensure parsed_data structure exists
        if 'parsed_data' not in resume_data:
            resume_data['parsed_data'] = {}
        
        # Ensure required sections exist with defaults
        parsed_data = resume_data['parsed_data']
        if 'personal_info' not in parsed_data:
            parsed_data['personal_info'] = {}
        if 'skills' not in parsed_data:
            parsed_data['skills'] = []
        if 'experience' not in parsed_data:
            parsed_data['experience'] = []

        if request.method == 'POST':
            try:
                data = request.json
                if not data:
                    return jsonify({
                        'success': False,
                        'error': 'No data provided'
                    }), 400

                # Validate required fields
                required_fields = ['recipient_name', 'company_name', 'role']
                for field in required_fields:
                    if not data.get(field):
                        return jsonify({
                            'success': False,
                            'error': f'{field.replace("_", " ").title()} is required'
                        }), 400

                result = app.config['email_gen'].generate_email_sync({
                    'resume_data': resume_data,
                    'recipient_name': data.get('recipient_name'),
                    'company_name': data.get('company_name'),
                    'role': data.get('role'),
                    'additional_context': data.get('additional_context', ''),
                    'email_style': data.get('email_style', 'professional')
                })
                
                if not result.get('success'):
                    return jsonify({
                        'success': False,
                        'error': result.get('error', 'Failed to generate email')
                    }), 500
                    
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Email generation error in POST: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Email generation failed: {str(e)}'
                }), 500

        # GET request - render form with serialized data
        serialized_resume_data = serialize_resume_data(resume_data)
        return render_template('email.html', 
                            resume_data=serialized_resume_data,
                            resume_id=resume_id)
                            
    except Exception as e:
        logger.error(f"Email generation error: {str(e)}")
        if request.method == 'POST':
            return jsonify({
                'success': False,
                'error': f'System error: {str(e)}'
            }), 500
        return render_template('error.html', error=str(e))
@app.route('/view-resume/<resume_id>')
def view_resume(resume_id):
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found"), 404
        
        # Ensure parsed_data exists and has proper structure
        if 'parsed_data' not in resume_data:
            resume_data['parsed_data'] = {}
        
        # Validate and fix data structure for template
        parsed_data = resume_data['parsed_data']
        
        # Ensure all required sections exist
        default_sections = {
            'personal_info': {},
            'professional_summary': '',
            'objective': '',
            'skills': {},
            'experience': [],
            'education': [],
            'projects': [],
            'certifications': [],
            'awards': [],
            'languages': []
        }
        
        for section, default_value in default_sections.items():
            if section not in parsed_data:
                parsed_data[section] = default_value
        
        # Serialize the resume data to handle ObjectId conversion
        serialized_resume_data = serialize_resume_data(resume_data)
        
        return render_template('view_resume.html', resume_data=serialized_resume_data)
        
    except Exception as e:
        logger.error(f"Resume view error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return render_template('error.html', error=f"Error loading resume: {str(e)}"), 500
@app.route('/improve-resume/<resume_id>', methods=['GET', 'POST'])
def improve_resume(resume_id):
    """Handle resume improvement requests"""
    try:
        # Get resume data synchronously
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        if request.method == 'POST':
            data = request.json
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400

            # Validate required fields
            improvement_type = data.get('improvement_type')
            if not improvement_type:
                return jsonify({
                    'success': False,
                    'error': 'Improvement type is required'
                }), 400

            # Call synchronous improvement method
            result = app.config['resume_gen'].improve_resume_sync(
                resume_data=resume_data,
                improvement_type=improvement_type,
                job_description=data.get('job_description', ''),
                improvement_options={
                    'industry': data.get('industry'),
                    'focus_areas': data.get('focus_areas', []),
                    'experience_level': data.get('experience_level', 'mid_level')
                }
            )

            return jsonify(result)

        return render_template(
            'improve_resume.html',
            resume_data=resume_data,
            resume_id=resume_id
        )

    except Exception as e:
        logger.error(f"Resume improvement error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@app.route('/upload')
def upload_page():
    """Render the upload page"""
    try:
        return render_template('upload.html')
    except Exception as e:
        logger.error(f"Upload page error: {str(e)}")
        return render_template('error.html', error=str(e))

# @app.route('/mock-interview/<resume_id>')
# def mock_interview(resume_id):
#     """Mock interview practice page"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")

#         return render_template('mock_interview.html',
#                              resume_data=resume_data,
#                              resume_id=resume_id)

#     except Exception as e:
#         logger.error(f"Mock interview error: {str(e)}")
#         return render_template('error.html', error=str(e))

# @app.route('/interview-history/<resume_id>')
# def interview_history(resume_id):
#     """Interview history page"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")

#         history = app.config['interview_prep'].get_interview_history(resume_id)
#         return render_template('interview_history.html',
#                              resume_data=resume_data,
#                              history=history,
#                              resume_id=resume_id)

#     except Exception as e:
#         logger.error(f"Interview history error: {str(e)}")
#         return render_template('error.html', error=str(e))

# @app.route('/interview-feedback/<resume_id>', methods=['GET', 'POST'])
# def interview_feedback(resume_id):
#     """Interview feedback page"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")

#         if request.method == 'POST':
#             feedback_data = request.json
#             result = app.config['interview_prep'].save_interview_feedback(
#                 resume_id=resume_id,
#                 feedback_data=feedback_data
#             )
#             return jsonify(result)

#         return render_template('interview_feedback.html',
#                              resume_data=resume_data,
#                              resume_id=resume_id)

#     except Exception as e:
#         logger.error(f"Interview feedback error: {str(e)}")
#         return render_template('error.html', error=str(e))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# Add error handling middleware
@app.before_request
def before_request():
    """Log all requests"""
    logger.info(f"{request.method} {request.path} - {request.remote_addr}")

@app.after_request
def after_request(response):
    """Add CORS headers and log response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    logger.info(f"Response: {response.status_code}")
    return response

# Add OPTIONS handler for CORS preflight
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS preflight requests"""
    return '', 200

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'debug': str(e) if app.debug else None
        }), 500
    else:
        return render_template('error.html', error=str(e)), 500

# @app.route('/interview-prep/<resume_id>', methods=['GET', 'POST'])
# def interview_preparation(resume_id):
#     """Interview preparation page"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")

#         if request.method == 'POST':
#             data = request.json
            
#             # Generate comprehensive interview guide
#             guide = app.config['interview_prep'].prepare_interview_guide(
#                 resume_data=resume_data,
#                 job_description=data.get('job_description', ''),
#                 company_name=data.get('company_name', '')
#             )

#             if not guide.get('success'):
#                 return jsonify({
#                     'success': False,
#                     'error': guide.get('error', 'Failed to generate guide')
#                 }), 500

#             # Add default values for missing sections
#             interview_guide = guide['interview_guide']
#             interview_guide.setdefault('technical_preparation', {})
#             interview_guide.setdefault('behavioral_questions', {})
#             interview_guide.setdefault('company_questions', {})
#             interview_guide.setdefault('preparation_tips', {})
            
#             return jsonify({
#                 'success': True,
#                 'interview_guide': interview_guide
#             })

#         # GET request - render form
#         return render_template('interview_prep.html',
#                              resume_data=resume_data,
#                              resume_id=resume_id)

#     except Exception as e:
#         logger.error(f"Interview preparation error: {str(e)}")
#         if request.method == 'POST':
#             return jsonify({
#                 'success': False,
#                 'error': str(e)
#             }), 500
#         return render_template('error.html', error=str(e))
# @app.route('/interview-resources/<resume_id>')
# def interview_resources(resume_id):
#     """Interview learning resources page"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             logger.error(f"Resume not found: {resume_id}")
#             return render_template('error.html', error="Resume not found")

#         # Get learning resources based on resume skills
#         resources = app.config['interview_prep'].get_learning_resources(resume_data)
#         # Ensure we have at least default resources
#         if not resources:
#             resources = app.config['interview_prep']._get_default_resources()
#         return render_template('interview_resources.html',
#                              resume_data=resume_data,
#                              resources=resources,
#                              resume_id=resume_id)
#     except Exception as e:
#         logger.error(f"Interview resources error: {str(e)}")
#         return render_template('error.html', error=str(e))
# @app.route('/generate-study-plan/<resume_id>')
# def generate_study_plan(resume_id):
#     """Generate personalized study plan"""
#     try:
#         resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
#         if not resume_data:
#             return render_template('error.html', error="Resume not found")

#         # Generate study plan based on resume skills and experience
#         study_plan = app.config['interview_prep']._generate_study_plan(resume_data)
        
#         return render_template('study_plan.html',
#                              resume_data=resume_data,
#                              study_plan=study_plan,
#                              resume_id=resume_id)

#     except Exception as e:
#         logger.error(f"Study plan generation error: {str(e)}")
#         return render_template('error.html', error=str(e))
@app.route('/resume-suggestions/<resume_id>')
def resume_suggestions(resume_id):
    """Get comprehensive resume suggestions"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        # Get suggestions
        suggestions = app.config['resume_suggester'].analyze_resume(resume_data)
        
        if not suggestions.get('success'):
            return render_template('error.html', 
                                error=suggestions.get('error', 'Failed to analyze resume'))

        return render_template('resume_suggestions.html',
                             resume_data=resume_data,
                             suggestions=suggestions,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Resume suggestions error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/api/resume/suggestions/<resume_id>')
def get_resume_suggestions(resume_id):
    """Get resume suggestions as JSON"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return jsonify({
                'success': False,
                'error': 'Resume not found'
            }), 404

        # Get suggestions
        suggestions = app.config['resume_suggester'].analyze_resume(resume_data)
        
        if not suggestions.get('success'):
            return jsonify({
                'success': False,
                'error': suggestions.get('error', 'Failed to analyze resume')
            }), 500

        return jsonify(suggestions)

    except Exception as e:
        logger.error(f"Resume suggestions error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def serialize_resume_data(resume_data):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if isinstance(resume_data, list):
        return [serialize_resume_data(item) for item in resume_data]
    
    if isinstance(resume_data, dict):
        serialized = {}
        for key, value in resume_data.items():
            if isinstance(value, ObjectId):
                serialized[key] = str(value)
            elif isinstance(value, dict):
                serialized[key] = serialize_resume_data(value)
            elif isinstance(value, list):
                serialized[key] = serialize_resume_data(value)
            else:
                serialized[key] = value
        return serialized
    
    return resume_data

@app.route('/profile-analysis')
def profile_analysis():
    """Profile analysis page"""
    return render_template('profile_analysis.html')

@app.route('/profile-results')
def profile_results():
    """Profile analysis results page - serves HTML template"""
    return render_template('profile_results.html')

# Add a simple in-memory cache for profile analysis results
profile_analysis_cache = {}

@app.route('/api/analyze-profile', methods=['POST'])
def analyze_profile():
    """Analyze a single profile with enhanced AI-powered insights"""
    try:
        data = request.get_json()
        logger.info(f"Profile analysis request: {data}")
        
        profile_url = data.get('profile_url')
        user_interests = data.get('user_interests', [])
        
        if not profile_url:
            return jsonify({
                'success': False,
                'error': 'Profile URL is required'
            }), 400
        
        # Add validation for URL format
        if not profile_url.startswith(('http://', 'https://')):
            profile_url = 'https://' + profile_url
        
        logger.info(f"Analyzing profile: {profile_url} with interests: {user_interests}")
        
        # Analyze the profile
        result = app.config['profile_analyzer'].analyze_profile(profile_url, user_interests)
        logger.info(f"Analysis result success: {result.get('success')}")
        
        if not result['success']:
            logger.error(f"Analysis failed: {result.get('error')}")
            return jsonify(result), 500
        
        # Structure the response for the frontend
        analysis = result['analysis']
        response_data = {
            'success': True,
            'platform': result['platform'],
            'profile_url': result['profile_url'],
            'professional_score': analysis['professional_score'],
            'section_scores': analysis['section_scores'],
            'analysis': {
                'overall_assessment': analysis['overall_assessment'],
                'strengths': analysis['strengths'],
                'areas_for_improvement': analysis['areas_for_improvement']
            },
            'suggestions': {
                'immediate_actions': analysis['specific_suggestions']['immediate_actions'],
                'medium_term_goals': analysis['specific_suggestions']['medium_term_goals'],
                'industry_specific_tips': analysis['specific_suggestions']['industry_specific_tips']
            },
            'platform_advice': analysis['platform_specific_advice'],
            'privacy_concerns': analysis['privacy_concerns'],
            'visibility_metrics': {
                'visibility_score': analysis['visibility_score'],
                'recruiter_appeal': analysis['recruiter_appeal'],
                'optimization_keywords': analysis['optimization_keywords']
            },
            'user_interests': user_interests,
            'analysis_metadata': {
                'analysis_date': result['analysis_timestamp'],
                'ai_powered': bool(app.config['profile_analyzer'].model),
                'platform_detected': result['platform']
            },
            'scraped_data': result.get('scraped_data', {}),
            'debug_info': {
                'scraper_available': hasattr(app.config['profile_analyzer'], 'scrape_single_profile'),
                'gemini_available': bool(app.config['profile_analyzer'].model),
                'analysis_timestamp': result['analysis_timestamp']
            },
            # Add redirect URL for frontend
            'redirect_url': f'/profile-results?profile_url={profile_url}&platform={result["platform"]}'
        }
        
        # Cache the results for the profile-results page
        cache_key = profile_url
        profile_analysis_cache[cache_key] = {
            'success': True,
            'profile_url': result['profile_url'],
            'platform': result['platform'],
            'results_available': True,
            'last_analysis_date': result['analysis_timestamp'],
            'summary': {
                'professional_score': analysis['professional_score'],
                'visibility_score': analysis['visibility_score'],
                'overall_assessment': analysis['overall_assessment'],
                'strengths': analysis['strengths'],
                'areas_for_improvement': analysis['areas_for_improvement'],
                'immediate_actions': analysis['specific_suggestions']['immediate_actions'],
                'medium_term_goals': analysis['specific_suggestions']['medium_term_goals'],
                'optimization_keywords': analysis['optimization_keywords']
            },
            'detailed_analysis': {
                'section_scores': analysis['section_scores'],
                'platform_advice': analysis['platform_specific_advice'],
                'privacy_concerns': analysis['privacy_concerns'],
                'recruiter_appeal': analysis['recruiter_appeal']
            }
        }
        
        logger.info(f"Analysis cached for URL: {cache_key}")
        logger.info(f"Response data structure: platform={response_data['platform']}, "
                   f"score={response_data['professional_score']}, "
                   f"sections={len(response_data['section_scores'])}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Profile analysis failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'debug_info': {
                'error_type': type(e).__name__,
                'error_location': 'main.py:analyze_profile'
            },
            'fallback_suggestions': [
                'Verify the profile URL is correct and accessible',
                'Check if the profile is public',
                'Try again in a few minutes',
                'Contact support if the issue persists'
            ]
        }), 500

@app.route('/api/profile-results')
def profile_results_api():
    """Profile analysis results API endpoint - returns cached JSON data"""
    try:
        # Get data from query parameters
        profile_url = request.args.get('profile_url', '')
        platform = request.args.get('platform', 'unknown')
        
        if not profile_url:
            return jsonify({
                'success': False,
                'error': 'Profile URL is required'
            }), 400
        
        logger.info(f"API Profile results request for: {profile_url}")
        
        # Check if we have cached results
        cache_key = profile_url
        if cache_key in profile_analysis_cache:
            cached_result = profile_analysis_cache[cache_key]
            logger.info(f"Found cached results for: {profile_url}")
            return jsonify(cached_result)
        
        # If no cached results, perform analysis
        logger.info(f"No cached results found, performing new analysis for: {profile_url}")
        user_interests = []
        
        # Analyze the profile using the profile analyzer
        result = app.config['profile_analyzer'].analyze_profile(profile_url, user_interests)
        
        if not result.get('success'):
            logger.error(f"Analysis failed: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Analysis failed')
            }), 500
        
        # Structure the response for the frontend
        analysis = result['analysis']
        
        response_data = {
            'success': True,
            'profile_url': result['profile_url'],
            'platform': result['platform'],
            'results_available': True,
            'last_analysis_date': result['analysis_timestamp'],
            'summary': {
                'professional_score': analysis['professional_score'],
                'visibility_score': analysis['visibility_score'],
                'overall_assessment': analysis['overall_assessment'],
                'strengths': analysis['strengths'],
                'areas_for_improvement': analysis['areas_for_improvement'],
                'immediate_actions': analysis['specific_suggestions']['immediate_actions'],
                'medium_term_goals': analysis['specific_suggestions']['medium_term_goals'],
                'optimization_keywords': analysis['optimization_keywords']
            },
            'detailed_analysis': {
                'section_scores': analysis['section_scores'],
                'platform_advice': analysis['platform_specific_advice'],
                'privacy_concerns': analysis['privacy_concerns'],
                'recruiter_appeal': analysis['recruiter_appeal']
            }
        }
        
        # Cache the new results
        profile_analysis_cache[cache_key] = response_data
        logger.info(f"New analysis completed and cached for: {profile_url}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Profile results API error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Profile results API error: {str(e)}'
        }), 500

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests"""
    return '', 204

@app.route('/undefined')
def handle_undefined():
    """Handle undefined redirects gracefully"""
    logger.warning("Accessed /undefined route - likely frontend navigation error")
    return redirect('/')

#make it for the blog
# @app.route('/ats-resume-generator')
# def ats_resume_generator():
#     """Render the ATS-friendly resume generator page"""
#     try:
#         return render_template('ats_resume.html')
#     except Exception as e:
#         logger.error(f"ATS Resume generator error: {str(e)}")
#         return render_template('error.html', error=str(e))

@app.route('/generate-ats-resume/<resume_id>')
def generate_ats_resume(resume_id):
    """Generate ATS-friendly resume for a specific resume"""
    try:
        logger.info(f"Starting ATS resume generation for ID: {resume_id}")
        
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        logger.info(f"Resume data found, initializing ATS generator...")
        
        # Serialize resume data to handle ObjectIds before passing to ATS generator
        serialized_resume_data = serialize_resume_data(resume_data)
        
        # Initialize ATS resume generator
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        logger.info(f"Generating ATS resume...")
        
        # Generate or retrieve ATS resume with serialized data
        result = ats_generator.generate_ats_resume(resume_id, serialized_resume_data)
        
        logger.info(f"ATS generation result: success={result.get('success')}, pdf_generated={result.get('pdf_generated')}")
        
        if not result["success"]:
            logger.error(f"ATS Resume generation failed: {result['error']}")
            return render_template('error.html', error=result["error"])

        logger.info(f"Rendering results template...")
        
        # Ensure we have proper status for template
        pdf_generated = result.get("pdf_generated", False)
        pdf_file_id = result.get("pdf_file_id")
        
        # Double-check PDF status if file_id exists but pdf_generated is False
        if pdf_file_id and not pdf_generated:
            try:
                from bson import ObjectId
                if isinstance(pdf_file_id, str):
                    pdf_file_id = ObjectId(pdf_file_id)
                
                if ats_generator.fs.exists(pdf_file_id):
                    pdf_generated = True
                    logger.info(f"PDF confirmed to exist in GridFS: {pdf_file_id}")
            except Exception as e:
                logger.warning(f"Error verifying PDF in GridFS: {e}")
        
        # Add additional context for template with serialized data
        template_context = {
            'resume_data': serialized_resume_data,  # Use serialized data
            'ats_data': result["ats_data"],
            'pdf_path': result.get("pdf_path"),
            'tex_path': result.get("tex_path"),
            'pdf_file_id': str(result.get("pdf_file_id")) if result.get("pdf_file_id") else None,
            'tex_file_id': str(result.get("tex_file_id")) if result.get("tex_file_id") else None,
            'from_database': result.get("from_database", False),
            'pdf_generated': pdf_generated,  # Use the verified status
            'resume_id': resume_id,
            'generated_at': result.get("generated_at")
        }
        
        logger.info(f"Template context prepared: pdf_generated={pdf_generated}, pdf_file_id={template_context['pdf_file_id']}")
        
        return render_template('ats_resume_result.html', **template_context)

    except Exception as e:
        logger.error(f"ATS Resume generation error: {str(e)}", exc_info=True)
        return render_template('error.html', error=str(e))

@app.route('/api/regenerate-ats-resume/<resume_id>', methods=['POST'])
def regenerate_ats_resume(resume_id):
    """Force regeneration of ATS resume"""
    try:
        logger.info(f"Regenerating ATS resume for ID: {resume_id}")
        
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Delete existing ATS resume from database
        ats_generator.db.ats_resumes.delete_one({"resume_id": resume_id})
        logger.info(f"Deleted existing ATS resume for ID: {resume_id}")
        
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return jsonify({"success": False, "error": "Resume not found"}), 404

        # Serialize resume data before passing to generator
        serialized_resume_data = serialize_resume_data(resume_data)

        # Generate new ATS resume with serialized data
        result = ats_generator.generate_ats_resume(resume_id, serialized_resume_data)
        
        # Serialize the result to handle ObjectId conversion
        serialized_result = serialize_resume_data(result)
        
        return jsonify(serialized_result)

    except Exception as e:
        logger.error(f"ATS Resume regeneration error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/update-ats-resume/<resume_id>', methods=['POST'])
def update_ats_resume(resume_id):
    """Update ATS resume data from editing interface"""
    try:
        logger.info(f"Updating ATS resume data for ID: {resume_id}")
        
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Get the updated data from request
        request_data = request.json
        if not request_data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Extract ats_data from request, handle both formats
        if "ats_data" in request_data:
            updated_ats_data = request_data["ats_data"]
        else:
            updated_ats_data = request_data
        
        logger.info(f"Received updated data keys: {list(updated_ats_data.keys()) if isinstance(updated_ats_data, dict) else 'Not a dict'}")
        
        # Get existing ATS resume
        result = ats_generator.get_ats_resume_by_id(resume_id)
        if not result["success"]:
            return jsonify({"success": False, "error": "ATS resume not found"}), 404
        
        # Update the ATS data with new information
        ats_resume = result["data"]
        
        # Update the database entry with the new ATS data
        update_result = ats_generator.db.ats_resumes.update_one(
            {"resume_id": resume_id},
            {
                "$set": {
                    "ats_data": updated_ats_data, 
                    "updated_at": datetime.now()
                }
            }
        )
        
        if update_result.modified_count > 0:
            logger.info(f"Successfully updated ATS resume data for ID: {resume_id}")
            
            # Optionally regenerate PDF with updated data
            try:
                # Create new LaTeX and PDF with updated data
                latex_content = ats_generator.create_ats_latex_resume(updated_ats_data)
                
                # Generate new PDF
                tex_filename = f"temp_ats_resume_{resume_id}.tex"
                pdf_filename = f"temp_ats_resume_{resume_id}.pdf"
                
                with open(tex_filename, 'w') as f:
                    f.write(latex_content)
                
                # Compile to PDF
                import subprocess
                result = subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_filename], 
                                      capture_output=True, text=True)
                
                if os.path.exists(pdf_filename):
                    # Store new PDF in GridFS
                    new_pdf_file_id = ats_generator.store_file_in_gridfs(
                        pdf_filename, resume_id, "pdf", "application/pdf"
                    )
                    
                    # Update database with new PDF file ID
                    ats_generator.db.ats_resumes.update_one(
                        {"resume_id": resume_id},
                        {"$set": {"pdf_file_id": new_pdf_file_id}}
                    )
                    
                    logger.info(f"Generated new PDF for updated resume: {new_pdf_file_id}")
                
                # Clean up temporary files
                for temp_file in [tex_filename, pdf_filename]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        
            except Exception as pdf_error:
                logger.warning(f"Failed to regenerate PDF after update: {pdf_error}")
            
            return jsonify({"success": True, "message": "Resume data updated successfully"})
        else:
            logger.warning(f"No documents modified for resume ID: {resume_id}")
            return jsonify({"success": False, "error": "Failed to update resume data"}), 500
            
    except Exception as e:
        logger.error(f"ATS Resume update error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/get-ats-resume-data/<resume_id>')
def get_ats_resume_data(resume_id):
    """Get ATS resume data for editing"""
    try:
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Get ATS resume from database
        result = ats_generator.get_ats_resume_by_id(resume_id)
        
        if not result["success"]:
            return jsonify({"success": False, "error": "ATS resume not found"}), 404
        
        ats_resume = result["data"]
        ats_data = ats_resume.get("ats_data", {})
        
        # Serialize the data to handle ObjectIds
        serialized_data = serialize_resume_data(ats_data)
        
        return jsonify({"success": True, "data": serialized_data})
        
    except Exception as e:
        logger.error(f"Get ATS resume data error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download-ats-resume/<resume_id>')
def download_ats_resume(resume_id):
    """Download ATS resume PDF from GridFS or local file"""
    try:
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Get ATS resume from database
        result = ats_generator.get_ats_resume_by_id(resume_id)
        
        if not result["success"]:
            logger.error(f"ATS resume not found for ID: {resume_id}")
            return jsonify({'error': 'ATS resume not found'}), 404
        
        ats_resume = result["data"]
        logger.info(f"Retrieved ATS resume data for ID: {resume_id}")
        
        # Try to get PDF from GridFS first
        pdf_file_id = ats_resume.get("pdf_file_id")
        if pdf_file_id:
            try:
                from bson import ObjectId
                # Convert string ID to ObjectId if needed
                if isinstance(pdf_file_id, str):
                    pdf_file_id = ObjectId(pdf_file_id)
                
                pdf_data = ats_generator.get_ats_file_from_gridfs(pdf_file_id)
                if pdf_data:
                    logger.info(f"Successfully retrieved PDF from GridFS for resume {resume_id}")
                    return send_file(
                        io.BytesIO(pdf_data),
                        mimetype='application/pdf',
                        as_attachment=False,  # Display inline instead of download
                        download_name=f"ats_resume_{resume_id}.pdf"
                    )
                else:
                    logger.warning(f"PDF data is empty for file ID: {pdf_file_id}")
            except Exception as e:
                logger.warning(f"Failed to get PDF from GridFS: {e}")
        
        # Fallback to local file if GridFS fails
        pdf_path = ats_resume.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            logger.info(f"Serving PDF from local file: {pdf_path}")
            return send_file(
                pdf_path, 
                mimetype='application/pdf',
                as_attachment=False,  # Display inline
                download_name=f"ats_resume_{resume_id}.pdf"
            )
        
        logger.error(f"No PDF file found for resume {resume_id}")
        return jsonify({'error': 'PDF file not found'}), 404

    except Exception as e:
        logger.error(f"ATS Resume download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download-ats-tex/<resume_id>')
def download_ats_tex(resume_id):
    """Download ATS resume LaTeX file from GridFS"""
    try:
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Get ATS resume from database
        result = ats_generator.get_ats_resume_by_id(resume_id)
        
        if not result["success"]:
            return jsonify({'error': 'ATS resume not found'}), 404
        
        ats_resume = result["data"]
        
        # Try to get LaTeX file from GridFS
        tex_file_id = ats_resume.get("tex_file_id")
        if tex_file_id:
            try:
                from bson import ObjectId
                # Convert string ID to ObjectId if needed
                if isinstance(tex_file_id, str):
                    tex_file_id = ObjectId(tex_file_id)
                
                tex_data = ats_generator.get_ats_file_from_gridfs(tex_file_id)
                if tex_data:
                    return send_file(
                        io.BytesIO(tex_data),
                        mimetype='text/plain',
                        as_attachment=True,
                        download_name=f"ats_resume_{resume_id}.tex"
                    )
            except Exception as e:
                logger.warning(f"Failed to get LaTeX file from GridFS: {e}")
        
        # Fallback to using tex_content from database
        tex_content = ats_resume.get("tex_content")
        if tex_content:
            return send_file(
                io.BytesIO(tex_content.encode('utf-8')),
                mimetype='text/plain',
                as_attachment=True,
                download_name=f"ats_resume_{resume_id}.tex"
            )
        
        return jsonify({'error': 'LaTeX file not found'}), 404

    except Exception as e:
        logger.error(f"ATS LaTeX download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/view-ats-pdf/<resume_id>')
def view_ats_pdf(resume_id):
    """View ATS resume PDF inline in browser"""
    try:
        from gen_resume import ATSResumeGenerator
        ats_generator = ATSResumeGenerator()
        
        # Get ATS resume from database
        result = ats_generator.get_ats_resume_by_id(resume_id)
        
        if not result["success"]:
            logger.error(f"ATS resume not found for ID: {resume_id}")
            return jsonify({'error': 'ATS resume not found'}), 404
        
        ats_resume = result["data"]
        logger.info(f"Viewing PDF for resume ID: {resume_id}")
        
        # Try to get PDF from GridFS first
        pdf_file_id = ats_resume.get("pdf_file_id")
        if pdf_file_id:
            try:
                from bson import ObjectId
                # Convert string ID to ObjectId if needed
                if isinstance(pdf_file_id, str):
                    pdf_file_id = ObjectId(pdf_file_id)
                
                pdf_data = ats_generator.get_ats_file_from_gridfs(pdf_file_id)
                if pdf_data:
                    logger.info(f"Successfully retrieved PDF from GridFS for viewing")
                    response = send_file(
                        io.BytesIO(pdf_data),
                        mimetype='application/pdf',
                        as_attachment=False
                    )
                    # Add headers to ensure inline display
                    response.headers['Content-Disposition'] = 'inline'
                    return response
                else:
                    logger.warning(f"PDF data is empty for file ID: {pdf_file_id}")
            except Exception as e:
                logger.warning(f"Failed to get PDF from GridFS for viewing: {e}")
        
        # Fallback to local file if GridFS fails
        pdf_path = ats_resume.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            logger.info(f"Serving PDF from local file for viewing: {pdf_path}")
            response = send_file(pdf_path, mimetype='application/pdf', as_attachment=False)
            response.headers['Content-Disposition'] = 'inline'
            return response
        
        logger.error(f"No PDF file found for viewing resume {resume_id}")
        return jsonify({'error': 'PDF file not found'}), 404

    except Exception as e:
        logger.error(f"PDF viewing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/email-history/<resume_id>')
def email_history(resume_id):
    """View email history for a resume"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        # Get email history
        email_history = app.config['email_gen'].get_email_history(resume_id)
        
        # Serialize the email history to handle ObjectId conversion
        serialized_history = serialize_resume_data(email_history)
        
        return render_template('email_history.html',
                             resume_data=resume_data,
                             email_history=serialized_history,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Email history error: {str(e)}")
        return render_template('error.html', error=str(e))


@app.route('/cover-letter-history/<resume_id>')
def cover_letter_history(resume_id):
    """View cover letter history for a resume"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        # Get cover letter history
        letter_history = app.config['cover_letter_gen'].get_cover_letter_history(resume_id)
        
        # Serialize the letter history to handle ObjectId conversion
        serialized_history = serialize_resume_data(letter_history)
        
        return render_template('cover_letter_history.html',
                             resume_data=resume_data,
                             letter_history=serialized_history,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Cover letter history error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/api/regenerate-cover-letter', methods=['POST'])
def regenerate_cover_letter():
    """Regenerate cover letter with feedback"""
    try:
        data = request.json
        resume_id = data.get('resume_id')
        
        
        if not resume_id:
            return jsonify({
                'success': False,
                'error': 'Resume ID is required'
            }), 400

        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return jsonify({
                'success': False,
                'error': 'Resume not found'
            }), 404

        # Generate new cover letter with feedback
        result = app.config['cover_letter_gen'].customize_cover_letter(
            resume_data=resume_data,
            company_name=data.get('company_name', ''),
            position=data.get('job_title', ''),
            job_description=data.get('job_description', ''),
            additional_context=f"{data.get('additional_context', '')} \n\nFeedback for improvement: {data.get('feedback', '')}"
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Cover letter regeneration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# Add error handling middleware
@app.before_request
def before_request():
    """Log all requests"""
    logger.info(f"{request.method} {request.path} - {request.remote_addr}")

@app.after_request
def after_request(response):
    """Add CORS headers and log response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    logger.info(f"Response: {response.status_code}")
    return response


def serialize_resume_data(resume_data):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if isinstance(resume_data, list):
        return [serialize_resume_data(item) for item in resume_data]
    
    if isinstance(resume_data, dict):
        serialized = {}
        for key, value in resume_data.items():
            if isinstance(value, ObjectId):
                serialized[key] = str(value)
            elif isinstance(value, dict):
                serialized[key] = serialize_resume_data(value)
            elif isinstance(value, list):
                serialized[key] = serialize_resume_data(value)
            else:
                serialized[key] = value
        return serialized
    
    return resume_data
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)