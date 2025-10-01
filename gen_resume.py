import json
import os
import subprocess
from datetime import datetime
import google.generativeai as genai
from pymongo import MongoClient
import gridfs
import logging
import sys
from bson import ObjectId

resume_sample = {
  "personal_info": {
    "name": "Nithin Jambula",
    "address": "3-3-277 , Pulivendula, Andhra Pradesh 516390",
    "phone": "+91 9347632259",
    "email": "nithinjambula89@gmail.com",
    "linkedin": "https://linkedin.com/in/nithin-jambula",
    "linkedin_display": "linkedin.com/in/nithin-jambula",
    "github": "https://github.com/nithin434",
    "github_display": "github.com/nithin434"
  },
  "education": [
    {
      "institution": "Vellore Institute of Technology",
      "duration": "Sep. 2023 -- May 2027",
      "degree": "Bachelor of Science in Computer Science",
      "location": "Amaravathi, Andhra Pradesh",
    }
  ],
  "coursework": [
    "Machine Learning",
    "Deep Learning Algorithms",
    "Computer Vision",
    "Natural Language Processing",
    "Artificial Intelligence",
    "Neural Networks",
    "Systems Programming",
    "Computer Architecture",
  ],
  "experience": [
    {
      "company": "Sripto",
      "duration": "Dec 2024 -- May 2025",
      "position": "Machine Learning Intern",
      "location": "Amaravathi, Andhra Pradesh",
      "points": [
        "Spearheaded development of foundational ML infrastructure in a startup setting, contributing to Sripto's core intelligent systems and future product roadmap.",
        "Built and deployed Retrieval-Augmented Generation (RAG) pipelines, enabling real-time response generation with contextual document embeddings.",
        "Engineered advanced LLM-powered applications including a PDF-based chatbot, semantic product matcher, and dynamic SQL query generator for natural language-based database retrieval.",
        "Managed server deployment, model serving infrastructure, and system scalability for AI-based solutions integrating both frontend and backend components."
      ]
    }
  ],
  "projects": [
    {
      "name": "Vulcan: Self-Driving EV Car",
      "technologies": "PyTorch, RL, DAgger, Segmentation(DeppLabV3)",
      "date": "December 2024",
      "points": [
        "Designed an end-to-end autonomous driving pipeline using CARLA simulator and Soft Actor-Critic (SAC) reinforcement learning.",
        "Integrated semantic segmentation with DeepLabV3 for scene understanding; implemented low-computation path planning models.",
        "Applied DAgger to fine-tune models in dynamic environments, achieving smoother lane alignment and better obstacle avoidance.",
        "Deployed optimized model for real-time performance on resource-constrained systems with minimal latency."
      ]
    },
    {
      "name": "EchoSight: Assistive Navigation Glasses for the Visually Impaired",
      "technologies": "YOLOv8, Roboflow, OpenCV, TTS",
      "date": "August 2024",
      "points": [
        "Developed wearable vision-based system for real-time object detection and navigation feedback via Bluetooth earbuds.",
        "Fine-tuned YOLOv8 with a custom dataset (50+ object classes), enabling 45+ FPS detection with positional awareness",
        "Integrated spatial direction and distance estimation using monocular vision and depth inference algorithms."
      ]
    }
  ],
  "skills": [
    {
      "category": "Languages",
      "items": ": Python, SQL, C++, Java"
    },
    {
      "category": "Technologies",
      "items": ": TensorFlow, PyTorch, OpenCV, YOLOv8, Hugging Face, LangChain, LLaMA, Scikit-Learn"
    },
    {
      "category": "Technologies/Frameworks",
      "items": ": Linux, MLflow, Roboflow, CVAT, GitHub"
    }
  ],
  "leadership": [
    {
      "organization": "ACS International Student Chapter",
      "duration": "Spring 2024 -- Present",
      "position": "President",
      "location": "VIT-AP",
      "points": [
        "Managed executive board of 5 members and ran weekly meetings to oversee progress in essential parts of the chapter.",
        "Led chapter of 30+ members to work towards goals that improve and promote community service, academics, and unity."
      ]
    }
  ]
}

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class ATSResumeGenerator:
    def __init__(self):
        self.setup()
    
    def setup(self):
        if 'GEMINI_API_KEY' not in os.environ:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize MongoDB and GridFS
        self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
        self.db = self.mongo_client["resumeDB"]
        self.fs = gridfs.GridFS(self.db)
        
        # Initialize collections
        self.ats_resumes = self.db.ats_resumes
        self.resume_logs = self.db.resume_logs
        self.resume_metadata = self.db.resume_metadata
    
    def log_operation(self, resume_id, operation, status, details=None, error=None):
        """Log all resume operations to MongoDB"""
        try:
            log_entry = {
                "resume_id": resume_id,
                "operation": operation,
                "status": status,
                "timestamp": datetime.now(),
                "details": details or {},
                "error": error
            }
            self.resume_logs.insert_one(log_entry)
            logger.info(f"Logged operation {operation} for resume {resume_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")
    
    def store_file_in_gridfs(self, file_path, resume_id, file_type, content_type):
        """Store file in GridFS and return file ID"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                return None
                
            with open(file_path, 'rb') as file:
                file_id = self.fs.put(
                    file.read(),
                    filename=f"{file_type}_resume_{resume_id}.{file_type}",
                    content_type=content_type,
                    metadata={
                        "resume_id": resume_id,
                        "file_type": file_type,
                        "original_path": file_path,
                        "uploaded_at": datetime.now(),
                        "file_size": os.path.getsize(file_path)
                    }
                )
            logger.info(f"{file_type.upper()} file stored in GridFS with ID: {file_id}")
            return file_id
        except Exception as e:
            logger.error(f"Failed to store {file_type} file in GridFS: {e}")
            return None
    
    def store_resume_metadata(self, resume_id, ats_data, generation_info):
        """Store comprehensive resume metadata"""
        try:
            metadata = {
                "resume_id": resume_id,
                "ats_data": ats_data,
                "generation_info": generation_info,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "version": 1,
                "status": "active"
            }
            
            # Update or insert metadata
            result = self.resume_metadata.update_one(
                {"resume_id": resume_id},
                {"$set": metadata, "$inc": {"version": 1}},
                upsert=True
            )
            
            logger.info(f"Resume metadata stored for ID: {resume_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to store resume metadata: {e}")
            return None

    def convert_resume_to_ats_format(self, resume_data):
        """Convert resume data to ATS-friendly JSON format using Gemini"""
        try:
            # Convert datetime objects and ObjectIds to strings before serializing
            def serialize_data(obj):
                from bson import ObjectId
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, dict):
                    return {key: serialize_data(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_data(item) for item in obj]
                else:
                    return obj
            
            serialized_data = serialize_data(resume_data)
            
            prompt = f"""
