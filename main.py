from flask import Flask, request, jsonify, Blueprint, render_template, redirect, send_file
import os
import logging
import json
import io
from functools import wraps
from werkzeug.utils import secure_filename
from cover_letter_generator import CoverLetterGenerator
from cold_email_generator import ColdEmailGenerator
# from resume_generator import ResumeGenerator
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
from logging.handlers import RotatingFileHandler
from db_pool_manager import get_database, get_connection_stats
from cache_manager import init_cache_manager, get_cache_manager, cache_set, cache_get, cache_delete, cache_exists

# Configure logging with file output
def setup_logging():
    """Configure logging to save to files with timestamps"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create timestamp for log filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"syntexa_app_{timestamp}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler with rotation
    file_handler = RotatingFileHandler(
        log_filepath,
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Create error log file handler
    error_log_filename = f"syntexa_errors_{timestamp}.log"
    error_log_filepath = os.path.join(logs_dir, error_log_filename)
    error_handler = RotatingFileHandler(
        error_log_filepath,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("="*80)
    logger.info("SYNTEXA APPLICATION STARTING")
    logger.info(f"Log file: {log_filepath}")
    logger.info(f"Error log file: {error_log_filepath}")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info("="*80)
    
    return logger

# Initialize logging
logger = setup_logging()

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
        
        # Check for token in multiple places
        # 1. Authorization header (preferred)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                if is_api_request():
                    return jsonify({'success': False, 'error': 'Invalid token format'}), 401
                return redirect('/login')
        
        # 2. Token in cookies (for web pages)
        elif 'syntexa_access_token' in request.cookies:
            token = request.cookies.get('syntexa_access_token')
        
        # 3. Token in query parameters (fallback)
        elif request.args.get('token'):
            token = request.args.get('token')
        
        if not token:
            if is_api_request():
                return jsonify({'success': False, 'error': 'Token is missing'}), 401
            return redirect('/login')
        
        try:
            # Verify token using user manager
            user_manager = UserManager()
            payload = user_manager.verify_jwt_token(token)
            
            if payload is None:
                # Token is invalid or expired
                if is_api_request():
                    return jsonify({
                        'success': False, 
                        'error': 'Token is invalid or expired',
                        'requires_refresh': True
                    }), 401
                return redirect('/login')
            
            # Check if it's an access token
            if payload.get('type') != 'access':
                if is_api_request():
                    return jsonify({'success': False, 'error': 'Invalid token type'}), 401
                return redirect('/login')
            
            # Add user info to request context
            request.user_id = payload['user_id']
            request.user_email = payload['email']
            
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            if is_api_request():
                return jsonify({'success': False, 'error': 'Token verification failed'}), 401
            return redirect('/login')
        
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
    
    # Log database pool initialization
    logger.info("Initializing application components with database pooling...")
    
    # Initialize components with database pooling
    try:
        app.config['resume_parser'] = ResumeParser()
        logger.info("✓ Resume parser initialized with database pooling")
    except Exception as e:
        logger.error(f"✗ Failed to initialize resume parser: {e}")
        
    try:
        app.config['cover_letter_gen'] = CoverLetterGenerator()
        logger.info("✓ Cover letter generator initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize cover letter generator: {e}")
        
    try:
        app.config['email_gen'] = ColdEmailGenerator()
        logger.info("✓ Cold email generator initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize email generator: {e}")
        
    try:
        app.config['job_analyzer'] = JobAnalyzer()
        logger.info("✓ Job analyzer initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize job analyzer: {e}")
        
    try:
        app.config['interview_prep'] = InterviewPreparation()
        logger.info("✓ Interview preparation initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize interview preparation: {e}")
        
    try:
        app.config['resume_suggester'] = ResumeSuggester()
        logger.info("✓ Resume suggester initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize resume suggester: {e}")
    
    # Initialize Profile Analyzer with Gemini AI
    try:
        app.config['profile_analyzer'] = ProfileAnalyzer()
        logger.info("✓ Profile analyzer initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize profile analyzer: {e}")
    
    # Initialize User Management with database pooling
    try:
        app.config['user_manager'] = UserManager()
        logger.info("✓ User manager initialized with database pooling")
    except Exception as e:
        logger.error(f"✗ Failed to initialize user manager: {e}")
    
    # Initialize Centralized Cache Manager
    try:
        # Get database connection for cache
        cache_db = get_database('cache_manager')
        app.config['cache_manager'] = init_cache_manager(cache_db)
        logger.info("✓ Centralized cache manager initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize cache manager: {e}")
    
    # Check if Gemini API key is available
    if not os.getenv('GEMINI_API_KEY'):
        logger.warning("GEMINI_API_KEY not found. Profile analysis will use basic fallback methods.")
    
    # Log database connection stats
    try:
        db_stats = get_connection_stats()
        logger.info(f"Database pool status: {db_stats['active_connections']} active connections")
        logger.info(f"Database pool config: max={db_stats['pool_config']['maxPoolSize']}, min={db_stats['pool_config']['minPoolSize']}")
    except Exception as e:
        logger.warning(f"Could not get database pool stats: {e}")
    @app.errorhandler(405)
    def method_not_allowed(e):
        return make_response({"error": "Method Not Allowed"}, 405)
    return app

app = create_app()

@app.route('/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint with database pool status"""
    try:
        # Get database connection stats
        db_stats = get_connection_stats()
        
        # Check database connectivity
        db_healthy = False
        try:
            test_db = get_database()
            test_db.command('ping')
            db_healthy = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        
        health_status = {
            'success': True,
            'status': 'healthy' if db_healthy else 'degraded',
            'message': 'Resume AI API is running',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'active_connections': db_stats.get('active_connections', 0),
                'total_connections': db_stats.get('total_connections', 0),
                'failed_connections': db_stats.get('failed_connections', 0),
                'last_health_check': db_stats.get('last_health_check').isoformat() if db_stats.get('last_health_check') else None,
                'pool_config': {
                    'max_pool_size': db_stats.get('pool_config', {}).get('maxPoolSize', 0),
                    'min_pool_size': db_stats.get('pool_config', {}).get('minPoolSize', 0)
                }
            },
            'components': {
                'resume_parser': 'resume_parser' in app.config,
                'cover_letter_gen': 'cover_letter_gen' in app.config,
                'email_gen': 'email_gen' in app.config,
                'job_analyzer': 'job_analyzer' in app.config,
                'user_manager': 'user_manager' in app.config,
                'profile_analyzer': 'profile_analyzer' in app.config
            }
        }
        
        return jsonify(health_status), 200 if db_healthy else 503
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/system/db-stats', methods=['GET'])
def get_db_stats():
    """Get detailed database connection statistics"""
    try:
        db_stats = get_connection_stats()
        
        # Add additional runtime information
        db_stats['runtime_info'] = {
            'python_version': os.sys.version,
            'flask_debug': app.debug,
            'environment': os.getenv('FLASK_ENV', 'production'),
            'uptime': str(datetime.now() - datetime.fromtimestamp(time.time()))
        }
        
        return jsonify({
            'success': True,
            'database_stats': db_stats
        })
        
    except Exception as e:
        logger.error(f"Database stats error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system/connection-test', methods=['POST'])
def test_database_connection():
    """Test database connection and perform basic operations"""
    try:
        test_results = {
            'connection_test': False,
            'read_test': False,
            'write_test': False,
            'timing': {}
        }
        
        # Test basic connection
        start_time = time.time()
        test_db = get_database('test_connection')
        test_db.command('ping')
        test_results['connection_test'] = True
        test_results['timing']['connection'] = (time.time() - start_time) * 1000
        
        # Test read operation
        start_time = time.time()
        collections = test_db.list_collection_names()
        test_results['read_test'] = True
        test_results['timing']['read'] = (time.time() - start_time) * 1000
        test_results['collections_count'] = len(collections)
        
        # Test write operation (insert and delete a test document)
        start_time = time.time()
        test_collection = test_db.connection_test
        test_doc = {'test': True, 'timestamp': datetime.now()}
        insert_result = test_collection.insert_one(test_doc)
        test_collection.delete_one({'_id': insert_result.inserted_id})
        test_results['write_test'] = True
        test_results['timing']['write'] = (time.time() - start_time) * 1000
        
        return jsonify({
            'success': True,
            'test_results': test_results,
            'message': 'All database tests passed'
        })
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'test_results': test_results
        }), 500

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

