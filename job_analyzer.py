#writes cover letter

import json
#import spacy
from typing import Dict, List, Tuple, Any
from bs4 import BeautifulSoup
import requests
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
from pymongo import MongoClient
# import cohere
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re
import google.generativeai as genai
from google.generativeai.types import content_types

class JobAnalyzer:
    def __init__(self):
        load_dotenv()
        #self.nlp = spacy.load("en_core_web_lg")
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize MongoDB
        self.mongo_client = MongoClient("mongodb://127.0.0.1:27017")
        self.db = self.mongo_client["resumeDB"]
        
        # Collections
        self.resumes = self.db["resumes"]
        self.job_matches = self.db["job_matches"]

    def get_similar_jobs_sync(self, job_description: str, company: str = '') -> List[Dict]:
        """Get similar jobs based on description"""
        try:
            # Use Gemini to find similar jobs
            prompt = f"""
            Based on this job description and company, find 5 similar job titles and descriptions:
            
            Job Description: {job_description}
            Company: {company}

            Return a JSON array of similar jobs with format:
            [{{
                "title": "Job Title",
                "company": "Company Name",
                "description": "Brief description",
                "location": "Location",
                "salary": "Salary range (if available)"
            }}]
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40
                }
            )

            # Parse response
            text = response.text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                return []
                
            similar_jobs = json.loads(text[start_idx:end_idx])
            
            return similar_jobs[:5]  # Return top 5 similar jobs

        except Exception as e:
            print(f"Similar jobs error: {str(e)}")
            return []

    def get_industry_insights_sync(self, job_title: str, industry: str) -> List[Dict]:
        """Get industry insights for the job"""
        try:
            prompt = f"""
            Provide industry insights for this role:
            Job Title: {job_title}
            Industry: {industry}

            Return a JSON array with format:
            [{{
                "title": "Insight Title",
                "description": "Detailed description",
                "growth_rate": "Growth rate or trend",
                "source": "Source of information"
            }}]

            Include insights about:
            1. Industry trends
            2. Salary ranges
            3. Growth potential
            4. Required skills trends
            5. Market demand
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40
                }
            )

            # Parse response
            text = response.text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                return []
                
            insights = json.loads(text[start_idx:end_idx])
            
            return insights

        except Exception as e:
            print(f"Industry insights error: {str(e)}")
            return []

    def _extract_job_title_from_description(self, job_description: str) -> str:
        """Extract job title from description text"""
        try:
            # Use Gemini to extract title
            prompt = f"""
            Extract the job title from this description:
            {job_description}

            Return only the job title as a single line of text.
            """
            response = self.model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            print(f"Job title extraction error: {str(e)}")
            return "Not specified"

    def _scrape_linkedin_jobs(self, job_title: str) -> List[Dict]:
        """Get job listings from LinkedIn"""
        try:
            return [{
                'title': job_title,
                'company': 'Various Companies',
                'url': f'https://www.linkedin.com/jobs/search/?keywords={job_title.replace(" ", "%20")}'
            }]
        except Exception as e:
            print(f"LinkedIn scraping error: {str(e)}")
            return []

    def _scrape_indeed(self, job_title: str) -> List[Dict]:
        """Get job listings from Indeed"""
        try:
            return [{
                'title': job_title,
                'company': 'Various Companies',
                'url': f'https://www.indeed.com/jobs?q={job_title.replace(" ", "+")}'
            }]
        except Exception as e:
            print(f"Indeed scraping error: {str(e)}")
            return []

    def _scrape_glassdoor(self, job_title: str) -> List[Dict]:
        """Get job data from Glassdoor"""
        try:
            return [{
                'title': job_title,
                'company': 'Various Companies',
                'url': f'https://www.glassdoor.com/Job/jobs.htm?sc.keyword={job_title.replace(" ", "+")}'
            }]
        except Exception as e:
            print(f"Glassdoor scraping error: {str(e)}")
            return []

    def _scrape_stackoverflow(self, job_title: str) -> List[Dict]:
        """Get job data from StackOverflow"""
        try:
            return [{
                'title': job_title,
                'company': 'Various Companies',
                'url': f'https://stackoverflow.com/jobs?q={job_title.replace(" ", "+")}'
            }]
        except Exception as e:
            print(f"StackOverflow scraping error: {str(e)}")
            return []

    def _get_company_insights(self, job_title: str) -> Dict:
        """Get company insights and research"""
        return {
            'company_culture': 'Information not available',
            'work_environment': 'Information not available',
            'growth_opportunities': 'Information not available',
            'research_links': [
                {
                    'name': 'Company Reviews',
                    'url': f'https://www.glassdoor.com/Reviews/company-reviews.htm'
                },
                {
                    'name': 'Company Research',
                    'url': f'https://www.linkedin.com/company/'
                }
            ]
        }

    def _get_market_trends(self, job_title: str) -> Dict:
        """Get market trends for the role"""
        return {
            'demand': 'High',
            'growth_rate': '15% annually',
            'industry_outlook': 'Positive',
            'research_links': [
                {
                    'name': 'Industry Reports',
                    'url': 'https://www.bls.gov/ooh/'
                },
                {
                    'name': 'Salary Trends',
                    'url': f'https://www.payscale.com/research/US/Job={job_title.replace(" ", "_")}'
                }
            ]
        }

    def _get_salary_range(self, job_title: str, level: str) -> str:
        """Get salary range for job title and level"""
        base_ranges = {
            'entry': '40,000-60,000',
            'mid': '60,000-90,000',
            'senior': '90,000-140,000'
        }
        return base_ranges.get(level, 'Not available')

    def analyze_job_sync(self, job_description: str, resume_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Enhanced job analysis with culture fit and career path"""
        try:
            prompt = f"""
            Analyze this job description in detail:
            {job_description}

            Return a JSON object with:
            {{
                "position": {{
                    "title": "Job title",
                    "level": "Career level",
                    "department": "Department/team"
                }},
                "company_culture": {{
                    "values": ["List of company values"],
                    "work_style": "Remote/Hybrid/Office",
                    "team_dynamics": "Description of team collaboration",
                    "communication": "Communication style and expectations"
                }},
                "growth_potential": {{
                    "career_path": ["Possible career progression steps"],
                    "skill_development": ["Skills to develop for growth"],
                    "advancement_timeline": "Estimated timeline for progression"
                }},
                "required_skills": {{
                    "technical": ["Technical skills"],
                    "soft": ["Soft skills"],
                    "tools": ["Required tools"]
                }},
                "salary_insights": {{
                    "range": "Salary range",
                    "industry_average": "Industry average",
                    "benefits": ["List of benefits"],
                    "negotiables": ["Negotiable aspects"]
                }}
            }}
            """

            response = self.model.generate_content(prompt)
            analysis = json.loads(response.text[response.text.find('{'):response.text.rfind('}')+1])

            # Add real salary data from scraping
            salary_data = self._scrape_salary_data(analysis['position']['title'])
            analysis['salary_data'] = salary_data

            # Add real company reviews
            if 'company_name' in analysis:
                company_reviews = self._scrape_company_reviews(analysis['company_name'])
                analysis['company_reviews'] = company_reviews

            # Add resume match if provided
            if resume_data:
                analysis['match_analysis'] = self._analyze_resume_match(analysis, resume_data)
                analysis['culture_fit'] = self._analyze_culture_fit(analysis, resume_data)

            return {
                'success': True,
                'analysis': analysis
            }

        except Exception as e:
            print(f"Job analysis error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _scrape_salary_data(self, job_title: str) -> Dict[str, Any]:
        """Scrape real salary data from multiple sources"""
        try:
            # Format job title for URLs
            formatted_title = job_title.lower().replace(' ', '-')
            
            salary_data = {
                'sources': [
                    {
                        'name': 'Glassdoor',
                        'url': f'https://www.glassdoor.com/Salaries/{formatted_title}-salary-SRCH_KO0,{len(job_title)}.htm',
                        'data': self._scrape_glassdoor_salary(formatted_title)
                    },
                    {
                        'name': 'PayScale',
                        'url': f'https://www.payscale.com/research/US/Job={formatted_title}/Salary',
                        'data': self._scrape_payscale_salary(formatted_title)
                    },
                    {
                        'name': 'Indeed',
                        'url': f'https://www.indeed.com/career/{formatted_title}/salaries',
                        'data': self._scrape_indeed_salary(formatted_title)
                    }
                ],
                'average': None,
                'range': None
            }

            # Calculate average from available data
            valid_salaries = [source['data']['average'] for source in salary_data['sources'] 
                             if source['data'] and source['data']['average']]
            if valid_salaries:
                salary_data['average'] = sum(valid_salaries) / len(valid_salaries)
                salary_data['range'] = {
                    'min': min(s['data']['range']['min'] for s in salary_data['sources'] if s['data'] and s['data']['range']),
                    'max': max(s['data']['range']['max'] for s in salary_data['sources'] if s['data'] and s['data']['range'])
                }

            return salary_data

        except Exception as e:
            print(f"Salary scraping error: {str(e)}")
            return {
                'sources': [],
                'average': None,
                'range': None
            }

    def _scrape_glassdoor_salary(self, job_title: str) -> Dict[str, Any]:
        """Get salary data from Glassdoor using SerpAPI or direct search"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Use Google search to find Glassdoor salary page
            search_query = f"{job_title} salary glassdoor"
            search_url = f"https://www.google.com/search?q={search_query}"
            
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract first Glassdoor result
            salary_data = {
                'average': None,
                'range': {'min': None, 'max': None},
                'source_url': None
            }

            # Find Glassdoor link
            glassdoor_link = soup.find('a', href=re.compile(r'glassdoor\.com.*salary'))
            if glassdoor_link:
                salary_data['source_url'] = glassdoor_link['href']
                
                # Visit Glassdoor page
                glassdoor_response = requests.get(glassdoor_link['href'], headers=headers)
                glassdoor_soup = BeautifulSoup(glassdoor_response.text, 'html.parser')
                
                # Extract salary information using common patterns
                salary_text = glassdoor_soup.find(text=re.compile(r'\$[\d,]+\s*-\s*\$[\d,]+'))
                if salary_text:
                    salary_range = re.findall(r'\$[\d,]+', salary_text)
                    if len(salary_range) >= 2:
                        salary_data['range']['min'] = self._parse_salary(salary_range[0])
                        salary_data['range']['max'] = self._parse_salary(salary_range[1])
                        salary_data['average'] = (salary_data['range']['min'] + salary_data['range']['max']) / 2

            return salary_data

        except Exception as e:
            print(f"Glassdoor salary scraping error: {str(e)}")
            return {'average': None, 'range': {'min': None, 'max': None}, 'source_url': None}

    def _scrape_indeed_salary(self, job_title: str) -> Dict[str, Any]:
        """Get salary data from Indeed using search"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            search_query = f"{job_title} salary indeed"
            search_url = f"https://www.google.com/search?q={search_query}"
            
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            salary_data = {
                'average': None,
                'range': {'min': None, 'max': None},
                'source_url': None
            }

            # Find Indeed link
            indeed_link = soup.find('a', href=re.compile(r'indeed\.com.*salary'))
            if indeed_link:
                salary_data['source_url'] = indeed_link['href']
                
                indeed_response = requests.get(indeed_link['href'], headers=headers)
                indeed_soup = BeautifulSoup(indeed_response.text, 'html.parser')
                
                salary_text = indeed_soup.find(text=re.compile(r'\$[\d,]+\s*-\s*\$[\d,]+'))
                if salary_text:
                    salary_range = re.findall(r'\$[\d,]+', salary_text)
                    if len(salary_range) >= 2:
                        salary_data['range']['min'] = self._parse_salary(salary_range[0])
                        salary_data['range']['max'] = self._parse_salary(salary_range[1])
                        salary_data['average'] = (salary_data['range']['min'] + salary_data['range']['max']) / 2

            return salary_data

        except Exception as e:
            print(f"Indeed salary scraping error: {str(e)}")
            return {'average': None, 'range': {'min': None, 'max': None}, 'source_url': None}

    def _scrape_payscale_salary(self, job_title: str) -> Dict[str, Any]:
        """Get salary data from PayScale using search"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            search_query = f"{job_title} salary payscale"
            search_url = f"https://www.google.com/search?q={search_query}"
            
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            salary_data = {
                'average': None,
                'range': {'min': None, 'max': None},
                'source_url': None
            }

            # Find PayScale link
            payscale_link = soup.find('a', href=re.compile(r'payscale\.com.*salary'))
            if payscale_link:
                salary_data['source_url'] = payscale_link['href']
                
                payscale_response = requests.get(payscale_link['href'], headers=headers)
                payscale_soup = BeautifulSoup(payscale_response.text, 'html.parser')
                
                salary_text = payscale_soup.find(text=re.compile(r'\$[\d,]+\s*-\s*\$[\d,]+'))
                if salary_text:
                    salary_range = re.findall(r'\$[\d,]+', salary_text)
                    if len(salary_range) >= 2:
                        salary_data['range']['min'] = self._parse_salary(salary_range[0])
                        salary_data['range']['max'] = self._parse_salary(salary_range[1])
                        salary_data['average'] = (salary_data['range']['min'] + salary_data['range']['max']) / 2

            return salary_data

        except Exception as e:
            print(f"PayScale salary scraping error: {str(e)}")
            return {'average': None, 'range': {'min': None, 'max': None}, 'source_url': None}

    def _parse_salary(self, salary_str: str) -> float:
        """Parse salary string to float"""
        try:
            return float(salary_str.replace('$', '').replace(',', ''))
        except:
            return 0.0

    def _analyze_resume_match(self, job_analysis: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze resume match with job requirements"""
        try:
            # Extract skills
            resume_skills = set(skill.lower() for skill in resume_data.get('parsed_data', {}).get('skills', []))
            required_skills = set()
            
            # Collect all required skills
            for skill_type in ['technical', 'soft', 'tools']:
                skills = job_analysis.get('required_skills', {}).get(skill_type, [])
                required_skills.update(skill.lower() for skill in skills)

            # Calculate matches
            matching_skills = resume_skills.intersection(required_skills)
            missing_skills = required_skills - resume_skills
            additional_skills = resume_skills - required_skills
            
            # Calculate match percentage
            if required_skills:
                match_percentage = (len(matching_skills) / len(required_skills)) * 100
            else:
                match_percentage = 0

            return {
                'overall_match': round(match_percentage, 2),
                'matching_skills': list(matching_skills),
                'missing_skills': list(missing_skills),
                'additional_skills': list(additional_skills),
                'total_required': len(required_skills),
                'total_matching': len(matching_skills)
            }

        except Exception as e:
            print(f"Resume match analysis error: {str(e)}")
            return {
                'overall_match': 0,
                'matching_skills': [],
                'missing_skills': [],
                'additional_skills': [],
                'total_required': 0,
                'total_matching': 0
            }

    def _analyze_culture_fit(self, job_analysis: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze culture fit based on resume and job requirements"""
        try:
            resume_experience = resume_data.get('parsed_data', {}).get('experience', [])
            work_style_indicators = {
                'remote_work': 0,
                'team_collaboration': 0,
                'leadership': 0,
                'communication': 0
            }

            # Analyze past experience for cultural indicators
            for exp in resume_experience:
                exp_text = f"{exp.get('description', '')} {exp.get('achievements', '')}"
                if 'remote' in exp_text.lower():
                    work_style_indicators['remote_work'] += 1
                if any(word in exp_text.lower() for word in ['team', 'collaboration', 'group']):
                    work_style_indicators['team_collaboration'] += 1
                if any(word in exp_text.lower() for word in ['lead', 'manage', 'direct']):
                    work_style_indicators['leadership'] += 1
                if any(word in exp_text.lower() for word in ['communicate', 'present', 'report']):
                    work_style_indicators['communication'] += 1

            job_culture = job_analysis.get('company_culture', {})
            fit_analysis = {
                'overall_fit': 0,
                'strengths': [],
                'areas_to_consider': [],
                'recommendations': []
            }

            # Calculate fit scores
            if job_culture.get('work_style') == 'Remote' and work_style_indicators['remote_work'] > 0:
                fit_analysis['strengths'].append('Remote work experience')
            
            if 'team' in job_culture.get('team_dynamics', '').lower() and work_style_indicators['team_collaboration'] > 0:
                fit_analysis['strengths'].append('Team collaboration experience')

            # Calculate overall fit
            fit_analysis['overall_fit'] = (len(fit_analysis['strengths']) / 4) * 100

            return fit_analysis

        except Exception as e:
            print(f"Culture fit analysis error: {str(e)}")
            return {
                'overall_fit': 0,
                'strengths': [],
                'areas_to_consider': [],
                'recommendations': []
            }

    def get_job_recommendations_sync(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get job recommendations based on resume"""
        try:
            # Extract skills and experience
            parsed_data = resume_data.get('parsed_data', {})
            skills = parsed_data.get('skills', [])
            experience = parsed_data.get('experience', [])

            prompt = f"""
            Analyze this professional profile and provide detailed recommendations:
            Skills: {', '.join(skills if isinstance(skills, list) else [])}
            Experience: {json.dumps(experience, indent=2)}

            Return a JSON object with:
            {{
                "roles": [
                    {{
                        "title": "Job title",
                        "match_score": "85",
                        "description": "Role description",
                        "salary_range": "Salary range"
                    }}
                ],
                "industry_insights": [
                    {{
                        "title": "Insight title",
                        "description": "Insight description",
                        "growth_rate": "Growth percentage"
                    }}
                ],
                "career_path": [
                    {{
                        "role": "Position title",
                        "timeline": "1-2 years",
                        "description": "Role description",
                        "required_skills": ["skill1", "skill2"]
                    }}
                ],
                "skill_analysis": {{
                    "current_strengths": ["skill1", "skill2"],
                    "development_areas": ["skill1", "skill2"],
                    "emerging_skills": ["skill1", "skill2"]
                }}
            }}
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40
                }
            )

            # Parse response
            text = response.text.strip()
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format")
                
            recommendations = json.loads(text[start_idx:end_idx])

            # Add real salary data for recommended roles
            for role in recommendations.get('roles', []):
                salary_data = self._scrape_salary_data(role['title'])
                if salary_data.get('range'):
                    role['salary_range'] = f"{salary_data['range']['min']} - {salary_data['range']['max']}"

            return {
                'success': True,
                'recommendations': recommendations
            }

        except Exception as e:
            print(f"Job recommendations error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': {
                    'roles': [],
                    'industry_insights': [],
                    'career_path': [],
                    'skill_analysis': {
                        'current_strengths': [],
                        'development_areas': [],
                        'emerging_skills': []
                    }
                }
            }

    def calculate_resume_analytics(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive resume analytics using Gemini AI"""
        try:
            parsed_data = resume_data.get('parsed_data', {})
            
            # Prepare resume text for analysis
            resume_text = json.dumps(parsed_data, indent=2)
            
            prompt = f"""
            Analyze this resume comprehensively and provide detailed analytics:
            
            Resume Data: {resume_text}
            
            Return a JSON object with exact structure:
            {{
                "ats_score": {{
                    "overall": 85,
                    "breakdown": {{
                        "format": 90,
                        "keywords": 80,
                        "experience": 85,
                        "skills": 88,
                        "education": 92
                    }},
                    "recommendations": ["Add more quantified achievements", "Include industry keywords"]
                }},
                "job_matches": [
                    {{
                        "role": "Software Engineer",
                        "match_percentage": 85,
                        "salary_range": "$75,000-$95,000",
                        "market_demand": "High"
                    }},
                    {{
                        "role": "Full Stack Developer", 
                        "match_percentage": 80,
                        "salary_range": "$70,000-$90,000",
                        "market_demand": "High"
                    }},
                    {{
                        "role": "Backend Developer",
                        "match_percentage": 75,
                        "salary_range": "$68,000-$88,000", 
                        "market_demand": "Medium-High"
                    }}
                ],
                "salary_analysis": {{
                    "estimated_range": "$75,000-$95,000",
                    "market_average": "$82,500",
                    "experience_level": "Mid-level",
                    "location_factor": "United States",
                    "growth_potential": "15% annually"
                }},
                "skills_analysis": {{
                    "technical_skills": {{
                        "strengths": ["Python", "JavaScript", "React"],
                        "in_demand": ["Cloud Computing", "DevOps", "Machine Learning"],
                        "missing": ["Docker", "Kubernetes", "AWS"]
                    }},
                    "soft_skills": {{
                        "identified": ["Leadership", "Communication", "Problem Solving"],
                        "recommended": ["Project Management", "Team Collaboration"]
                    }}
                }},
                "experience_analysis": {{
                    "total_years": 3.5,
                    "progression": "Good",
                    "industry_relevance": "High",
                    "achievements_quantified": 65,
                    "recommendations": ["Add more metrics", "Highlight leadership roles"]
                }},
                "profile_completeness": {{
                    "overall": 78,
                    "sections": {{
                        "personal_info": 95,
                        "experience": 85,
                        "skills": 80,
                        "education": 90,
                        "projects": 65,
                        "certifications": 45
                    }},
                    "missing_sections": ["Certifications", "Awards"]
                }},
                "improvement_suggestions": [
                    {{
                        "priority": "High",
                        "category": "ATS Optimization",
                        "suggestion": "Add more industry-specific keywords",
                        "impact": "Increase ATS score by 10-15%"
                    }},
                    {{
                        "priority": "Medium", 
                        "category": "Skills",
                        "suggestion": "Add cloud computing certifications",
                        "impact": "Better job matching for senior roles"
                    }},
                    {{
                        "priority": "Low",
                        "category": "Formatting",
                        "suggestion": "Improve section organization",
                        "impact": "Better readability"
                    }}
                ],
                "market_insights": {{
                    "industry_trends": [
                        "Cloud computing skills in high demand",
                        "Remote work experience valued",
                        "Full-stack development trending"
                    ],
                    "salary_trends": "15% growth year-over-year",
                    "job_availability": "High demand in tech sector"
                }}
            }}
            
            Analyze based on:
            1. ATS compatibility (keywords, format, structure)
            2. Market demand for skills
            3. Experience progression and achievements
            4. Salary potential based on skills and experience
            5. Job role matches with realistic percentages
            6. Specific improvement recommendations
            7. Current market trends and insights
            
            Ensure all scores are realistic (0-100) and suggestions are actionable.
            """

            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,  # Lower temperature for consistent analysis
                    'top_p': 0.8,
                    'top_k': 20,
                    'max_output_tokens': 4096
                }
            )

            # Parse response
            text = response.text.strip()
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("Invalid response format from AI")
                
            analytics = json.loads(text[start_idx:end_idx])
            
            # Add timestamp and metadata
            analytics['generated_at'] = datetime.now().isoformat()
            analytics['version'] = '1.0'
            analytics['resume_id'] = str(resume_data.get('_id', ''))
            
            # Store analytics in database
            resume_id = resume_data.get('_id')
            if resume_id:
                # Update resume document with analytics
                self.resumes.update_one(
                    {'_id': resume_id},
                    {
                        '$set': {
                            'analytics': analytics,
                            'analytics_updated': datetime.now()
                        }
                    }
                )
                print(f"Analytics stored for resume {resume_id}")
            
            return {
                'success': True,
                'analytics': analytics
            }

        except json.JSONDecodeError as e:
            print(f"JSON parsing error in analytics: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to parse AI response',
                'analytics': self._get_default_analytics()
            }
        except Exception as e:
            print(f"Resume analytics calculation error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analytics': self._get_default_analytics()
            }

    def _get_default_analytics(self) -> Dict[str, Any]:
        """Return default analytics structure when calculation fails"""
        return {
            "ats_score": {
                "overall": 70,
                "breakdown": {
                    "format": 80,
                    "keywords": 60,
                    "experience": 70,
                    "skills": 75,
                    "education": 85
                },
                "recommendations": ["Add more quantified achievements", "Include industry keywords"]
            },
            "job_matches": [
                {
                    "role": "Software Engineer",
                    "match_percentage": 75,
                    "salary_range": "$70,000-$90,000",
                    "market_demand": "High"
                },
                {
                    "role": "Developer",
                    "match_percentage": 70,
                    "salary_range": "$65,000-$85,000",
                    "market_demand": "Medium-High"
                }
            ],
            "salary_analysis": {
                "estimated_range": "$70,000-$90,000",
                "market_average": "$80,000",
                "experience_level": "Mid-level",
                "location_factor": "United States",
                "growth_potential": "10% annually"
            },
            "skills_analysis": {
                "technical_skills": {
                    "strengths": [],
                    "in_demand": ["Cloud Computing", "Machine Learning"],
                    "missing": ["Advanced frameworks"]
                },
                "soft_skills": {
                    "identified": ["Communication"],
                    "recommended": ["Leadership", "Project Management"]
                }
            },
            "experience_analysis": {
                "total_years": 2,
                "progression": "Good",
                "industry_relevance": "Medium",
                "achievements_quantified": 50,
                "recommendations": ["Add more metrics", "Highlight achievements"]
            },
            "profile_completeness": {
                "overall": 70,
                "sections": {
                    "personal_info": 90,
                    "experience": 70,
                    "skills": 75,
                    "education": 80,
                    "projects": 60,
                    "certifications": 30
                },
                "missing_sections": ["Certifications", "Projects"]
            },
            "improvement_suggestions": [
                {
                    "priority": "High",
                    "category": "Content",
                    "suggestion": "Add more quantified achievements",
                    "impact": "Improve ATS score"
                }
            ],
            "market_insights": {
                "industry_trends": ["Technology skills in demand"],
                "salary_trends": "Stable growth",
                "job_availability": "Good opportunities available"
            },
            "generated_at": datetime.now().isoformat(),
            "version": "1.0"
        }

    def get_resume_analytics(self, resume_id: str) -> Dict[str, Any]:
        """Get analytics for a specific resume, calculate if not exists"""
        try:
            from bson import ObjectId
            
            # Get resume data
            resume = self.resumes.find_one({'_id': ObjectId(resume_id)})
            if not resume:
                return {
                    'success': False,
                    'error': 'Resume not found'
                }
            
            # Check if analytics already exist and are recent (less than 24 hours old)
            if 'analytics' in resume and 'analytics_updated' in resume:
                last_updated = resume['analytics_updated']
                if isinstance(last_updated, datetime):
                    if (datetime.now() - last_updated).total_seconds() < 86400:  # 24 hours
                        print(f"Using cached analytics for resume {resume_id}")
                        return {
                            'success': True,
                            'analytics': resume['analytics'],
                            'cached': True
                        }
            
            # Calculate new analytics
            print(f"Calculating new analytics for resume {resume_id}")
            result = self.calculate_resume_analytics(resume)
            
            if result['success']:
                result['cached'] = False
                
            return result
            
        except Exception as e:
            print(f"Error getting resume analytics: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analytics': self._get_default_analytics()
            }