You are an expert resume writer and ATS optimization specialist. Convert the following resume data into a structured JSON format that is optimized for Applicant Tracking Systems (ATS).

Resume Data:
{json.dumps(serialized_data, indent=2, ensure_ascii=False)}

Please convert this into the following JSON structure. If any information is missing, mark it as "None" or provide an empty array/object as appropriate:
ANd give the returning dat in the same format as the example data is and make sure you won't madu up any things in there and only add the relevent course work and mention all the projects and experiences clearly in the json format.
example data, not to include in any one of those in the returing dat just include as mentioned json format and this is just for the example:
{json.dumps(resume_sample, indent=2)}
Guidelines:
1. Extract and optimize all relevant information from the resume data
2. Use action verbs and quantified achievements where possible
3. Ensure consistent formatting for dates (use -- between dates)
4. Group similar skills into logical categories
5. If information is missing or unclear, use "None" for strings or empty arrays for lists
6. Maintain professional language and ATS-friendly keywords
Mention all skills listed in the resume, and also make those ats optimized and include values and don't make up values if not give just don't include them.
And CHeck the example clearly and give the coursework according to the projects and experience related and make sure it will give all the projects and experiences clearily in the json format.

Return only the JSON structure, no additional text or explanation.
"""

            response = self.model.generate_content(prompt)
            
            # Clean up the response text to extract JSON
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Parse the JSON response
            ats_data = json.loads(response_text)
            logger.info("Successfully converted resume data to ATS format")
            return {"success": True, "data": ats_data}
            
        except Exception as e:
            logger.error(f"Error converting resume to ATS format: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_ats_resume(self, resume_id, resume_data):
        """Generate ATS-friendly resume in LaTeX and PDF format with comprehensive DB storage"""
        start_time = datetime.now()
        
        try:
            # Log the start of generation
            self.log_operation(resume_id, "generate_ats_resume", "started", {
                "input_data_size": len(str(resume_data)),
                "start_time": start_time
            })
            
            # First check if ATS resume already exists in database
            existing_resume = self.ats_resumes.find_one({"resume_id": resume_id})
            if existing_resume:
                logger.info(f"Found existing ATS resume for ID: {resume_id}")
                
                # Check if files actually exist in GridFS
                pdf_exists = self._check_file_exists_in_gridfs(existing_resume.get("pdf_file_id"))
                tex_exists = self._check_file_exists_in_gridfs(existing_resume.get("tex_file_id"))
                
                self.log_operation(resume_id, "retrieve_existing", "success", {
                    "pdf_exists": pdf_exists,
                    "tex_exists": tex_exists,
                    "from_database": True
                })
                
                return {
                    "success": True,
                    "ats_data": existing_resume["ats_data"],
                    "tex_path": existing_resume.get("tex_path"),
                    "pdf_path": existing_resume.get("pdf_path"),
                    "tex_file_id": existing_resume.get("tex_file_id"),
                    "pdf_file_id": existing_resume.get("pdf_file_id"),
                    "from_database": True,
                    "pdf_generated": pdf_exists,
                    "tex_generated": tex_exists,
                    "generated_at": existing_resume.get("generated_at")
                }

            # Convert resume data to ATS format using Gemini
            self.log_operation(resume_id, "convert_to_ats", "started")
            conversion_result = self.convert_resume_to_ats_format(resume_data)
            
            if not conversion_result["success"]:
                self.log_operation(resume_id, "convert_to_ats", "failed", error=conversion_result["error"])
                return {"success": False, "error": conversion_result["error"]}
            
            ats_data = conversion_result["data"]
            self.log_operation(resume_id, "convert_to_ats", "success", {
                "ats_sections": list(ats_data.keys())
            })
            
            # Create output directory
            output_dir = f"output/ats_resume_{resume_id}"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Generate LaTeX content
            self.log_operation(resume_id, "generate_latex", "started")
            latex_content = self.create_ats_latex_resume(ats_data)
            
            # Save LaTeX file
            tex_filename = os.path.join(output_dir, "ats_resume.tex")
            with open(tex_filename, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Store LaTeX file in GridFS
            tex_file_id = self.store_file_in_gridfs(tex_filename, resume_id, "tex", "text/plain")
            
            if tex_file_id:
                self.log_operation(resume_id, "store_tex_gridfs", "success", {
                    "file_id": str(tex_file_id),
                    "file_size": os.path.getsize(tex_filename)
                })
            else:
                self.log_operation(resume_id, "store_tex_gridfs", "failed")
            
            # Generate PDF with comprehensive logging
            pdf_path = None
            pdf_file_id = None
            pdf_generation_start = datetime.now()
            
            try:
                self.log_operation(resume_id, "generate_pdf", "started", {
                    "tex_file": tex_filename
                })
                
                # Run pdflatex with timeout and capture all output
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory', output_dir, tex_filename], 
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                pdf_generation_time = (datetime.now() - pdf_generation_start).total_seconds()
                
                # Log pdflatex execution details
                self.log_operation(resume_id, "pdflatex_execution", "completed", {
                    "exit_code": result.returncode,
                    "execution_time": pdf_generation_time,
                    "stdout_length": len(result.stdout) if result.stdout else 0,
                    "stderr_length": len(result.stderr) if result.stderr else 0
                })
                
                pdf_path = os.path.join(output_dir, 'ats_resume.pdf')
                
                # Check if PDF was actually created
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    # Store PDF file in GridFS
                    pdf_file_id = self.store_file_in_gridfs(pdf_path, resume_id, "pdf", "application/pdf")
                    
                    if pdf_file_id:
                        self.log_operation(resume_id, "generate_pdf", "success", {
                            "file_id": str(pdf_file_id),
                            "file_size": os.path.getsize(pdf_path),
                            "generation_time": pdf_generation_time
                        })
                    else:
                        self.log_operation(resume_id, "store_pdf_gridfs", "failed")
                else:
                    self.log_operation(resume_id, "generate_pdf", "failed", {
                        "exit_code": result.returncode,
                        "reason": "PDF file not created or empty"
                    })
                    pdf_path = None
                    
            except subprocess.TimeoutExpired:
                self.log_operation(resume_id, "generate_pdf", "failed", {
                    "error": "timeout",
                    "timeout_seconds": 60
                })
                pdf_path = None
            except FileNotFoundError:
                self.log_operation(resume_id, "generate_pdf", "failed", {
                    "error": "pdflatex_not_found"
                })
                pdf_path = None
            except Exception as e:
                self.log_operation(resume_id, "generate_pdf", "failed", {
                    "error": str(e)
                })
                pdf_path = None
            
            # Prepare comprehensive resume document for MongoDB
            generation_info = {
                "generation_time": (datetime.now() - start_time).total_seconds(),
                "tex_generated": tex_file_id is not None,
                "pdf_generated": pdf_file_id is not None,
                "output_directory": output_dir,
                "latex_content_length": len(latex_content)
            }
            
            resume_doc = {
                "resume_id": resume_id,
                "ats_data": ats_data,
                "tex_content": latex_content,
                "tex_path": tex_filename,
                "pdf_path": pdf_path,
                "tex_file_id": tex_file_id,
                "pdf_file_id": pdf_file_id,
                "generated_at": datetime.now(),
                "generation_info": generation_info,
                "type": "ats_resume",
                "status": "completed"
            }
            
            # Store main resume document
            result = self.ats_resumes.update_one(
                {"resume_id": resume_id},
                {"$set": resume_doc},
                upsert=True
            )
            
            # Store metadata
            self.store_resume_metadata(resume_id, ats_data, generation_info)
            
            self.log_operation(resume_id, "store_resume_document", "success", {
                "mongo_id": str(result.upserted_id) if result.upserted_id else "updated",
                "total_generation_time": generation_info["generation_time"]
            })
            
            logger.info(f"ATS resume generation completed for resume ID: {resume_id}")
            
            return {
                "success": True,
                "ats_data": ats_data,
                "tex_path": tex_filename,
                "pdf_path": pdf_path,
                "tex_file_id": str(tex_file_id) if tex_file_id else None,
                "pdf_file_id": str(pdf_file_id) if pdf_file_id else None,
                "from_database": False,
                "mongo_id": str(result.upserted_id) if result.upserted_id else None,
                "pdf_generated": pdf_path is not None and pdf_file_id is not None,
                "tex_generated": tex_file_id is not None,
                "generation_info": generation_info
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_operation(resume_id, "generate_ats_resume", "failed", error=error_msg)
            logger.error(f"Error generating ATS resume: {error_msg}")
            return {"success": False, "error": error_msg}
    
    def _check_file_exists_in_gridfs(self, file_id):
        """Check if file exists in GridFS"""
        if not file_id:
            return False
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)
            return self.fs.exists(file_id)
        except Exception as e:
            logger.warning(f"Error checking file in GridFS: {e}")
            return False
    
    def get_ats_file_from_gridfs(self, file_id):
        """Get file from GridFS by file ID with logging"""
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)
            
            logger.info(f"Retrieving file from GridFS with ID: {file_id}")
            
            # Get file from GridFS
            file_data = self.fs.get(file_id)
            content = file_data.read()
            
            # Log retrieval
            self.log_operation(
                file_data.metadata.get('resume_id', 'unknown'), 
                "retrieve_file_gridfs", 
                "success", 
                {
                    "file_id": str(file_id),
                    "file_size": len(content),
                    "file_type": file_data.metadata.get('file_type', 'unknown')
                }
            )
            
            logger.info(f"Successfully retrieved file, size: {len(content)} bytes")
            return content
            
        except Exception as e:
            logger.error(f"Error retrieving file from GridFS with ID {file_id}: {str(e)}")
            return None

    def create_ats_latex_resume(self, data):
        """Create LaTeX content for ATS-friendly resume"""
        template = generate_latex_template()
        
        header_content = generate_header(data)
        education_content = generate_education(data)
        coursework_content = generate_coursework(data)
        experience_content = generate_experience(data)
        projects_content = generate_projects(data)
        skills_content = generate_skills(data)
        leadership_content = generate_leadership(data)
        
        latex_content = template.replace("{HEADER_CONTENT}", header_content)
        latex_content = latex_content.replace("{EDUCATION_CONTENT}", education_content)
        latex_content = latex_content.replace("{COURSEWORK_CONTENT}", coursework_content)
        latex_content = latex_content.replace("{EXPERIENCE_CONTENT}", experience_content)
        latex_content = latex_content.replace("{PROJECTS_CONTENT}", projects_content)
        latex_content = latex_content.replace("{SKILLS_CONTENT}", skills_content)
        latex_content = latex_content.replace("{LEADERSHIP_CONTENT}", leadership_content)
        
        return latex_content
    
    def get_ats_resume_by_id(self, resume_id):
        """Get ATS resume from MongoDB by resume ID with comprehensive data"""
        try:
            logger.info(f"Retrieving ATS resume from database for ID: {resume_id}")
            
            # Get main resume document
            ats_resume = self.ats_resumes.find_one({"resume_id": resume_id})
            
            if ats_resume:
                # Get metadata
                metadata = self.resume_metadata.find_one({"resume_id": resume_id})
                
                # Get recent logs
                recent_logs = list(self.resume_logs.find(
                    {"resume_id": resume_id}
                ).sort("timestamp", -1).limit(10))
                
                # Check file existence
                pdf_exists = self._check_file_exists_in_gridfs(ats_resume.get('pdf_file_id'))
                tex_exists = self._check_file_exists_in_gridfs(ats_resume.get('tex_file_id'))
                
                self.log_operation(resume_id, "retrieve_resume", "success", {
                    "has_metadata": metadata is not None,
                    "logs_count": len(recent_logs),
                    "pdf_exists": pdf_exists,
                    "tex_exists": tex_exists
                })
                
                return {
                    "success": True, 
                    "data": ats_resume,
                    "metadata": metadata,
                    "recent_logs": recent_logs,
                    "file_status": {
                        "pdf_exists": pdf_exists,
                        "tex_exists": tex_exists
                    }
                }
            else:
                self.log_operation(resume_id, "retrieve_resume", "not_found")
                logger.warning(f"No ATS resume found in database for ID: {resume_id}")
                return {"success": False, "error": "ATS resume not found"}
                
        except Exception as e:
            error_msg = str(e)
            self.log_operation(resume_id, "retrieve_resume", "failed", error=error_msg)
            logger.error(f"Error retrieving ATS resume: {error_msg}")
            return {"success": False, "error": error_msg}
    
    def get_resume_logs(self, resume_id, limit=50):
        """Get logs for a specific resume ID"""
        try:
            logs = list(self.resume_logs.find(
                {"resume_id": resume_id}
            ).sort("timestamp", -1).limit(limit))
            
            return {"success": True, "logs": logs}
        except Exception as e:
            logger.error(f"Error retrieving logs for resume {resume_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup_old_files(self, resume_id):
        """Clean up old files for a resume ID"""
        try:
            # Find old files in GridFS
            old_files = self.fs.find({"metadata.resume_id": resume_id})
            
            deleted_count = 0
            for file in old_files:
                self.fs.delete(file._id)
                deleted_count += 1
            
            # Clean up file system
            output_dir = f"output/ats_resume_{resume_id}"
            if os.path.exists(output_dir):
                import shutil
                shutil.rmtree(output_dir)
            
            self.log_operation(resume_id, "cleanup_files", "success", {
                "gridfs_files_deleted": deleted_count,
                "filesystem_cleaned": True
            })
            
            return {"success": True, "files_deleted": deleted_count}
        except Exception as e:
            self.log_operation(resume_id, "cleanup_files", "failed", error=str(e))
            return {"success": False, "error": str(e)}


        
def load_json_data(json_file):
    with open(json_file, 'r') as f:
        return json.load(f)

def escape_latex_chars(text):
    replacements = {
        '%': '\\%',
        '&': '\\&',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}'
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text

def generate_header(data):
    personal = data['personal_info']
    header = f"""\\begin{{center}}
    {{\\Huge \\scshape {personal['name']}}} \\\\ \\vspace{{1pt}}
    {personal['address']} \\\\ \\vspace{{1pt}}
    \\small \\raisebox{{-0.1\\height}}\\faPhone\\ {personal['phone']} ~ \\href{{mailto:{personal['email']}}}{{\\raisebox{{-0.2\\height}}\\faEnvelope\\  \\underline{{{personal['email']}}}}} ~ 
    \\href{{{personal['linkedin']}}}{{\\raisebox{{-0.2\\height}}\\faLinkedin\\ \\underline{{{personal['linkedin_display']}}}}}  ~
    \\href{{{personal['github']}}}{{\\raisebox{{-0.2\\height}}\\faGithub\\ \\underline{{{personal['github_display']}}}}}
    \\vspace{{-8pt}}
