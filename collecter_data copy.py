import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import time
import os
from urllib.parse import urlparse, urljoin
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Simple user agents instead of fake_useragent to avoid import issues
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

@dataclass
class ProfileAnalysisResult:
    platform: str
    profile_data: Dict[str, Any]
    analysis: Dict[str, Any]
    suggestions: Dict[str, Any]
    privacy_concerns: List[str]
    professional_score: float
    section_scores: Dict[str, float]

class ProfileDataCollector:
    def __init__(self):
        # Initialize user agent first
        self.user_agent = USER_AGENTS[0]
        
        # Initialize session
        self.session = self._create_session()
        self.chrome_driver = None
        self.uc_driver = None
        
        # Initialize Gemini AI
        self.gemini_model = self._setup_gemini()
        
        self._setup_drivers()
    
    def _setup_gemini(self):
        """Setup Gemini AI model"""
        try:
            # Get API key from environment variable
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in environment variables")
                return None
            
            # Configure Gemini
            genai.configure(api_key=api_key)
            
            # Initialize model with safety settings
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "top_k": 64,
                    "max_output_tokens": 8192,
                }
            )
            
            logger.info("Gemini AI model initialized successfully")
            return model
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI: {e}")
            return None

    def _create_session(self):
        """Create a robust session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Default headers
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def _setup_drivers(self):
        """Setup Chrome drivers with simple fallback options"""
        try:
            # Method 1: Auto-install ChromeDriver
            try:
                chromedriver_autoinstaller.install()
                logger.info("ChromeDriver auto-installed successfully")
            except Exception as e:
                logger.warning(f"ChromeDriver auto-install failed: {e}")
            
            # Method 2: Setup regular Chrome with options
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.user_agent}')
            
            # For production, run headless
            if os.getenv('ENVIRONMENT') == 'production':
                chrome_options.add_argument('--headless')
            
            self.chrome_options = chrome_options
            
            # Test Chrome driver (optional)
            try:
                test_driver = webdriver.Chrome(options=chrome_options)
                test_driver.quit()
                logger.info("Standard Chrome driver setup successful")
            except Exception as e:
                logger.warning(f"Standard Chrome driver test failed: {e}")
                
        except Exception as e:
            logger.error(f"Driver setup error: {e}")

    def _get_driver(self, use_undetected=False):
        """Get Chrome driver with simple fallback options"""
        try:
            # Simple Chrome driver setup
            try:
                driver = webdriver.Chrome(options=self.chrome_options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return driver
            except Exception as e:
                logger.warning(f"Standard Chrome failed: {e}")
            
            # Fallback with service
            try:
                service = Service()
                driver = webdriver.Chrome(service=service, options=self.chrome_options)
                return driver
            except Exception as e:
                logger.warning(f"Chrome with service failed: {e}")
                
        except Exception as e:
            logger.error(f"All driver methods failed: {e}")
            
        return None

    def _detect_platform(self, profile_url: str) -> str:
        """Detect platform from profile URL"""
        try:
            if not profile_url:
                return 'unknown'
            
            url_lower = profile_url.lower()
            
            if 'linkedin.com' in url_lower:
                return 'linkedin'
            elif 'github.com' in url_lower:
                return 'github'
            elif 'twitter.com' in url_lower or 'x.com' in url_lower:
                return 'twitter'
            elif 'stackoverflow.com' in url_lower:
                return 'stackoverflow'
            elif 'medium.com' in url_lower:
                return 'medium'
            else:
                return 'beta'  # For unsupported platforms
                
        except Exception as e:
            logger.error(f"Error detecting platform: {e}")
            return 'unknown'

    def _analyze_profile_with_gemini(self, profile_data: Dict, platform: str, user_interests: List[str]) -> Dict[str, Any]:
        """Use Gemini AI to analyze profile data"""
        if not self.gemini_model:
            logger.warning("Gemini model not available, falling back to basic analysis")
            return self._basic_fallback_analysis(profile_data, platform, user_interests)
        
        try:
            # Create comprehensive prompt for Gemini
            prompt = self._create_analysis_prompt(profile_data, platform, user_interests)
            
            # Generate analysis with Gemini
            response = self.gemini_model.generate_content(prompt)
            
            # Parse JSON response
            analysis_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            elif "```" in analysis_text:
                json_start = analysis_text.find("```") + 3
                json_end = analysis_text.rfind("```")
                analysis_text = analysis_text[json_start:json_end].strip()
            
            # Parse the JSON response
            analysis_result = json.loads(analysis_text)
            
            logger.info("Gemini AI analysis completed successfully")
            return analysis_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Raw response: {response.text[:500]}...")
            return self._basic_fallback_analysis(profile_data, platform, user_interests)
            
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return self._basic_fallback_analysis(profile_data, platform, user_interests)

    def _create_analysis_prompt(self, profile_data: Dict, platform: str, user_interests: List[str]) -> str:
        """Create comprehensive analysis prompt for Gemini"""
        
        interests_text = ", ".join(user_interests) if user_interests else "general professional development"
        
        prompt = f"""
