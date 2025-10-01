import os
import logging
from datetime import datetime
import json
from pathlib import Path
import json
from typing import Dict, Optional, List
from dotenv import load_dotenv
import PyPDF2
import docx
import google.generativeai as genai
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
class ResumeParser:
    def __init__(self):
        """Initialize resume parser with synchronous operations."""
        load_dotenv()
        try:
            # MongoDB setup
            self.mongo_client = MongoClient("mongodb://localhost:27017")
            self.db = self.mongo_client["resumeDB"]
            self.resumes = self.db["resumes"]
            self.fs = gridfs.GridFS(self.db)

            # Gemini setup
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            
            # # ChromaDB setup
            # self.chroma_client = chroma_client
            # if self.chroma_client:
            #     self.collection = self.chroma_client.get_or_create_collection("resumes")
            
        except Exception as e:
            logging.error(f"Initialization error: {e}")
            raise
    def _format_experience_data(self, experience_entries: List[Dict]) -> List[Dict]:
        print("experience_entries")
        formatted_entries = []
        
        # Add safety check
        if not experience_entries or not isinstance(experience_entries, list):
            print("No valid experience entries found")
            return []
        
        for entry in experience_entries:
            # Safety check for entry
            if not entry or not isinstance(entry, dict):
                print("Skipping invalid entry")
                continue
                
            formatted_entry = {
                'title': str(entry.get('title', '')).strip() if entry.get('title') else '',
                'company': str(entry.get('company', '')).strip() if entry.get('company') else '',
                'location': str(entry.get('location', '')).strip() if entry.get('location') else '',
                'duration': str(entry.get('duration', '')).strip() if entry.get('duration') else '',
                'employment_type': str(entry.get('employment_type', '')).strip() if entry.get('employment_type') else '',
                'responsibilities': [
                    str(resp).strip() for resp in entry.get('responsibilities', [])
                    if resp and str(resp).strip()
                ],
                'achievements': [
                    str(ach).strip() for ach in entry.get('achievements', [])
                    if ach and str(ach).strip()
                ],
                'technologies': [
                    str(tech).strip() for tech in entry.get('technologies', [])
                    if tech and str(tech).strip()
                ],
                'metrics': [
                    str(metric).strip() for metric in entry.get('metrics', [])
                    if metric and str(metric).strip()
                ]
            }
            
            # Only include entries with title and company
            if formatted_entry['title'] and formatted_entry['company']:
                formatted_entries.append(formatted_entry)
            else:
                print(f"Skipping entry without title/company: {formatted_entry}")
                
        return formatted_entries

    def get_recent_resumes_sync(self, limit: int = 10) -> List[Dict]:
        """Get recent resumes from MongoDB (synchronous)."""
        try:
            logging.info("Fetching recent resumes from MongoDB...")
            resumes = list(self.resumes.find().sort('upload_date', -1).limit(limit))
            logging.info(f"Found {len(resumes)} resumes")
            
            # Convert ObjectId to string for serialization
            for resume in resumes:
                resume['_id'] = str(resume['_id'])
                
            return resumes
        except Exception as e:
            logging.error(f"Error getting recent resumes: {str(e)}")
            return []
            
    def get_all_resumes_sync(self, user_id: str = None) -> List[Dict]:
        """Get all resumes from MongoDB (synchronous), optionally filtered by user_id."""
        try:
            # Build query based on user_id
            query = {}
            if user_id:
                query['user_id'] = user_id
                logging.info(f"Fetching resumes for user: {user_id}")
            else:
                logging.info("Fetching all resumes from MongoDB...")
            
            resumes = list(self.resumes.find(query).sort('upload_date', -1))
            logging.info(f"Found {len(resumes)} resumes")
            
            # Convert ObjectId to string for serialization
            for resume in resumes:
                resume['_id'] = str(resume['_id'])
                
            return resumes
        except Exception as e:
            logging.error(f"Error getting resumes: {str(e)}")
            return []
    
    def _extract_text(self, file_path: str) -> Optional[str]:
        """Extract text from resume file with multiple fallback methods."""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                # Try multiple PDF parsing methods
                text = self._extract_pdf_text(file_path)
            elif file_ext in ['.doc', '.docx']:
                doc = docx.Document(file_path)
                text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            return text.strip() if text else None
        except Exception as e:
            logging.error(f"Text extraction error: {str(e)}")
            return None
    
    def _extract_pdf_text(self, file_path: str) -> Optional[str]:
        """Extract text from PDF using multiple fallback methods."""
        text = None
        
        # Method 1: Try PyPDF2
        try:
            logging.info(f"Attempting PDF extraction with PyPDF2 for: {file_path}")
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ' '.join([page.extract_text() for page in reader.pages])
                if text and text.strip():
                    logging.info("Successfully extracted text with PyPDF2")
                    return text
        except Exception as e:
            logging.warning(f"PyPDF2 extraction failed: {str(e)}")
        
        # Method 2: Try pdfplumber
        try:
            import pdfplumber
            logging.info(f"Attempting PDF extraction with pdfplumber for: {file_path}")
            with pdfplumber.open(file_path) as pdf:
                text = ' '.join([page.extract_text() or '' for page in pdf.pages])
                if text and text.strip():
                    logging.info("Successfully extracted text with pdfplumber")
                    return text
        except ImportError:
            logging.warning("pdfplumber not available")
        except Exception as e:
            logging.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Method 3: Try pymupdf (fitz)
        try:
            import fitz  # PyMuPDF
            logging.info(f"Attempting PDF extraction with PyMuPDF for: {file_path}")
            doc = fitz.open(file_path)
            text = ' '.join([page.get_text() for page in doc])
            doc.close()
            if text and text.strip():
                logging.info("Successfully extracted text with PyMuPDF")
                return text
        except ImportError:
            logging.warning("PyMuPDF not available")
        except Exception as e:
            logging.warning(f"PyMuPDF extraction failed: {str(e)}")
        
        # Method 4: Try pdfminer
        try:
            from pdfminer.high_level import extract_text
            logging.info(f"Attempting PDF extraction with pdfminer for: {file_path}")
            text = extract_text(file_path)
            if text and text.strip():
                logging.info("Successfully extracted text with pdfminer")
                return text
        except ImportError:
            logging.warning("pdfminer not available")
        except Exception as e:
            logging.warning(f"pdfminer extraction failed: {str(e)}")
        
        logging.error(f"All PDF extraction methods failed for: {file_path}")
        return None
    
    def _clean_and_parse_response(self, text: str) -> Dict:
        """Clean and parse Gemini response."""
        try:
            # Find JSON content in the response
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if (start_idx == -1 or end_idx == 0):
                raise ValueError("No JSON found in response")
                
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
        except Exception as e:
            logging.error(f"Response parsing error: {str(e)}")
            return {}
    
    def parse_resume(self, file_path: str, user_id: str = None) -> Dict:
        """Parse resume and extract information, store file in GridFS with user association."""
        try:
            # Step 1: Store the PDF file in GridFS first
            original_filename = Path(file_path).name
            file_id = self._store_file_in_gridfs(file_path, original_filename)
            if not file_id:
                return {'success': False, 'error': 'Failed to store PDF file'}

            # Step 2: Extract text
            text = self._extract_text(file_path)
            if not text:
                logging.error(f"Text extraction failed for file: {file_path}")
                return {
                    'success': False, 
                    'error': 'Unable to extract text from PDF. The file may be corrupted, image-based, or in an unsupported format.',
                    'details': 'Try converting the PDF to text format or using a different PDF viewer to save as text.'
                }

            # Step 3: Enhanced prompt for comprehensive parsing with better projects detection
            prompt = f"""
                You are an expert resume parser. Analyze this resume text VERY CAREFULLY and extract ALL information into a comprehensive JSON structure. 
                Pay special attention to PROJECTS section which is often missed.
                
                CRITICAL INSTRUCTIONS:
                1. Look for ALL sections including: Experience, Education, Skills, Projects, Certifications, Awards, etc.
                2. PROJECTS section is MANDATORY - look for keywords like "Projects", "Personal Projects", "Academic Projects", "Portfolio", "Work"
                3. Extract EVERY piece of information, don't skip anything
                4. If you see project names, descriptions, technologies used - put them in projects section
                5. Look for GitHub links, portfolio links, project URLs
                
                Return ONLY a valid JSON object with this EXACT structure:
                {{
                    "personal_info": {{
                        "name": "Full name extracted from resume",
                        "email": "email@example.com",
                        "phone": "phone number",
                        "location": "city, state/country",
                        "linkedin": "LinkedIn URL if found",
                        "github": "GitHub URL if found", 
                        "website": "personal website URL",
                        "portfolio": "portfolio URL"
                    }},
                    "professional_summary": "Professional summary or objective text",
                    "objective": "Career objective if separate from summary",
                    "skills": {{
                        "technical_skills": ["skill1", "skill2"],
                        "programming_languages": ["Python", "Java", "JavaScript"],
                        "frameworks": ["React", "Django", "Spring"],
                        "tools": ["Git", "Docker", "AWS"],
                        "databases": ["MySQL", "MongoDB", "PostgreSQL"],
                        "cloud_platforms": ["AWS", "Azure", "GCP"],
                        "soft_skills": ["Leadership", "Communication"],
                        "languages": ["English", "Spanish"]
                    }},
                    "experience": [
                        {{
                            "title": "Job title",
                            "company": "Company name",
                            "location": "Job location",
                            "duration": "Start date - End date",
                            "employment_type": "Full-time/Part-time/Internship",
                            "responsibilities": ["responsibility 1", "responsibility 2"],
                            "achievements": ["achievement 1", "achievement 2"],
                            "technologies": ["tech1", "tech2"],
                            "metrics": ["quantified achievement"]
                        }}
                    ],
                    "education": [
                        {{
                            "degree": "Degree type",
                            "field_of_study": "Major/Field",
                            "institution": "University/School name",
                            "location": "Institution location",
                            "year": "Graduation year or date range",
                            "gpa": "GPA if mentioned",
                            "relevant_coursework": ["course1", "course2"],
                            "honors": ["honor1", "honor2"]
                        }}
                    ],
                    "projects": [
                        {{
                            "name": "Project name",
                            "description": "Detailed project description",
                            "technologies": ["tech1", "tech2", "tech3"],
                            "duration": "Project duration or date",
                            "link": "GitHub/demo link if available",
                            "achievements": ["project achievement 1", "project achievement 2"],
                            "type": "Personal/Academic/Professional"
                        }}
                    ],
                    "certifications": [
                        {{
                            "name": "Certification name",
                            "issuer": "Issuing organization",
                            "date": "Issue date",
                            "expiry": "Expiry date if applicable",
                            "credential_id": "ID if mentioned",
                            "link": "Verification link"
                        }}
                    ],
                    "publications": [
                        {{
                            "title": "Publication title",
                            "journal": "Journal/Conference name",
                            "date": "Publication date",
                            "authors": ["author1", "author2"],
                            "link": "Publication link"
                        }}
                    ],
                    "awards": [
                        {{
                            "title": "Award title",
                            "issuer": "Issuing organization",
                            "date": "Award date",
                            "description": "Award description"
                        }}
                    ],
                    "volunteer_experience": [
                        {{
                            "organization": "Organization name",
                            "role": "Volunteer role",
                            "duration": "Time period",
                            "description": "Description of volunteer work"
                        }}
                    ],
                    "additional_sections": {{
                        "interests": ["interest1", "interest2"],
                        "hobbies": ["hobby1", "hobby2"],
                        "references": ["reference info"],
                        "memberships": ["membership1", "membership2"],
                        "conferences": ["conference1", "conference2"],
                        "patents": ["patent info"],
                        "other_info": ["any other relevant information"]
                    }}
                }}

                IMPORTANT PARSING RULES:
                - NEVER return null values, use empty strings "" or empty arrays []
                - For missing sections, return empty arrays [] not null
                - Extract ALL projects mentioned - look for ANY project-related content
                - Look for GitHub repositories, personal projects, academic projects, capstone projects
                - Include project technologies even if listed separately
                - Parse dates in a consistent format
                - Extract metrics and quantified achievements
                - Look for multiple ways projects might be labeled (Portfolio, Work, Academic Projects, etc.)
                
                Resume text to parse:
                {text}
                
                Return ONLY the JSON object, no additional text, explanations, or formatting.
                """

            # Step 4: Generate response with better parameters for accuracy
            response = self._generate_text_sync(prompt)
            if not response:
                return {'success': False, 'error': 'Failed to generate analysis'}

            parsed_data = self._clean_and_parse_response(response)
            if not parsed_data:
                return {'success': False, 'error': 'Failed to parse response'}

            # Step 5: Validate and fix parsed data structure
            parsed_data = self._validate_and_fix_parsed_data(parsed_data)

            # Step 6: Format experience data
            if 'experience' in parsed_data:
                parsed_data['experience'] = self._format_experience_data(
                    parsed_data['experience']
                )

            # Step 7: Ensure projects section exists and is properly formatted
            if 'projects' not in parsed_data or not parsed_data['projects']:
                # Try to extract projects from other sections or raw text
                parsed_data['projects'] = self._extract_projects_fallback(text)

            # Step 8: Create comprehensive MongoDB document
            doc = {
                'file_id': file_id,  # GridFS file reference
                'original_filename': original_filename,
                'file_size': os.path.getsize(file_path),
                'file_type': Path(file_path).suffix.lower(),
                'raw_text': text,
                'parsed_data': parsed_data,
                'upload_date': datetime.now(),
                'last_updated': datetime.now(),
                'processing_status': 'completed',
                'metadata': {
                    'text_length': len(text),
                    'sections_found': list(parsed_data.keys()),
                    'parsing_version': '2.0'
                }
            }
            
            # Add user_id if provided for multi-user support
            if user_id:
                doc['user_id'] = user_id
                logging.info(f"Resume will be associated with user: {user_id}")

            # Step 9: Save to MongoDB
            result = self.resumes.insert_one(doc)
            print("result")
            resume_id = str(result.inserted_id)

            return {
                'success': True,
                'resume_id': resume_id,
                'file_id': str(file_id),
                'parsed_data': parsed_data,
                'metadata': doc['metadata']
            }

        except Exception as e:
            logging.error(f"Resume parsing error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _store_file_in_gridfs(self, file_path: str, filename: str) -> Optional[str]:
        """Store file in MongoDB GridFS."""
        try:
            with open(file_path, 'rb') as f:
                file_id = self.fs.put(
                    f,
                    filename=filename,
                    content_type=self._get_content_type(file_path),
                    upload_date=datetime.now(),
                    metadata={
                        'original_name': filename,
                        'file_size': os.path.getsize(file_path)
                    }
                )
            logging.info(f"Stored file in GridFS with ID: {file_id}")
            return file_id
        except Exception as e:
            logging.error(f"Error storing file in GridFS: {str(e)}")
            return None

    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension."""
        ext = Path(file_path).suffix.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return content_types.get(ext, 'application/octet-stream')

    def get_resume_file(self, file_id: str) -> Optional[bytes]:
        """Retrieve original file from GridFS."""
        try:
            file_data = self.fs.get(ObjectId(file_id))
            return file_data.read()
        except Exception as e:
            logging.error(f"Error retrieving file from GridFS: {str(e)}")
            return None

    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata from GridFS."""
        try:
            file_info = self.fs.get(ObjectId(file_id))
            print(file_info)
            return {
                'filename': file_info.filename,
                'content_type': file_info.content_type,
                'upload_date': file_info.upload_date,
                'length': file_info.length,
                'metadata': getattr(file_info, 'metadata', {})
            }
        except Exception as e:
            logging.error(f"Error getting file metadata: {str(e)}")
            return None
    def _generate_text_sync(self, prompt: str) -> str:
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,  # Lower temperature for more consistent parsing
                    'top_p': 0.8,        # More focused responses
                    'top_k': 20,         # Reduced for better accuracy
                    'max_output_tokens': 4096  # Ensure enough tokens for complete response
                }
            )
            return response.text
        except Exception as e:
            logging.error(f"Text generation error: {str(e)}")
            return None
    

    def get_resume_by_id_sync(self, resume_id: str) -> Optional[Dict]:
        """Get a specific resume by ID."""
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(resume_id)
            resume = self.resumes.find_one({"_id": object_id})
            
            if resume:
                # Convert ObjectId to string for serialization
                resume['_id'] = str(resume['_id'])
                logging.info(f"Found resume with ID: {resume_id}")
                return resume
            else:
                logging.warning(f"No resume found with ID: {resume_id}")
                return None
        except Exception as e:
            logging.error(f"Error getting resume by ID: {str(e)}")
            return None

    def get_resume_data(self, resume_id: str) -> Dict:
        """Get resume data by ID"""
        return self.get_resume_by_id_sync(resume_id)

    def generate_pdf(self, resume_data: Dict) -> bytes:
        """Generate PDF from resume data"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Add personal info
            personal_info = resume_data['parsed_data']['personal_info']
            story.append(Paragraph(f"{personal_info.get('name', '')}", styles['Title']))
            story.append(Paragraph(f"{personal_info.get('email', '')} | {personal_info.get('phone', '')}", styles['Normal']))
            story.append(Paragraph(f"{personal_info.get('location', '')}", styles['Normal']))
            story.append(Spacer(1, 12))

            # Add skills section
            if 'skills' in resume_data['parsed_data']:
                story.append(Paragraph('SKILLS', styles['Heading1']))
                skills_text = ', '.join(resume_data['parsed_data']['skills'])
                story.append(Paragraph(skills_text, styles['Normal']))
                story.append(Spacer(1, 12))

            # Add experience section
            if 'experience' in resume_data['parsed_data']:
                story.append(Paragraph('EXPERIENCE', styles['Heading1']))
                for exp in resume_data['parsed_data']['experience']:
                    story.append(Paragraph(f"{exp['title']} at {exp['company']}", styles['Heading2']))
                    story.append(Paragraph(exp['duration'], styles['Normal']))
                    for resp in exp['responsibilities']:
                        story.append(Paragraph(f"• {resp}", styles['Normal']))
                    story.append(Spacer(1, 12))

            # Add education section
            if 'education' in resume_data['parsed_data']:
                story.append(Paragraph('EDUCATION', styles['Heading1']))
                for edu in resume_data['parsed_data']['education']:
                    story.append(Paragraph(f"{edu['degree']}", styles['Heading2']))
                    story.append(Paragraph(f"{edu['institution']} | {edu['year']}", styles['Normal']))
                    story.append(Spacer(1, 12))

            doc.build(story)
            return buffer.getvalue()

        except Exception as e:
            logging.error(f"PDF generation error: {str(e)}")
            raise

    def save_parsed_resume(self, resume_data: Dict) -> bool:
        """Save parsed resume to MongoDB."""
        try:
            # Generate a unique ID if not provided
            if '_id' not in resume_data:
                resume_data['_id'] = ObjectId()

            # Ensure personal_info exists
            if 'personal_info' not in resume_data:
                resume_data['personal_info'] = {}

            # Add metadata
            resume_data.update({
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'version': 1
            })

            # Insert with upsert based on _id
            result = self.resumes.update_one(
                {'_id': resume_data['_id']},
                {'$set': resume_data},
                upsert=True
            )

            # Store embeddings if text available
            if 'raw_text' in resume_data and self.chroma_client:
                self._store_embeddings_sync(
                    str(resume_data['_id']), 
                    resume_data['raw_text']
                )

            return True

        except Exception as e:
            logging.error(f"Error saving resume: {str(e)}")
            return False

    def _validate_and_fix_parsed_data(self, data: Dict) -> Dict:
        """Validate and fix the parsed data structure to ensure all required fields exist."""
        
        # Define the expected structure with default values
        default_structure = {
            "personal_info": {
                "name": "", "email": "", "phone": "", "location": "",
                "linkedin": "", "github": "", "website": "", "portfolio": ""
            },
            "professional_summary": "",
            "objective": "",
            "skills": {
                "technical_skills": [], "programming_languages": [], "frameworks": [],
                "tools": [], "databases": [], "cloud_platforms": [],
                "soft_skills": [], "languages": []
            },
            "experience": [],
            "education": [],
            "projects": [],
            "certifications": [],
            "publications": [],
            "awards": [],
            "volunteer_experience": [],
            "additional_sections": {
                "interests": [], "hobbies": [], "references": [],
                "memberships": [], "conferences": [], "patents": [], "other_info": []
            }
        }
        
        # Merge with default structure to ensure all fields exist
        for key, default_value in default_structure.items():
            if key not in data:
                data[key] = default_value
            elif isinstance(default_value, dict):
                # For nested dictionaries, ensure all sub-keys exist
                for sub_key, sub_default in default_value.items():
                    if sub_key not in data[key]:
                        data[key][sub_key] = sub_default
        
        return data

    def _extract_projects_fallback(self, text: str) -> List[Dict]:
        """Fallback method to extract projects if main parsing missed them."""
        projects = []
        
        try:
            # Look for common project indicators in the text
            project_indicators = [
                'project', 'portfolio', 'github', 'developed', 'built', 'created',
                'designed', 'implemented', 'capstone', 'thesis'
            ]
            
            lines = text.split('\n')
            current_project = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Check if line might be a project title
                line_lower = line.lower()
                if any(indicator in line_lower for indicator in project_indicators):
                    # This might be project-related content
                    if len(line) < 100 and not line.endswith('.'):
                        # Likely a project title
                        if current_project:
                            projects.append(current_project)
                        
                        current_project = {
                            "name": line,
                            "description": "",
                            "technologies": [],
                            "duration": "",
                            "link": "",
                            "achievements": [],
                            "type": "Personal"
                        }
                    elif current_project:
                        # Likely project description
                        if not current_project["description"]:
                            current_project["description"] = line
                        else:
                            current_project["description"] += " " + line
                            
                        # Extract technologies from description
                        tech_keywords = [
                            'python', 'java', 'javascript', 'react', 'node', 'django',
                            'flask', 'mysql', 'mongodb', 'aws', 'docker', 'git'
                        ]
                        
                        for tech in tech_keywords:
                            if tech in line_lower and tech not in current_project["technologies"]:
                                current_project["technologies"].append(tech.title())
            
            # Add the last project if exists
            if current_project:
                projects.append(current_project)
                
            return projects[:5]  # Limit to 5 projects to avoid noise
            
        except Exception as e:
            logging.error(f"Error in projects fallback extraction: {e}")
            return []