\\end{{center}}"""
    return header

def generate_education(data):
    if 'education' not in data or not data['education']:
        return ""
    
    section = "%-----------EDUCATION-----------\n\\section{Education}\n  \\resumeSubHeadingListStart\n"
    
    for edu in data['education']:
        section += f"""    \\resumeSubheading
      {{{edu['institution']}}}{{{edu['duration']}}}
      {{{edu['degree']}}}{{{edu['location']}}}
"""
    
    section += "  \\resumeSubHeadingListEnd\n\n"
    return section

def generate_coursework(data):
    if 'coursework' not in data or not data['coursework']:
        return ""
    
    section = "%------RELEVANT COURSEWORK-------\n\\section{Relevant Coursework}\n"
    section += "    \\begin{multicols}{4}\n        \\begin{itemize}[itemsep=-5pt, parsep=3pt]\n"
    
    for course in data['coursework']:
        section += f"            \\item\\small {course}\n"
    
    section += "        \\end{itemize}\n    \\end{multicols}\n    \\vspace*{2.0\\multicolsep}\n\n"
    return section

def generate_experience(data):
    if 'experience' not in data or not data['experience']:
        return ""
    
    section = "%-----------EXPERIENCE-----------\n\\section{Experience}\n  \\resumeSubHeadingListStart\n\n"
    
    for exp in data['experience']:
        section += f"""    \\resumeSubheading
      {{{escape_latex_chars(exp['company'])}}}{{{exp['duration']}}}
      {{{escape_latex_chars(exp['position'])}}}{{{escape_latex_chars(exp['location'])}}}
      \\resumeItemListStart
