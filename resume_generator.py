'''Not used just a keep up file '''


import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import json
import logging
from pymongo import MongoClient
import numpy as np

# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# from init_databases import init_databases

class ResumeGenerator:
    def __init__(self):
        """Initialize the resume generator."""
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
            
            # Initialize ChromaDB
            # self.chroma_client = chroma_client or chromadb.PersistentClient(
            #     path="./data/chromadb"
            # )
            
            # try:
            #     self.collection = self.chroma_client.get_collection("resume_embeddings")
            # except:
            #     self.collection = self.chroma_client.create_collection(
            #         name="resume_embeddings",
            #         metadata={"hnsw:space": "cosine"}
            #     )
            
            # Load NLP model
            #self.nlp = spacy.load("en_core_web_lg")
            
            # Load section prompts and templates
            self.section_prompts = self._initialize_prompts()
            self.templates = self._load_templates()
            
            # Initialize collections
            self.resumes = self.db["resumes"]
            
        except Exception as e:
            logging.error(f"Initialization error: {str(e)}")
            raise
    # Add this method in the ResumeGenerator class
    def _group_skills_by_category(self, skills: List[str]) -> Dict[str, List[str]]:
        """Group skills into meaningful categories"""
        try:
            # Default categories
            categories = {
                'Programming Languages': [],
                'Frameworks & Tools': [],
                'Cloud & DevOps': [],
                'Databases': [],
                'Soft Skills': [],
                'Other': []
            }

            # Keyword-based categorization
            category_keywords = {
                'Programming Languages': [
                    'python', 'java', 'javascript', 'c++', 'ruby', 'php', 'typescript',
                    'golang', 'rust', 'swift', 'kotlin'
                ],
                'Frameworks & Tools': [
                    'react', 'angular', 'vue', 'django', 'flask', 'spring', 'node',
                    'docker', 'kubernetes', 'git', 'jenkins'
                ],
                'Cloud & DevOps': [
                    'aws', 'azure', 'gcp', 'cloud', 'devops', 'ci/cd', 'terraform',
                    'ansible', 'serverless'
                ],
                'Databases': [
                    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
                    'oracle', 'dynamodb'
                ],
                'Soft Skills': [
                    'leadership', 'communication', 'teamwork', 'management', 'agile',
                    'problem solving', 'analytical'
                ]
            }

            for skill in skills:
                skill_lower = skill.lower()
                categorized = False
                
                for category, keywords in category_keywords.items():
                    if any(keyword in skill_lower for keyword in keywords):
                        categories[category].append(skill)
                        categorized = True
                        break
                
                if not categorized:
                    categories['Other'].append(skill)

            # Remove empty categories
            return {k: v for k, v in categories.items() if v}

        except Exception as e:
            logging.error(f"Skills grouping error: {str(e)}")
            return {'Other': skills}
    def _calculate_section_score(self, section_data: any) -> float:
        """Calculate quality score for a resume section"""
        try:
            if not section_data:
                return 0.0
                
            score = 0.0
            
            if isinstance(section_data, list):
                # For sections like skills, experience, education
                if not section_data:
                    return 0.0
                    
                # Calculate based on completeness and quality
                if all(isinstance(item, dict) for item in section_data):
                    # For structured sections like experience, education
                    required_fields = {
                        'experience': ['title', 'company', 'duration', 'responsibilities'],
                        'education': ['degree', 'institution', 'year'],
                        'skills': ['name', 'level']
                    }
                    
                    # Determine section type by checking first item's keys
                    first_item = section_data[0]
                    section_type = None
                    for type_name, fields in required_fields.items():
                        if any(field in first_item for field in fields):
                            section_type = type_name
                            break
                    
                    if section_type:
                        fields = required_fields[section_type]
                        field_scores = []
                        
                        for item in section_data:
                            filled_fields = sum(1 for field in fields if field in item and item[field])
                            field_scores.append(filled_fields / len(fields))
                        
                        score = (sum(field_scores) / len(field_scores)) * 100
                    else:
                        # For simple list sections
                        score = min(100, len(section_data) * 10)  # 10 points per item, max 100
                        
                else:
                    # For simple lists like skills
                    score = min(100, len(section_data) * 10)
                    
            elif isinstance(section_data, dict):
                # For sections like personal_info
                required_fields = ['name', 'email', 'phone', 'location']
                filled_fields = sum(1 for field in required_fields if field in section_data and section_data[field])
                score = (filled_fields / len(required_fields)) * 100
                
            elif isinstance(section_data, str):
                # For text sections like summary
                words = section_data.split()
                score = min(100, len(words) / 2)  # 2 points per word, max 100
                
            return round(score, 2)
            
        except Exception as e:
            logging.error(f"Section score calculation error: {str(e)}")
            return 0.0

    def _check_section_headers(self, parsed_data: Dict) -> float:
        """Check if section headers are properly formatted"""
        try:
            required_headers = ['personal_info', 'experience', 'education', 'skills']
            headers_present = sum(1 for header in required_headers if header in parsed_data)
            return headers_present / len(required_headers)
        except Exception as e:
            logging.error(f"Header check error: {str(e)}")
            return 0.0

    def _check_bullet_points(self, parsed_data: Dict) -> float:
        """Check bullet point formatting in experience section"""
        try:
            if 'experience' not in parsed_data:
                return 0.0
                
            experiences = parsed_data['experience']
            bullet_score = 0
            
            for exp in experiences:
                if 'responsibilities' in exp:
                    # Check if responsibilities are in bullet point format
                    resp_count = len(exp['responsibilities'])
                    if resp_count > 0:
                        bullet_score += 1
                        
            return bullet_score / len(experiences) if experiences else 0.0
        except Exception as e:
            logging.error(f"Bullet point check error: {str(e)}")
            return 0.0

    def _check_consistency(self, parsed_data: Dict) -> float:
        """Check formatting consistency across sections"""
        try:
            consistency_score = 0
            checks = 0
            
            # Check date format consistency
            if 'experience' in parsed_data:
                date_formats = set()
                for exp in parsed_data['experience']:
                    if 'duration' in exp:
                        date_formats.add(self._get_date_format(exp['duration']))
                if date_formats:
                    consistency_score += 1 if len(date_formats) == 1 else 0
                    checks += 1
                    
            # Check capitalization consistency
            if 'skills' in parsed_data:
                caps_styles = set()
                for skill in parsed_data['skills']:
                    if isinstance(skill, str):
                        caps_styles.add(self._get_caps_style(skill))
                if caps_styles:
                    consistency_score += 1 if len(caps_styles) == 1 else 0
                    checks += 1
                    
            return consistency_score / checks if checks > 0 else 0.0
        except Exception as e:
            logging.error(f"Consistency check error: {str(e)}")
            return 0.0

    def _get_date_format(self, date_str: str) -> str:
        """Helper to determine date format"""
        try:
            # Simple format detection
            if '/' in date_str:
                return 'slash'
            elif '-' in date_str:
                return 'dash'
            return 'other'
        except:
            return 'unknown'

    def _get_caps_style(self, text: str) -> str:
        """Helper to determine capitalization style"""
        if text.isupper():
            return 'upper'
        elif text.islower():
            return 'lower'
        elif text[0].isupper():
            return 'title'
        return 'mixed'
    def calculate_ats_scores_sync(self, resume_data: Dict) -> Dict:
            """Synchronous version of ATS score calculation"""
            scores = {
                'overall': 0,
                'sections': {},
                'keywords': 0,
                'formatting': 0
            }
            
            # Calculate section scores
            for section in ['summary', 'experience', 'skills', 'education']:
                if section in resume_data.get('parsed_data', {}):
                    scores['sections'][section] = self._calculate_section_score(
                        resume_data['parsed_data'][section]
                    )
            
            # Calculate overall score
            section_weights = {
                'summary': 0.2,
                'experience': 0.4,
                'skills': 0.25,
                'education': 0.15
            }
            
            scores['overall'] = sum(
                scores['sections'].get(section, 0) * weight
                for section, weight in section_weights.items()
            )
            
            return scores

    def analyze_skills_sync(self, resume_data: Dict) -> Dict:
        """Synchronous version of skills analysis"""
        skills_data = {}
        
        if 'skills' in resume_data.get('parsed_data', {}):
            # Group skills by category
            skills_data = self._group_skills_by_category(
                resume_data['parsed_data']['skills']
            )
        
        return skills_data

    def get_recommendations_sync(self, resume_data: Dict) -> List[Dict]:
        """Synchronous version of getting recommendations"""
        recommendations = []
        
        # Basic recommendations based on content
        parsed_data = resume_data.get('parsed_data', {})
        
        if not parsed_data.get('summary'):
            recommendations.append({
                'type': 'missing_section',
                'section': 'summary',
                'message': 'Add a professional summary'
            })
            
        if not parsed_data.get('skills'):
            recommendations.append({
                'type': 'missing_section',
                'section': 'skills',
                'message': 'Add relevant skills'
            })
            
        return recommendations[:5]  # Return top 5 recommendations
    def _initialize_prompts(self) -> Dict[str, PromptTemplate]:
        """Initialize comprehensive prompts for each section."""
        return {
            'summary': PromptTemplate(
                input_variables=["current_content", "experience_level", "industry", "domain"],
                template="""
                Optimize this professional summary for a {experience_level} {domain} professional in {industry}:
                Current: {current_content}

                Follow these rules based on experience level:
                Entry Level (0-2 years):
                - Emphasize education, internships, and relevant projects
                - Focus on technical skills and learning ability
                - Highlight any relevant certifications or training

                Junior (2-5 years):
                - Focus on hands-on technical achievements
                - Emphasize specific technologies and methodologies
                - Include measurable impacts from projects

                Mid-Level (5-10 years):
                - Balance technical expertise with leadership skills
                - Showcase team coordination and project management
                - Emphasize business impact of technical decisions

                Senior (10+ years):
                - Focus on strategic initiatives and leadership
                - Emphasize architectural decisions and organizational impact
                - Highlight mentorship and team growth

                Domain-specific focus for {domain}:
                Technical: Emphasize technical stack, architecture decisions, and scalability
                Marketing: Focus on campaign results, market growth, and brand metrics
                Management: Highlight team size, budget management, and business impact

                Requirements:
                - Length: 50-100 words
                - No personal pronouns
                - Include key achievements with metrics
                - Match tone to seniority level
                - Use domain-specific keywords
                """
            ),
            'experience': PromptTemplate(
                input_variables=["current_content", "experience_level", "domain", "role_type"],
                template="""
                Enhance these experience entries for a {experience_level} {domain} {role_type}:
                Current: {current_content}

                Format each role following these rules:
                1. Structure:
                   - Company, Title, Duration (MM/YYYY)
                   - 3-5 bullet points per role
                   - Most recent role gets most detail

                2. Content Rules by Experience Level:
                   Entry Level:
                   - Focus on technical skills gained
                   - Highlight project outcomes
                   - Include relevant coursework/internships

                   Junior:
                   - Emphasize individual contributions
                   - Quantify project impacts
                   - Show progression in responsibilities

                   Mid-Level:
                   - Balance technical and leadership
                   - Show team management
                   - Emphasize cross-functional work

                   Senior:
                   - Focus on strategic impact
                   - Highlight organizational changes
                   - Show business results

                3. Domain-Specific Emphasis:
                   Technical:
                   - Technical stack details
                   - System architecture decisions
                   - Performance improvements

                   Marketing:
                   - Campaign metrics
                   - Market growth numbers
                   - Brand impact

                   Management:
                   - Team size and growth
                   - Budget management
                   - Strategic initiatives

                4. Role-Type Keywords for {role_type}:
                   - Use industry-standard terminologies
                   - Include relevant tools and methodologies
                   - Highlight domain-specific achievements

                Maintain and enhance existing achievements, don't fabricate new ones.
                """
            ),
            'skills': PromptTemplate(
                input_variables=["current_content", "domain", "experience_level"],
                template="""
                Organize and enhance these skills for a {experience_level} {domain} professional:
                Current: {current_content}

                Categorize skills into:
                1. Technical Skills:
                   - Programming Languages
                   - Frameworks & Libraries
                   - Cloud Platforms
                   - Tools & Technologies

                2. Domain Skills:
                   - Methodologies
                   - Industry Tools
                   - Best Practices

                3. Soft Skills:
                   - Leadership (if applicable)
                   - Communication
                   - Project Management

                Rules:
                - Group similar skills
                - Order by proficiency
                - Include version numbers for relevant tools
                - Remove outdated technologies
                - Keep mentioned skills from experience section
                """
            ),
            'projects': PromptTemplate(
                input_variables=["current_content", "domain", "experience_level"],
                template="""
                Enhance project descriptions for a {experience_level} {domain} professional:
                Current: {current_content}

                For each project include:
                1. Project Overview:
                   - Clear objective
                   - Scale and scope
                   - Role and responsibilities

                2. Technical Details:
                   - Technologies used
                   - Architecture decisions
                   - Implementation challenges

                3. Measurable Outcomes:
                   - Performance metrics
                   - Business impact
                   - User/customer benefits

                4. Links (if applicable):
                   - GitHub repository
                   - Live demo
                   - Documentation

                Format:
                - Bullet points for clarity
                - Start with action verbs
                - Include metrics where possible
                """
            )
        }

    def _load_templates(self) -> Dict[str, str]:
        """Load resume section templates."""
        return {
            'summary': """
                {experience_level} {domain} professional with {years_experience} years of experience 
                in {key_skills}. Demonstrated expertise in {achievements} resulting in {metrics}. 
                Seeking to leverage {expertise} to {career_goal}.
            """,
            
            'experience': """
                {company_name} | {location}
                {job_title} | {start_date} - {end_date}
                
                • {responsibility_1}
                • {responsibility_2}
                • {achievement_1} resulting in {metric_1}
                • {achievement_2} resulting in {metric_2}
            """,
            
            'skills': """
                Technical Skills:
                • {programming_languages}
                • {frameworks_tools}
                • {databases}
                
                Domain Knowledge:
                • {domain_skills}
                • {methodologies}
                
                Soft Skills:
                • {leadership_skills}
                • {communication_skills}
            """,
            
            'education': """
                {degree} in {major}
                {university} - {graduation_date}
                • GPA: {gpa}
                • Relevant Coursework: {coursework}
                • {achievements}
            """,
            
            'projects': """
                {project_name} | {technologies}
                • {project_description}
                • {technical_details}
                • {achievements_metrics}
                • {link}
            """
        }


    async def _optimize_section(
        self, 
        section: str, 
        content: str, 
        optimization_type: str,
        experience_level: str,
        metadata: Dict
    ) -> str:
        """Optimize section content using Gemini."""
        try:
            prompt_template = self.section_prompts.get(section)
            if not prompt_template:
                raise ValueError(f"No prompt template for section: {section}")

            prompt = prompt_template.format(
                current_content=content,
                experience_level=experience_level,
                **metadata
            )

            optimized_content = await self._generate_text(prompt)
            return optimized_content if optimized_content else content

        except Exception as e:
            logging.error(f"Section optimization error: {str(e)}")
            return content


    def _extract_years_from_duration(self, duration: str) -> float:
        """Extract years from duration string"""
        try:
            duration = duration.lower()
            if 'year' in duration:
                return float(''.join(filter(str.isdigit, duration)))
            elif 'month' in duration:
                months = float(''.join(filter(str.isdigit, duration)))
                return round(months / 12, 1)
            return 0
        except:
            return 0


    async def _generate_text(self, prompt: str, context: Dict = None) -> str:
        """Generate text using Gemini."""
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            return response.text
        except Exception as e:
            logging.error(f"Text generation error: {str(e)}")
            return None

    async def calculate_ats_scores(self, resume_data: Dict) -> Dict:
        """Calculate detailed ATS compatibility scores."""
        scores = {
            'overall': 0,
            'sections': {},
            'keywords': 0,
            'formatting': 0
        }
        
        # Calculate section scores
        for section in ['summary', 'experience', 'skills', 'education']:
            if section in resume_data:
                scores['sections'][section] = await self._calculate_section_score(
                    resume_data[section]
                )
        
        # Calculate overall score
        section_weights = {
            'summary': 0.2,
            'experience': 0.4,
            'skills': 0.25,
            'education': 0.15
        }
        
        scores['overall'] = sum(
            scores['sections'].get(section, 0) * weight
            for section, weight in section_weights.items()
        )
        
        return scores

    async def analyze_skills(self, resume_data: Dict) -> Dict:
        """Analyze skills and their proficiency levels."""
        skills_data = {}
        
        if 'skills' in resume_data:
            # Group skills by category
            for skill in resume_data['skills']:
                category = skill.get('category', 'Other')
                proficiency = skill.get('proficiency', 0)
                
                if category not in skills_data:
                    skills_data[category] = []
                
                skills_data[category].append({
                    'name': skill['name'],
                    'proficiency': proficiency,
                    'years': skill.get('years', 0)
                })
        
        return skills_data



    async def get_recommendations(self, resume_data: Dict) -> List[Dict]:
        """Generate improvement recommendations."""
        recommendations = []
        
        # Analyze sections and generate recommendations
        for section in ['summary', 'experience', 'skills', 'education']:
            section_recs = await self._analyze_section_for_recommendations(
                section,
                resume_data.get(section, {})
            )
            recommendations.extend(section_recs)
        
        return sorted(
            recommendations,
            key=lambda x: x.get('priority', 0),
            reverse=True
        )[:5]

    async def generate_optimized_resume(
        self, 
        resume_id: str, 
        job_description: str
    ) -> Dict:
        try:
            # Get base resume data
            resume_data = await self._get_resume_data(resume_id)
            
            # Analyze job requirements
            job_analysis = await self._analyze_job_requirements(job_description)
            
            # Optimize content for job match
            optimized_sections = await self._optimize_sections(
                resume_data, 
                job_analysis
            )
            
            # Generate ATS-friendly format
            formatted_resume = await self._format_for_ats(optimized_sections)
            
            # Calculate match score
            match_score = await self._calculate_match_score(
                formatted_resume, 
                job_description
            )
            
            return {
                'success': True,
                'optimized_resume': formatted_resume,
                'match_score': match_score,
                'optimization_details': {
                    'changes_made': self._get_changes_made(
                        resume_data, 
                        formatted_resume
                    ),
                    'improvement_areas': self._get_improvement_areas(match_score)
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def improve_resume_sync(
        self, 
        resume_data: Dict, 
        improvement_type: str, 
        job_description: str = '',
        improvement_options: Dict = None
    ) -> Dict:
        """Synchronous method to improve resume"""
        try:
            if not resume_data or 'parsed_data' not in resume_data:
                return {
                    'success': False,
                    'error': 'Invalid resume data'
                }

            if improvement_options is None:
                improvement_options = {}

            # Define improvement functions
            improvements = {
                'ats_optimization': lambda: self._optimize_for_ats(resume_data, job_description),
                'content_enhancement': lambda: self._enhance_content(resume_data, improvement_options),
                'skill_highlighting': lambda: self._highlight_skills(resume_data, job_description),
                'job_targeting': lambda: self._target_for_job(resume_data, job_description)
            }

            if improvement_type not in improvements:
                return {
                    'success': False,
                    'error': f'Invalid improvement type. Allowed: {", ".join(improvements.keys())}'
                }

            # Generate improvement prompt
            prompt = f"""
            Improve this resume based on the following parameters:
            Improvement Type: {improvement_type}
            Industry: {improvement_options.get('industry', 'Not specified')}
            Focus Areas: {', '.join(improvement_options.get('focus_areas', []))}

            Original Resume:
            {json.dumps(resume_data['parsed_data'], indent=2)}

            Job Description (if provided):
            {job_description}

            Requirements:
            1. Maintain factual accuracy
            2. Enhance formatting and clarity
            3. Optimize for ATS systems
            4. Focus on specified improvement type
            5. Keep original structure
            
            Return the improved resume content in JSON format.
            """

            # Generate improvements using Gemini
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )

            # Parse the response
            text = response.text
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format from model")
                
            improved_content = json.loads(text[start_idx:end_idx])

            # Calculate ATS score
            ats_score = self._calculate_ats_score_sync(improved_content)

            # Track changes
            changes = self._get_changes(resume_data['parsed_data'], improved_content)

            return {
                'success': True,
                'original_content': resume_data['parsed_data'],
                'improved_content': improved_content,
                'improvement_type': improvement_type,
                'ats_score': ats_score,
                'changes': changes
            }

        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to parse improvement response'
            }
        except Exception as e:
            logging.error(f"Resume improvement error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _optimize_for_ats(self, resume_data: Dict, job_description: str) -> Dict:
        """Optimize resume for ATS compatibility"""
        try:
            optimized = resume_data.copy()
            parsed_data = optimized.get('parsed_data', {})

            # Optimize each section
            if 'skills' in parsed_data:
                parsed_data['skills'] = self._optimize_skills(
                    parsed_data['skills'], 
                    job_description
                )

            if 'experience' in parsed_data:
                parsed_data['experience'] = self._optimize_experience(
                    parsed_data['experience']
                )

            optimized['parsed_data'] = parsed_data
            return optimized

        except Exception as e:
            logging.error(f"ATS optimization error: {str(e)}")
            return resume_data

    def _calculate_ats_score_sync(self, resume_data: Dict) -> float:
        """Calculate ATS compatibility score synchronously"""
        try:
            scores = {
                'keyword_match': 0.0,
                'formatting': 0.0,
                'content_quality': 0.0,
                'section_completeness': 0.0
            }
            
            parsed_data = resume_data.get('parsed_data', {})
            
            # Check completeness
            required_sections = ['personal_info', 'experience', 'education', 'skills']
            scores['section_completeness'] = sum(
                1 for section in required_sections if section in parsed_data
            ) / len(required_sections) * 100

            # Check formatting
            scores['formatting'] = self._check_formatting(parsed_data)
            
            # Calculate final score
            weights = {
                'keyword_match': 0.3,
                'formatting': 0.2,
                'content_quality': 0.3,
                'section_completeness': 0.2
            }
            
            final_score = sum(
                score * weights[metric] 
                for metric, score in scores.items()
            )
            
            return round(final_score, 2)

        except Exception as e:
            logging.error(f"ATS score calculation error: {str(e)}")
            return 0.0

    def _get_changes(self, original: Dict, improved: Dict) -> List[str]:
        """Track changes made during improvement"""
        changes = []
        
        original_data = original.get('parsed_data', {})
        improved_data = improved.get('parsed_data', {})
        
        for section in improved_data:
            if section not in original_data:
                changes.append(f"Added new section: {section}")
            elif improved_data[section] != original_data[section]:
                changes.append(f"Updated {section} section")
                
        return changes

    def _check_formatting(self, parsed_data: Dict) -> float:
        """Check resume formatting score"""
        score = 0
        checks = [
            self._check_section_headers(parsed_data),
            self._check_bullet_points(parsed_data),
            self._check_consistency(parsed_data)
        ]
        return sum(checks) / len(checks) * 100
    def _get_learning_resources(self, skills: List[str]) -> List[Dict[str, str]]:
        """Get learning resources for required skills"""
        resources = []
        for skill in skills[:3]:  # Get resources for top 3 skills
            resources.extend([
                {
                    'name': f'Coursera - {skill}',
                    'url': f'https://www.coursera.org/search?query={skill}',
                    'type': 'course'
                },
                {
                    'name': f'Udemy - {skill}',
                    'url': f'https://www.udemy.com/courses/search/?q={skill}',
                    'type': 'course'
                }
            ])
        return resources
    def _get_market_insights(self, job_title: str, industry: str) -> Dict[str, Any]:
        """Get market insights for the job"""
        return {
            'demand_level': 'High',  # You can make this dynamic based on real data
            'growth_rate': '15% annually',  # You can make this dynamic
            'top_companies': [
                'Company A',
                'Company B',
                'Company C'
            ],
            'salary_ranges': {
                'entry_level': '$60,000 - $80,000',
                'mid_level': '$80,000 - $120,000',
                'senior_level': '$120,000 - $180,000'
            }
        }
    def get_job_recommendations_sync(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get job recommendations based on resume data"""
        try:
            # Extract skills and experience from resume
            skills = resume_data.get('parsed_data', {}).get('skills', [])
            experience = resume_data.get('parsed_data', {}).get('experience', [])

            # Generate recommendations using Gemini
            prompt = f"""
            Generate job recommendations based on this profile:
            Skills: {', '.join(skills)}
            Experience: {json.dumps(experience, indent=2)}

            Return a JSON array of 10 job recommendations with format:
            [{{
                "title": "Job Title",
                "description": "Brief job description",
                "required_skills": ["skill1", "skill2"],
                "skill_match": "Percentage match with candidate skills",
                "experience_level": "Required experience level",
                "industry": "Industry name",
                "potential_salary": "Salary range",
                "growth_potential": "Career growth description",
                "job_market_demand": "Current demand level (High/Medium/Low)"
            }}]
            
            Focus on roles that match at least 60% of the candidate's skills.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 1,
                    'top_k': 40,
                    'max_output_tokens': 2048
                }
            )

            # Parse the response
            text = response.text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format from model")
                
            recommendations = json.loads(text[start_idx:end_idx])

            # Add learning resources and market insights
            enhanced_recommendations = []
            for rec in recommendations:
                rec['learning_resources'] = self._get_learning_resources(rec['required_skills'])
                rec['market_insights'] = self._get_market_insights(rec['title'], rec['industry'])
                enhanced_recommendations.append(rec)

            return {
                'success': True,
                'recommendations': enhanced_recommendations[:10]  # Limit to 10 recommendations
            }

        except Exception as e:
            print(f"Job recommendations error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _calculate_total_experience(self, experience: List[Dict]) -> float:
        """Calculate total years of experience"""
        try:
            total_years = 0
            for exp in experience:
                duration = exp.get('duration', '').lower() if exp else ''
                if 'year' in duration:
                    years = float(''.join(filter(str.isdigit, duration)))
                    total_years += years
                elif 'month' in duration:
                    months = float(''.join(filter(str.isdigit, duration)))
                    total_years += months / 12
            return round(total_years, 1)
        except Exception as e:
            logging.error(f"Experience calculation error: {str(e)}")
            return 0.0


    def analyze_job_description(self, job_description: str, resume_data: Dict = None) -> Dict:
        """Analyze job description and compare with resume if provided"""
        try:
            # Generate analysis using Gemini
            prompt = f"""
            Analyze this job description and extract key information:
            {job_description}

            Return a JSON object with:
            1. required_skills (list of technical and soft skills)
            2. requirements (list of key job requirements)
            3. responsibilities (list of main duties)
            4. experience_needed (years and type)
            5. culture_notes (company culture indicators)
            6. tech_stack (if mentioned)
            7. benefits (if mentioned)
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )

            # Parse JSON response
            text = response.text
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format")
                
            analysis = json.loads(text[start_idx:end_idx])

            # Add match analysis if resume data is provided
            if resume_data and 'parsed_data' in resume_data:
                resume_skills = set(skill.lower() for skill in resume_data['parsed_data'].get('skills', []))
                required_skills = set(skill.lower() for skill in analysis.get('required_skills', []))

                # Calculate match percentages
                skill_matches = resume_skills.intersection(required_skills)
                match_score = len(skill_matches) / len(required_skills) * 100 if required_skills else 0

                analysis['match_analysis'] = {
                    'match_score': round(match_score, 2),
                    'matching_skills': list(skill_matches),
                    'missing_skills': list(required_skills - resume_skills),
                    'recommendations': self._generate_job_match_recommendations(
                        match_score,
                        list(required_skills - resume_skills)
                    )
                }

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

    def _generate_job_match_recommendations(self, match_score: float, missing_skills: List[str]) -> List[str]:
        """Generate recommendations based on job match analysis"""
        recommendations = []

        if match_score < 50:
            recommendations.append("Consider upskilling before applying - significant skill gaps exist")
        elif match_score < 70:
            recommendations.append("You meet basic requirements but could strengthen your profile")
        else:
            recommendations.append("Strong match with requirements - consider highlighting matching skills")

        if missing_skills:
            recommendations.append(f"Focus on acquiring these key skills: {', '.join(missing_skills[:3])}")

        return recommendations

    def _target_for_job(self, resume_data: Dict, job_description: str) -> Dict:
        """Target resume for specific job"""
        try:
            targeted = resume_data.copy()
            parsed_data = targeted.get('parsed_data', {})

            # Analyze job description
            job_analysis = self.analyze_job_description(job_description)['analysis']
            
            # Target skills section
            if 'skills' in parsed_data:
                parsed_data['skills'] = self._prioritize_skills(
                    parsed_data['skills'],
                    job_analysis.get('required_skills', [])
                )

            # Target experience section
            if 'experience' in parsed_data:
                parsed_data['experience'] = self._highlight_relevant_experience(
                    parsed_data['experience'],
                    job_analysis
                )

            # Update summary
            if 'summary' in parsed_data:
                parsed_data['summary'] = self._target_summary(
                    parsed_data['summary'],
                    job_analysis
                )

            targeted['parsed_data'] = parsed_data
            return targeted

        except Exception as e:
            logging.error(f"Job targeting error: {str(e)}")
            return resume_data

    def _prioritize_skills(self, skills: List[str], required_skills: List[str]) -> List[str]:
        """Prioritize skills based on job requirements"""
        try:
            required_skills_lower = [skill.lower() for skill in required_skills]
            
            # Sort skills putting required ones first
            prioritized = sorted(
                skills,
                key=lambda x: x.lower() in required_skills_lower,
                reverse=True
            )
            
            return prioritized

        except Exception as e:
            logging.error(f"Skills prioritization error: {str(e)}")
            return skills

    def _highlight_relevant_experience(self, experience: List[Dict], job_analysis: Dict) -> List[Dict]:
        """Highlight experience relevant to job requirements"""
        try:
            requirements = set(req.lower() for req in job_analysis.get('requirements', []))
            responsibilities = set(resp.lower() for resp in job_analysis.get('responsibilities', []))
            
            for exp in experience:
                # Add relevance markers
                exp['relevant_points'] = []
                
                for resp in exp.get('responsibilities', []):
                    if any(req in resp.lower() for req in requirements) or \
                       any(duty in resp.lower() for duty in responsibilities):
                        exp['relevant_points'].append(resp)
                
                # Reorder responsibilities to put relevant points first
                if exp['relevant_points']:
                    other_points = [r for r in exp['responsibilities'] 
                                  if r not in exp['relevant_points']]
                    exp['responsibilities'] = exp['relevant_points'] + other_points
                    
            return experience

        except Exception as e:
            logging.error(f"Experience highlighting error: {str(e)}")
            return experience

    def _target_summary(self, summary: str, job_analysis: Dict) -> str:
        """Target summary for specific job"""
        try:
            prompt = f"""
            Revise this professional summary to target the job requirements:

            Current Summary: {summary}

            Job Requirements:
            - Required Skills: {', '.join(job_analysis.get('required_skills', []))}
            - Key Responsibilities: {', '.join(job_analysis.get('responsibilities', []))}
            - Experience Needed: {job_analysis.get('experience_needed', 'Not specified')}

            Keep the same professional experience and achievements, but align them with the job requirements.
            Make it concise and impactful.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )

            return response.text.strip()

        except Exception as e:
            logging.error(f"Summary targeting error: {str(e)}")
            return summary

    def _enhance_content(self, resume_data: Dict, options: Dict) -> Dict:
        """Enhance resume content"""
        try:
            enhanced = resume_data.copy()
            parsed_data = enhanced.get('parsed_data', {})
            
            industry = options.get('industry', '')
            focus_areas = options.get('focus_areas', [])
            
            # Enhance each section
            if 'summary' in parsed_data:
                parsed_data['summary'] = self._enhance_summary(
                    parsed_data['summary'],
                    industry,
                    focus_areas
                )
                
            if 'experience' in parsed_data:
                parsed_data['experience'] = self._enhance_experience(
                    parsed_data['experience'],
                    industry
                )
                
            enhanced['parsed_data'] = parsed_data
            return enhanced
            
        except Exception as e:
            logging.error(f"Content enhancement error: {str(e)}")
            return resume_data

    def _optimize_skills(self, skills: List[str], job_description: str) -> List[str]:
        """Optimize skills section for ATS"""
        try:
            # Remove duplicates and standardize format
            unique_skills = list(set(skills))
            
            # Sort by relevance to job description
            return sorted(
                unique_skills,
                key=lambda x: x.lower() in job_description.lower(),
                reverse=True
            )
            
        except Exception as e:
            logging.error(f"Skills optimization error: {str(e)}")
            return skills

    def _optimize_experience(self, experience: List[Dict]) -> List[Dict]:
        """Optimize experience section for ATS"""
        try:
            for exp in experience:
                # Standardize date format
                if 'duration' in exp:
                    exp['duration'] = self._standardize_date_format(exp['duration'])
                    
                # Format responsibilities
                if 'responsibilities' in exp:
                    exp['responsibilities'] = [
                        self._format_bullet_point(resp)
                        for resp in exp['responsibilities']
                    ]
                    
            return experience
            
        except Exception as e:
            logging.error(f"Experience optimization error: {str(e)}")
            return experience

    def _standardize_date_format(self, date_str: str) -> str:
        """Standardize date format"""
        try:
            # Implement date standardization logic
            return date_str
        except Exception as e:
            logging.error(f"Date standardization error: {str(e)}")
            return date_str

    def _format_bullet_point(self, text: str) -> str:
        """Format bullet point for ATS"""
        try:
            # Start with action verb if not already
            words = text.strip().split()
            if words and not words[0].endswith('ed') and not words[0].endswith('ing'):
                return text
                
            return text
            
        except Exception as e:
            logging.error(f"Bullet point formatting error: {str(e)}")
            return text

    def regenerate_resume_sync(self, resume_id: str, feedback: str) -> Dict:
        """Regenerate resume with feedback synchronously"""
        try:
            # Get existing resume
            resume_data = self.resumes.find_one({"_id": resume_id})
            if not resume_data:
                return {
                    'success': False,
                    'error': 'Resume not found'
                }

            # Generate improved version using feedback
            prompt = f"""
            Improve this resume based on the following feedback:
            {feedback}

            Current Resume:
            {json.dumps(resume_data['parsed_data'], indent=2)}

            Requirements:
            1. Maintain all factual information
            2. Improve formatting and phrasing
            3. Address specific feedback points
            4. Enhance ATS compatibility
            5. Keep section structure intact
            
            Return the improved resume in the same JSON format.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )

            # Parse improved content
            text = response.text
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format")

            improved_data = json.loads(text[start_idx:end_idx])
            
            # Calculate new ATS score
            ats_score = self._calculate_ats_score_sync(improved_data)

            # Track changes
            changes = self._get_changes(resume_data['parsed_data'], improved_data)

            return {
                'success': True,
                'original_resume': resume_data['parsed_data'],
                'improved_resume': improved_data,
                'ats_score': ats_score,
                'changes_made': changes,
                'feedback_addressed': self._analyze_feedback_implementation(
                    feedback,
                    improved_data
                )
            }

        except Exception as e:
            logging.error(f"Resume regeneration error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _analyze_feedback_implementation(self, feedback: str, improved_data: Dict) -> List[str]:
        """Analyze how feedback was implemented"""
        try:
            implemented = []
            feedback_points = feedback.lower().split('\n')
            
            resume_text = json.dumps(improved_data).lower()
            
            for point in feedback_points:
                if point.strip() and any(keyword in resume_text for keyword in point.split()):
                    implemented.append(f"Addressed: {point.strip()}")
                    
            return implemented
            
        except Exception as e:
            logging.error(f"Feedback analysis error: {str(e)}")
            return ["Could not analyze feedback implementation"]