As an expert career consultant and professional profile analyst, analyze the following {platform.upper()} profile data and provide a comprehensive analysis in JSON format.

PROFILE DATA:
{json.dumps(profile_data, indent=2)}

USER INTERESTS: {interests_text}

Please provide a detailed analysis in the following JSON structure:

{{
    "overall_assessment": "A comprehensive 3-4 sentence assessment of the profile's professional strength and current state",
    "professional_score": <integer between 0-100>,
    "section_scores": {{
        "profile_completeness": <0-100>,
        "content_quality": <0-100>,
        "professional_presentation": <0-100>,
        "industry_relevance": <0-100>,
        "networking_potential": <0-100>
    }},
    "strengths": [
        "List 3-5 specific strengths of this profile",
        "Focus on what makes this profile stand out",
        "Include both content and presentation strengths"
    ],
    "areas_for_improvement": [
        "List 3-5 specific areas that need improvement",
        "Be constructive and actionable",
        "Focus on the most impactful changes"
    ],
    "detailed_analysis": {{
        "profile_summary": "Analysis of basic profile information and completeness",
        "content_analysis": "Assessment of content quality, depth, and professionalism",
        "technical_expertise": "Analysis of technical skills and project quality (if applicable)",
        "professional_branding": "Assessment of personal brand and professional image",
        "industry_alignment": "How well the profile aligns with industry standards and user interests"
    }},
    "suggestions": {{
        "immediate_actions": [
            "3-5 actionable items that can be completed in 1-2 days",
            "Quick wins for profile improvement"
        ],
        "medium_term_goals": [
            "3-5 goals that should be accomplished in 1-4 weeks",
            "More substantial improvements"
        ],
        "long_term_strategy": [
            "2-3 strategic recommendations for long-term profile growth",
            "Career development suggestions"
        ]
    }},
    "privacy_concerns": [
        "List any privacy or security concerns found",
        "Include sensitive information that should be removed or made private",
        "Return empty array if no concerns found"
    ],
    "industry_specific_tips": [
        "Provide 3-5 tips specific to the user's interests: {interests_text}",
        "Industry best practices and standards",
        "Platform-specific optimization for {platform}"
    ],
    "content_quality": {{
        "writing_quality": <0-100>,
        "keyword_optimization": <0-100>,
        "industry_relevance": <0-100>,
        "engagement_potential": <0-100>
    }}
}}

ANALYSIS GUIDELINES:
1. Be specific and actionable in recommendations
2. Consider {platform}-specific best practices
3. Align suggestions with user interests: {interests_text}
4. Provide realistic and achievable goals
5. Focus on professional growth and visibility
6. Consider current industry trends and standards
7. Be constructive but honest in assessments