"""
        for point in exp['points']:
            section += f"        \\resumeItem{{{escape_latex_chars(point)}}}\n"
        
        section += "      \\resumeItemListEnd\n\n"
    
    section += "  \\resumeSubHeadingListEnd\n\\vspace{-16pt}\n\n"
    return section

def generate_projects(data):
    if 'projects' not in data or not data['projects']:
        return ""
    
    section = "%-----------PROJECTS-----------\n\\section{Projects}\n    \\vspace{-5pt}\n    \\resumeSubHeadingListStart\n"
    
    for i, project in enumerate(data['projects']):
        section += f"""      \\resumeProjectHeading
          {{\\textbf{{{escape_latex_chars(project['name'])}}} $|$ \\emph{{{escape_latex_chars(project['technologies'])}}}}}{{{project['date']}}}
          \\resumeItemListStart
"""
        for point in project['points']:
            section += f"            \\resumeItem{{{escape_latex_chars(point)}}}\n"
        
        section += "          \\resumeItemListEnd"
        if i < len(data['projects']) - 1:
            section += " \n          \\vspace{-13pt}\n"
        else:
            section += " \n"
    
    section += "    \\resumeSubHeadingListEnd\n\\vspace{-15pt}\n\n"
    return section

def generate_skills(data):
    if 'skills' not in data or not data['skills']:
        return ""
    
    section = "%-----------PROGRAMMING SKILLS-----------\n\\section{Technical Skills}\n \\begin{itemize}[leftmargin=0.15in, label={}]\n    \\small{\\item{\n"
    
    for skill_category in data['skills']:
        section += f"     \\textbf{{{skill_category['category']}}}{{{skill_category['items']}}} \\\\\n"
    
    section += "    }}\n \\end{itemize}\n \\vspace{-16pt}\n\n"
    return section

def generate_leadership(data):
    if 'leadership' not in data or not data['leadership']:
        return ""
    
    section = "%-----------INVOLVEMENT---------------\n\\section{Leadership / Extracurricular}\n    \\resumeSubHeadingListStart\n"
    
    for leader in data['leadership']:
        section += f"""        \\resumeSubheading{{{escape_latex_chars(leader['organization'])}}}{{{leader['duration']}}}{{{escape_latex_chars(leader['position'])}}}{{{escape_latex_chars(leader['location'])}}}
            \\resumeItemListStart
