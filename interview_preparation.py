import os
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import chromadb
from pymongo import MongoClient
from bson.objectid import ObjectId
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json
import re

class InterviewPreparation:
    def __init__(self, chroma_client: Optional[chromadb.Client] = None):
        """Initialize interview preparation system."""
        load_dotenv()
        
        try:
            # Initialize Gemini
            self.gemini_key = os.getenv('GEMINI_API_KEY')
            genai.configure(api_key=self.gemini_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Initialize MongoDB
            self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
            self.db = self.mongo_client["resumeDB"]
            self.interviews = self.db["interview_prep"]
            
            # Initialize ChromaDB
            # self.chroma_client = chroma_client or chromadb.PersistentClient(
            #     path="./data/chromadb"
            # )
            
        except Exception as e:
            logging.error(f"Initialization error: {str(e)}")
            raise
    def _clean_json_response(self, text: str) -> str:
        """Clean and extract valid JSON from AI response"""
        try:
            # Remove markdown code blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Find JSON content between braces
            start_idx = text.find('{')
            if start_idx == -1:
                return '{}'
                
            # Find matching closing brace
            brace_count = 0
            end_idx = start_idx
            
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            json_str = text[start_idx:end_idx]
            
            # Clean up common JSON issues
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
            
            return json_str
            
        except Exception as e:
            logging.error(f"JSON cleaning error: {str(e)}")
            return '{}'

    def _parse_json_safely(self, text: str) -> Dict:
        """Safely parse JSON with fallback"""
        try:
            cleaned_json = self._clean_json_response(text)
            return json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {str(e)}")
            logging.error(f"Problematic JSON: {cleaned_json[:500]}...")
            return {}
        except Exception as e:
            logging.error(f"Unexpected parsing error: {str(e)}")
            return {}

    def _generate_technical_screen_questions(self, resume_data: Dict, job_analysis: Dict) -> Dict:
        """Generate technical screening questions based on candidate profile"""
        try:
            skills = resume_data.get('parsed_data', {}).get('skills', [])
            experience_level = self._determine_experience_level(resume_data)
            
            # Handle skills if it's a dict
            if isinstance(skills, dict):
                skills_list = []
                for skill_category, skill_values in skills.items():
                    if isinstance(skill_values, list):
                        skills_list.extend(skill_values)
                    elif isinstance(skill_values, str):
                        skills_list.append(skill_values)
                skills = skills_list
        
            skills_text = ', '.join(skills[:10]) if skills else 'General programming skills'
            
            prompt = f"""
            Generate technical screening questions for a {experience_level} level candidate with these skills:
            {skills_text}

            Job Requirements:
            {json.dumps(job_analysis, indent=2) if job_analysis else 'General requirements'}

            Return ONLY a valid JSON object with this exact structure:
            {{
                "core_concepts": [
                    {{
                        "question": "What is your experience with Python?",
                        "expected_points": ["Specific examples", "Years of experience"],
                        "follow_up": ["Can you explain a challenging project?"],
                        "difficulty": "medium"
                    }}
                ],
                "problem_solving": [
                    {{
                        "question": "How do you approach debugging?",
                        "expected_points": ["Systematic approach", "Tools used"],
                        "follow_up": ["Describe a difficult bug you solved"],
                        "difficulty": "medium"
                    }}
                ]
            }}

            Make sure the JSON is valid with no trailing commas.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32,
                    'max_output_tokens': 2048
                }
            )

            if not response.text:
                return self._get_default_technical_questions()

            # Use safe JSON parsing
            questions = self._parse_json_safely(response.text)
            
            if not questions:
                return self._get_default_technical_questions()
                
            return questions

        except Exception as e:
            logging.error(f"Technical screen questions generation error: {str(e)}")
            return self._get_default_technical_questions()

    def _generate_coding_questions(self, resume_data: Dict, job_analysis: Dict) -> List[Dict]:
        """Generate coding round questions based on candidate profile"""
        try:
            skills = resume_data.get('parsed_data', {}).get('skills', [])
            experience_level = self._determine_experience_level(resume_data)
            
            # Handle skills if it's a dict
            if isinstance(skills, dict):
                skills_list = []
                for skill_category, skill_values in skills.items():
                    if isinstance(skill_values, list):
                        skills_list.extend(skill_values)
                    elif isinstance(skill_values, str):
                        skills_list.append(skill_values)
                skills = skills_list
        
            skills_text = ', '.join(skills[:10]) if skills else 'General programming skills'

            prompt = f"""
            Generate coding interview questions for a {experience_level} level candidate with these skills:
            {skills_text}

            Job Requirements:
            {json.dumps(job_analysis, indent=2) if job_analysis else 'General requirements'}

            Return ONLY a valid JSON array with this exact structure:
            [
                {{
                    "title": "Array Sum Problem",
                    "description": "Find two numbers that add up to target",
                    "difficulty": "easy",
                    "concepts": ["Arrays", "Hash Tables"],
                    "time_complexity": "O(n)",
                    "space_complexity": "O(n)",
                    "approach": "Use hash table for lookup",
                    "follow_up": ["What if array is sorted?"],
                    "sample_input": "[2,7,11,15], target=9",
                    "sample_output": "[0,1]"
                }}
            ]

            Make sure the JSON array is valid with no trailing commas.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32,
                    'max_output_tokens': 2048
                }
            )

            if not response.text:
                return self._get_default_coding_questions()

            # Extract array from response
            text = response.text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                return self._get_default_coding_questions()
            
            json_str = text[start_idx:end_idx]
            
            # Clean up common JSON issues
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            
            try:
                questions = json.loads(json_str)
                return questions if isinstance(questions, list) else self._get_default_coding_questions()
            except json.JSONDecodeError as e:
                logging.error(f"Coding questions JSON parsing error: {str(e)}")
                return self._get_default_coding_questions()

        except Exception as e:
            logging.error(f"Coding questions generation error: {str(e)}")
            return self._get_default_coding_questions()

    def _get_default_technical_questions(self) -> Dict:
        """Return default technical questions if generation fails"""
        return {
            "core_concepts": [
                {
                    "question": "Explain your experience with the main technologies in your resume",
                    "expected_points": ["Depth of knowledge", "Practical applications", "Recent projects"],
                    "follow_up": ["What challenges did you face?", "How did you solve them?"],
                    "difficulty": "medium"
                }
            ],
            "problem_solving": [
                {
                    "question": "How do you approach solving complex technical problems?",
                    "expected_points": ["Systematic approach", "Research methods", "Testing strategies"],
                    "follow_up": ["Give an example", "What tools do you use?"],
                    "difficulty": "medium"
                }
            ]
        }

    def _get_default_coding_questions(self) -> List[Dict]:
        """Return default coding questions if generation fails"""
        return [
            {
                "title": "Array Two Sum",
                "description": "Given an array of integers and a target sum, find two numbers that add up to the target",
                "difficulty": "easy",
                "concepts": ["Arrays", "Hash Tables"],
                "time_complexity": "O(n)",
                "space_complexity": "O(n)",
                "approach": "Use hash table to store complements",
                "follow_up": ["What if array is sorted?", "What about multiple solutions?"],
                "sample_input": "[2,7,11,15], target=9",
                "sample_output": "[0,1]"
            },
            {
                "title": "String Reversal",
                "description": "Reverse a string without using built-in reverse functions",
                "difficulty": "easy",
                "concepts": ["Strings", "Two Pointers"],
                "time_complexity": "O(n)",
                "space_complexity": "O(1)",
                "approach": "Use two pointers from start and end",
                "follow_up": ["How about reversing words?", "What about Unicode?"],
                "sample_input": "hello",
                "sample_output": "olleh"
            }
        ]

    def prepare_interview_guide(self, resume_data: Dict, job_description: str, company_name: str) -> Dict:
        """Generate comprehensive interview preparation guide"""
        try:
            # Research company
            company_info = self._research_company(company_name)
            
            # Analyze job requirements
            job_analysis = self._analyze_job_requirements(job_description)

            # Generate all components
            technical_questions = self._generate_technical_screen_questions(resume_data, job_analysis)
            behavioral_questions = self._generate_behavioral_questions(resume_data, job_analysis)
            system_design = self._generate_system_design_questions(job_analysis)
            coding_questions = self._generate_coding_questions(resume_data, job_analysis)
            
            # Create the guide structure that matches what the HTML expects
            guide = {
                'technical_preparation': {
                    'core_concepts': technical_questions.get('core_concepts', []),
                    'problem_solving': technical_questions.get('problem_solving', []),
                    'system_design_questions': system_design,
                    'coding_practice': coding_questions,
                    'recommended_topics': [
                        'Data structures and algorithms',
                        'System design fundamentals',
                        'Code optimization techniques',
                        'Database design patterns'
                    ],
                    'practice_resources': [
                        'LeetCode - Algorithm practice',
                        'System Design Primer - Architecture concepts',
                        'Clean Code - Best practices'
                    ]
                },
                'behavioral_questions': {
                    'common_questions': [
                        'Tell me about yourself',
                        'Why do you want to work here?',
                        'Describe a challenging project you worked on',
                        'How do you handle tight deadlines?',
                        'Tell me about a time you had to learn something new quickly'
                    ],
                    'star_method_examples': [
                        'Situation: Set the context',
                        'Task: Explain your responsibility',
                        'Action: Describe what you did',
                        'Result: Share the outcome'
                    ],
                    'leadership_questions': behavioral_questions.get('leadership', []),
                    'teamwork_questions': behavioral_questions.get('teamwork', []),
                    'problem_solving_scenarios': behavioral_questions.get('problem_solving', [])
                },
                'company_questions': {
                    'about_role': [
                        'What does success look like in this role?',
                        'What are the biggest challenges facing the team?',
                        'How does this role contribute to company goals?',
                        'What opportunities for growth exist?'
                    ],
                    'about_company': [
                        'What is the company culture like?',
                        'How does the company handle remote work?',
                        'What are the company\'s future plans?',
                        'How does the company support professional development?'
                    ],
                    'about_team': [
                        'How is the team structured?',
                        'What collaboration tools do you use?',
                        'How do you handle code reviews?',
                        'What is the typical project timeline?'
                    ],
                    'company_research': company_info
                },
                'preparation_tips': {
                    'timeline': '2-3 weeks before interview',
                    'daily_preparation': [
                        'Review 2-3 coding problems',
                        'Practice explaining technical concepts',
                        'Research company news and updates',
                        'Prepare STAR method examples'
                    ],
                    'week_before': [
                        'Conduct mock interviews',
                        'Review your resume thoroughly',
                        'Prepare questions for interviewer',
                        'Plan your interview day logistics'
                    ],
                    'day_of_interview': [
                        'Review key talking points',
                        'Test your technology (for remote interviews)',
                        'Prepare pen and paper for notes',
                        'Arrive 10-15 minutes early'
                    ],
                    'general_tips': [
                        'Be specific with examples',
                        'Show enthusiasm for the role',
                        'Ask thoughtful questions',
                        'Follow up within 24 hours'
                    ]
                }
            }

            return {
                'success': True,
                'interview_guide': guide
            }

        except Exception as e:
            logging.error(f"Interview guide generation error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'interview_guide': self._create_default_guide({}, job_description)
            }

    def _scrape_interview_questions(self, company_name: str, job_title: str) -> List[Dict]:
        """Scrape real interview questions from various sources"""
        try:
            questions = []
            sources = [
                f"https://www.glassdoor.com/Interview/{company_name}-{job_title}-Interview-Questions",
                f"https://www.leetcode.com/discuss/{company_name.lower()}-interview-questions",
                f"https://www.teamblind.com/search/{company_name}-interview"
            ]

            for source in sources:
                try:
                    response = requests.get(source, 
                                        headers={'User-Agent': 'Mozilla/5.0'})
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # Extract questions based on site structure
                        # Add to questions list
                except Exception as e:
                    logging.error(f"Error scraping {source}: {str(e)}")
                    continue

            return questions

        except Exception as e:
            logging.error(f"Interview questions scraping error: {str(e)}")
            return []

    def _research_company(self, company_name: str) -> Dict:
        """Research company information from various sources."""
        try:
            prompt = f"""
            Research and provide comprehensive information about {company_name}. 
            Return the information in this exact JSON format:
            {{
                "company_overview": {{
                    "description": "Brief company description",
                    "industry": "Primary industry",
                    "size": "Company size range",
                    "founded": "Founding year",
                    "headquarters": "HQ location"
                }},
                "culture": {{
                    "values": ["Value 1", "Value 2"],
                    "mission": "Mission statement",
                    "work_environment": "Description of work environment",
                    "benefits": ["Benefit 1", "Benefit 2"]
                }},
                "recent_developments": [
                    {{
                        "title": "Development title",
                        "description": "Brief description",
                        "date": "Approximate date",
                        "impact": "Potential impact"
                    }}
                ],
                "products_services": [
                    {{
                        "category": "Category name",
                        "items": ["Product/Service 1", "Product/Service 2"]
                    }}
                ],
                "market_position": {{
                    "industry_rank": "Market position",
                    "competitors": ["Competitor 1", "Competitor 2"],
                    "strengths": ["Strength 1", "Strength 2"],
                    "growth_areas": ["Area 1", "Area 2"]
                }},
                "technologies": {{
                    "stack": ["Technology 1", "Technology 2"],
                    "tools": ["Tool 1", "Tool 2"],
                    "frameworks": ["Framework 1", "Framework 2"]
                }},
                "interview_process": {{
                    "stages": ["Stage 1", "Stage 2"],
                    "typical_duration": "Average process length",
                    "key_focus_areas": ["Area 1", "Area 2"]
                }}
            }}
            
            Ensure all JSON keys and values are properly quoted and formatted.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )

            # Extract and validate JSON
            text = response.text.strip()
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format")
                
            company_info = json.loads(text[start_idx:end_idx])

            # Add real sources if available
            sources = self._get_company_sources(company_name)
            if sources:
                company_info['sources'] = sources

            return company_info

        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error in company research: {str(e)}")
            return self._get_default_company_info(company_name)
        except Exception as e:
            logging.error(f"Company research error: {str(e)}")
            return self._get_default_company_info(company_name)

    def _get_company_sources(self, company_name: str) -> List[Dict[str, str]]:
        """Get reliable sources for company research"""
        formatted_name = company_name.replace(' ', '+')
        return [
            {
                'name': 'LinkedIn Company Page',
                'url': f'https://www.linkedin.com/company/{formatted_name}'
            },
            {
                'name': 'Glassdoor Reviews',
                'url': f'https://www.glassdoor.com/Overview/Working-at-{formatted_name}'
            },
            {
                'name': 'Crunchbase Profile',
                'url': f'https://www.crunchbase.com/organization/{formatted_name.lower()}'
            }
        ]

    def _get_default_company_info(self, company_name: str) -> Dict:
        """Return default company information structure"""
        return {
            "company_overview": {
                "description": f"Information about {company_name} is being retrieved",
                "industry": "Not specified",
                "size": "Not specified",
                "founded": "Not specified",
                "headquarters": "Not specified"
            },
            "culture": {
                "values": [],
                "mission": "Not specified",
                "work_environment": "Not specified",
                "benefits": []
            },
            "recent_developments": [],
            "products_services": [],
            "market_position": {
                "industry_rank": "Not specified",
                "competitors": [],
                "strengths": [],
                "growth_areas": []
            },
            "technologies": {
                "stack": [],
                "tools": [],
                "frameworks": []
            },
            "interview_process": {
                "stages": [],
                "typical_duration": "Not specified",
                "key_focus_areas": []
            }
        }

    def _analyze_job_requirements(self, job_description: str) -> Dict:
        """Analyze job requirements and expectations."""
        try:
            prompt = f"""
            Analyze this job description and extract:
            1. Key Technical Requirements
            2. Required Experience Levels
            3. Soft Skills Requirements
            4. Role Responsibilities
            5. Team Structure Hints
            6. Project Involvement Expectations
            7. Growth Opportunities
            8. Performance Expectations
            
            Job Description:
            {job_description}
            
            Return as detailed JSON with these categories.
            """
            
            response = self.model.generate_content(prompt)
            analysis = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])
            
            return analysis
            
        except Exception as e:
            logging.error(f"Job analysis error: {str(e)}")
            return {}

    def _generate_technical_questions(self, resume_data: Dict, job_description: str) -> Dict:
        """Generate technical interview questions."""
        try:
            skills = resume_data.get('parsed_data', {}).get('skills', [])
            
            prompt = f"""
            Generate technical interview questions for a candidate with these skills:
            {', '.join(skills)}

            For this job description:
            {job_description}

            Include:
            1. Basic Concept Questions
            2. Advanced Technical Questions
            3. System Design Questions
            4. Problem-Solving Scenarios
            5. Code Review Questions
            6. Architecture Questions
            7. Best Practices Questions
            8. Technology-Specific Questions
            
            For each question, provide:
            - Question
            - Expected Answer Points
            - Follow-up Questions
            - Preparation Tips
            
            Return as detailed JSON.
            """
            
            response = self.model.generate_content(prompt)
            questions = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])
            
            return questions
            
        except Exception as e:
            logging.error(f"Technical questions generation error: {str(e)}")
            return {}

    def get_interview_prep_data(self, job_description: str, resume_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get interview preparation data integrated with job analysis"""
        try:
            # Get job analysis
            analysis = self.analyze_job_sync(job_description, resume_data)
            
            # Get salary insights
            salary_data = self._scrape_salary_data(
                analysis['analysis']['position']['title']
            )

            # Get company insights
            company_info = self._get_company_insights(
                analysis['analysis']['position']['title']
            )

            return {
                'success': True,
                'data': {
                    'job_analysis': analysis['analysis'],
                    'salary_insights': salary_data,
                    'company_insights': company_info,
                    'interview_prep': {
                        'technical_questions': self._generate_technical_questions(
                            analysis['analysis']['required_skills']
                        ),
                        'behavioral_questions': self._generate_behavioral_questions(
                            analysis['analysis']
                        ),
                        'company_questions': self._generate_company_questions(
                            company_info
                        )
                    }
                }
            }

        except Exception as e:
            logging.error(f"Interview prep data error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    def _generate_behavioral_questions(self, resume_data: Dict, job_analysis: Dict) -> Dict:
        """Generate behavioral interview questions."""
        try:
            experience = resume_data.get('parsed_data', {}).get('experience', [])
            
            prompt = f"""
            Generate behavioral interview questions based on candidate experience and job requirements.
            
            Experience: {json.dumps(experience, ensure_ascii=False)}
            Job Requirements: {json.dumps(job_analysis, ensure_ascii=False)}
            
            Return a JSON object with this exact structure:
            {{
                "leadership": [
                    {{
                        "question": "Tell me about a time you led a project",
                        "star_guide": "Focus on your leadership style and team impact",
                        "key_points": ["Decision making", "Team motivation", "Results"]
                    }}
                ],
                "teamwork": [
                    {{
                        "question": "Describe a successful team collaboration",
                        "star_guide": "Highlight your collaboration skills",
                        "key_points": ["Communication", "Support", "Shared goals"]
                    }}
                ],
                "problem_solving": [
                    {{
                        "question": "Tell me about a technical challenge you overcame",
                        "star_guide": "Show your analytical thinking process",
                        "key_points": ["Problem analysis", "Solution approach", "Results"]
                    }}
                ]
            }}
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32
                }
            )
            
            # Use safe JSON parsing
            questions = self._parse_json_safely(response.text)
            
            if not questions:
                return self._get_default_behavioral_questions()
                
            return questions
            
        except Exception as e:
            logging.error(f"Behavioral questions generation error: {str(e)}")
            return self._get_default_behavioral_questions()

    def _get_default_behavioral_questions(self) -> Dict:
        """Return default behavioral questions if generation fails."""
        return {
            "leadership": [
                {
                    "question": "Describe a situation where you had to lead a team through a challenging project.",
                    "star_guide": "Situation: Project context, Task: Leadership role, Action: Steps taken, Result: Outcome achieved",
                    "example_structure": "Project background → Challenge → Your leadership → Team impact → Results",
                    "emphasis_points": ["Decision making", "Team motivation", "Goal achievement"],
                    "avoid_points": ["Taking all credit", "Blaming others", "Vague details"]
                }
            ],
            "teamwork": [
                {
                    "question": "Tell me about a successful team project you were part of.",
                    "star_guide": "Situation: Project context, Task: Your role, Action: Collaboration, Result: Team success",
                    "example_structure": "Project overview → Team dynamics → Your contribution → Collective achievement",
                    "emphasis_points": ["Collaboration", "Communication", "Shared success"],
                    "avoid_points": ["Individual focus", "Downplaying others", "Lack of specifics"]
                }
            ],
            # Add more default questions for other categories...
        }

    def _generate_company_questions(self, company_info: Dict) -> Dict:
        """Generate company-specific questions."""
        try:
            prompt = f"""
            Generate company-specific questions based on:
            {json.dumps(company_info)}
            
            Include:
            1. Company Culture Questions
            2. Product/Service Questions
            3. Market Position Questions
            4. Growth and Development Questions
            5. Role-Specific Questions
            6. Team Structure Questions
            7. Future Plans Questions
            8. Questions to Ask Interviewer
            
            For each question provide:
            - Question
            - Context
            - Preparation Notes
            - Response Strategy
            
            Return as detailed JSON.
            """
            
            response = self.model.generate_content(prompt)
            questions = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])
            
            return questions
            
        except Exception as e:
            logging.error(f"Company questions generation error: {str(e)}")
            return {}

    def _generate_manager_questions(self, company_info: Dict, job_analysis: Dict) -> List[Dict]:
        """Generate hiring manager round questions"""
        try:
            prompt = f"""
            Generate hiring manager interview questions based on:
            Company Info: {json.dumps(company_info, indent=2)}
            Job Analysis: {json.dumps(job_analysis, indent=2)}

            Generate questions covering:
            1. Role-specific expertise
            2. Leadership potential
            3. Strategic thinking
            4. Culture fit
            5. Career goals
            6. Project management
            7. Decision making
            8. Team dynamics

            For each question include:
            - Question text
            - Expected answer points
            - Follow-up questions
            - What manager is looking for
            - Red flags to avoid
            - Best practices
            - Example scenarios

            Return as structured JSON array.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'top_k': 40
                }
            )

            questions = json.loads(response.text[response.text.find('['):response.text.rfind(']')+1])
            
            return questions

        except Exception as e:
            logging.error(f"Manager questions generation error: {str(e)}")
            return []

    def _generate_preparation_tips(self, resume_data: Dict, job_analysis: Dict, company_info: Dict) -> Dict:
        """Generate interview preparation tips."""
        try:
            prompt = f"""
            Generate comprehensive interview preparation tips based on:
            
            Resume Data: {json.dumps(resume_data.get('parsed_data', {}))}
            Job Analysis: {json.dumps(job_analysis)}
            Company Info: {json.dumps(company_info)}
            
            Include:
            1. Pre-Interview Preparation
            2. Technical Preparation Guide
            3. Behavioral Interview Tips
            4. Company Research Points
            5. Questions to Ask
            6. Presentation Tips
            7. Remote Interview Tips
            8. Follow-up Strategies
            
            For each section provide:
            - Main Points
            - Action Items
            - Resources
            - Timeline
            
            Return as detailed JSON.
            """
            
            response = self.model.generate_content(prompt)
            tips = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])
            
            return tips
            
        except Exception as e:
            logging.error(f"Preparation tips generation error: {str(e)}")
            return {}

    def get_interview_guide(self, guide_id: str) -> Dict:
        """Retrieve stored interview guide."""
        try:
            guide = self.interviews.find_one({"_id": ObjectId(guide_id)})
            if guide:
                guide['_id'] = str(guide['_id'])
            return guide
        except Exception as e:
            logging.error(f"Guide retrieval error: {str(e)}")
            return None

    def get_interview_statistics(self, resume_id: str) -> Dict:
        """Get interview practice statistics for a resume"""
        try:
            # Get all interview sessions for this resume
            sessions = self.interviews.find({'resume_id': resume_id})
            sessions_list = list(sessions)
            
            if not sessions_list:
                return {
                    'practice_sessions': 0,
                    'questions_practiced': 0,
                    'average_score': 0
                }

            total_questions = sum(len(session.get('questions', [])) for session in sessions_list)
            total_score = sum(session.get('score', 0) for session in sessions_list)
            
            return {
                'practice_sessions': len(sessions_list),
                'questions_practiced': total_questions,
                'average_score': round(total_score / len(sessions_list), 1) if sessions_list else 0
            }
            
        except Exception as e:
            logging.error(f"Error getting interview statistics: {str(e)}")
            return {
                'practice_sessions': 0,
                'questions_practiced': 0,
                'average_score': 0
            }

    def _generate_study_plan(self, resume_data: Dict) -> Dict:
        """Generate personalized study plan based on resume"""
        try:
            skills = resume_data.get('parsed_data', {}).get('skills', [])
            experience = resume_data.get('parsed_data', {}).get('experience', [])
            
            prompt = f"""
            Generate a personalized study plan based on:
            Skills: {', '.join(skills)}
            Experience: {json.dumps(experience)}

            Return a JSON object with:
            {{
                "schedule": [
                    {{
                        "week": 1,
                        "tasks": [
                            {{
                                "title": "Task title",
                                "description": "Task description",
                                "resources": ["resource1", "resource2"]
                            }}
                        ]
                    }}
                ],
                "focus_areas": [
                    {{
                        "name": "Area name",
                        "topics": ["topic1", "topic2"],
                        "priority": "high/medium/low"
                    }}
                ],
                "resources": {{
                    "category1": [
                        {{
                            "name": "Resource name",
                            "url": "URL",
                            "type": "Type of resource",
                            "difficulty": "beginner/intermediate/advanced"
                        }}
                    ]
                }}
            }}
            """
            
            response = self.model.generate_content(prompt)
            plan = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])
            
            return plan
            
        except Exception as e:
            logging.error(f"Study plan generation error: {str(e)}")
            return self._get_default_study_plan()

    def _generate_system_design_questions(self, job_analysis: Dict) -> List[Dict]:
        """Generate system design questions based on job requirements"""
        try:
            prompt = f"""
            Generate system design interview questions based on these job requirements:
            {json.dumps(job_analysis, indent=2) if job_analysis else 'General system design requirements'}

            Return ONLY a valid JSON array with this exact structure:
            [
                {{
                    "title": "Design a URL Shortener",
                    "description": "Design a system like bit.ly that shortens URLs",
                    "difficulty": "medium",
                    "concepts": ["System Design", "Databases", "Caching"],
                    "key_components": ["Load Balancer", "Database", "Cache"],
                    "scalability_aspects": ["Horizontal scaling", "Database sharding"],
                    "discussion_points": [
                        "How would you handle millions of requests?",
                        "Database schema design",
                        "Caching strategy"
                    ],
                    "follow_up_questions": [
                        "How would you handle analytics?",
                        "What about custom URLs?"
                    ],
                    "estimated_time": "45-60 minutes"
                }}
            ]

            Make sure the JSON array is valid with no trailing commas.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32,
                    'max_output_tokens': 2048
                }
            )

            if not response.text:
                return self._get_default_system_design_questions()

            # Extract array from response
            text = response.text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                return self._get_default_system_design_questions()
            
            json_str = text[start_idx:end_idx]
            
            # Clean up common JSON issues
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            
            try:
                questions = json.loads(json_str)
                return questions if isinstance(questions, list) else self._get_default_system_design_questions()
            except json.JSONDecodeError as e:
                logging.error(f"System design questions JSON parsing error: {str(e)}")
                return self._get_default_system_design_questions()

        except Exception as e:
            logging.error(f"System design questions generation error: {str(e)}")
            return self._get_default_system_design_questions()

    def _get_default_system_design_questions(self) -> List[Dict]:
        """Return default system design questions if generation fails"""
        return [
            {
                "title": "Design a Chat Application",
                "description": "Design a real-time messaging system like WhatsApp or Slack",
                "difficulty": "medium",
                "concepts": ["WebSockets", "Databases", "Message Queues"],
                "key_components": ["Message Server", "Database", "Notification Service"],
                "scalability_aspects": ["Real-time messaging", "Message storage", "User presence"],
                "discussion_points": [
                    "How to handle real-time messaging?",
                    "Message storage and retrieval",
                    "User authentication and presence",
                    "Group chat functionality"
                ],
                "follow_up_questions": [
                    "How would you handle message encryption?",
                    "What about file sharing?",
                    "How to handle offline users?"
                ],
                "estimated_time": "45-60 minutes"
            },
            {
                "title": "Design a Social Media Feed",
                "description": "Design a news feed system like Facebook or Twitter",
                "difficulty": "hard",
                "concepts": ["Databases", "Caching", "Content Delivery"],
                "key_components": ["Feed Generator", "Timeline Service", "Content Database"],
                "scalability_aspects": ["Feed generation", "Content ranking", "Real-time updates"],
                "discussion_points": [
                    "How to generate personalized feeds?",
                    "Content ranking algorithms",
                    "Handling millions of users",
                    "Real-time feed updates"
                ],
                "follow_up_questions": [
                    "How would you handle trending topics?",
                    "What about content moderation?",
                    "How to optimize for mobile?"
                ],
                "estimated_time": "60-90 minutes"
            },
            {
                "title": "Design a URL Shortener",
                "description": "Design a URL shortening service like bit.ly or tinyurl",
                "difficulty": "easy",
                "concepts": ["Databases", "Caching", "Encoding"],
                "key_components": ["URL Encoder", "Database", "Cache Layer"],
                "scalability_aspects": ["URL encoding strategy", "Database scaling", "Cache optimization"],
                "discussion_points": [
                    "URL encoding algorithms",
                    "Database schema design",
                    "Caching strategy",
                    "Analytics and tracking"
                ],
                "follow_up_questions": [
                    "How would you handle custom URLs?",
                    "What about URL expiration?",
                    "How to handle analytics?"
                ],
                "estimated_time": "30-45 minutes"
            }
        ]

    def _get_default_study_plan(self) -> Dict:
        """Return default study plan if generation fails"""
        return {
            "schedule": [
                {
                    "week": 1,
                    "tasks": [
                        {
                            "title": "Technical Foundation Review",
                            "description": "Review core programming concepts and data structures",
                            "resources": ["LeetCode Easy Problems", "System Design Basics"]
                        }
                    ]
                }
            ],
            "focus_areas": [
                {
                    "name": "Technical Skills",
                    "topics": ["Data Structures", "Algorithms", "System Design"],
                    "priority": "high"
                }
            ],
            "resources": {
                "technical": [
                    {
                        "name": "LeetCode",
                        "url": "https://leetcode.com",
                        "type": "Practice Platform",
                        "difficulty": "intermediate"
                    }
                ]
            }
        }
    # Add these missing methods to your InterviewPreparation class:

    def _determine_experience_level(self, resume_data: Dict) -> str:
        """Determine experience level based on resume data"""
        try:
            experience = resume_data.get('parsed_data', {}).get('experience', [])
            
            if not experience:
                return 'entry'
            
            # Calculate total years of experience
            total_years = 0
            for exp in experience:
                duration = exp.get('duration', '')
                years = self._extract_years_from_duration(duration)
                total_years += years
            
            if total_years < 2:
                return 'entry'
            elif total_years < 5:
                return 'mid'
            elif total_years < 10:
                return 'senior'
            else:
                return 'lead'
                
        except Exception as e:
            logging.error(f"Experience level determination error: {str(e)}")
            return 'mid'

    def _extract_years_from_duration(self, duration: str) -> float:
        """Extract years from duration string"""
        try:
            duration = duration.lower()
            
            # Handle different formats
            if 'year' in duration:
                # Extract number before 'year'
                import re
                years_match = re.search(r'(\d+(?:\.\d+)?)\s*year', duration)
                if years_match:
                    return float(years_match.group(1))
            
            if 'month' in duration:
                # Extract months and convert to years
                months_match = re.search(r'(\d+)\s*month', duration)
                if months_match:
                    return float(months_match.group(1)) / 12
            
            # Try to extract any number (assume years)
            numbers = re.findall(r'\d+(?:\.\d+)?', duration)
            if numbers:
                return float(numbers[0])
            
            return 1.0  # Default to 1 year if can't parse
            
        except Exception:
            return 1.0

    def _generate_prep_timeline(self, requirements: Dict) -> List[Dict]:
        """Generate preparation timeline based on requirements"""
        try:
            return [
                {
                    "phase": "Week 1-2: Foundation",
                    "duration": "2 weeks",
                    "focus": "Core concepts and basic preparation",
                    "tasks": [
                        "Review resume and identify key talking points",
                        "Research company thoroughly",
                        "Practice elevator pitch",
                        "Review fundamental concepts"
                    ],
                    "deliverables": [
                        "Updated elevator pitch",
                        "Company research notes",
                        "Technical concepts summary"
                    ]
                },
                {
                    "phase": "Week 3-4: Technical Preparation",
                    "duration": "2 weeks", 
                    "focus": "Technical skills and coding practice",
                    "tasks": [
                        "Solve coding problems daily",
                        "Review system design concepts",
                        "Practice technical explanations",
                        "Mock technical interviews"
                    ],
                    "deliverables": [
                        "Coding practice log",
                        "System design templates",
                        "Technical explanation scripts"
                    ]
                },
                {
                    "phase": "Week 5-6: Behavioral & Final Prep",
                    "duration": "2 weeks",
                    "focus": "Behavioral questions and final preparation", 
                    "tasks": [
                        "Prepare STAR method examples",
                        "Practice behavioral questions",
                        "Prepare questions for interviewer",
                        "Final mock interviews"
                    ],
                    "deliverables": [
                        "STAR examples document",
                        "Questions for interviewer",
                        "Interview day checklist"
                    ]
                }
            ]
        except Exception as e:
            logging.error(f"Prep timeline generation error: {str(e)}")
            return []

    def get_learning_resources(self, resume_data: Dict) -> Dict:
        """Get learning resources based on resume skills"""
        try:
            parsed_data = resume_data.get('parsed_data', {})
            skills = parsed_data.get('skills', [])
            
            # Handle skills if it's a dict
            if isinstance(skills, dict):
                skills_list = []
                for skill_category, skill_values in skills.items():
                    if isinstance(skill_values, list):
                        skills_list.extend(skill_values)
                    elif isinstance(skill_values, str):
                        skills_list.append(skill_values)
                skills = skills_list

            return {
                'technical_resources': [
                    {'name': 'LeetCode', 'type': 'Coding Practice', 'url': 'https://leetcode.com'},
                    {'name': 'HackerRank', 'type': 'Technical Skills', 'url': 'https://hackerrank.com'},
                    {'name': 'System Design Primer', 'type': 'System Design', 'url': 'https://github.com/donnemartin/system-design-primer'},
                    {'name': 'InterviewBit', 'type': 'Interview Prep', 'url': 'https://interviewbit.com'}
                ],
                'interview_prep': [
                    {'name': 'Pramp', 'type': 'Mock Interviews', 'url': 'https://pramp.com'},
                    {'name': 'Glassdoor', 'type': 'Interview Questions', 'url': 'https://glassdoor.com'},
                    {'name': 'Blind', 'type': 'Company Insights', 'url': 'https://teamblind.com'}
                ],
                'skill_specific': [
                    {'name': f'{skill} Documentation', 'type': 'Reference', 'skill': skill, 'url': f'https://docs.{skill.lower()}.org'}
                    for skill in skills[:5] if skill
                ],
                'behavioral_prep': [
                    {'name': 'STAR Method Guide', 'type': 'Framework', 'description': 'Situation, Task, Action, Result framework for behavioral questions'},
                    {'name': 'Company Culture Research', 'type': 'Research', 'description': 'Research company values and culture fit'}
                ],
                'books': [
                    {'name': 'Cracking the Coding Interview', 'author': 'Gayle McDowell', 'type': 'Technical'},
                    {'name': 'System Design Interview', 'author': 'Alex Xu', 'type': 'System Design'},
                    {'name': 'Behavioral Interview Questions', 'author': 'Various', 'type': 'Behavioral'}
                ]
            }

        except Exception as e:
            logging.error(f"Error getting learning resources: {str(e)}")
            return self._get_default_resources()

    def _get_default_resources(self) -> Dict:
        """Get default learning resources"""
        return {
            'technical_resources': [
                {'name': 'LeetCode', 'type': 'Coding Practice', 'url': 'https://leetcode.com'},
                {'name': 'HackerRank', 'type': 'Technical Skills', 'url': 'https://hackerrank.com'}
            ],
            'interview_prep': [
                {'name': 'Pramp', 'type': 'Mock Interviews', 'url': 'https://pramp.com'},
                {'name': 'Glassdoor', 'type': 'Interview Questions', 'url': 'https://glassdoor.com'}
            ],
            'general': [
                {'name': 'STAR Method Guide', 'type': 'Behavioral Prep', 'description': 'Framework for answering behavioral questions'}
            ]
        }

    def save_interview_feedback(self, resume_id: str, feedback_data: Dict) -> Dict:
        """Save interview feedback to database"""
        try:
            feedback_doc = {
                'resume_id': resume_id,
                'feedback': feedback_data,
                'created_at': datetime.now(),
                'session_type': feedback_data.get('session_type', 'general'),
                'score': feedback_data.get('score', 0)
            }
            
            result = self.db.interview_feedback.insert_one(feedback_doc)
            
            return {
                'success': True,
                'feedback_id': str(result.inserted_id)
            }

        except Exception as e:
            logging.error(f"Save feedback error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_interview_history(self, resume_id: str) -> List[Dict]:
        """Get interview history for a resume"""
        try:
            history = list(self.db.interview_sessions.find(
                {"resume_id": resume_id}
            ).sort("created_at", -1))
            
            # Serialize ObjectIds
            for item in history:
                if '_id' in item:
                    item['_id'] = str(item['_id'])
            
            return history

        except Exception as e:
            logging.error(f"Get interview history error: {str(e)}")
            return []

    def analyze_job_sync(self, job_description: str, resume_data: Dict = None) -> Dict:
        """Analyze job description and compare with resume if provided"""
        try:
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
            8. position (title, level, department)
            9. company_info (size, industry, location)
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
                raise ValueError("No valid JSON found in response")
                
            analysis = json.loads(text[start_idx:end_idx])

            # Add match analysis if resume data is provided
            if resume_data and 'parsed_data' in resume_data:
                match_analysis = self._analyze_resume_match(analysis, resume_data)
                analysis['match_analysis'] = match_analysis

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

    def _analyze_resume_match(self, job_analysis: Dict, resume_data: Dict) -> Dict:
        """Analyze how well the resume matches the job requirements"""
        try:
            parsed_data = resume_data.get('parsed_data', {})
            resume_skills = set()
            
            # Handle skills properly
            skills = parsed_data.get('skills', [])
            if isinstance(skills, dict):
                for skill_category, skill_values in skills.items():
                    if isinstance(skill_values, list):
                        resume_skills.update(skill.lower() for skill in skill_values)
                    elif isinstance(skill_values, str):
                        resume_skills.add(skill_values.lower())
            elif isinstance(skills, list):
                resume_skills.update(skill.lower() for skill in skills)
            
            required_skills = set(skill.lower() for skill in job_analysis.get('required_skills', []))

            # Calculate match percentages
            skill_matches = resume_skills.intersection(required_skills)
            skill_match_percentage = len(skill_matches) / len(required_skills) * 100 if required_skills else 0

            # Check experience match
            experience_match = self._check_experience_match(
                job_analysis.get('experience_needed', ''),
                parsed_data.get('experience', [])
            )

            return {
                'overall_match_percentage': round(skill_match_percentage, 2),
                'matching_skills': list(skill_matches),
                'missing_skills': list(required_skills - resume_skills),
                'additional_skills': list(resume_skills - required_skills),
                'experience_match': experience_match,
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
            required_years = 0
            import re
            years_match = re.search(r'(\d+)', required_experience)
            if years_match:
                required_years = int(years_match.group(1))
            
            # Calculate total experience from resume
            total_years = 0
            for exp in resume_experience:
                duration = exp.get('duration', '')
                years = self._extract_years_from_duration(duration)
                total_years += years

            return {
                'has_sufficient_experience': total_years >= required_years,
                'years_of_experience': round(total_years, 1),
                'years_required': required_years,
                'gap': max(0, required_years - total_years)
            }

        except Exception as e:
            logging.error(f"Experience match check error: {str(e)}")
            return {}

    def _generate_match_recommendations(self, match_percentage: float, missing_skills: List[str]) -> List[str]:
        """Generate recommendations based on match analysis"""
        recommendations = []
        
        if match_percentage < 50:
            recommendations.append("Consider gaining more relevant skills before applying")
            recommendations.append("Focus on learning the most critical missing technologies")
        elif match_percentage < 75:
            recommendations.append("Good match! Consider highlighting relevant experience more prominently")
            recommendations.append("Consider learning 1-2 additional skills to strengthen your profile")
        else:
            recommendations.append("Excellent match! You should definitely apply")
            recommendations.append("Emphasize your matching skills in your application")

        if missing_skills:
            recommendations.append(f"Consider learning: {', '.join(missing_skills[:3])}")

        return recommendations

    def _scrape_salary_data(self, job_title: str) -> Dict:
        """Get salary data for a job title"""
        try:
            # In a real implementation, you'd scrape from salary sites
            # For now, return mock data
            return {
                'average_salary': '$80,000 - $120,000',
                'salary_range': {
                    'min': 80000,
                    'max': 120000,
                    'median': 100000
                },
                'factors': [
                    'Experience level significantly impacts salary',
                    'Location affects compensation',
                    'Company size influences pay scale',
                    'Technical skills premium applies'
                ],
                'sources': ['Glassdoor', 'PayScale', 'Indeed']
            }
        except Exception as e:
            logging.error(f"Salary data error: {str(e)}")
            return {}

    def _get_company_insights(self, job_title: str) -> Dict:
        """Get company insights for the role"""
        try:
            return {
                'industry_trends': [
                    'Remote work becoming more common',
                    'Focus on cloud technologies',
                    'Emphasis on agile methodologies',
                    'Growing importance of data skills'
                ],
                'hiring_trends': [
                    'Companies prioritizing cultural fit',
                    'Technical skills remain crucial',
                    'Portfolio projects highly valued',
                    'Continuous learning expectations'
                ],
                'preparation_tips': [
                    'Research company recent news',
                    'Understand their technology stack',
                    'Prepare relevant project examples',
                    'Practice explaining technical concepts simply'
                ]
            }
        except Exception as e:
            logging.error(f"Company insights error: {str(e)}")
            return {}
    # In interview_preparation.py, add these missing methods if they don't exist:

    def _research_company(self, company_name: str) -> Dict:
        """Research company information"""
        try:
            return {
                'company_size': 'Unknown',
                'industry': 'Technology',
                'recent_news': [],
                'culture_notes': ['Research company values', 'Check recent news', 'Review company website']
            }
        except Exception as e:
            logging.error(f"Company research error: {str(e)}")
            return {}

    def _analyze_job_requirements(self, job_description: str) -> Dict:
        """Analyze job requirements from description"""
        try:
            return {
                'required_skills': [],
                'experience_level': 'mid',
                'key_responsibilities': [],
                'nice_to_have': []
            }
        except Exception as e:
            logging.error(f"Job analysis error: {str(e)}")
            return {}
    def _create_default_guide(self, parsed_data: Dict, job_description: str) -> Dict:
        return {
            'technical_preparation': {
                'core_concepts': [
                    {
                        'question': 'Explain your experience with the main technologies in your resume',
                        'expected_points': ['Depth of knowledge', 'Practical applications', 'Recent projects'],
                        'follow_up': ['What challenges did you face?', 'How did you solve them?'],
                        'difficulty': 'medium'
                    }
                ],
                'problem_solving': [
                    {
                        'question': 'How do you approach solving complex technical problems?',
                        'expected_points': ['Systematic approach', 'Research methods', 'Testing strategies'],
                        'follow_up': ['Give an example', 'What tools do you use?'],
                        'difficulty': 'medium'
                    }
                ],
                'recommended_topics': ['Problem solving', 'System design', 'Technical concepts'],
                'practice_resources': ['Practice platforms', 'Documentation review']
            },
            'behavioral_questions': {
                'common_questions': [
                    'Tell me about yourself',
                    'Why do you want to work here?',
                    'Describe a challenging project'
                ],
                'star_method_examples': ['Prepare examples using STAR method'],
                'preparation_notes': ['Use specific examples', 'Focus on your role', 'Highlight results']
            },
            'company_questions': {
                'about_role': [
                    'What does success look like in this role?',
                    'What are the biggest challenges facing the team?',
                    'How does this role contribute to company goals?'
                ],
                'about_company': [
                    'What is the company culture like?',
                    'What are the growth opportunities?',
                    'How does the company handle work-life balance?'
                ]
            },
            'preparation_tips': {
                'timeline': '1-2 weeks before interview',
                'daily_preparation': [
                    'Research company and role',
                    'Practice technical skills',
                    'Prepare STAR examples',
                    'Mock interview practice'
                ],
                'general_tips': [
                    'Be specific with examples',
                    'Show enthusiasm',
                    'Ask thoughtful questions',
                    'Follow up promptly'
                ]
            }
        }