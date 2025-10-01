from flask import Flask, request, jsonify, Blueprint, send_file
import os
import logging
import json
import io
from werkzeug.utils import secure_filename
from cover_letter_generator import CoverLetterGenerator
from cold_email_generator import ColdEmailGenerator
from resume_generator import ResumeGenerator
from resume_parser import ResumeParser
from job_analyzer import JobAnalyzer
from bson import ObjectId
from typing import List, Dict
from interview_preparation import InterviewPreparation
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_FOLDER = 'uploads'
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

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    CORS(app, origins=["*"])
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Initialize components without ChromaDB
    app.config['resume_parser'] = ResumeParser()
    app.config['resume_gen'] = ResumeGenerator()
    app.config['cover_letter_gen'] = CoverLetterGenerator()
    app.config['email_gen'] = ColdEmailGenerator()
    app.config['job_analyzer'] = JobAnalyzer()
    app.config['interview_prep'] = InterviewPreparation()
    
    return app

def _analyze_resume_match(self, job_analysis: Dict, resume_data: Dict) -> Dict:
    """Analyze how well the resume matches the job requirements"""
    try:
        resume_skills = set(skill.lower() for skill in resume_data['parsed_data'].get('skills', []))
        required_skills = set(skill.lower() for skill in job_analysis.get('required_skills', []))

        # Calculate match percentages
        skill_matches = resume_skills.intersection(required_skills)
        skill_match_percentage = len(skill_matches) / len(required_skills) * 100 if required_skills else 0

        return {
            'overall_match_percentage': round(skill_match_percentage, 2),
            'matching_skills': list(skill_matches),
            'missing_skills': list(required_skills - resume_skills),
            'additional_skills': list(resume_skills - required_skills),
            'experience_match': self._check_experience_match(
                job_analysis.get('experience_needed', ''),
                resume_data['parsed_data'].get('experience', [])
            ),
            'recommendations': self._generate_match_recommendations(
                skill_match_percentage,
                list(required_skills - resume_skills)
            )
        }

    except Exception as e:
        logging.error(f"Resume match analysis error: {str(e)}")
        return {}

def _check_experience_match(self, required_experience: str, resume_experience: List[Dict]) -> Dict:
    """Check if resume experience matches job requirements"""
    try:
        # Extract years from requirement (e.g., "3+ years" -> 3)
        required_years = int(''.join(filter(str.isdigit, required_experience))) if required_experience else 0
        
        # Calculate total experience from resume
        total_years = sum(self._calculate_experience_duration(exp.get('duration', ''))
                         for exp in resume_experience)

        return {
            'has_sufficient_experience': total_years >= required_years,
            'years_of_experience': total_years,
            'years_required': required_years,
            'gap': required_years - total_years if required_years > total_years else 0
        }

    except Exception as e:
        logging.error(f"Experience match check error: {str(e)}")
        return {}

def _calculate_experience_duration(self, duration_str: str) -> float:
    """Calculate years of experience from duration string"""
    try:
        # Handle common duration formats
        duration_str = duration_str.lower()
        if 'year' in duration_str:
            return float(''.join(filter(str.isdigit, duration_str)))
        elif 'month' in duration_str:
            months = float(''.join(filter(str.isdigit, duration_str)))
            return round(months / 12, 1)
        return 0
    except:
        return 0

def _generate_match_recommendations(self, match_percentage: float, missing_skills: List[str]) -> List[str]:
    """Generate recommendations based on match analysis"""
    recommendations = []
    
    if match_percentage < 60:
        recommendations.append("Consider upskilling in key areas before applying")
    elif match_percentage < 80:
        recommendations.append("You meet basic requirements but could strengthen your profile")
    
    if missing_skills:
        recommendations.append(f"Focus on acquiring these skills: {', '.join(missing_skills[:3])}")
    
    return recommendations

def analyze_job_description(self, job_description: str, resume_data: Dict = None) -> Dict:
    """Analyze job description and compare with resume if provided"""
    try:
        prompt = f"""
        Analyze this job description and extract key information:
        {job_description}

        Return a structured analysis with:
        1. Required skills and qualifications
        2. Key responsibilities
        3. Company culture indicators
        4. Important keywords
        5. Level of experience needed
        6. Technical requirements
        7. Soft skills requirements

        If resume data is provided, include compatibility analysis.
        Format as JSON with clear sections.
        """

        # Get analysis from Gemini
        response = self.model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,
                'top_p': 1,
                'top_k': 32
            }
        )

        # Parse the response
        start_idx = response.text.find('{')
        end_idx = response.text.rfind('}') + 1
        analysis = json.loads(response.text[start_idx:end_idx])

        # If resume data is provided, add match analysis
        if resume_data:
            analysis['resume_match'] = self._analyze_resume_match(
                job_analysis=analysis,
                resume_data=resume_data
            )

        return {
            'success': True,
            'analysis': analysis
        }

    except Exception as e:
        logging.error(f"Job analysis error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

app = create_app()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for deployment"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'message': 'Resume AI API is running'
    })