"""
        for point in leader['points']:
            section += f"                \\resumeItem{{{escape_latex_chars(point)}}}\n"
        
        section += "            \\resumeItemListEnd\n"
    
    section += "    \\resumeSubHeadingListEnd\n\n"
    return section

def generate_latex_template():
    template = """\\documentclass[letterpaper,11pt]{article}

\\usepackage{latexsym}
\\usepackage[empty]{fullpage}
\\usepackage{titlesec}
\\usepackage{marvosym}
\\usepackage[usenames,dvipsnames]{color}
\\usepackage{verbatim}
\\usepackage{enumitem}
\\usepackage[hidelinks]{hyperref}
\\usepackage{fancyhdr}
\\usepackage[english]{babel}
\\usepackage{tabularx}
\\usepackage{fontawesome5}
\\usepackage{multicol}
\\setlength{\\multicolsep}{-3.0pt}
\\setlength{\\columnsep}{-1pt}
\\input{glyphtounicode}

\\pagestyle{fancy}
\\fancyhf{} % clear all header and footer fields
\\fancyfoot{}
\\renewcommand{\\headrulewidth}{0pt}
\\renewcommand{\\footrulewidth}{0pt}

% Adjust margins
\\addtolength{\\oddsidemargin}{-0.6in}
\\addtolength{\\evensidemargin}{-0.5in}
\\addtolength{\\textwidth}{1.19in}
\\addtolength{\\topmargin}{-.7in}
\\addtolength{\\textheight}{1.4in}

