import subprocess
import json
import sys
import os
from datetime import datetime, timedelta
import google.generativeai as genai
from pymongo import MongoClient
import logging
import traceback
import re

class ProfileAnalyzer:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.scraper_path = os.path.join(self.script_dir, 'scraper.js')
        self.debug_dir = os.path.join(self.script_dir, 'debug_data')
        self.ensure_debug_dir()
        
        # Initialize MongoDB
        self.setup_mongodb()
        
        # Initialize Gemini API
        self.setup_gemini()
    
    def setup_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = MongoClient("mongodb://localhost:27017/")
            self.db = self.mongo_client.resumeDB
            self.profile_roasts_collection = self.db.profile_roasts
            print("✅ MongoDB connection established for profile roasts")
        except Exception as e:
            print(f"❌ Error connecting to MongoDB: {e}")
            self.mongo_client = None
            self.db = None
            self.profile_roasts_collection = None
    
    def setup_gemini(self):
        """Initialize Gemini API"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                print("✅ Gemini API initialized successfully")
            else:
                self.model = None
                print("⚠️ GEMINI_API_KEY not found. Using fallback analysis.")
        except Exception as e:
            self.model = None
            print(f"❌ Error initializing Gemini API: {e}")
    
    def ensure_debug_dir(self):
        """Create debug directory if it doesn't exist"""
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
    
    def detect_platform(self, url):
        """Detect the platform from URL"""
        try:
            if 'linkedin.com' in url.lower():
                return 'linkedin'
            elif 'github.com' in url.lower():
                return 'github'
            else:
                return 'unknown'
        except:
            return 'unknown'
    
    def scrape_single_profile(self, profile_url):
        """Scrape a single profile URL"""
        try:
            platform = self.detect_platform(profile_url)
            
            # Prepare command arguments based on platform
            cmd = ['node', self.scraper_path]
            
            if platform == 'linkedin':
                cmd.append(f'linkedin:{profile_url}')
            elif platform == 'github':
                cmd.append(f'github:{profile_url}')
                # Also try to get repositories if it's a user profile
                if '/in/' not in profile_url and '?tab=' not in profile_url:
                    repos_url = f"{profile_url}?tab=repositories"
                    cmd.append(f'repos:{repos_url}')
            else:
                return None, f"Unsupported platform: {platform}"
            
            # Run the scraper with increased timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=600,  # Increased from 300 to 600 seconds (10 minutes)
                cwd=self.script_dir
            )
            
            if result.returncode != 0:
                return None, f"Scraping failed: {result.stderr}"
            
            # Parse JSON output
            output = result.stdout or ""
            start_marker = "=" * 50
            
            if start_marker in output:
                lines = output.split('\n')
                json_started = False
                json_lines = []
                
                for line in lines:
                    if line.strip() == start_marker:
                        if not json_started:
                            json_started = True
                        else:
                            break
                    elif json_started:
                        json_lines.append(line)
                
                if json_lines:
                    json_str = '\n'.join(json_lines)
                    try:
                        data = json.loads(json_str)
                        return data, None
                    except json.JSONDecodeError as e:
                        return None, f"Failed to parse scraped data: {e}"
            
            return None, "No valid data found in scraper output"
            
        except subprocess.TimeoutExpired:
            return None, "Scraping timed out after 10 minutes. Please try again."
        except Exception as e:
            return None, f"Scraping error: {e}"
    
    def analyze_with_gemini(self, profile_data, platform, user_interests=None):
        """Analyze profile data using Gemini API"""
        if not self.model:
            return self.fallback_analysis(profile_data, platform)
        
        try:
            # Prepare analysis prompt
            prompt = self.create_analysis_prompt(profile_data, platform, user_interests)
            
            # Get analysis from Gemini
            response = self.model.generate_content(prompt)
            print(f"🤖 Gemini response received: {response.text[:200]}...")
            
            # Clean and parse the response
            analysis_text = self.clean_gemini_response(response.text)
            print(f"🔧 Cleaned response: {analysis_text[:200]}...")
            
            # Try to parse as JSON, fallback to structured parsing
            try:
                analysis = json.loads(analysis_text)
                print(f"✅ Successfully parsed Gemini JSON response")
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parsing failed, using fallback: {e}")
                print(f"🔍 Raw analysis text length: {len(analysis_text)}")
                print(f"🔍 First 500 chars: {analysis_text[:500]}")
                analysis = self.parse_analysis_text(analysis_text, platform)
            
            return analysis
            
        except Exception as e:
            print(f"❌ Gemini analysis failed: {e}")
            return self.fallback_analysis(profile_data, platform)
    def clean_gemini_response(self, response_text):
        """Clean Gemini response to extract valid JSON"""
        import re
        
        # Remove any leading/trailing whitespace
        cleaned_text = response_text.strip()
        
        # Remove markdown code block markers
        if '```json' in cleaned_text:
            # Extract content between ```json and ```
            start_marker = '```json'
            end_marker = '```'
            start_idx = cleaned_text.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = cleaned_text.find(end_marker, start_idx)
                if end_idx != -1:
                    cleaned_text = cleaned_text[start_idx:end_idx].strip()
                else:
                    cleaned_text = cleaned_text[start_idx:].strip()
        elif '```' in cleaned_text:
            # Handle generic code blocks
            parts = cleaned_text.split('```')
            if len(parts) >= 2:
                # Take the content between first pair of ```
                cleaned_text = parts[1].strip()
        
        # If still has code block markers, remove them
        cleaned_text = cleaned_text.replace('```json', '').replace('```', '').strip()
        
        # Find JSON content using regex - look for content between outermost braces
        json_pattern = r'\{.*\}'
        json_match = re.search(json_pattern, cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(0)
        
        # Clean up common formatting issues
        cleaned_text = cleaned_text.replace('\n', ' ')  # Replace newlines with spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Normalize whitespace
        
        # Replace smart quotes with regular quotes
        cleaned_text = cleaned_text.replace('"', '"').replace('"', '"')
        cleaned_text = cleaned_text.replace(''', "'").replace(''', "'")
        
        # Remove any non-JSON text before the opening brace
        if '{' in cleaned_text:
            first_brace = cleaned_text.find('{')
            cleaned_text = cleaned_text[first_brace:]
        
        # Remove any non-JSON text after the closing brace
        if '}' in cleaned_text:
            last_brace = cleaned_text.rfind('}')
            cleaned_text = cleaned_text[:last_brace + 1]
        
        # Final validation - ensure it starts with { and ends with }
        if not cleaned_text.startswith('{'):
            cleaned_text = '{' + cleaned_text
        if not cleaned_text.endswith('}'):
            cleaned_text = cleaned_text + '}'
        
        return cleaned_text
    
    def create_analysis_prompt(self, profile_data, platform, user_interests=None):
        """Create comprehensive analysis prompt for Gemini"""
        
        # Extract relevant text content
        if platform == 'linkedin':
            content = profile_data.get('linkedin', {})
            text_content = content.get('allVisibleText', '') or content.get('rawPageText', '')
        elif platform == 'github':
            content = profile_data.get('github', {})
            text_content = content.get('allVisibleText', '') or content.get('rawPageText', '')
            # Add repository info if available
            repos_content = profile_data.get('repos', {})
            if repos_content:
                text_content += "\n\nRepositories:\n" + (repos_content.get('allVisibleText', '') or '')
        else:
            text_content = str(profile_data)
        
        interests_context = ""
        if user_interests:
            interests_context = f"\nUser's interests: {', '.join(user_interests)}"
        
        prompt = f"""
Analyze the following {platform.upper()} profile and provide a comprehensive professional assessment in JSON format.

Profile Content:
{text_content[:8000]}  # Limit content to avoid token limits

{interests_context}

Please provide analysis in the following JSON structure:
{{
    "professional_score": <number 0-100>,
    "platform": "{platform}",
    "overall_assessment": "<detailed assessment>",
    "strengths": ["<strength1>", "<strength2>", ...],
    "areas_for_improvement": ["<improvement1>", "<improvement2>", ...],
    "section_scores": {{
        "profile_completeness": <0-100>,
        "content_quality": <0-100>,
        "professional_presentation": <0-100>,
        "industry_relevance": <0-100>,
        "networking_potential": <0-100>
    }},
    "specific_suggestions": {{
        "immediate_actions": ["<action1>", "<action2>", ...],
        "medium_term_goals": ["<goal1>", "<goal2>", ...],
        "industry_specific_tips": ["<tip1>", "<tip2>", ...]
    }},
    "platform_specific_advice": {{
        "headline_suggestions": ["<suggestion1>", "<suggestion2>", ...],
        "skills_to_add": ["<skill1>", "<skill2>", ...],
        "certifications_recommended": ["<cert1>", "<cert2>", ...],
        "content_strategy": ["<strategy1>", "<strategy2>", ...],
        "networking_tips": ["<tip1>", "<tip2>", ...]
    }},
    "privacy_concerns": ["<concern1>", "<concern2>", ...],
    "optimization_keywords": ["<keyword1>", "<keyword2>", ...],
    "visibility_score": <0-100>,
    "recruiter_appeal": <0-100>
}}

Focus on actionable, specific advice for improving professional visibility and appeal to recruiters.
GIve the good updated headline if the current one is not revelevent to profile or not represing properly. 
And also all the updates should be more revelevent to industry and current trends. should be more professional and appealing to recruiters.
Avoid generic suggestions and ensure all advice is tailored to the provided profile content.

"""
        
        return prompt
    
    def parse_analysis_text(self, text, platform):
        """Parse analysis text when JSON parsing fails"""
        # Fallback structured parsing
        return {
            "professional_score": 75,
            "platform": platform,
            "overall_assessment": "Profile analysis completed successfully.",
            "strengths": ["Profile content analyzed"],
            "areas_for_improvement": ["Consider updating profile regularly"],
            "section_scores": {
                "profile_completeness": 75,
                "content_quality": 70,
                "professional_presentation": 80,
                "industry_relevance": 70,
                "networking_potential": 75
            },
            "specific_suggestions": {
                "immediate_actions": ["Review profile content"],
                "medium_term_goals": ["Expand professional network"],
                "industry_specific_tips": ["Stay updated with industry trends"]
            },
            "platform_specific_advice": {
                "headline_suggestions": ["Consider updating your headline"],
                "skills_to_add": ["Add relevant technical skills"],
                "certifications_recommended": ["Industry-relevant certifications"],
                "content_strategy": ["Regular content posting"],
                "networking_tips": ["Connect with industry professionals"]
            },
            "privacy_concerns": [],
            "optimization_keywords": ["professional", "experienced"],
            "visibility_score": 75,
            "recruiter_appeal": 75
        }
    
    def fallback_analysis(self, profile_data, platform):
        """Fallback analysis when Gemini is not available"""
        return {
            "professional_score": 70,
            "platform": platform,
            "overall_assessment": "Basic profile analysis completed. For detailed insights, please configure Gemini API.",
            "strengths": ["Profile data successfully extracted"],
            "areas_for_improvement": ["Consider professional review"],
            "section_scores": {
                "profile_completeness": 70,
                "content_quality": 65,
                "professional_presentation": 70,
                "industry_relevance": 65,
                "networking_potential": 70
            },
            "specific_suggestions": {
                "immediate_actions": ["Review profile completeness"],
                "medium_term_goals": ["Enhance professional presence"],
                "industry_specific_tips": ["Industry networking"]
            },
            "platform_specific_advice": {
                "headline_suggestions": ["Professional headline optimization"],
                "skills_to_add": ["Relevant technical skills"],
                "certifications_recommended": ["Industry certifications"],
                "content_strategy": ["Content planning"],
                "networking_tips": ["Strategic networking"]
            },
            "privacy_concerns": [],
            "optimization_keywords": ["professional"],
            "visibility_score": 70,
            "recruiter_appeal": 65
        }
    
    def analyze_profile(self, profile_url, user_interests=None):
        """Main method to analyze a profile"""
        try:
            print(f"🎯 Starting analysis for: {profile_url}")
            
            # Detect platform
            platform = self.detect_platform(profile_url)
            if platform == 'unknown':
                return {
                    'success': False,
                    'error': 'Unsupported platform. Please use LinkedIn or GitHub URLs.'
                }
            
            print(f"📱 Platform detected: {platform}")
            
            # Scrape profile data
            profile_data, scrape_error = self.scrape_single_profile(profile_url)
            if scrape_error:
                print(f"❌ Scraping error: {scrape_error}")
                return {
                    'success': False,
                    'error': f'Failed to scrape profile: {scrape_error}'
                }
            
            print(f"✅ Scraping successful, data keys: {list(profile_data.keys()) if profile_data else 'None'}")
            
            # Save debug data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = os.path.join(self.debug_dir, f"profile_analysis_{timestamp}.json")
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'profile_url': profile_url,
                    'platform': platform,
                    'scraped_data': profile_data,
                    'user_interests': user_interests,
                    'timestamp': timestamp
                }, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Debug data saved: {debug_file}")
            
            # Analyze with Gemini
            print(f"🤖 Starting Gemini analysis (model available: {bool(self.model)})")
            analysis = self.analyze_with_gemini(profile_data, platform, user_interests)
            
            print(f"✅ Analysis complete, score: {analysis.get('professional_score', 'N/A')}")
            
            # Combine results
            result = {
                'success': True,
                'platform': platform,
                'profile_url': profile_url,
                'analysis': analysis,
                'scraped_data': profile_data,
                'user_interests': user_interests or [],
                'analysis_timestamp': datetime.now().isoformat(),
                'debug_file': debug_file
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Analysis failed with exception: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Analysis failed: {str(e)}',
                'debug_info': {
                    'exception_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                }
            }
    
    def create_roast_prompt(self, profile_data, platform, user_interests=None, company=None):
        """Create a humorous roasting prompt for Gemini with optional company-specific roasting"""
        
        # Extract relevant text content
        if platform == 'linkedin':
            content = profile_data.get('linkedin', {})
            text_content = content.get('allVisibleText', '') or content.get('rawPageText', '')
        elif platform == 'github':
            content = profile_data.get('github', {})
            text_content = content.get('allVisibleText', '') or content.get('rawPageText', '')
            # Add repository info if available
            repos_content = profile_data.get('repos', {})
            if repos_content:
                text_content += "\n\nRepositories:\n" + (repos_content.get('allVisibleText', '') or '')
        else:
            text_content = str(profile_data)
        
        interests_context = ""
        if user_interests:
            interests_context = f"\nUser's interests: {', '.join(user_interests)}"
        
        # Company-specific roasting context
        company_context = ""
        if company:
            company_context = self._get_company_roast_context(company)
        
        prompt = f"""
You are a witty, sarcastic tech reviewer who specializes in roasting {platform.upper()} profiles with humor and charm. Your job is to provide a brutally honest but funny assessment of this profile. Be sarcastic but not mean-spirited - think more "friendly roast" than "career destruction."

{company_context}

Profile Content:
{text_content[:8000]}

{interests_context}

Please provide your roast in the following JSON structure:
{{
    "platform": "{platform}",
    "complete_roast_summary": "<A comprehensive, entertaining roast that covers the entire profile in a flowing narrative style. Make it 3-4 paragraphs long, covering their headline, bio, experience, skills, and overall presentation. Be witty, sarcastic, and entertaining throughout. This should be the main content that users see and want to share.>",
    "roast_highlights": [
        "<sarcastic comment about their headline/bio>",
        "<witty observation about their experience>",
        "<humorous take on their skills>",
        "<funny comment about their posts/repos>",
        "<sarcastic advice disguised as help>"
    ],
    "cringe_moments": [
        "<most cringeworthy thing on their profile>",
        "<second most cringeworthy thing>",
        "<third most cringeworthy thing>"
    ],
    "missed_opportunities": [
        "<what they should have done but didn't>",
        "<obvious improvement they're ignoring>",
        "<low-hanging fruit they're missing>"
    ],
    "backhanded_compliments": [
        "<compliment that's actually an insult>",
        "<praise with a sting>",
        "<fake encouragement>"
    ],
    "reality_check": {{
        "what_they_think_they_are": "<their self-perception>",
        "what_they_actually_are": "<reality>",
        "what_recruiters_see": "<recruiter's honest opinion>"
    }},
    "improvement_roast": [
        "<sarcastic suggestion for improvement>",
        "<backhanded advice>",
        "<humorous reality check>"
    ],
    "overall_verdict": "<final humorous verdict>",
    "roast_level": "<mild/medium/spicy/nuclear>",
    "comedy_gold_quote": "<most quotable roast from the analysis>"
}}

Remember:
- Be funny, not cruel
- Focus on professional profile elements
- Use tech industry humor and references
- Keep it witty and entertaining
- Make observations that are relatable to other professionals
- Don't cross into personal attacks
- Keep the tone like a friend roasting another friend
- The complete_roast_summary should be the star of the show - make it engaging and shareable
- Write it like a viral social media post that people will want to share

Make this entertaining enough that they'll want to share it with friends!
"""
        
        return prompt
    
    def _get_company_roast_context(self, company):
        """Get company-specific roasting context"""
        company_contexts = {
            'google': """
You are now roasting this profile as if you're a Google recruiter who's seen thousands of profiles and has zero patience for mediocrity. 
Use Google-specific references, mention their high standards, their famous interview process, and their culture of excellence.
Make jokes about their "Googleyness" or lack thereof, their technical skills compared to Google's standards, and their ability to handle Google's fast-paced environment.
Reference Google's famous perks, their rigorous hiring process, and their high expectations.
""",
            'meta': """
You are now roasting this profile as if you're a Meta (Facebook) recruiter who's tired of seeing the same generic profiles.
Use Meta-specific references, mention their focus on impact, their famous "move fast and break things" culture, and their high technical standards.
Make jokes about their ability to handle Meta's scale, their understanding of social media, and their fit for Meta's innovative culture.
Reference Meta's famous interview process, their focus on data-driven decisions, and their high expectations for technical excellence.
""",
            'amazon': """
You are now roasting this profile as if you're an Amazon recruiter who's seen too many profiles that don't meet their high bar.
Use Amazon-specific references, mention their leadership principles, their customer obsession, and their high technical standards.
Make jokes about their ability to handle Amazon's scale, their understanding of Amazon's culture, and their fit for Amazon's demanding environment.
Reference Amazon's famous interview process, their focus on operational excellence, and their high expectations for technical and leadership skills.
""",
            'microsoft': """
You are now roasting this profile as if you're a Microsoft recruiter who's looking for the next great innovator.
Use Microsoft-specific references, mention their focus on empowering people, their culture of learning, and their high technical standards.
Make jokes about their ability to handle Microsoft's scale, their understanding of Microsoft's mission, and their fit for Microsoft's collaborative culture.
Reference Microsoft's famous interview process, their focus on growth mindset, and their high expectations for technical excellence and collaboration.
""",
            'apple': """
You are now roasting this profile as if you're an Apple recruiter who's looking for someone who thinks different.
Use Apple-specific references, mention their focus on design excellence, their culture of innovation, and their high standards for quality.
Make jokes about their ability to handle Apple's attention to detail, their understanding of Apple's design philosophy, and their fit for Apple's secretive culture.
Reference Apple's famous interview process, their focus on user experience, and their high expectations for technical excellence and design thinking.
""",
            'netflix': """
You are now roasting this profile as if you're a Netflix recruiter who's looking for someone who can handle their culture of freedom and responsibility.
Use Netflix-specific references, mention their focus on high performance, their culture of radical honesty, and their high standards for excellence.
Make jokes about their ability to handle Netflix's fast-paced environment, their understanding of Netflix's culture, and their fit for Netflix's demanding standards.
Reference Netflix's famous culture deck, their focus on impact, and their high expectations for both technical excellence and cultural fit.
"""
        }
        
        return company_contexts.get(company.lower(), "")
    
    def roast_with_gemini(self, profile_data, platform, user_interests=None, company=None):
        """Roast profile data using Gemini API with humor and sarcasm"""
        if not self.model:
            return self.fallback_roast(profile_data, platform)
        
        try:
            # Prepare roasting prompt with company context
            prompt = self.create_roast_prompt(profile_data, platform, user_interests, company)
            
            # Get roast from Gemini
            response = self.model.generate_content(prompt)
            print(f"🔥 Gemini roast response received: {response.text[:200]}...")
            
            # Clean and parse the response
            roast_text = self.clean_gemini_response(response.text)
            print(f"🔧 Cleaned roast response: {roast_text[:200]}...")
            
            # Try to parse as JSON, fallback to structured parsing
            try:
                roast = json.loads(roast_text)
                print(f"✅ Successfully parsed Gemini JSON roast")
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parsing failed, using fallback roast: {e}")
                roast = self.parse_roast_text(roast_text, platform)
            
            return roast
            
        except Exception as e:
            print(f"❌ Gemini roast failed: {e}")
            return self.fallback_roast(profile_data, platform)
    
    def parse_roast_text(self, text, platform):
        """Parse roast text when JSON parsing fails"""
        return {
            "platform": platform,
            "complete_roast_summary": "Oh boy, where do I even begin with this masterpiece of mediocrity? Your LinkedIn profile is like a corporate training video - technically functional but about as exciting as watching paint dry. Your headline reads like it was written by an AI that gave up halfway through, and your bio has all the personality of a default template. I've seen more creativity in a spam email than in your entire professional presentation. Your experience section is shorter than a TikTok video, and your skills list looks like you just copied the first page of a 'How to Write a Resume' book. Even your profile picture screams 'I peaked in college' - and that's being generous. The only thing more generic than your profile is probably your coffee order. But hey, at least you're consistent in your mediocrity - that's got to count for something, right?",
            "roast_highlights": [
                "Your headline reads like it was written by an AI that gave up halfway through",
                "I've seen more personality in a default template",
                "Your experience section is shorter than a TikTok video",
                "Skills listed: 'Proficient in breathing, expert in existing'",
                "Your profile picture screams 'I peaked in college'"
            ],
            "cringe_moments": [
                "That time you called yourself a 'thought leader' with 3 LinkedIn connections",
                "Using 'synergy' unironically in your bio",
                "Listing 'Microsoft Office' as a technical skill in 2025"
            ],
            "missed_opportunities": [
                "Actually putting effort into your summary",
                "Posting content that people might want to read",
                "Connecting with people who aren't your relatives"
            ],
            "backhanded_compliments": [
                "Your profile is so unique - just like everyone else's!",
                "You've really mastered the art of saying nothing with many words",
                "Your consistency in mediocrity is truly impressive"
            ],
            "reality_check": {
                "what_they_think_they_are": "Industry disruptor and innovation catalyst",
                "what_they_actually_are": "Someone who attended a webinar once",
                "what_recruiters_see": "Hard pass"
            },
            "improvement_roast": [
                "Maybe try writing a bio that doesn't put people to sleep",
                "Consider adding achievements that actually happened",
                "Your network needs more people and fewer bot connections"
            ],
            "overall_verdict": "Your profile is the LinkedIn equivalent of elevator music - technically functional but utterly forgettable.",
            "roast_level": "medium",
            "comedy_gold_quote": "This profile has all the charisma of a corporate training video."
        }
    
    def fallback_roast(self, profile_data, platform):
        """Fallback roast when Gemini is not available"""
        return {
            "platform": platform,
            "complete_roast_summary": "Well, well, well... what do we have here? Another LinkedIn profile that's so basic it makes vanilla ice cream look exotic. Your bio reads like it was translated through Google Translate five times, and your headline has all the originality of a default template. I've seen more creativity in a spam email than in your entire professional presentation. Congratulations on having the most generic profile on the internet - that's quite an achievement! Your skills section is shorter than my attention span, and even your mother wouldn't endorse you on LinkedIn. Your last post from 2019 about 'exciting opportunities' is about as current as dial-up internet. But hey, at least you're consistent in your mediocrity - that's got to count for something in this world of overachievers.",
            "roast_highlights": [
                "I've seen more creativity in a spam email",
                "Your bio reads like it was translated through Google Translate 5 times",
                "Congratulations on having the most generic profile on the internet",
                "Your skills section is shorter than my attention span",
                "Even your mother wouldn't endorse you on LinkedIn"
            ],
            "cringe_moments": [
                "That generic motivational quote in your headline",
                "Claiming to be 'passionate about excellence'",
                "Your last post from 2019 about 'exciting opportunities'"
            ],
            "missed_opportunities": [
                "Actually having a personality",
                "Writing something people might want to read",
                "Making connections with humans instead of bots"
            ],
            "backhanded_compliments": [
                "Your profile is perfectly adequate for someone with zero ambition",
                "You've really nailed the 'invisible employee' aesthetic",
                "Your humility is inspiring - almost like you're not there at all!"
            ],
            "reality_check": {
                "what_they_think_they_are": "Rising star in their field",
                "what_they_actually_are": "Another face in the crowd",
                "what_recruiters_see": "Who?"
            },
            "improvement_roast": [
                "Maybe try standing out from the crowd of corporate clones",
                "Consider writing a bio that doesn't induce instant narcolepsy",
                "Your profile needs CPR - Charisma, Personality, and Relevance"
            ],
            "overall_verdict": "Your profile is the professional equivalent of beige wallpaper - technically there, but why?",
            "roast_level": "spicy",
            "comedy_gold_quote": "This profile has all the impact of a whisper in a hurricane."
        }
    
    def roast_profile(self, profile_url, user_interests=None, company=None):
        """Main method to roast a profile with humor and sarcasm"""
        try:
            print(f"🔥 Starting roast session for: {profile_url}")
            
            # Detect platform
            platform = self.detect_platform(profile_url)
            if platform == 'unknown':
                return {
                    'success': False,
                    'error': 'Unsupported platform. We only roast LinkedIn and GitHub profiles (they deserve it).'
                }
            
            print(f"📱 Platform detected: {platform} (prepare for carnage)")
            
            # Scrape profile data
            profile_data, scrape_error = self.scrape_single_profile(profile_url)
            if scrape_error:
                print(f"❌ Scraping error: {scrape_error}")
                return {
                    'success': False,
                    'error': f'Failed to scrape profile (maybe it\'s so bad our scraper gave up): {scrape_error}'
                }
            
            print(f"✅ Scraping successful, found data to roast: {list(profile_data.keys()) if profile_data else 'Nothing worth roasting'}")
            
            # Roast with Gemini
            print(f"🤖 Starting Gemini roast session (model available: {bool(self.model)})")
            roast = self.roast_with_gemini(profile_data, platform, user_interests, company)
            
            print(f"🔥 Roast complete, savage level: {roast.get('roast_level', 'unknown')}")
            
            # Combine results
            result = {
                'success': True,
                'platform': platform,
                'profile_url': profile_url,
                'roast': roast,
                'scraped_data': profile_data,
                'user_interests': user_interests or [],
                'company': company,
                'roast_timestamp': datetime.now().isoformat(),
                'disclaimer': 'This roast is for entertainment purposes only. Please don\'t cry.'
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Roast failed with exception: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Roast failed: {str(e)}',
                'debug_info': {
                    'exception_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                },
                'consolation': 'Don\'t worry, even our roasting AI couldn\'t handle your profile.'
            }
    
    def save_roast_to_db(self, profile_url, roast_data):
        """Save roast data to MongoDB"""
        if self.profile_roasts_collection is None:
            print("⚠️ MongoDB not available, skipping database save")
            return False
        
        try:
            # Prepare document for database
            document = {
                'profile_url': profile_url,
                'platform': roast_data.get('platform'),
                'roast': roast_data.get('roast'),
                'scraped_data': roast_data.get('scraped_data'),
                'user_interests': roast_data.get('user_interests', []),
                'created_at': datetime.now(),
                'last_updated': datetime.now(),
                'roast_timestamp': roast_data.get('roast_timestamp'),
                'disclaimer': roast_data.get('disclaimer')
            }
            
            # Use upsert to replace existing data for the same profile_url
            result = self.profile_roasts_collection.replace_one(
                {'profile_url': profile_url},
                document,
                upsert=True
            )
            
            if result.upserted_id:
                print(f"💾 New roast saved to database for {profile_url}")
            else:
                print(f"🔄 Roast updated in database for {profile_url}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save roast to database: {e}")
            return False
    
    def get_roast_from_db(self, profile_url):
        """Get roast data from MongoDB if it exists and is fresh (less than 24 hours)"""
        if self.profile_roasts_collection is None:
            print("⚠️ MongoDB not available, cannot check for cached roast")
            return None
        
        try:
            # Check if we have a cached roast for this URL
            cached_roast = self.profile_roasts_collection.find_one({'profile_url': profile_url})
            
            if not cached_roast:
                print(f"📭 No cached roast found for {profile_url}")
                return None
            
            # Check if the roast is still fresh (less than 24 hours old)
            last_updated = cached_roast.get('last_updated')
            if last_updated:
                time_diff = datetime.now() - last_updated
                if time_diff > timedelta(hours=24):
                    print(f"⏰ Cached roast expired for {profile_url} (age: {time_diff})")
                    # Delete the expired roast
                    self.profile_roasts_collection.delete_one({'profile_url': profile_url})
                    return None
                else:
                    print(f"✅ Fresh cached roast found for {profile_url} (age: {time_diff})")
            
            # Convert MongoDB document back to the expected format
            result = {
                'success': True,
                'platform': cached_roast.get('platform'),
                'profile_url': profile_url,
                'roast': cached_roast.get('roast'),
                'scraped_data': cached_roast.get('scraped_data'),
                'user_interests': cached_roast.get('user_interests', []),
                'roast_timestamp': cached_roast.get('roast_timestamp'),
                'disclaimer': cached_roast.get('disclaimer'),
                'from_cache': True,
                'cached_at': cached_roast.get('last_updated').isoformat() if cached_roast.get('last_updated') else None
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Failed to retrieve roast from database: {e}")
            return None
    
    def roast_profile_with_cache(self, profile_url, user_interests=None, company=None):
        """Main method to roast a profile with database caching and 24-hour refresh"""
        try:
            print(f"🔥 Starting roast session for: {profile_url}")
            
            # First, check if we have a fresh roast in the database
            cached_result = self.get_roast_from_db(profile_url)
            if cached_result:
                print(f"🎯 Using cached roast from database")
                return cached_result
            
            # No fresh cache found, generate new roast
            print(f"🆕 Generating fresh roast for {profile_url}")
            result = self.roast_profile(profile_url, user_interests, company)
            
            # Save to database if successful
            if result.get('success'):
                self.save_roast_to_db(profile_url, result)
            
            return result
            
        except Exception as e:
            print(f"❌ Cached roast failed with exception: {e}")
            print(f"📋 Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Cached roast failed: {str(e)}',
                'debug_info': {
                    'exception_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                },
                'consolation': 'Don\'t worry, even our caching system couldn\'t handle your profile.'
            }
#     print(f"GitHub: {github_url}")
#     print(f"Repos: {repos_url}")
#     print(f"LinkedIn: {linkedin_url}")
    
#     # Scrape the profiles
#     data = scraper.scrape_profiles(
#         github_url=github_url,
#         repos_url=repos_url,
#         linkedin_url=linkedin_url
#     )
    
#     # Save parsed data for debugging if successful
#     if data:
#         scraper.save_debug_data(data, "successful_scrape")
    
#     # Display the results
#     scraper.print_profile_data(data)
    
#     if data:
#         print("\n✅ Scraping completed successfully!")
#         print(f"📁 Debug data saved in: {scraper.debug_dir}")
#         return data
#     else:
#         print("\n❌ Scraping failed!")
#         print(f"📁 Raw output saved in: {scraper.debug_dir}")
#         return None

# if __name__ == "__main__":
#     main()