@app.route('/api/auth/verify-token', methods=['POST'])
def verify_token():
    """Verify JWT token endpoint"""
    try:
        # If we reach here, the token is valid (auth_required decorator passed)
        result = app.config['user_manager'].get_user_profile(request.user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token is valid',
                'user': result['user']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to get user profile'
            }), 400
            
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Token verification failed'
        }), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('refresh_token'):
            return jsonify({
                'success': False,
                'error': 'Refresh token is required'
            }), 400
        
        # Refresh access token
        result = app.config['user_manager'].refresh_access_token(
            refresh_token=data['refresh_token']
        )
        
        if result:
            return jsonify({
                'success': True,
                'access_token': result['access_token'],
                'refresh_token': result['refresh_token']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired refresh token'
            }), 401
            
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Token refresh failed'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@auth_required
def logout():
    """User logout endpoint"""
    try:
        # Revoke refresh token
        success = app.config['user_manager'].revoke_refresh_token(request.user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Logged out successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Logout failed'
            }), 400
            
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status without requiring authentication"""
    try:
        token = None
        
        # Check Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                pass
        
        # Check cookies
        elif 'syntexa_access_token' in request.cookies:
            token = request.cookies.get('syntexa_access_token')
        
        if not token:
            return jsonify({
                'success': False,
                'authenticated': False,
                'message': 'No token found'
            })
        
        # Verify token
        user_manager = UserManager()
        payload = user_manager.verify_jwt_token(token)
        
        if payload and payload.get('type') == 'access':
            return jsonify({
                'success': True,
                'authenticated': True,
                'user': {
                    'id': payload['user_id'],
                    'email': payload['email']
                }
            })
        else:
            return jsonify({
                'success': False,
                'authenticated': False,
                'message': 'Invalid or expired token'
            })
            
    except Exception as e:
        logger.error(f"Auth status check error: {str(e)}")
        return jsonify({
            'success': False,
            'authenticated': False,
            'error': str(e)
        })

@app.route('/api/auth/profile', methods=['GET'])
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
    """Soft delete user account endpoint (mark as deleted)"""
    try:
        data = request.get_json()
        user_id = getattr(request, 'user_id', None)
        user_email = getattr(request, 'user_email', None)
        
        logger.info(f"Account deletion request for user: {user_email} (ID: {user_id})")
        
        if not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Password is required to delete account'
            }), 400
        
        # Soft delete account (mark as deleted)
        result = app.config['user_manager'].soft_delete_account(
            user_id=user_id,
            password=data['password']
        )
        
        if result['success']:
            logger.info(f"Account soft deleted successfully for user: {user_email} (ID: {user_id})")
            return jsonify(result), 200
        else:
            logger.error(f"Account deletion failed for user: {user_email} (ID: {user_id}): {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Delete account error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Account deletion failed. Please try again.'
        }), 500

@app.route('/api/auth/export-data', methods=['GET'])
@auth_required
def export_user_data():
    """Export user data including resumes and profile"""
    try:
        user_id = getattr(request, 'user_id', None)
        user_email = getattr(request, 'user_email', None)
        
        logger.info(f"Data export request for user: {user_email} (ID: {user_id})")
        
        # Get user profile
        profile_result = app.config['user_manager'].get_user_profile(user_id)
        
        # Get user resumes
        resumes = app.config['resume_parser'].get_all_resumes_sync(user_id)
        
        # Prepare export data
        export_data = {
            'export_date': datetime.utcnow().isoformat(),
            'user_profile': profile_result.get('user', {}) if profile_result.get('success') else {},
            'resumes': [],
            'total_resumes': len(resumes)
        }
        
        # Add resume data (without file content for size reasons)
        for resume in resumes:
            resume_data = {
                'id': str(resume.get('_id', '')),
                'filename': resume.get('original_filename', ''),
                'upload_date': resume.get('upload_date', '').isoformat() if hasattr(resume.get('upload_date', ''), 'isoformat') else str(resume.get('upload_date', '')),
                'parsed_data': serialize_resume_data(resume.get('parsed_data', {})),
                'analysis': serialize_resume_data(resume.get('analysis', {})),
                'metadata': serialize_resume_data(resume.get('metadata', {}))
            }
            export_data['resumes'].append(resume_data)
        
        logger.info(f"Data export completed for user: {user_email} (ID: {user_id}) - {len(resumes)} resumes exported")
        
        # Return as downloadable JSON
        response = jsonify(export_data)
        response.headers['Content-Disposition'] = f'attachment; filename=syntexa_data_export_{user_id}_{datetime.now().strftime("%Y%m%d")}.json'
        response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        logger.error(f"Export data error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Data export failed. Please try again.'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@auth_required
def change_password_api():
    """Change user password endpoint"""
    try:
        data = request.get_json()
        user_id = getattr(request, 'user_id', None)
        user_email = getattr(request, 'user_email', None)
        
        logger.info(f"Password change request for user: {user_email} (ID: {user_id})")
        
        if not all([data.get('current_password'), data.get('new_password')]):
            return jsonify({
                'success': False,
                'error': 'Current password and new password are required'
            }), 400
        
        # Change password
        result = app.config['user_manager'].change_password(
            user_id=user_id,
            current_password=data['current_password'],
            new_password=data['new_password']
        )
        
        if result['success']:
            logger.info(f"Password changed successfully for user: {user_email} (ID: {user_id})")
            return jsonify(result), 200
        else:
            logger.error(f"Password change failed for user: {user_email} (ID: {user_id}): {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Password change failed. Please try again.'
        }), 500

# ===============================
# END AUTHENTICATION ENDPOINTS
# ===============================
# AUTHENTICATION PAGES
# ===============================

@app.route('/login')
def login_page():
    """Serve the login page"""
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    """Serve the signup page"""
    return render_template('signup.html')

# ===============================
# MAIN DASHBOARD
# ===============================


@app.route('/')
def index():
    """Main index route - redirect based on authentication status"""
    try:
        # Check if user is authenticated (from token in cookies or headers)
        token = None
        
        # Check Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                pass
        
        # Check cookies
        elif 'syntexa_access_token' in request.cookies:
            token = request.cookies.get('syntexa_access_token')
        
        if token:
            # Verify token
            try:
                user_manager = UserManager()
                payload = user_manager.verify_jwt_token(token)
                
                if payload and payload.get('type') == 'access':
                    # User is authenticated, check if they have resumes
                    try:
                        user_id = payload.get('user_id')
                        if user_id:
                            # Get user-specific resumes
                            resumes = app.config['resume_parser'].get_all_resumes_sync(user_id=user_id)
                        if resumes and len(resumes) > 0:
                                # User has resumes, redirect to dashboard with most recent resume
                                most_recent_resume = resumes[0]  # resumes are already sorted by upload_date desc
                                resume_id = str(most_recent_resume.get('_id'))
                                logger.info(f"Redirecting user {user_id} to dashboard with resume {resume_id}")
                                return redirect(f'/dashboard/{resume_id}')
                        else:
                            # User has no resumes, redirect to upload
                            logger.info(f"User {user_id} has no resumes, redirecting to upload")
                            return redirect('/upload')
                    #                     else:
                    # logger.warning("No user_id in token payload")
                    # return redirect('/upload')
                    except Exception as e:
                        logger.warning(f"Error checking resumes: {str(e)}")
                        return redirect('/upload')
            except Exception as e:
                logger.warning(f"Token verification failed: {str(e)}")
        
        # User is not authenticated, redirect to login
        return redirect('/login')
        
    except Exception as e:
        logger.error(f"Index route error: {str(e)}")
        return redirect('/login')

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
@auth_required
def my_resumes():
    """API: Return user's recent resumes (minimal info)"""
    try:
        if 'resume_parser' not in app.config:
            return jsonify({'success': False, 'error': 'Resume parser not initialized'}), 500
        resumes = app.config['resume_parser'].get_all_resumes_sync(user_id=request.user_id)
        result = []
        for resume in resumes:
            result.append({
                'id': str(resume.get('_id')),
                'name': resume.get('original_filename', 'Resume'),
                'upload_date': str(resume.get('upload_date', 'Unknown')),
                'dashboard_url': f"/dashboard/{resume.get('_id')}",
                'ats_url': f"/generate-ats-resume/{resume.get('_id')}"
            })
        return jsonify({'success': True, 'resumes': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/<resume_id>')
@auth_required
def dashboard(resume_id):
    """Dashboard for a specific resume with authentication"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.warning(f"No resume found with ID: {resume_id}")
            return render_template('404.html'), 404

        # Validate user ownership (if resume has user_id field)
        if 'user_id' in resume_data and resume_data['user_id'] != request.user_id:
            logger.warning(f"User {request.user_email} attempted to access resume {resume_id} owned by {resume_data.get('user_id')}")
            return render_template('error.html', 
                                error="You don't have permission to access this resume"), 403

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
@auth_required
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
@app.route('/dashboard_json/<resume_id>')
def dashboard_json(resume_id):
    """Dashboard for a specific resume - Returns JSON data"""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.warning(f"No resume found with ID: {resume_id}")
            return jsonify({
                'success': False,
                'error': 'Resume not found'
            }), 404

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

        # Calculate additional analytics
        analytics = {
            'profile_completeness': _calculate_profile_completeness(resume_data),
            'keyword_optimization': _analyze_keywords(resume_data),
            'ats_score': 0  # Default value
        }

        # Try to get ATS score
        try:
            if hasattr(app.config['resume_gen'], 'calculate_ats_scores_sync'):
                ats_result = app.config['resume_gen'].calculate_ats_scores_sync(resume_data)
                analytics['ats_score'] = ats_result.get('overall', 0)
        except Exception as e:
            logger.warning(f"Could not calculate ATS score: {str(e)}")

        # Get resume summary stats
        parsed_data = resume_data.get('parsed_data', {})
        summary_stats = {
            'total_experience_years': len(parsed_data.get('experience', [])),
            'total_skills': len(parsed_data.get('skills', [])),
            'education_count': len(parsed_data.get('education', [])),
            'projects_count': len(parsed_data.get('projects', [])),
            'certifications_count': len(parsed_data.get('certifications', []))
        }

        # Serialize the resume data
        serialized_resume = serialize_resume_data(resume_data)

        # Return comprehensive dashboard data
        dashboard_data = {
            'success': True,
            'resume_data': serialized_resume,
            'interview_stats': interview_stats,
            'analytics': analytics,
            'summary_stats': summary_stats,
            'personal_info': parsed_data.get('personal_info', {}),
            'recent_activity': {
                'last_updated': resume_data.get('upload_date', 'Unknown'),
                'file_size': resume_data.get('file_size', 0),
                'processing_status': resume_data.get('processing_status', 'completed')
            }
        }

        return jsonify(dashboard_data)

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to load dashboard data'
        }), 500
@app.route('/api/resume/download/<resume_id>')
def download_resume(resume_id):
    """Download original PDF file from GridFS."""
    try:
        # Get resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return jsonify({'success': False, 'error': 'Resume not found'}), 404
        
        # Check if file_id exists
        if 'file_id' not in resume_data:
            return jsonify({'success': False, 'error': 'Original file not found'}), 404
        
        # Get original file from GridFS
        file_data = app.config['resume_parser'].get_resume_file(resume_data['file_id'])
        if not file_data:
            return jsonify({'success': False, 'error': 'File data not found'}), 404
        
        # Get file metadata
        file_metadata = app.config['resume_parser'].get_file_metadata(resume_data['file_id'])
        filename = file_metadata.get('filename', f"resume_{resume_id}.pdf") if file_metadata else f"resume_{resume_id}.pdf"
        
        return send_file(
            io.BytesIO(file_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Resume download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/cover-letter/<resume_id>', methods=['GET', 'POST'])
@auth_required
def generate_cover_letter(resume_id):
    """Generate cover letter using existing resume data with authentication"""
    try:
        # Get existing resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        # Validate user ownership
        if 'user_id' in resume_data and resume_data['user_id'] != request.user_id:
            logger.warning(f"User {request.user_email} attempted to access resume {resume_id}")
            return render_template('error.html', 
                                error="You don't have permission to access this resume"), 403

        if request.method == 'POST':
            data = request.json
            # Use synchronous method instead of async
            result = app.config['cover_letter_gen'].customize_cover_letter(
                resume_data=resume_data,
                company_name=data.get('company_name'),
                position=data.get('job_title'),  # Changed from job_title to match form
                job_description=data.get('job_description'),
                additional_context=data.get('additional_context', '')
            )
            return jsonify(result)

        # GET request - render form
        return render_template('cover_letter.html', 
                             resume_data=resume_data,
                             resume_id=resume_id)
                             
    except Exception as e:
        logger.error(f"Cover letter generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
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
@app.route('/job-recommendations/<resume_id>')
def job_recommendations(resume_id):
    """Show job recommendations based on resume"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")
            
        # Get recommendations
        result = app.config['job_analyzer'].get_job_recommendations_sync(resume_data)
        
        if not result.get('success'):
            logger.error(f"Failed to get recommendations: {result.get('error')}")
            return render_template('error.html', 
                                error="Failed to generate recommendations")

        return render_template('job_recommendations.html',
                             resume_data=resume_data,
                             recommendations=result.get('recommendations', {}),
                             resume_id=resume_id)
                             
    except Exception as e:
        logger.error(f"Job recommendations error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/api/resume/upload', methods=['POST'])
@auth_required
def upload_resume():
    """Handle resume upload with authentication and enhanced parsing."""
    try:
        user_id = getattr(request, 'user_id', 'unknown')
        user_email = getattr(request, 'user_email', 'unknown')
        logger.info(f"Resume upload started for user: {user_email} (ID: {user_id})")
        
        # Debug: Log all request files and form data
        logger.info(f"Request files: {list(request.files.keys())}")
        logger.info(f"Request form: {list(request.form.keys())}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Content-Type: {request.content_type}")
        
        if 'file' not in request.files:
            logger.error(f"No file in request. Available files: {list(request.files.keys())}")
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']
        if not file or not allowed_file(file.filename):
            logger.error(f"Invalid file type: {file.filename if file else 'No filename'} for user: {user_email} (ID: {user_id})")
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Allowed: PDF, DOC, DOCX'
            }), 400

        # Validate file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        logger.info(f"File size: {file_size} bytes for user: {user_email} (ID: {user_id})")
        
        if file_size > app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            logger.error(f"File too large: {file_size} bytes for user: {user_email} (ID: {user_id})")
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size: 16MB'
            }), 400

        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"Saving file to: {temp_path} for user: {user_email} (ID: {user_id})")
        file.save(temp_path)

        try:
            # Parse resume with user_id for multi-user support
            logger.info(f"Starting resume parsing for: {filename} for user: {user_email} (ID: {user_id})")
            result = app.config['resume_parser'].parse_resume(temp_path, user_id=user_id)
            logger.info(f"Parse result: {result.get('success', 'Unknown')} - {result.get('error', 'No error info')} for user: {user_email} (ID: {user_id})")
            
            if result.get('success'):
                resume_id = result['resume_id']
                logger.info(f"Resume parsing successful, Resume ID: {resume_id} for user: {user_email} (ID: {user_id})")
                
                # Clean up temporary file after successful processing
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Cleaned up temporary file: {temp_path}")
                
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
                
                logger.info(f"Returning successful response for Resume ID: {resume_id}, user: {user_email} (ID: {user_id})")
                return jsonify(serialized_result), 200
            else:
                error_msg = result.get('error', 'Unknown error')
                error_details = result.get('details', '')
                logger.error(f"Resume parsing failed: {error_msg} for user: {user_email} (ID: {user_id})")
                
                # Clean up temporary file on failure
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Cleaned up temporary file: {temp_path}")
                
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'details': error_details,
                    'suggestions': [
                        'Ensure your PDF is not password protected',
                        'Try saving your resume as a new PDF from the original application',
                        'Check if your PDF contains selectable text (not just images)',
                        'Consider converting to DOCX format if PDF continues to fail'
                    ]
                }), 400
                
        except Exception as parse_error:
            logger.error(f"Exception during parsing: {str(parse_error)} for user: {user_email} (ID: {user_id})", exc_info=True)
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
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
@auth_required
def generate_email(resume_id):
    """Generate cold email using existing resume data with authentication"""
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

        # Validate user ownership
        if 'user_id' in resume_data and resume_data['user_id'] != request.user_id:
            logger.warning(f"User {request.user_email} attempted to access resume {resume_id}")
            if request.method == 'POST':
                return jsonify({
                    'success': False,
                    'error': 'Permission denied'
                }), 403
            return render_template('error.html', 
                                error="You don't have permission to access this resume"), 403

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

