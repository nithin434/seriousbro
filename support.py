import json
import logging  
from typing import Dict, List
from google.generativeai import GenerativeModel
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
def dashbord_analytics():
    pass