# Routes
@app.route('/')
def index():
    """Main page route - API only"""
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

# Add a new endpoint for recent resumes
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
            return jsonify({
                'success': False,
                'error': "Application not properly initialized"
            }), 500
            
        # Add more detailed logging
        logging.info("Fetching all resumes...")
        resumes = app.config['resume_parser'].get_all_resumes_sync()
        
        # Debug the resumes data
        logging.info(f"Found {len(resumes)} resumes")
        for i, resume in enumerate(resumes):
            logging.info(f"Resume {i}: ID={resume.get('_id')}, filename={resume.get('original_filename')}")
        
        if not resumes:
            logging.warning("No resumes found in database")
            return jsonify({
                'success': True,
                'resumes': [],
                'message': "No resumes found"
            })
        
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
            
        return jsonify({
            'success': True,
            'resumes': resumes
        })
        
    except Exception as e:
        logging.error(f"My resumes error: {str(e)}")
        logging.error(f"Error type: {type(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': "Unable to fetch resumes"
        }), 500

@app.route('/resume')
def resume_page():
    return jsonify({
        'success': True,
        'page': 'resume',
        'message': 'Resume page endpoint'
    })

@app.route('/cover-letter')
def cover_letter_page():
    return jsonify({
        'success': True,
        'page': 'cover_letter',
        'message': 'Cover letter page endpoint'
    })

@app.route('/email')
def email_page():
    return jsonify({
        'success': True,
        'page': 'email',
        'message': 'Email page endpoint'
    })