@app.route('/interview-prep/<resume_id>', methods=['GET', 'POST'])
def interview_preparation(resume_id):
    """Interview preparation page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        if request.method == 'POST':
            data = request.json
            
            # Generate comprehensive interview guide
            guide = app.config['interview_prep'].prepare_interview_guide(
                resume_data=resume_data,
                job_description=data.get('job_description', ''),
                company_name=data.get('company_name', '')
            )

            if not guide.get('success'):
                return jsonify({
                    'success': False,
                    'error': guide.get('error', 'Failed to generate guide')
                }), 500

            # Add default values for missing sections
            interview_guide = guide['interview_guide']
            interview_guide.setdefault('technical_preparation', {})
            interview_guide.setdefault('behavioral_questions', {})
            interview_guide.setdefault('company_questions', {})
            interview_guide.setdefault('preparation_tips', {})
            
            return jsonify({
                'success': True,
                'interview_guide': interview_guide
            })

        # GET request - render form
        return render_template('interview_prep.html',
                             resume_data=resume_data,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Interview preparation error: {str(e)}")
        if request.method == 'POST':
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        return render_template('error.html', error=str(e))
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
@app.route('/generate-study-plan/<resume_id>')
def generate_study_plan(resume_id):
    """Generate personalized study plan"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            return render_template('error.html', error="Resume not found")

        # Generate study plan based on resume skills and experience
        study_plan = app.config['interview_prep']._generate_study_plan(resume_data)
        
        return render_template('study_plan.html',
                             resume_data=resume_data,
                             study_plan=study_plan,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Study plan generation error: {str(e)}")
        return render_template('error.html', error=str(e))
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

def schedule_cache_cleanup():
    """Schedule periodic cache cleanup using centralized cache manager"""
    try:
        import threading
        import time
        
        def cleanup_worker():
            while True:
                try:
                    # Clean cache every 6 hours
                    time.sleep(6 * 60 * 60)  # 6 hours
                    deleted_count = get_cache_manager().clear_expired()
                    logger.info(f"Scheduled cleanup removed {deleted_count} expired cache entries")
                except Exception as e:
                    logger.error(f"Scheduled cache cleanup error: {str(e)}")
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Centralized cache cleanup scheduler started")
        
        # Run initial cleanup
        initial_cleanup = get_cache_manager().clear_expired()
        logger.info(f"Initial cache cleanup removed {initial_cleanup} expired entries")
        
    except Exception as e:
        logger.error(f"Failed to start cache cleanup scheduler: {str(e)}")

@app.route('/api/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Manual cleanup of expired cache entries"""
    try:
        deleted_count = get_cache_manager().clear_expired()
        return jsonify({
            'success': True,
            'deleted_entries': deleted_count,
            'message': f'Cleaned {deleted_count} expired cache entries'
        })
    except Exception as e:
        logger.error(f"Cache cleanup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get centralized cache statistics"""
    try:
        stats = get_cache_manager().get_stats()
        return jsonify({
            'success': True,
            'cache_stats': stats
        })
    except Exception as e:
        logger.error(f"Cache stats error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'cache_stats': {
                'total_entries': 0,
                'expired_entries': 0,
                'valid_entries': 0,
                'recent_entries_24h': 0,
                'type_distribution': [],
                'expiry_distribution': [],
                'database_status': 'error'
            }
        }), 500

@app.route('/api/cache/clear/<cache_type>', methods=['POST'])
def clear_cache_by_type(cache_type):
    """Clear cache entries by type"""
    try:
        deleted_count = get_cache_manager().clear_by_type(cache_type)
        return jsonify({
            'success': True,
            'deleted_entries': deleted_count,
            'message': f'Cleared {deleted_count} cache entries of type: {cache_type}'
        })
    except Exception as e:
        logger.error(f"Cache clear by type error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Cache helper functions for consistent key generation
def get_profile_cache_key(profile_url):
    """Generate consistent cache key for profile analysis"""
    return f"profile_analysis:{profile_url}"

def get_profile_results_cache_key(profile_url):
    """Generate consistent cache key for profile results"""
    return f"{profile_url}_results"

# Centralized cache for all application data with configurable expiration

@app.route('/api/analyze-profile', methods=['POST'])
def analyze_profile():
    """Analyze a single profile with enhanced AI-powered insights and centralized caching"""
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
        
        # Check cache first using centralized cache manager
        cache_key = get_profile_cache_key(profile_url)
        cached_analysis = cache_get(cache_key)
        if cached_analysis:
            logger.info(f"Returning cached analysis for: {profile_url}")
            # Update user interests if different
            cached_analysis['user_interests'] = user_interests
            cached_analysis['analysis_metadata']['from_cache'] = True
            return jsonify(cached_analysis)
        
        # Analyze the profile if not in cache
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
                'platform_detected': result['platform'],
                'from_cache': False
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
        
        # Save to database cache for 5 days
        cache_data_for_results = {
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
        
        # Save both response data and results data to centralized cache
        cache_set(cache_key, response_data, cache_type='profile_analysis')
        cache_set(get_profile_results_cache_key(profile_url), cache_data_for_results, cache_type='profile_analysis')
        
        logger.info(f"Analysis cached in database for URL: {profile_url}")
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

@app.route('/api/roast-profile', methods=['POST'])
def roast_profile():
    """Roast a LinkedIn profile with humor and wit"""
    try:
        data = request.get_json()
        logger.info(f"Profile roast request: {data}")
        
        profile_url = data.get('profile_url')
        user_interests = data.get('user_interests', [])
        tone = data.get('tone', 'witty')  # Options: mild, witty, savage, nuclear
        
        if not profile_url:
            return jsonify({
                'success': False,
                'error': 'Profile URL is required for roasting'
            }), 400
        
        # Add validation for URL format
        if not profile_url.startswith(('http://', 'https://')):
            profile_url = 'https://' + profile_url
        
        # Validate platform (currently supporting LinkedIn)
        if 'linkedin.com' not in profile_url.lower():
            return jsonify({
                'success': False,
                'error': 'Currently only LinkedIn profiles can be roasted. Sorry!'
            }), 400
        
        logger.info(f"Roasting profile: {profile_url} with tone: {tone}")
        
        # Roast the profile using cached method
        result = app.config['profile_analyzer'].roast_profile_with_cache(profile_url, user_interests)
        logger.info(f"Roast result success: {result.get('success')}")
        
        if not result['success']:
            logger.error(f"Roast failed: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to roast profile'),
                'consolation': result.get('consolation', 'Even our AI couldn\'t handle this profile!')
            }), 500
        
        # Structure the response for the frontend
        roast_data = result['roast']
        response_data = {
            'success': True,
            'platform': result['platform'],
            'profile_url': result['profile_url'],
            'roast': {
                'complete_roast_summary': roast_data['complete_roast_summary'],
                'roast_highlights': roast_data['roast_highlights'],
                'cringe_moments': roast_data['cringe_moments'],
                'missed_opportunities': roast_data['missed_opportunities'],
                'backhanded_compliments': roast_data['backhanded_compliments'],
                'reality_check': roast_data['reality_check'],
                'improvement_roast': roast_data['improvement_roast'],
                'overall_verdict': roast_data['overall_verdict'],
                'roast_level': roast_data['roast_level'],
                'comedy_gold_quote': roast_data['comedy_gold_quote']
            },
            'metadata': {
                'roast_timestamp': result['roast_timestamp'],
                'from_cache': result.get('from_cache', False),
                'cached_at': result.get('cached_at'),
                'user_interests': user_interests,
                'requested_tone': tone,
                'disclaimer': result.get('disclaimer', 'This roast is for entertainment purposes only!')
            },
            'sharing': {
                'shareable_quote': roast_data['comedy_gold_quote'],
                'roast_summary': roast_data['complete_roast_summary'][:280] + '...' if len(roast_data['complete_roast_summary']) > 280 else roast_data['complete_roast_summary'],
                'hashtags': ['#LinkedInRoast', '#ProfileAnalysis', '#SYNTEXA', '#CareerHumor']
            }
        }
        
        logger.info(f"Roast completed for URL: {profile_url}, level: {roast_data.get('roast_level', 'unknown')}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Profile roast failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'consolation': 'Don\'t worry, even our roasting AI couldn\'t handle your profile!',
            'debug_info': {
                'error_type': type(e).__name__,
                'error_location': 'main.py:roast_profile'
            },
            'fallback_suggestions': [
                'Make sure your LinkedIn profile is public',
                'Check if the URL is correct',
                'Try a different profile (maybe one that\'s less perfect?)',
                'Contact support if the roasting keeps failing'
            ]
        }), 500

@app.route('/api/get-cached-roast', methods=['GET'])
def get_cached_roast():
    """Get cached roast data for a profile URL"""
    try:
        profile_url = request.args.get('profile_url')
        
        if not profile_url:
            return jsonify({
                'success': False,
                'error': 'Profile URL is required'
            }), 400
        
        logger.info(f"Checking for cached roast: {profile_url}")
        
        # Check if we have a cached roast
        cached_result = app.config['profile_analyzer'].get_roast_from_db(profile_url)
        
        if cached_result:
            logger.info(f"Found cached roast for: {profile_url}")
            return jsonify({
                'success': True,
                'cached': True,
                'data': cached_result
            })
        else:
            logger.info(f"No cached roast found for: {profile_url}")
            return jsonify({
                'success': False,
                'cached': False,
                'message': 'No cached roast found for this profile'
            })
        
    except Exception as e:
        logger.error(f"Failed to get cached roast: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/roast-stats', methods=['GET'])
def get_roast_stats():
    """Get statistics about roasted profiles"""
    try:
        # Check if MongoDB is available
        if not app.config['profile_analyzer'].profile_roasts_collection:
            return jsonify({
                'success': False,
                'error': 'Database not available'
            }), 503
        
        # Get basic statistics
        total_roasts = app.config['profile_analyzer'].profile_roasts_collection.count_documents({})
        
        # Get recent roasts (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = datetime.now() - timedelta(hours=24)
        recent_roasts = app.config['profile_analyzer'].profile_roasts_collection.count_documents({
            'created_at': {'$gte': yesterday}
        })
        
        # Get platform distribution
        pipeline = [
            {'$group': {'_id': '$platform', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        platform_stats = list(app.config['profile_analyzer'].profile_roasts_collection.aggregate(pipeline))
        
        return jsonify({
            'success': True,
            'stats': {
                'total_roasts': total_roasts,
                'recent_roasts_24h': recent_roasts,
                'platform_distribution': platform_stats,
                'available_tones': ['mild', 'witty', 'savage', 'nuclear'],
                'database_status': 'connected'
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get roast stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {
                'total_roasts': 0,
                'recent_roasts_24h': 0,
                'platform_distribution': [],
                'available_tones': ['mild', 'witty', 'savage', 'nuclear'],
                'database_status': 'error'
            }
        }), 500

@app.route('/api/profile-results')
def profile_results_api():
    """Profile analysis results API endpoint - returns cached JSON data with 5-day database caching"""
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
        
        # Check centralized cache first (5-day expiration)
        results_cache_key = get_profile_results_cache_key(profile_url)
        cached_result = cache_get(results_cache_key)
        if cached_result:
            logger.info(f"Found cached results in centralized cache for: {profile_url}")
            return jsonify(cached_result)
        
        # Check main analysis cache as fallback
        analysis_cache_key = get_profile_cache_key(profile_url)
        analysis_cached_result = cache_get(analysis_cache_key)
        if analysis_cached_result:
            logger.info(f"Found analysis cache, extracting results for: {profile_url}")
            # Extract results format from analysis cache
            analysis = analysis_cached_result.get('analysis', {})
            platform = analysis_cached_result.get('platform', platform)
            
            if analysis:
                response_data = {
                    'success': True,
                    'profile_url': profile_url,
                    'platform': platform,
                    'results_available': True,
                    'last_analysis_date': analysis_cached_result.get('analysis_metadata', {}).get('analysis_date'),
                    'summary': {
                        'professional_score': analysis_cached_result.get('professional_score', 0),
                        'visibility_score': analysis_cached_result.get('visibility_metrics', {}).get('visibility_score', 0),
                        'overall_assessment': analysis.get('overall_assessment', ''),
                        'strengths': analysis.get('strengths', []),
                        'areas_for_improvement': analysis.get('areas_for_improvement', []),
                        'immediate_actions': analysis_cached_result.get('suggestions', {}).get('immediate_actions', []),
                        'medium_term_goals': analysis_cached_result.get('suggestions', {}).get('medium_term_goals', []),
                        'optimization_keywords': analysis_cached_result.get('visibility_metrics', {}).get('optimization_keywords', [])
                    },
                    'detailed_analysis': {
                        'section_scores': analysis_cached_result.get('section_scores', {}),
                        'platform_advice': analysis_cached_result.get('platform_advice', {}),
                        'privacy_concerns': analysis_cached_result.get('privacy_concerns', []),
                        'recruiter_appeal': analysis_cached_result.get('visibility_metrics', {}).get('recruiter_appeal', 0)
                    }
                }
                
                # Cache the results format for future use in centralized cache
                cache_set(get_profile_results_cache_key(profile_url), response_data, cache_type='profile_analysis')
                return jsonify(response_data)
        
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
        
        # Cache the new results in centralized cache
        cache_set(get_profile_results_cache_key(profile_url), response_data, cache_type='profile_analysis')
        logger.info(f"New analysis completed and cached in database for: {profile_url}")
        
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
@auth_required
def generate_ats_resume(resume_id):
    """Generate ATS-friendly resume for a specific resume with authentication"""
    try:
        logger.info(f"Starting ATS resume generation for ID: {resume_id} user: {request.user_email}")
        
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
    except Exception as e:
        logger.error(f"ATS Resume download error: {str(e)}")
        return render_template('error.html', error=str(e))

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
    try:
        # Log final startup information
        logger.info("="*80)
        logger.info("SYNTEXA APPLICATION STARTUP COMPLETE")
        
        # Final database pool status
        db_stats = get_connection_stats()
        logger.info(f"Database Pool Ready: {db_stats.get('active_connections', 0)} active connections")
        logger.info(f"Max Pool Size: {db_stats.get('pool_config', {}).get('maxPoolSize', 0)}")
        logger.info(f"Server ready to handle multiple concurrent users")
        
        # Start profile analysis cache cleanup scheduler
        schedule_cache_cleanup()
        
        logger.info("="*80)
        
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        # Cleanup database connections on shutdown
        try:
            from db_pool_manager import db_pool
            db_pool.close_all_connections()
            logger.info("Database connections closed cleanly")
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")