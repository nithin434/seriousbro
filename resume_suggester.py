import logging
from typing import Dict, List, Any
import json
import re
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
import os

@dataclass
class SectionSuggestion:
    section_name: str
    original_content: str
    suggestions: List[str]
    improvements: List[str]
    keep_elements: List[str]
    remove_elements: List[str]
    score: float
    comments: str

class ResumeSuggester:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Initialize Gemini API
        try:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini: {str(e)}")
            self.model = None

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
            self.logger.error(f"JSON cleaning error: {str(e)}")
            return '{}'

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Safely parse JSON with fallback"""
        try:
            cleaned_json = self._clean_json_response(text)
            return json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {str(e)}")
            return self._get_default_analysis()
        except Exception as e:
            self.logger.error(f"Unexpected parsing error: {str(e)}")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> Dict[str, Any]:
        """Return default analysis when AI fails"""
        return {
            'suggestions': ['Review content for improvements', 'Consider professional formatting'],
            'keep_elements': ['Existing content structure'],
            'remove_elements': ['Unnecessary information'],
            'score': 65,
            'comments': 'General analysis - consider manual review for specific improvements'
        }
        
    def _get_gemini_analysis(self, section_name: str, content: str) -> Dict[str, Any]:
        """Get AI-powered analysis from Gemini with robust error handling"""
        try:
            if not self.model:
                return self._get_default_analysis()

            prompt = f"""
            Analyze this {section_name} section of a resume and provide detailed feedback:
            
            Content:
            {content}
            
            Please provide your response as a valid JSON object with these exact keys:
            {{
                "suggestions": ["suggestion1", "suggestion2"],
                "keep_elements": ["element1", "element2"],
                "remove_elements": ["element1", "element2"],
                "score": 75,
                "comments": "detailed comments here"
            }}

            Focus on:
            1. ATS optimization
            2. Professional formatting
            3. Content improvements
            4. Industry best practices

            Ensure the JSON is valid with no trailing commas.
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32,
                    'max_output_tokens': 1024
                }
            )
            
            if not response.text:
                return self._get_default_analysis()

            # Use safe JSON parsing
            analysis = self._parse_json_safely(response.text)
            
            # Validate required fields
            required_fields = ['suggestions', 'keep_elements', 'remove_elements', 'score', 'comments']
            for field in required_fields:
                if field not in analysis:
                    if field == 'score':
                        analysis[field] = 65
                    elif field == 'comments':
                        analysis[field] = f"Analysis for {section_name} section"
                    else:
                        analysis[field] = []

            # Ensure score is a number
            if not isinstance(analysis['score'], (int, float)):
                analysis['score'] = 65

            return analysis
            
        except Exception as e:
            self.logger.error(f"Gemini API error: {str(e)}")
            return self._get_default_analysis()
        
    def analyze_resume(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze resume and provide comprehensive suggestions
        """
        try:
            parsed_data = resume_data.get('parsed_data', {})
            
            # Analyze each section
            sections = {
                'personal_info': self._analyze_personal_info(parsed_data.get('personal_info', {})),
                'summary': self._analyze_summary(parsed_data.get('summary', '')),
                'experience': self._analyze_experience(parsed_data.get('experience', [])),
                'education': self._analyze_education(parsed_data.get('education', [])),
                'skills': self._analyze_skills(parsed_data.get('skills', {})),
                'projects': self._analyze_projects(parsed_data.get('projects', [])),
                'certifications': self._analyze_certifications(parsed_data.get('certifications', []))
            }
            
            # Calculate overall metrics
            metrics = self._calculate_metrics(sections)
            
            # Generate overall summary
            summary = self._generate_summary(sections, metrics)
            
            return {
                'success': True,
                'sections': sections,
                'metrics': metrics,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing resume: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_personal_info(self, personal_info: Dict) -> SectionSuggestion:
        """Analyze personal information section"""
        content = json.dumps(personal_info, indent=2) if personal_info else "No personal information found"
        ai_analysis = self._get_gemini_analysis("Personal Information", content)
        
        return SectionSuggestion(
            section_name="Personal Information",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Personal information analysis')
        )
    
    def _analyze_summary(self, summary: str) -> SectionSuggestion:
        """Analyze professional summary section"""
        if isinstance(summary, list):
            summary = ' '.join(summary)
        elif not isinstance(summary, str):
            summary = str(summary) if summary else "No summary provided"
            
        ai_analysis = self._get_gemini_analysis("Professional Summary", summary)
        
        return SectionSuggestion(
            section_name="Professional Summary",
            original_content=summary,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Professional summary analysis')
        )
    
    def _analyze_experience(self, experience: List[Dict]) -> SectionSuggestion:
        """Analyze work experience section"""
        content = json.dumps(experience, indent=2) if experience else "No work experience found"
        ai_analysis = self._get_gemini_analysis("Work Experience", content)
        
        return SectionSuggestion(
            section_name="Work Experience",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Work experience analysis')
        )
    
    def _analyze_education(self, education: List[Dict]) -> SectionSuggestion:
        """Analyze education section"""
        content = json.dumps(education, indent=2) if education else "No education information found"
        ai_analysis = self._get_gemini_analysis("Education", content)
        
        return SectionSuggestion(
            section_name="Education",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Education analysis')
        )
    
    def _analyze_skills(self, skills: Dict) -> SectionSuggestion:
        """Analyze skills section"""
        content = json.dumps(skills, indent=2) if skills else "No skills information found"
        ai_analysis = self._get_gemini_analysis("Skills", content)
        
        return SectionSuggestion(
            section_name="Skills",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Skills analysis')
        )
    
    def _analyze_projects(self, projects: List[Dict]) -> SectionSuggestion:
        """Analyze projects section"""
        content = json.dumps(projects, indent=2) if projects else "No projects found"
        ai_analysis = self._get_gemini_analysis("Projects", content)
        
        return SectionSuggestion(
            section_name="Projects",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Projects analysis')
        )
    
    def _analyze_certifications(self, certifications: List[Dict]) -> SectionSuggestion:
        """Analyze certifications section"""
        content = json.dumps(certifications, indent=2) if certifications else "No certifications found"
        ai_analysis = self._get_gemini_analysis("Certifications", content)
        
        return SectionSuggestion(
            section_name="Certifications",
            original_content=content,
            suggestions=ai_analysis.get('suggestions', []),
            improvements=[],
            keep_elements=ai_analysis.get('keep_elements', []),
            remove_elements=ai_analysis.get('remove_elements', []),
            score=ai_analysis.get('score', 65),
            comments=ai_analysis.get('comments', 'Certifications analysis')
        )
    
    def _calculate_metrics(self, sections: Dict[str, SectionSuggestion]) -> Dict[str, Any]:
        """Calculate overall resume metrics"""
        total_score = sum(section.score for section in sections.values())
        average_score = total_score / len(sections) if sections else 0
        
        # Count suggestions and improvements
        total_suggestions = sum(len(section.suggestions) for section in sections.values())
        total_improvements = sum(len(section.improvements) for section in sections.values())
        
        return {
            'overall_score': round(average_score, 1),
            'total_suggestions': total_suggestions,
            'total_improvements': total_improvements,
            'section_scores': {name: section.score for name, section in sections.items()}
        }
    
    def _generate_summary(self, sections: Dict[str, SectionSuggestion], metrics: Dict[str, Any]) -> str:
        """Generate overall resume summary using Gemini with fallback"""
        try:
            if not self.model:
                return self._get_default_summary(metrics)

            prompt = f"""
            Based on the following resume analysis, provide a comprehensive summary:
            
            Section Scores:
            {json.dumps(metrics['section_scores'], indent=2)}
            
            Total Suggestions: {metrics['total_suggestions']}
            Total Improvements: {metrics['total_improvements']}
            Overall Score: {metrics['overall_score']}
            
            Please provide a detailed summary that includes:
            1. Overall assessment
            2. Key strengths
            3. Areas for improvement
            4. Specific recommendations
            """
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 1,
                    'top_k': 32,
                    'max_output_tokens': 512
                }
            )
            
            return response.text if response.text else self._get_default_summary(metrics)
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return self._get_default_summary(metrics)

    def _get_default_summary(self, metrics: Dict[str, Any]) -> str:
        """Generate default summary when AI fails"""
        score = metrics.get('overall_score', 0)
        suggestions = metrics.get('total_suggestions', 0)
        
        if score >= 80:
            assessment = "Your resume is in excellent shape with strong content across all sections."
        elif score >= 70:
            assessment = "Your resume is good but has room for improvement in some areas."
        elif score >= 60:
            assessment = "Your resume needs moderate improvements to be more competitive."
        else:
            assessment = "Your resume requires significant improvements to meet industry standards."
        
        return f"""
        {assessment}
        
        Key Findings:
        - Overall Score: {score}/100
        - Total Suggestions: {suggestions}
        
        Focus Areas:
        - Review section-specific recommendations
        - Ensure ATS compatibility
        - Optimize keyword usage
        - Improve content formatting
        
        Next Steps:
        - Implement the suggested improvements
        - Tailor content to specific job applications
        - Consider professional formatting review
        """