\\urlstyle{same}

\\raggedbottom
\\raggedright
\\setlength{\\tabcolsep}{0in}

% Sections formatting
\\titleformat{\\section}{
  \\vspace{-4pt}\\scshape\\raggedright\\large\\bfseries
}{}{0em}{}[\\color{black}\\titlerule \\vspace{-5pt}]

% Ensure that generate pdf is machine readable/ATS parsable
\\pdfgentounicode=1

%-------------------------
% Custom commands
\\newcommand{\\resumeItem}[1]{
  \\item\\small{
    {#1 \\vspace{-2pt}}
  }
}

\\newcommand{\\classesList}[4]{
    \\item\\small{
        {#1 #2 #3 #4 \\vspace{-2pt}}
  }
}

\\newcommand{\\resumeSubheading}[4]{
  \\vspace{-2pt}\\item
    \\begin{tabular*}{1.0\\textwidth}[t]{l@{\\extracolsep{\\fill}}r}
      \\textbf{#1} & \\textbf{\\small #2} \\\\
      \\textit{\\small#3} & \\textit{\\small #4} \\\\
    \\end{tabular*}\\vspace{-7pt}
}

\\newcommand{\\resumeSubSubheading}[2]{
    \\item
    \\begin{tabular*}{0.97\\textwidth}{l@{\\extracolsep{\\fill}}r}
      \\textit{\\small#1} & \\textit{\\small #2} \\\\
    \\end{tabular*}\\vspace{-7pt}
}

\\newcommand{\\resumeProjectHeading}[2]{
    \\item
    \\begin{tabular*}{1.001\\textwidth}{l@{\\extracolsep{\\fill}}r}
      \\small#1 & \\textbf{\\small #2}\\\\
    \\end{tabular*}\\vspace{-7pt}
}

\\newcommand{\\resumeSubItem}[1]{\\resumeItem{#1}\\vspace{-4pt}}

\\renewcommand\\labelitemi{$\\vcenter{\\hbox{\\tiny$\\bullet$}}$}
\\renewcommand\\labelitemii{$\\vcenter{\\hbox{\\tiny$\\bullet$}}$}

\\newcommand{\\resumeSubHeadingListStart}{\\begin{itemize}[leftmargin=0.0in, label={}]}
\\newcommand{\\resumeSubHeadingListEnd}{\\end{itemize}}
\\newcommand{\\resumeItemListStart}{\\begin{itemize}}
\\newcommand{\\resumeItemListEnd}{\\end{itemize}\\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%

\\begin{document}

{HEADER_CONTENT}

{EDUCATION_CONTENT}

{COURSEWORK_CONTENT}

{EXPERIENCE_CONTENT}

{PROJECTS_CONTENT}

{SKILLS_CONTENT}

{LEADERSHIP_CONTENT}

\\end{document}"""
    return template

def create_resume(json_file, output_dir="output"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    data = load_json_data(json_file)
    
    template = generate_latex_template()
    
    header_content = generate_header(data)
    education_content = generate_education(data)
    coursework_content = generate_coursework(data)
    experience_content = generate_experience(data)
    projects_content = generate_projects(data)
    skills_content = generate_skills(data)
    leadership_content = generate_leadership(data)
    
    latex_content = template.replace("{HEADER_CONTENT}", header_content)
    latex_content = latex_content.replace("{EDUCATION_CONTENT}", education_content)
    latex_content = latex_content.replace("{COURSEWORK_CONTENT}", coursework_content)
    latex_content = latex_content.replace("{EXPERIENCE_CONTENT}", experience_content)
    latex_content = latex_content.replace("{PROJECTS_CONTENT}", projects_content)
    latex_content = latex_content.replace("{SKILLS_CONTENT}", skills_content)
    latex_content = latex_content.replace("{LEADERSHIP_CONTENT}", leadership_content)
    
    tex_filename = os.path.join(output_dir, "resume.tex")
    with open(tex_filename, 'w') as f:
        f.write(latex_content)
    
    print(f"LaTeX file generated: {tex_filename}")
    
    try:
        subprocess.run(['pdflatex', '-output-directory', output_dir, tex_filename], 
                      check=True, capture_output=True)
        print(f"PDF generated: {os.path.join(output_dir, 'resume.pdf')}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating PDF: {e}")
        print("Make sure pdflatex is installed and in your PATH")
    except FileNotFoundError:
        print("pdflatex not found. Please install LaTeX distribution (TeX Live, MiKTeX, etc.)")

def test_with_sample_data():
    """Test function to generate resume with sample data and store in DB"""
    try:
        # Initialize the generator
        generator = ATSResumeGenerator()
        
        # Use sample data
        test_resume_id = "test_nithin_001"
        
        # Generate ATS resume
        result = generator.generate_ats_resume(test_resume_id, resume_sample)
        
        if result["success"]:
            print(f"Test successful! Resume generated for ID: {test_resume_id}")
            print(f"PDF generated: {result.get('pdf_generated', False)}")
            print(f"TeX generated: {result.get('tex_generated', False)}")
            print(f"Generation info: {result.get('generation_info', {})}")
            
            # Test retrieval
            retrieved = generator.get_ats_resume_by_id(test_resume_id)
            if retrieved["success"]:
                print(f"Retrieval test successful!")
                print(f"Logs count: {len(retrieved.get('recent_logs', []))}")
            
        else:
            print(f"Test failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_with_sample_data()
    else:
        create_resume("resume_data.json")