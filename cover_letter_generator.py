import google.generativeai as genai
from typing import Dict, Optional, List
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import chromadb
from datetime import datetime
import logging


class CoverLetterGenerator:
    def __init__(self, chroma_client: Optional[chromadb.Client] = None, api_key: Optional[str] = None):
        """Initialize the cover letter generator."""
        load_dotenv()
        
        try:
            # Initialize API keys
            self.api_key = api_key or os.getenv('GEMINI_API_KEY')
            if not self.api_key:
                raise ValueError("Gemini API key is required")
            
            # Configure Gemini
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Initialize MongoDB
            self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
            self.db = self.mongo_client["resumeDB"]
            
 
            self.required_fields = {
                'job_title', 'company_name', 'top_skills', 
                'key_achievements', 'interest_reason'
            }
            
            self.default_values = {
                'job_title': 'A relevant role',
                'company_name': 'Your Company',
                'hiring_manager': 'Hiring Manager',
                'top_skills': 'A strong background in the industry',
                'key_achievements': 'Led projects that improved efficiency by 30%',
                'interest_reason': 'Passionate about the industry and excited about this opportunity',
                'call_to_action': 'Looking forward to discussing this opportunity further',
                'applicant_name': '',
                'contact_info': '',
                'additional_context': ''
            }
            
        except Exception as e:
            print(f"Initialization error: {str(e)}")
            raise


    def generate_prompt(self, letter_data: Dict) -> str:
        """Generate AI prompt for cover letter creation."""
        return f"""
        Generate a professional, compelling cover letter with the following context:
        
        Role Details:
        - Position: {letter_data['job_title']}
        - Company: {letter_data['company_name']}
        - Addressee: {letter_data['hiring_manager']}
        
        Candidate Qualifications:
        - Key Skills: {letter_data['top_skills']}
        - Achievements: {letter_data['key_achievements']}
        - Unique Value: {letter_data.get('unique_value_proposition', '')}
        - Motivation: {letter_data['interest_reason']}
        
        Additional Context: {letter_data.get('additional_context', '')}
        
        Requirements:
        1. Structure in clear paragraphs:
           - Opening: Compelling hook that mentions the role and company
           - Body Paragraph 1: Focus on key skills and achievements with metrics
           - Body Paragraph 2: Connect experiences to company needs and culture
           - Closing: Strong call to action - {letter_data['call_to_action']}
        2. striclty to Word count: 300-400 words
        3. Use action verbs and specific metrics
        4. Include company research details
        5. Highlight unique value proposition
        6. Maintain professional tone while showing enthusiasm
        
        Format the letter with:
        - Proper spacing between paragraphs
        - Professional salutation and closing
        - Clear paragraph transitions
        """

    async def generate_cover_letter(self, data: Dict) -> Dict:
        try:
            # Extract resume data
                    
            personal_info = data.get('personal_info', {})
            experience = data.get('experience', [])
            skills = data.get('skills', [])
            
            # Format experience and skills for the prompt
            recent_experience = experience[0] if experience else {}
            key_skills = ', '.join(skills[:5]) if skills else ''
            
            prompt = f"""
            Generate a professional cover letter for:
            - Job: {data.get('job_title')}
            - Company: {data.get('company_name')}
            - Candidate: {personal_info.get('name')}
            
            Use these key points:
            - Recent role: {recent_experience.get('title')} at {recent_experience.get('company')}
            - Key skills: {key_skills}
            
            Make it professional, concise, and highlight relevant experience.
            """
            
            response = await self.model.generate_content_async(prompt)
            cover_letter = self._format_letter(response.text, data)
            
            return {
                'success': True,
                'cover_letter': cover_letter
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    def customize_cover_letter(self, resume_data: Dict, company_name: str, position: str, job_description: str, additional_context: str = '') -> Dict:
        """Generate comprehensive, personalized cover letter with complete resume data"""
        try:
            logging.info(f"Starting enhanced cover letter generation for position: {position} at {company_name}")
            
            if not all([company_name, position, job_description]):
                return {
                    'success': False,
                    'error': 'Company name, position, and job description are required'
                }

            # Extract comprehensive resume data
            parsed_data = resume_data.get('parsed_data', {})
            personal_info = parsed_data.get('personal_info', {})
            experience = parsed_data.get('experience', [])
            skills = parsed_data.get('skills', [])
            education = parsed_data.get('education', [])
            projects = parsed_data.get('projects', [])
            certifications = parsed_data.get('certifications', [])
            
            logging.info(f"Extracted comprehensive data - Skills: {len(skills)}, Experience: {len(experience)}, Projects: {len(projects)}")

            # Extract and format complete personal information
            full_name = personal_info.get('name', 'Professional Candidate')
            email = personal_info.get('email', '')
            phone = personal_info.get('phone', '')
            location = personal_info.get('location', personal_info.get('address', ''))
            linkedin = personal_info.get('linkedin', '')
            portfolio = personal_info.get('portfolio', personal_info.get('website', ''))
            
            # Build complete contact header
            contact_lines = [full_name]
            if email: contact_lines.append(email)
            if phone: contact_lines.append(phone)
            if location: contact_lines.append(location)
            if linkedin: contact_lines.append(f"LinkedIn: {linkedin}")
            if portfolio: contact_lines.append(f"Portfolio: {portfolio}")
            
            # Extract and format comprehensive skills
            all_skills = []
            if isinstance(skills, list):
                for skill_item in skills:
                    if isinstance(skill_item, str):
                        all_skills.append(skill_item)
                    elif isinstance(skill_item, dict):
                        if 'items' in skill_item:
                            if isinstance(skill_item['items'], list):
                                all_skills.extend([str(item) for item in skill_item['items']])
                            else:
                                all_skills.append(str(skill_item['items']))
                        elif 'name' in skill_item:
                            all_skills.append(str(skill_item['name']))
                        elif 'skill' in skill_item:
                            all_skills.append(str(skill_item['skill']))
            
            # Extract comprehensive experience with achievements
            experience_details = []
            total_years = 0
            for exp in experience[:3]:  # Top 3 experiences
                if isinstance(exp, dict):
                    title = exp.get('title', exp.get('position', 'Professional Role'))
                    company = exp.get('company', exp.get('organization', 'Leading Organization'))
                    duration = exp.get('duration', exp.get('period', ''))
                    description = exp.get('description', exp.get('responsibilities', ''))
                    achievements = exp.get('achievements', [])
                    
                    # Calculate years from duration
                    if duration and any(word in duration.lower() for word in ['year', 'yr']):
                        try:
                            years_match = [int(s) for s in duration.split() if s.isdigit()]
                            if years_match:
                                total_years += max(years_match)
                        except:
                            total_years += 1
                    
                    exp_text = f"{title} at {company}"
                    if duration:
                        exp_text += f" ({duration})"
                    
                    if description:
                        exp_text += f" - {description[:200]}"
                    
                    if achievements:
                        achievement_text = ", ".join([str(ach)[:100] for ach in achievements[:2]])
                        exp_text += f". Key achievements: {achievement_text}"
                    
                    experience_details.append(exp_text)
            
            # Extract relevant projects
            project_details = []
            for project in projects[:3]:  # Top 3 projects
                if isinstance(project, dict):
                    name = project.get('name', project.get('title', 'Professional Project'))
                    description = project.get('description', '')
                    technologies = project.get('technologies', project.get('tech_stack', []))
                    achievements = project.get('achievements', project.get('results', ''))
                    
                    proj_text = f"{name}"
                    if technologies:
                        if isinstance(technologies, list):
                            tech_str = ", ".join([str(tech) for tech in technologies[:5]])
                        else:
                            tech_str = str(technologies)
                        proj_text += f" (Technologies: {tech_str})"
                    
                    if description:
                        proj_text += f" - {description[:150]}"
                    
                    if achievements:
                        proj_text += f". Impact: {str(achievements)[:100]}"
                    
                    project_details.append(proj_text)
            
            # Extract education
            education_details = []
            for edu in education[:2]:  # Top 2 education entries
                if isinstance(edu, dict):
                    degree = edu.get('degree', edu.get('qualification', 'Professional Qualification'))
                    institution = edu.get('institution', edu.get('school', 'Reputable Institution'))
                    year = edu.get('year', edu.get('graduation_year', ''))
                    gpa = edu.get('gpa', '')
                    
                    edu_text = f"{degree} from {institution}"
                    if year:
                        edu_text += f" ({year})"
                    if gpa:
                        edu_text += f", GPA: {gpa}"
                    
                    education_details.append(edu_text)
            
            # Extract certifications
            cert_details = []
            for cert in certifications[:3]:  # Top 3 certifications
                if isinstance(cert, dict):
                    name = cert.get('name', cert.get('title', str(cert)))
                    issuer = cert.get('issuer', cert.get('organization', ''))
                    year = cert.get('year', cert.get('date', ''))
                    
                    cert_text = name
                    if issuer:
                        cert_text += f" (from {issuer})"
                    if year:
                        cert_text += f" - {year}"
                    
                    cert_details.append(cert_text)
                elif isinstance(cert, str):
                    cert_details.append(cert)

            # Create comprehensive prompt with all data
            prompt = f"""
            Create a compelling, professional cover letter that is punchy, engaging, and completely personalized. Use ALL the provided information to create a comprehensive letter with NO placeholders or blanks.

            COMPLETE CANDIDATE PROFILE:
            Name: {full_name}
            Email: {email}
            Phone: {phone}
            Location: {location}
            LinkedIn: {linkedin}
            Portfolio: {portfolio}

            PROFESSIONAL EXPERIENCE ({total_years}+ years):
            {chr(10).join([f"• {exp}" for exp in experience_details])}

            TECHNICAL SKILLS & EXPERTISE:
            {', '.join(all_skills[:15])}

            KEY PROJECTS:
            {chr(10).join([f"• {proj}" for proj in project_details])}

            EDUCATION:
            {chr(10).join([f"• {edu}" for edu in education_details])}

            CERTIFICATIONS:
            {chr(10).join([f"• {cert}" for cert in cert_details])}

            TARGET OPPORTUNITY:
            Company: {company_name}
            Position: {position}
            Job Requirements: {job_description}
            Additional Context: {additional_context}

            INSTRUCTIONS:
            1. Create a HOOKY, attention-grabbing opening that immediately connects the candidate's unique value to the role
            2. Write in a confident, professional tone with personality - not templated corporate speak
            3. Strategically match the candidate's experience, projects, and skills to the job requirements
            4. Include specific achievements, technologies, and quantifiable results from their background
            5. Show deep understanding of the company and role - make it feel personalized
            6. Use action verbs and compelling language that makes them stand out
            7. End with a confident, forward-looking call to action
            8. Fill the letter with actual data - NO placeholders, brackets, or generic statements
            9. Make it 350-450 words with punchy paragraphs
            10. Include a compelling subject line suggestion

            FORMAT:
            Subject Line: [Compelling subject line for this application]

            [Date]

            Dear Hiring Manager / [Specific name if mentioned in job posting],

            [Compelling opening paragraph with hook]

            [Experience and skills paragraph with specific examples]

            [Projects and achievements paragraph with quantifiable results]

            [Company connection and enthusiasm paragraph]

            [Strong closing with call to action]

            Sincerely,
            {full_name}

            Make this cover letter irresistible and memorable while maintaining complete professionalism.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.8,
                    'top_p': 0.95,
                    'top_k': 50,
                    'max_output_tokens': 1500
                }
            )

            if not response.text:
                raise ValueError("No content generated")

            # Extract subject line if provided
            letter_text = response.text.strip()
            subject_line = ""
            
            if letter_text.startswith("Subject Line:"):
                lines = letter_text.split('\n')
                subject_line = lines[0].replace("Subject Line:", "").strip()
                letter_text = '\n'.join(lines[1:]).strip()

            # Format the complete letter with full contact information
            today = datetime.now().strftime("%B %d, %Y")
            
            # Build complete header
            contact_header = '\n'.join(contact_lines)
            
            formatted_letter = f"{contact_header}\n\n{today}\n\n{letter_text}"

            # Store in MongoDB with comprehensive metadata
            letter_data = {
                'resume_id': str(resume_data.get('_id')),
                'content': formatted_letter,
                'created_at': datetime.now(),
                'metadata': {
                    'company_name': company_name,
                    'position': position,
                    'additional_context': additional_context,
                    'subject_line': subject_line,
                    'word_count': len(formatted_letter.split()),
                    'generated_at': str(datetime.now()),
                    'candidate_name': full_name,
                    'candidate_email': email,
                    'years_experience': total_years,
                    'skills_count': len(all_skills),
                    'projects_count': len(project_details),
                    'education_count': len(education_details)
                }
            }
            
            # Add version number
            letter_data['version'] = self._get_next_version(str(resume_data.get('_id')))
            
            # Store in cover_letters collection
            self.db.cover_letters.insert_one(letter_data)

            return {
                'success': True,
                'cover_letter': formatted_letter,
                'subject_line': subject_line,
                'metadata': {
                    'word_count': len(formatted_letter.split()),
                    'generated_at': str(datetime.now()),
                    'candidate_name': full_name,
                    'years_experience': total_years,
                    'subject_line': subject_line
                }
            }

        except Exception as e:
            logging.error(f"Enhanced cover letter generation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _format_letter(self, content: str, letter_data: Dict) -> str:
        """Format the cover letter with proper structure"""
        today = datetime.now().strftime("%B %d, %Y")
        
        # Add header with contact information
        header = ""
        if letter_data.get('applicant_name') and letter_data.get('contact_info'):
            header = f"{letter_data['applicant_name']}\n{letter_data['contact_info']}\n\n"

        # Clean and structure the content
        content = content.strip()
        paragraphs = content.split('\n\n')
        formatted_content = '\n\n'.join(p.strip() for p in paragraphs)

        return f"{header}{today}\n\n{formatted_content}"
    def format_letter(self, content: str, letter_data: Dict) -> str:
        """Format the cover letter with proper structure and contact information."""
        # Add header with contact information if provided
        header = ""
        if letter_data['applicant_name'] and letter_data['contact_info']:
            header = f"{letter_data['applicant_name']}\n{letter_data['contact_info']}\n\n"

        # Add date
        date = datetime.now().strftime("%B %d, %Y\n\n")

        # Clean and structure the content
        content = content.strip()
        paragraphs = content.split('\n\n')
        formatted_content = '\n\n'.join(p.strip() for p in paragraphs)

        return f"{header}{date}{formatted_content}"

    async def regenerate_with_feedback(self, letter_data: Dict, feedback: str) -> Dict:
        """Regenerate cover letter based on feedback."""
        try:
            # Fill in missing fields with defaults before regenerating
            for key, default_value in self.default_values.items():
                if not letter_data.get(key):
                    letter_data[key] = default_value

            enhanced_prompt = f"""
            Previous cover letter needed improvement because: {feedback}
            
            Please regenerate with these specific improvements while maintaining all other quality requirements.
            
            {self.generate_prompt(letter_data)}
            """
            
            response = await self.model.generate_content_async(enhanced_prompt)
            cover_letter = self.format_letter(response.text, letter_data)
            
            return {
                'success': True,
                'cover_letter': cover_letter,
                'metadata': {
                    'generated_at': str(datetime.now()),
                    'regenerated': True,
                    'original_feedback': feedback,
                    'word_count': len(cover_letter.split())
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Cover letter regeneration failed: {str(e)}"
            }
    def customize_cover_letter_v2(self, resume_data: Dict, company_name: str, position: str, 
                             job_description: str, additional_context: str = '') -> Dict:
        """Generate customized cover letter (alternative method)"""
        try:
            parsed_data = resume_data.get('parsed_data', {})
            personal_info = parsed_data.get('personal_info', {})
            
            # Get relevant experience and skills with safe handling
            experience = parsed_data.get('experience', [])
            skills = parsed_data.get('skills', [])
            
            # Safely format experience
            experience_text = 'Not specified'
            if experience and isinstance(experience, list):
                try:
                    exp_items = []
                    for exp in experience[:3]:
                        if isinstance(exp, dict):
                            title = exp.get('title') or exp.get('position', '')
                            company = exp.get('company', '')
                            if title:
                                exp_items.append(f"{title} at {company}" if company else title)
                    experience_text = ', '.join(exp_items) if exp_items else str(experience[:3])
                except:
                    experience_text = str(experience[:3]) if len(experience) >= 3 else str(experience)
            
            # Safely format skills
            skills_text = 'Not specified'
            if skills:
                try:
                    if isinstance(skills, list):
                        if skills and isinstance(skills[0], str):
                            skills_text = ', '.join(skills[:8])
                        elif skills and isinstance(skills[0], dict):
                            skill_items = []
                            for skill_cat in skills[:5]:
                                if 'items' in skill_cat:
                                    skill_items.append(str(skill_cat['items']))
                            skills_text = ', '.join(skill_items) if skill_items else str(skills[:8])
                        else:
                            skills_text = str(skills[:8])
                    else:
                        skills_text = str(skills)
                except:
                    skills_text = str(skills)
            
            prompt = f"""
            Generate a professional cover letter with the following details:
            
            Applicant: {personal_info.get('name', 'Candidate')}
            Company: {company_name}
            Position: {position}
            
            Job Description: {job_description}
            
            Resume Experience: {experience_text}
            Key Skills: {skills_text}
            
            Additional Context: {additional_context}
            
            Requirements:
            1. Professional business letter format
            2. Personalized to the company and role
            3. Highlight relevant experience and skills
            4. Show enthusiasm and cultural fit
            5. Strong opening and closing
            6. 3-4 paragraphs, 250-400 words
            
            Include proper salutation and signature.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            
            # Store cover letter in history
            letter_data = {
                'resume_data': resume_data,
                'company_name': company_name,
                'position': position,
                'job_description': job_description,
                'additional_context': additional_context
            }
            
            letter_id = self._store_cover_letter_history(letter_data, response.text)
            
            return {
                'success': True,
                'cover_letter': response.text,
                'letter_id': letter_id
            }
            
        except Exception as e:
            logging.error(f"Cover letter generation error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _store_cover_letter_history(self, letter_data: Dict, generated_letter: str) -> str:
        """Store generated cover letter in history collection"""
        try:
            resume_data = letter_data.get('resume_data', {})
            resume_id = str(resume_data.get('_id', ''))
            
            letter_doc = {
                'resume_id': resume_id,
                'type': 'cover_letter',
                'content': generated_letter,
                'metadata': {
                    'company_name': letter_data.get('company_name', ''),
                    'position': letter_data.get('position', ''),
                    'job_description': letter_data.get('job_description', ''),
                    'additional_context': letter_data.get('additional_context', '')
                },
                'created_at': datetime.now(),
                'version': self._get_next_version(resume_id, 'cover_letter')
            }
            
            result = self.db.cover_letter_history.insert_one(letter_doc)
            logging.info(f"Stored cover letter history with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error storing cover letter history: {str(e)}")
            return None

    def _get_next_version(self, resume_id: str) -> int:
        """Get the next version number for a resume's cover letters"""
        try:
            # Find the highest version number for this resume
            latest = self.db.cover_letters.find_one(
                {'resume_id': resume_id},
                sort=[('version', -1)]
            )
            
            if latest and 'version' in latest:
                return latest['version'] + 1
            else:
                return 1
                
        except Exception as e:
            logging.error(f"Error getting next version: {str(e)}")
            return 1
        try:
            # Find the highest version number for this resume
            latest = self.db.cover_letters.find_one(
                {'resume_id': resume_id},
                sort=[('version', -1)]
            )
            
            if latest and 'version' in latest:
                return latest['version'] + 1
            else:
                return 1
                
        except Exception as e:
            logging.error(f"Error getting next version: {str(e)}")
            return 1

    def get_cover_letter_history(self, resume_id: str) -> List[Dict]:
        """Get cover letter history for a resume"""
        try:
            # Get from cover_letters collection (not cover_letter_history)
            history = list(self.db.cover_letters.find(
                {'resume_id': resume_id}
            ).sort('created_at', -1))
            
            # Convert ObjectIds to strings and ensure proper structure
            for letter in history:
                letter['_id'] = str(letter['_id'])
                
                # Ensure metadata exists for older records
                if 'metadata' not in letter:
                    letter['metadata'] = {
                        'company_name': letter.get('company_name', 'Unknown Company'),
                        'position': letter.get('position', 'Unknown Position'),
                        'additional_context': '',
                        'word_count': len(letter.get('content', '').split()),
                        'generated_at': str(letter.get('created_at', datetime.now()))
                    }
                
                # Ensure version exists
                if 'version' not in letter:
                    letter['version'] = 1
            
            return history
            
        except Exception as e:
            logging.error(f"Error getting cover letter history: {str(e)}")
            return []

    def get_cover_letter_by_id(self, letter_id: str) -> Dict:
        """Get specific cover letter by ID"""
        try:
            from bson import ObjectId
            letter = self.db.cover_letter_history.find_one({'_id': ObjectId(letter_id)})
            if letter:
                letter['_id'] = str(letter['_id'])
            return letter
        except Exception as e:
            logging.error(f"Error getting cover letter by ID: {str(e)}")
            return None