Return ONLY the JSON response, no additional text or explanations.
"""
        
        return prompt

    def _basic_fallback_analysis(self, profile_data: Dict, platform: str, user_interests: List[str]) -> Dict[str, Any]:
        """Fallback analysis when Gemini is not available"""
        return {
            "overall_assessment": f"Basic analysis completed for {platform} profile. Limited AI analysis available.",
            "professional_score": 65,
            "section_scores": {
                "profile_completeness": 60,
                "content_quality": 65,
                "professional_presentation": 70,
                "industry_relevance": 60,
                "networking_potential": 55
            },
            "strengths": [
                "Profile is publicly accessible",
                "Basic information is present",
                "Platform selection is appropriate for professional networking"
            ],
            "areas_for_improvement": [
                "Complete all profile sections",
                "Add more detailed professional information",
                "Optimize for better searchability"
            ],
            "detailed_analysis": {
                "profile_summary": "Basic profile structure is in place",
                "content_analysis": "Limited content analysis available",
                "technical_expertise": "Technical skills assessment limited",
                "professional_branding": "Basic professional presence detected",
                "industry_alignment": "General professional standards applied"
            },
            "suggestions": {
                "immediate_actions": [
                    "Complete basic profile information",
                    "Add professional profile photo",
                    "Write compelling headline/bio"
                ],
                "medium_term_goals": [
                    "Expand content sections",
                    "Add relevant skills and experience",
                    "Connect with industry professionals"
                ],
                "long_term_strategy": [
                    "Develop consistent content strategy",
                    "Build industry reputation and network"
                ]
            },
            "privacy_concerns": [],
            "industry_specific_tips": [
                f"Focus on {platform}-specific optimization",
                "Stay updated with industry trends",
                "Engage with relevant professional communities"
            ],
            "content_quality": {
                "writing_quality": 65,
                "keyword_optimization": 60,
                "industry_relevance": 65,
                "engagement_potential": 60
            }
        }

    def analyze_profile(self, profile_url: str, user_interests: List[str] = None) -> ProfileAnalysisResult:
        """Main method to analyze any profile with Gemini AI"""
        try:
            platform = self._detect_platform(profile_url)
            
            # Extract profile data based on platform
            if platform == 'github':
                profile_data = self._extract_github_data(profile_url)
            elif platform == 'linkedin':
                profile_data = self._extract_linkedin_data(profile_url)
            else:
                profile_data = self._extract_basic_profile_data_from_url(profile_url)
            
            # Use Gemini AI for comprehensive analysis
            analysis_result = self._analyze_profile_with_gemini(profile_data, platform, user_interests or [])
            
            # Extract components from Gemini response
            analysis = {
                'overall_assessment': analysis_result.get('overall_assessment', ''),
                'strengths': analysis_result.get('strengths', []),
                'areas_for_improvement': analysis_result.get('areas_for_improvement', []),
                'detailed_analysis': analysis_result.get('detailed_analysis', {}),
                'industry_specific_tips': analysis_result.get('industry_specific_tips', []),
                'content_quality': analysis_result.get('content_quality', {})
            }
            
            suggestions = analysis_result.get('suggestions', {})
            privacy_concerns = analysis_result.get('privacy_concerns', [])
            professional_score = analysis_result.get('professional_score', 65)
            section_scores = analysis_result.get('section_scores', {})
            
            return ProfileAnalysisResult(
                platform=platform,
                profile_data=profile_data,
                analysis=analysis,
                suggestions=suggestions,
                privacy_concerns=privacy_concerns,
                professional_score=professional_score,
                section_scores=section_scores
            )
            
        except Exception as e:
            logger.error(f"Profile analysis failed: {str(e)}")
            return self._create_error_result(profile_url, str(e))

    def _extract_github_data(self, profile_url: str) -> Dict[str, Any]:
        """Extract GitHub profile data"""
        try:
            username = self._extract_username_from_url(profile_url)
            if not username:
                raise ValueError("Could not extract username from URL")
            
            # Use GitHub API
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'ProfileAnalyzer/1.0'
            }
            
            github_token = os.getenv('GITHUB_TOKEN')
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            # Fetch data from GitHub API
            api_data = self._fetch_github_data(username, headers)
            
            # Process and structure the data
            return self._process_github_data_for_gemini(api_data, username, profile_url)
            
        except Exception as e:
            logger.error(f"GitHub data extraction failed: {e}")
            return {
                'url': profile_url,
                'platform': 'github',
                'error': str(e),
                'basic_info': {'username': username if 'username' in locals() else 'unknown'}
            }

    def _extract_linkedin_data(self, profile_url: str) -> Dict[str, Any]:
        """Extract LinkedIn profile data"""
        try:
            response = self.session.get(profile_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return self._process_linkedin_data_for_gemini(soup, profile_url)
            
        except Exception as e:
            logger.error(f"LinkedIn data extraction failed: {e}")
            return {
                'url': profile_url,
                'platform': 'linkedin',
                'error': str(e),
                'basic_info': {'name': 'Unable to extract'}
            }

    def _extract_basic_profile_data_from_url(self, profile_url: str) -> Dict[str, Any]:
        """Extract basic profile data from any URL"""
        try:
            response = self.session.get(profile_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return {
                'url': profile_url,
                'platform': self._detect_platform(profile_url),
                'title': soup.find('title').get_text(strip=True) if soup.find('title') else '',
                'description': soup.find('meta', attrs={'name': 'description'}).get('content', '') if soup.find('meta', attrs={'name': 'description'}) else '',
                'text_content': soup.get_text(separator=' ', strip=True)[:2000],
                'content_length': len(soup.get_text()),
                'meta_info': self._extract_meta_info(soup)
            }
            
        except Exception as e:
            logger.error(f"Basic data extraction failed: {e}")
            return {
                'url': profile_url,
                'platform': self._detect_platform(profile_url),
                'error': str(e)
            }

    def _process_github_data_for_gemini(self, api_data: Dict, username: str, profile_url: str) -> Dict[str, Any]:
        """Process GitHub API data for Gemini analysis"""
        user_data = api_data.get('user', {})
        repos_data = api_data.get('repos', [])
        
        # Structure data for Gemini
        processed_data = {
            'url': profile_url,
            'platform': 'github',
            'username': username,
            'basic_info': {
                'name': user_data.get('name', 'Not provided'),
                'bio': user_data.get('bio', 'No bio available'),
                'company': user_data.get('company', 'Not specified'),
                'location': user_data.get('location', 'Not specified'),
                'blog': user_data.get('blog', ''),
                'twitter_username': user_data.get('twitter_username', ''),
                'public_repos': user_data.get('public_repos', 0),
                'followers': user_data.get('followers', 0),
                'following': user_data.get('following', 0),
                'created_at': user_data.get('created_at', ''),
                'hireable': user_data.get('hireable', False)
            },
            'repository_stats': {
                'total_repos': len(repos_data),
                'languages': list(set([repo.get('language') for repo in repos_data if repo.get('language')])),
                'total_stars': sum([repo.get('stargazers_count', 0) for repo in repos_data]),
                'total_forks': sum([repo.get('forks_count', 0) for repo in repos_data]),
                'recent_repos': [
                    {
                        'name': repo.get('name'),
                        'description': repo.get('description'),
                        'language': repo.get('language'),
                        'stars': repo.get('stargazers_count', 0),
                        'forks': repo.get('forks_count', 0)
                    }
                    for repo in sorted(repos_data, key=lambda x: x.get('updated_at', ''), reverse=True)[:10]
                ]
            }
        }
        
        return processed_data

    def _process_linkedin_data_for_gemini(self, soup: BeautifulSoup, profile_url: str) -> Dict[str, Any]:
        """Process LinkedIn HTML data for Gemini analysis"""
        # Extract basic information from LinkedIn public profile
        title = soup.find('title')
        name = title.get_text().split('|')[0].strip() if title else 'Not found'
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = meta_desc.get('content', '') if meta_desc else ''
        
        # Get page text content
        page_text = soup.get_text(separator=' ', strip=True)[:2000]
        
        processed_data = {
            'url': profile_url,
            'platform': 'linkedin',
            'basic_info': {
                'name': name,
                'headline': 'LinkedIn Member',  # Default for public profiles
                'summary': description,
                'location': 'Not specified'
            },
            'content_analysis': {
                'page_title': title.get_text() if title else '',
                'meta_description': description,
                'content_length': len(page_text),
                'text_sample': page_text
            },
            'profile_elements': {
                'has_photo': bool(soup.find('img', {'alt': re.compile(name, re.I)})) if name != 'Not found' else False,
                'has_description': bool(description),
                'content_richness': len(page_text)
            }
        }
        
        return processed_data

    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract meta information from HTML"""
        meta_info = {}
        meta_tags = soup.find_all('meta')
        
        for meta in meta_tags:
            name = meta.get('name') or meta.get('property', '')
            content = meta.get('content', '')
            if name and content:
                meta_info[name] = content
        
        return meta_info

    def _detect_platform(self, profile_url: str) -> str:
        """Detect platform from profile URL"""
        try:
            if not profile_url:
                return 'unknown'
            
            url_lower = profile_url.lower()
            
            if 'linkedin.com' in url_lower:
                return 'linkedin'
            elif 'github.com' in url_lower:
                return 'github'
            elif 'twitter.com' in url_lower or 'x.com' in url_lower:
                return 'twitter'
            elif 'stackoverflow.com' in url_lower:
                return 'stackoverflow'
            elif 'medium.com' in url_lower:
                return 'medium'
            else:
                return 'beta'  # For unsupported platforms
                
        except Exception as e:
            logger.error(f"Error detecting platform: {e}")
            return 'unknown'

    def compare_profiles(self, profile_urls: List[str], user_interests: List[str] = None) -> Dict[str, Any]:
        """Compare multiple profiles using Gemini AI"""
        try:
            comparison_results = []
            
            for i, url in enumerate(profile_urls, 1):
                try:
                    result = self.analyze_profile(url, user_interests)
                    result_dict = {
                        'profile_index': i,
                        'url': url,
                        'platform': result.platform,
                        'professional_score': result.professional_score,
                        'section_scores': result.section_scores,
                        'strengths': result.analysis.get('strengths', []),
                        'areas_for_improvement': result.analysis.get('areas_for_improvement', []),
                        'privacy_concerns': result.privacy_concerns
                    }
                    comparison_results.append(result_dict)
                    
                except Exception as e:
                    logger.error(f"Failed to analyze profile {i}: {e}")
                    comparison_results.append({
                        'profile_index': i,
                        'url': url,
                        'error': str(e)
                    })
            
            # Use Gemini for comparison insights if available
            comparison_insights = self._generate_comparison_insights(comparison_results, user_interests)
            
            return {
                'success': True,
                'comparison_results': comparison_results,
                'insights': comparison_insights
            }
            
        except Exception as e:
            logger.error(f"Profile comparison failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_comparison_insights(self, comparison_results: List[Dict], user_interests: List[str]) -> Dict[str, Any]:
        """Generate comparison insights using Gemini AI"""
        if not self.gemini_model or len(comparison_results) < 2:
            return {'message': 'Basic comparison completed'}
        
        try:
            prompt = f"""
Analyze these profile comparison results and provide insights in JSON format:

COMPARISON DATA:
{json.dumps(comparison_results, indent=2)}

USER INTERESTS: {", ".join(user_interests) if user_interests else "general"}

Provide insights in this JSON structure:
{{
    "overall_comparison": "Summary of how the profiles compare",
    "strongest_profile": {{
        "index": <profile_index>,
        "reasons": ["Why this profile is strongest"]
    }},
    "key_differences": [
        "Major differences between profiles"
    ],
    "recommendations": [
        "Specific recommendations for improvement based on comparison"
    ]
}}

Return ONLY the JSON response.
"""
            
            response = self.gemini_model.generate_content(prompt)
            return json.loads(response.text.strip())
            
        except Exception as e:
            logger.error(f"Comparison insights generation failed: {e}")
            return {'message': 'Comparison completed successfully'}

    def _create_error_result(self, profile_url: str, error_message: str) -> ProfileAnalysisResult:
        """Create error result when analysis fails"""
        platform = self._detect_platform(profile_url)
        
        return ProfileAnalysisResult(
            platform=platform,
            profile_data={'error': error_message, 'url': profile_url},
            analysis={
                'overall_assessment': f'Analysis failed: {error_message}',
                'strengths': ['Profile URL is accessible'],
                'weaknesses': ['Unable to complete full analysis'],
                'section_analysis': {
                    'profile_setup': {'score': 0, 'feedback': 'Analysis incomplete'}
                }
            },
            suggestions={
                'immediate_actions': ['Verify profile is publicly accessible', 'Try again later'],
                'troubleshooting': [error_message]
            },
            privacy_concerns=['Unable to assess privacy settings'],
            professional_score=0,
            section_scores={'analysis_status': 0}
        )