import os
from typing import Dict, Optional, List
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import chromadb
from pymongo import MongoClient
import logging

class ColdEmailGenerator:
    def __init__(self):
        """Initialize cold email generator with Gemini."""
        load_dotenv()
        try:
            # Initialize Gemini
            self.gemini_key = os.getenv('GEMINI_API_KEY')
            genai.configure(api_key=self.gemini_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            self.embed_model = genai.GenerativeModel('embedding-001')
            
            # Initialize MongoDB
            self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
            self.db = self.mongo_client["resumeDB"]
            

            self.templates = self._load_email_templates()
            
        except Exception as e:
            logging.error(f"Initialization error: {str(e)}")
            raise
    def generate_email_sync(self, data: Dict) -> Dict:
        """Generate a punchy, high-response cold email with complete resume data"""
        try:
            resume_data = data['resume_data']
            parsed_data = resume_data.get('parsed_data', {})
            
            # Extract comprehensive personal information
            personal_info = parsed_data.get('personal_info', {})
            full_name = personal_info.get('name', 'Professional')
            email = personal_info.get('email', '')
            phone = personal_info.get('phone', '')
            location = personal_info.get('location', personal_info.get('address', ''))
            linkedin = personal_info.get('linkedin', '')
            
            # Extract detailed experience with achievements
            experience = parsed_data.get('experience', [])
            total_years = 0
            key_achievements = []
            current_role = "Professional"
            current_company = ""
            
            if experience and isinstance(experience, list):
                for exp in experience[:2]:  # Top 2 experiences
                    try:
                        if isinstance(exp, dict):
                            title = exp.get('title', exp.get('position', ''))
                            company = exp.get('company', exp.get('organization', ''))
                            duration = exp.get('duration', exp.get('period', ''))
                            achievements = exp.get('achievements', [])
                            description = exp.get('description', exp.get('responsibilities', ''))
                            
                            if not current_role or current_role == "Professional":
                                current_role = title or "Professional"
                                current_company = company or ""
                            
                            # Extract years of experience
                            if duration and isinstance(duration, str) and any(word in duration.lower() for word in ['year', 'yr']):
                                try:
                                    years_match = [int(s) for s in duration.split() if s.isdigit()]
                                    if years_match:
                                        total_years += max(years_match)
                                except:
                                    total_years += 1
                            
                            # Collect achievements
                            if achievements:
                                try:
                                    if isinstance(achievements, list):
                                        key_achievements.extend([str(ach)[:80] for ach in achievements[:2]])
                                    else:
                                        key_achievements.append(str(achievements)[:80])
                                except Exception as ach_error:
                                    logging.warning(f"Error processing achievements: {ach_error}")
                            
                            # Extract quantifiable results from description
                            if description:
                                try:
                                    import re
                                    # Convert description to string and then search for metrics
                                    desc_text = str(description).lower()
                                    metrics = re.findall(r'\d+%|\$\d+[kmb]?|\d+[kmb]?\+|\d+x', desc_text)
                                    if metrics:
                                        key_achievements.extend(metrics[:2])
                                except Exception as desc_error:
                                    logging.warning(f"Error processing description: {desc_error}")
                    except Exception as exp_error:
                        logging.warning(f"Error processing experience item: {exp_error}")
                        continue
            
            # Extract comprehensive skills
            skills = parsed_data.get('skills', [])
            all_skills = []
            if isinstance(skills, list):
                for skill_item in skills:
                    try:
                        if isinstance(skill_item, str):
                            all_skills.append(skill_item)
                        elif isinstance(skill_item, dict):
                            if 'items' in skill_item and isinstance(skill_item['items'], list):
                                all_skills.extend([str(item) for item in skill_item['items'][:3]])
                            elif 'name' in skill_item:
                                all_skills.append(str(skill_item['name']))
                            elif 'skill' in skill_item:
                                all_skills.append(str(skill_item['skill']))
                        else:
                            # Handle any other data type by converting to string
                            all_skills.append(str(skill_item))
                    except Exception as skill_error:
                        logging.warning(f"Error processing skill item {skill_item}: {skill_error}")
                        continue
            
            # Extract key projects with impact
            projects = parsed_data.get('projects', [])
            project_highlights = []
            for project in projects[:2]:  # Top 2 projects
                try:
                    if isinstance(project, dict):
                        name = project.get('name', project.get('title', ''))
                        description = project.get('description', '')
                        impact = project.get('achievements', project.get('results', ''))
                        technologies = project.get('technologies', project.get('tech_stack', []))
                        
                        if name:
                            proj_text = str(name)
                            if impact:
                                proj_text += f" - {str(impact)[:60]}"
                            elif description:
                                proj_text += f" - {str(description)[:60]}"
                            project_highlights.append(proj_text)
                except Exception as proj_error:
                    logging.warning(f"Error processing project: {proj_error}")
                    continue
            
            # Extract education highlights
            education = parsed_data.get('education', [])
            edu_highlight = ""
            if education and isinstance(education, list):
                top_edu = education[0]
                if isinstance(top_edu, dict):
                    degree = top_edu.get('degree', top_edu.get('qualification', ''))
                    institution = top_edu.get('institution', top_edu.get('school', ''))
                    if degree and institution:
                        edu_highlight = f"{degree} from {institution}"
            
            # Create comprehensive, punchy prompt
            recipient_name = data.get('recipient_name', 'Hiring Manager')
            company_name = data.get('company_name', 'Your Company')
            role = data.get('role', 'this opportunity')
            additional_context = data.get('additional_context', '')
            email_style = data.get('email_style', 'professional')
            
            prompt = f"""
            Create a PUNCHY, HIGH-RESPONSE cold email that gets replies. Use ALL the provided data to make it personal and compelling.

            SENDER PROFILE:
            Name: {full_name}
            Current Role: {current_role} at {current_company}
            Experience: {total_years}+ years
            Location: {location}
            Email: {email}
            LinkedIn: {linkedin}

            KEY ACHIEVEMENTS & METRICS:
            {chr(10).join([f"• {ach}" for ach in key_achievements[:3]])}

            TOP SKILLS:
            {', '.join(all_skills[:8])}

            PROJECT HIGHLIGHTS:
            {chr(10).join([f"• {proj}" for proj in project_highlights])}

            EDUCATION:
            {edu_highlight}

            TARGET:
            Recipient: {recipient_name}
            Company: {company_name}
            Role/Opportunity: {role}
            Context: {additional_context}
            Style: {email_style}

            EMAIL REQUIREMENTS:
            1. SUBJECT: Create a HOOKY subject line that gets opened (mention specific value/achievement)
            2. OPENING: Start with a compelling hook - specific achievement, mutual connection, or company insight
            3. VALUE PROP: 2-3 sentences max showing direct relevance and quantifiable impact
            4. SOCIAL PROOF: Quick mention of relevant experience/project that matters to them
            5. CALL TO ACTION: Simple, low-friction ask (15-min chat, coffee, quick call)
            6. TOTAL LENGTH: 80-120 words MAX (excluding signature)
            7. TONE: Confident but not pushy, professional but personable
            8. NO generic templates or corporate speak
            9. Include specific numbers/metrics where possible
            10. Make it feel like a human wrote it, not AI

            FORMAT:
            Subject: [Compelling subject line]

            Hi {recipient_name},

            [Hook - specific achievement or insight about their company]

            [Value proposition - how you can help them specifically with quantified results]

            [Social proof - relevant experience/project]

            [Simple call to action]

            Best,
            {full_name}
            {email}
            {phone}
            {linkedin}

            Make this email irresistible to reply to while keeping it authentic and concise.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.8,
                    'top_p': 0.9,
                    'top_k': 50,
                    'max_output_tokens': 800
                }
            )
            
            if not response.text:
                raise ValueError("No email content generated")
            
            # Extract subject line if provided
            email_text = response.text.strip()
            subject_line = ""
            
            if email_text.startswith("Subject:"):
                lines = email_text.split('\n')
                subject_line = lines[0].replace("Subject:", "").strip()
                email_text = '\n'.join(lines[1:]).strip()
            
            # Store email in history with comprehensive metadata
            email_data_enhanced = {
                'resume_data': resume_data,
                'recipient_name': recipient_name,
                'company_name': company_name,
                'role': role,
                'additional_context': additional_context,
                'email_style': email_style,
                'sender_name': full_name,
                'sender_email': email,
                'years_experience': total_years,
                'key_achievements': key_achievements[:3],
                'top_skills': all_skills[:8],
                'subject_line': subject_line
            }
            
            email_id = self._store_email_history(email_data_enhanced, email_text)
            
            return {
                'success': True,
                'email': email_text,
                'subject_line': subject_line,
                'email_id': email_id,
                'metadata': {
                    'word_count': len(email_text.split()),
                    'sender_name': full_name,
                    'years_experience': total_years,
                    'subject_line': subject_line,
                    'achievements_count': len(key_achievements)
                }
            }
            
        except Exception as e:
            logging.error(f"Enhanced email generation error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _store_email_history(self, email_data: Dict, generated_email: str) -> str:
        """Store generated email in history collection with enhanced metadata"""
        try:
            resume_data = email_data.get('resume_data', {})
            resume_id = str(resume_data.get('_id', ''))
            
            email_doc = {
                'resume_id': resume_id,
                'type': 'cold_email',
                'content': generated_email,
                'created_at': datetime.now(),
                'version': self._get_next_version(resume_id, 'cold_email'),
                'metadata': {
                    'recipient_name': email_data.get('recipient_name', ''),
                    'company_name': email_data.get('company_name', ''),
                    'role': email_data.get('role', ''),
                    'additional_context': email_data.get('additional_context', ''),
                    'email_style': email_data.get('email_style', 'professional'),
                    'subject_line': email_data.get('subject_line', ''),
                    'sender_name': email_data.get('sender_name', ''),
                    'sender_email': email_data.get('sender_email', ''),
                    'years_experience': email_data.get('years_experience', 0),
                    'key_achievements': email_data.get('key_achievements', []),
                    'top_skills': email_data.get('top_skills', []),
                    'word_count': len(generated_email.split()),
                    'generated_at': str(datetime.now())
                }
            }
            
            result = self.db.email_history.insert_one(email_doc)
            logging.info(f"Stored enhanced email history with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error storing email history: {str(e)}")
            return None

    def _get_next_version(self, resume_id: str, email_type: str) -> int:
        """Get next version number for email history"""
        try:
            last_version = self.db.email_history.find_one(
                {'resume_id': resume_id, 'type': email_type},
                sort=[('version', -1)]
            )
            return (last_version.get('version', 0) + 1) if last_version else 1
        except Exception as e:
            logging.error(f"Error getting next version: {str(e)}")
            return 1

    def get_email_history(self, resume_id: str, email_type: str = 'cold_email') -> List[Dict]:
        """Get email history for a resume with enhanced metadata"""
        try:
            history = list(self.db.email_history.find(
                {'resume_id': resume_id, 'type': email_type}
            ).sort('created_at', -1))
            
            # Convert ObjectIds to strings and ensure proper format
            for email in history:
                email['_id'] = str(email['_id'])
                
                # Ensure metadata exists with default values
                if 'metadata' not in email:
                    email['metadata'] = {}
                
                # Set default values for enhanced metadata
                email['metadata'].setdefault('company_name', 'Unknown Company')
                email['metadata'].setdefault('role', 'Unknown Role')
                email['metadata'].setdefault('recipient_name', 'Unknown Recipient')
                email['metadata'].setdefault('additional_context', '')
                email['metadata'].setdefault('email_style', 'professional')
                email['metadata'].setdefault('subject_line', '')
                email['metadata'].setdefault('sender_name', '')
                email['metadata'].setdefault('sender_email', '')
                email['metadata'].setdefault('years_experience', 0)
                email['metadata'].setdefault('key_achievements', [])
                email['metadata'].setdefault('top_skills', [])
                email['metadata'].setdefault('word_count', len(email.get('content', '').split()))
                email['metadata'].setdefault('generated_at', str(email.get('created_at', datetime.now())))
                
                # Ensure version exists
                email.setdefault('version', 1)
                
                # Ensure created_at is datetime
                if 'created_at' not in email:
                    email['created_at'] = datetime.now()
            
            return history
            
        except Exception as e:
            logging.error(f"Error getting email history: {str(e)}")
            return []

    def get_email_by_id(self, email_id: str) -> Dict:
        """Get specific email by ID"""
        try:
            from bson import ObjectId
            email = self.db.email_history.find_one({'_id': ObjectId(email_id)})
            if email:
                email['_id'] = str(email['_id'])
            return email
        except Exception as e:
            logging.error(f"Error getting email by ID: {str(e)}")
            return None

    def _load_email_templates(self) -> Dict[str, str]:
        """Load email templates for different scenarios."""
        return {
            'introduction': """
                Subject: {role_interest} Opportunity at {company_name}

                Dear {recipient_name},

                {introduction_para}

                {experience_highlight}

                {company_interest}

                {call_to_action}

                Best regards,
                {sender_name}
                {contact_info}
            """,
            'follow_up': """
                Subject: Following up - {role_interest} Position

                Dear {recipient_name},

                {follow_up_context}

                {additional_value}

                {closing}

                Best regards,
                {sender_name}
                {contact_info}
            """
        }

    def generate_email(self, email_data: Dict) -> Dict:
        """Generate a cold email based on provided data."""
        try:
            email_type = email_data.get('type', 'introduction')
            template = self.templates.get(email_type)
            
            if not template:
                raise ValueError(f"Invalid email type: {email_type}")
            
            # Generate content using Gemini
            prompt = self._create_email_prompt(email_data, email_type)
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            
            generated_content = response.text
            
            # Store in MongoDB
            email_id = self._store_email(email_data, generated_content)
            
            return {
                'success': True,
                'email_id': email_id,
                'content': generated_content
            }
            
        except Exception as e:
            logging.error(f"Email generation error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_email_prompt(self, email_data: Dict, email_type: str) -> str:
        """Create prompt for email generation."""
        base_prompt = """
        Generate a professional cold email with the following details:
        - Role: {role}
        - Company: {company}
        - Recipient: {recipient}
        - Key Skills: {skills}
        - Experience Highlights: {experience}
        - Company Research: {research}
        
        Make it:
        1. Concise (150-200 words)
        2. Professional but conversational
        3. Value-focused
        4. Specific to the company
        5. Clear call-to-action
        """
        
        return base_prompt.format(**email_data)

    def _store_email(self, email_data: Dict, content: str) -> str:
        """Store generated email in MongoDB."""
        email_doc = {
            'content': content,
            'metadata': email_data,
            'created_at': datetime.now(),
            'type': email_data.get('type', 'introduction')
        }
        
        result = self.db.cold_emails.insert_one(email_doc)
        return str(result.inserted_id)

    def generate_embeddings_sync(self, text: str):
        """Generate embeddings synchronously"""
        try:
            result = self.embed_model.embed_content(
                content=text,
                task_type="retrieval_document"
            )
            return result.embedding
        except Exception as e:
            logging.error(f"Embedding generation error: {str(e)}")
            return None

    def generate_text_sync(self, prompt: str):
        """Generate text synchronously"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40
                }
            )
            return response.text
        except Exception as e:
            logging.error(f"Text generation error: {str(e)}")
            return None