@app.route('/dashboard/<resume_id>')
def dashboard(resume_id):
    """Dashboard for a specific resume"""
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
        interview_stats = app.config['interview_prep'].get_interview_statistics(resume_id)
            
        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'interview_stats': interview_stats
        })
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
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
def generate_cover_letter(resume_id):
    """Generate cover letter using existing resume data"""
    try:
        # Get existing resume data
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return jsonify({
                'success': False,
                'error': "Resume not found"
            }), 404

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

        # GET request - return form data
        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'resume_id': resume_id,
            'page': 'cover_letter_form'
        })
                             
    except Exception as e:
        logger.error(f"Cover letter generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Create blueprints
cover_letter_bp = Blueprint('cover_letter', __name__, url_prefix='/api/cover-letter')
email_bp = Blueprint('email', __name__, url_prefix='/api/email')
resume_bp = Blueprint('resume', __name__, url_prefix='/api/resume')

# Cover Letter Routes
@cover_letter_bp.route('/generate', methods=['POST'])
async def generate_cover_letter():
    data = request.json
    result = await app.config['cover_letter_gen'].generate_cover_letter(data)
    
    if not result['success']:
        if result.get('needs_more_info'):
            return jsonify({
                'success': False,
                'needs_more_info': True,
                'follow_up_questions': result['follow_up_questions']
            }), 422
        return jsonify(result), 400
    
    return jsonify(result)

@cover_letter_bp.route('/regenerate', methods=['POST'])
async def regenerate_cover_letter():
    data = request.json
    feedback = data.pop('feedback', '')
    
    if not feedback:
        return jsonify({
            'success': False,
            'error': 'Feedback is required for regeneration'
        }), 400
    
    result = await app.config['cover_letter_gen'].regenerate_with_feedback(data, feedback)
    return jsonify(result)

@cover_letter_bp.route('/generate-with-analysis', methods=['POST'])
async def generate_cover_letter_with_analysis():
    data = request.json
    
    if not all([data.get('job_description'), data.get('resume_id')]):
        return jsonify({
            'success': False,
            'error': 'Job description and resume ID are required'
        }), 400
    
    result = await app.config['cover_letter_gen'].generate_cover_letter_with_analysis(
        data,
        data['job_description'],
        data['resume_id']
    )
    
    return jsonify(result)

# Email Routes
@email_bp.route('/generate', methods=['POST'])
async def generate_email():
    data = request.json
    result = await app.config['email_gen'].generate_email(data)
    return jsonify(result)

@email_bp.route('/generate-with-resume', methods=['POST'])
async def generate_email_with_resume():
    data = request.json
    if not all([data.get('resume_id'), data.get('role_context')]):
        return jsonify({
            'success': False,
            'error': 'Resume ID and role context are required'
        }), 400
    
    result = await app.config['email_gen'].generate_email_with_resume(
        data,
        data['resume_id']
    )
    return jsonify(result)

@email_bp.route('/regenerate', methods=['POST'])
async def regenerate_email():
    data = request.json
    feedback = data.pop('feedback', '')
    
    if not feedback:
        return jsonify({
            'success': False,
            'error': 'Feedback is required for regeneration'
        }), 400
    
    result = await app.config['email_gen'].regenerate_email(data, feedback)
    return jsonify(result)

@email_bp.route('/research-recipient', methods=['POST'])
async def research_recipient():
    data = request.json
    result = await app.config['email_gen'].research_recipient(data)
    return jsonify(result)

# Resume Routes
@resume_bp.route('/generate', methods=['POST'])
async def generate_resume():
    data = request.json
    job_description = data.pop('job_description', None)
    result = await app.config['resume_gen'].generate_resume(data, job_description)
    
    if not result['success']:
        return jsonify(result), 400
    
    return jsonify(result)

@resume_bp.route('/optimize', methods=['POST'])
async def optimize_content():
    data = request.json
    if not data.get('content') or not data.get('industry'):
        return jsonify({
            'success': False,
            'error': 'Content and industry are required'
        }), 400
    
    result = await app.config['resume_gen'].optimize_content(data['content'], data['industry'])
    return jsonify({'success': True, 'optimization': result})

@resume_bp.route('/regenerate', methods=['POST'])
async def regenerate_resume():
    data = request.json
    feedback = data.pop('feedback', '')
    
    if not feedback:
        return jsonify({
            'success': False,
            'error': 'Feedback is required for regeneration'
        }), 400
    
    result = await app.config['resume_gen'].regenerate_with_feedback(data, feedback)
    return jsonify(result)

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

        # GET request - return form data
        return jsonify({
            'success': True,
            'resume_id': resume_id,
            'resume_data': resume_data,
            'page': 'analyze_job_form'
        })

    except Exception as e:
        logger.error(f"Job analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/job-recommendations/<resume_id>')
def job_recommendations(resume_id):
    """Show job recommendations based on resume"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return jsonify({
                'success': False,
                'error': "Resume not found"
            }), 404
            
        # Get recommendations
        result = app.config['job_analyzer'].get_job_recommendations_sync(resume_data)
        
        if not result.get('success'):
            logger.error(f"Failed to get recommendations: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': "Failed to generate recommendations"
            }), 500

        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'recommendations': result.get('recommendations', {}),
            'resume_id': resume_id
        })
                             
    except Exception as e:
        logger.error(f"Job recommendations error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/email/preview/<resume_id>')
def preview_email(resume_id):
    """Email preview page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'resume_id': resume_id,
            'page': 'email_preview'
        })
    except Exception as e:
        logger.error(f"Email preview error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@resume_bp.route('/parse', methods=['POST'])
def parse_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No resume file uploaded'
            }), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
            
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'Unsupported file type. Allowed: {", ".join(allowed_extensions)}'
            }), 400
        
        # Save file temporarily
        os.makedirs('uploads', exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join('uploads', filename)
        file.save(filepath)
        
        try:
            # Use sync method instead of async
            result = app.config['resume_parser'].parse_resume_sync(filepath)
            return jsonify(result)
                
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
                
    except Exception as e:
        logging.error(f"Resume parsing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@resume_bp.route('/save', methods=['POST'])
async def save_resume():
    try:
        data = request.json
        success = app.config['resume_parser'].save_parsed_resume(data)
        
        return jsonify({
            'success': success,
            'error': None if success else 'Failed to save to database'
        })
        
    except Exception as e:
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

@app.route('/mock-interview/<resume_id>')
def mock_interview(resume_id):
    """Mock interview practice page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        return render_template('mock_interview.html',
                             resume_data=resume_data,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Mock interview error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/interview-history/<resume_id>')
def interview_history(resume_id):
    """Interview history page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        history = app.config['interview_prep'].get_interview_history(resume_id)
        return render_template('interview_history.html',
                             resume_data=resume_data,
                             history=history,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Interview history error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/interview-feedback/<resume_id>', methods=['GET', 'POST'])
def interview_feedback(resume_id):
    """Interview feedback page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        if request.method == 'POST':
            feedback_data = request.json
            result = app.config['interview_prep'].save_interview_feedback(
                resume_id=resume_id,
                feedback_data=feedback_data
            )
            return jsonify(result)

        return render_template('interview_feedback.html',
                             resume_data=resume_data,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Interview feedback error: {str(e)}")
        return render_template('error.html', error=str(e))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE')
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {str(e)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500
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
@app.route('/interview-resources/<resume_id>')
def interview_resources(resume_id):
    """Interview learning resources page"""
    try:
        resume_data = app.config['resume_parser'].get_resume_by_id_sync(resume_id)
        if not resume_data:
            logger.error(f"Resume not found: {resume_id}")
            return render_template('error.html', error="Resume not found")

        # Get learning resources based on resume skills
        resources = app.config['interview_prep'].get_learning_resources(resume_data)
        
        # Ensure we have at least default resources
        if not resources:
            resources = app.config['interview_prep']._get_default_resources()

        return render_template('interview_resources.html',
                             resume_data=resume_data,
                             resources=resources,
                             resume_id=resume_id)

    except Exception as e:
        logger.error(f"Interview resources error: {str(e)}")
        return render_template('error.html', error=str(e))
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

