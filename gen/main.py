import os
import json
import base64
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from google.auth.transport.requests import Request
from google.auth import default
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="18fps AI Video Generation API", version="1.0.0", description="Backend API for AI-powered video generation")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROJECT_ID = "quiet-being-467910-p9"
LOCATION_ID = "us-central1"
API_ENDPOINT = "us-central1-aiplatform.googleapis.com"
MODEL_ID = "veo-3.0-generate-001"

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

# Create necessary directories
DRAFTS_DIR = Path("drafts")
STATIC_DIR = Path("static")
LOGS_DIR = Path("logs")
DRAFTS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Setup logging
def setup_logging():
    """Setup comprehensive logging system"""
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(exist_ok=True)
    
    # Setup main application logger
    logger = logging.getLogger("geNV")
    logger.setLevel(logging.INFO)
    
    # Create formatter without emojis
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create file handler for general logs
    log_file = LOGS_DIR / f"genv_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_prompt_interaction(video_id: str, original_story: str, enhanced_prompt: str, style: str, duration: int):
    """Log prompt interactions with detailed information"""
    timestamp = datetime.now().isoformat()
    
    prompt_log = {
        "timestamp": timestamp,
        "video_id": video_id,
        "original_story": original_story,
        "enhanced_prompt": enhanced_prompt,
        "style": style,
        "duration": duration,
        "session_info": {
            "user_agent": "geNV_Application",
            "processing_stage": "prompt_enhancement"
        }
    }
    
    # Save to individual prompt log file
    prompt_file = LOGS_DIR / f"prompts_{datetime.now().strftime('%Y%m%d')}.json"
    
    # Read existing logs or create new list
    if prompt_file.exists():
        with open(prompt_file, 'r', encoding='utf-8') as f:
            existing_logs = json.load(f)
    else:
        existing_logs = []
    
    existing_logs.append(prompt_log)
    
    # Write back to file
    with open(prompt_file, 'w', encoding='utf-8') as f:
        json.dump(existing_logs, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Prompt logged for video_id: {video_id}")

def log_video_operation(video_id: str, operation_type: str, status: str, message: str, additional_data: dict = None):
    """Log video generation operations"""
    timestamp = datetime.now().isoformat()
    
    operation_log = {
        "timestamp": timestamp,
        "video_id": video_id,
        "operation_type": operation_type,
        "status": status,
        "message": message,
        "additional_data": additional_data or {}
    }
    
    # Save to operations log file
    operations_file = LOGS_DIR / f"operations_{datetime.now().strftime('%Y%m%d')}.json"
    
    # Read existing logs or create new list
    if operations_file.exists():
        with open(operations_file, 'r', encoding='utf-8') as f:
            existing_logs = json.load(f)
    else:
        existing_logs = []
    
    existing_logs.append(operation_log)
    
    # Write back to file
    with open(operations_file, 'w', encoding='utf-8') as f:
        json.dump(existing_logs, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Operation logged: {operation_type} - {status} for video_id: {video_id}")

# Initialize logging
logger = setup_logging()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/drafts", StaticFiles(directory="drafts"), name="drafts")

# Pydantic models
class StoryRequest(BaseModel):
    story: str
    style: Optional[str] = "cinematic"
    duration: Optional[int] = 8
    resolution: Optional[str] = "720p"

class VideoResponse(BaseModel):
    video_id: str
    status: str
    message: str
    video_path: Optional[str] = None

# Store active operations
active_operations: Dict[str, Dict] = {}

def load_context_template():
    """Load the context template for prompt enhancement"""
    try:
        # Try enhanced context first, fall back to original
        for context_file in ["context_enhanced.txt", "context.txt"]:
            if Path(context_file).exists():
                with open(context_file, "r", encoding="utf-8") as f:
                    return f.read()
        # Fallback if no context files found
        return """Follow the below instructions to create a good video prompt:

{
  "goal": "Generate a high-quality video according to the user's description.",
  "instructions": {
    "content_description": "<Describe clearly what the video should show — subject, action, setting>",
    "style_and_tone": "<Cinematic / cartoon / realistic / 3D / hand-drawn etc.>",
    "camera_details": "<Camera angle, movement, close-up/wide shot>",
    "duration": "<Approximate length in seconds>",
    "resolution": "<Desired resolution e.g. 1080p, 4K>",
    "color_palette": "<Warm, cool, pastel, monochrome etc.>",
    "audio_or_subtitles": "<Add background music, voice-over, or subtitles if needed>",
    "branding_or_text": "<Logos, captions, watermarks if any>",
    "output_format": "<mp4, webm, gif etc.>"
  }
}"""
    except Exception as e:
        print(f"Error loading context template: {e}")
        return "Create a detailed, cinematic video description based on the user's story."

def enhance_story_with_gemini(story: str, style: str = "cinematic") -> str:
    """Use Gemini to enhance a simple story into a detailed video prompt"""
    try:
        logger.info(f"Starting story enhancement - Style: {style}")
        context_template = load_context_template()
        
        prompt = f"""
        You are a creative video director. Take this simple story and turn it into a detailed, structured video prompt using the exact JSON format provided below.
        
        Original story: "{story}"
        Desired style: {style}
        
        Context instructions: {context_template}
        
        Fill out this JSON template with specific details based on the story. Replace ALL placeholder values ({{PLACEHOLDER}}) with actual content:
        
        {{
          "prompt": "{{PROMPT}}",
          "scene": {{
            "environment": "{{ENVIRONMENT}}",
            "characters": [
              {{
                "name": "{{CHARACTER_NAME}}",
                "role": "{{CHARACTER_ROLE}}",
                "actions": "{{CHARACTER_ACTIONS}}",
                "appearance": "{{CHARACTER_APPEARANCE}}"
              }}
            ],
            "objects": [
              {{
                "type": "{{OBJECT_TYPE}}",
                "details": "{{OBJECT_DETAILS}}"
              }}
            ],
            "atmosphere": "{{ATMOSPHERE}}"
          }},
          "style": {{
            "visual": "{{VISUAL_STYLE}}",
            "tone": "{{TONE}}",
            "color_palette": "{{COLOR_PALETTE}}",
            "art_direction": "{{ART_DIRECTION}}"
          }},
          "captions": {{
            "enabled": {{CAPTIONS_ENABLED}},
            "position": "{{CAPTION_POSITION}}",
            "style": "{{CAPTION_STYLE}}",
            "font": "{{CAPTION_FONT}}",
            "size": "{{CAPTION_SIZE}}",
            "content": [
              {{CAPTION_CONTENT}}
            ]
          }},
          "video_settings": {{
            "size": "{{WIDTH}}x{{HEIGHT}}",
            "aspect_ratio": "{{ASPECT_RATIO}}",
            "duration": "{{DURATION}}",
            "frame_rate": "{{FRAME_RATE}}",
            "format": "{{FORMAT}}",
            "quality": "{{QUALITY}}"
          }},
          "audio": {{
            "enabled": {{AUDIO_ENABLED}},
            "background_music": "{{BACKGROUND_MUSIC}}",
            "voiceover": {{
              "enabled": {{VOICEOVER_ENABLED}},
              "language": "{{VOICEOVER_LANGUAGE}}",
              "style": "{{VOICEOVER_STYLE}}",
              "content": [
                {{VOICEOVER_CONTENT}}
              ]
            }}
          }},
          "transitions": {{
            "enabled": {{TRANSITIONS_ENABLED}},
            "type": "{{TRANSITION_TYPE}}",
            "duration": "{{TRANSITION_DURATION}}"
          }},
          "metadata": {{
            "title": "{{TITLE}}",
            "description": "{{DESCRIPTION}}",
            "tags": [
              {{TAGS}}
            ],
            "author": "{{AUTHOR}}",
            "created_at": "{{CREATED_AT}}"
          }}
        }}
        
        Instructions for filling the template:
        1. PROMPT: Create a detailed video description based on the story
        2. ENVIRONMENT: Describe the setting/location in detail
        3. CHARACTERS: List main characters with names, roles, actions, and appearance
        4. OBJECTS: Important props or items in the scene
        5. ATMOSPHERE: Mood, lighting, weather conditions
        6. VISUAL_STYLE: Match the requested style ({style})
        7. TONE: Emotional tone of the video
        8. COLOR_PALETTE: Specific colors that fit the mood
        9. ART_DIRECTION: Overall artistic vision
        10. CAPTIONS: Set enabled to true/false, provide position and style
        11. VIDEO_SETTINGS: Use 1080x1920 for vertical, 9:16 aspect ratio, MP4 format
        12. AUDIO: Enable background music and voiceover as appropriate
        13. TRANSITIONS: Use smooth transitions between scenes
        14. METADATA: Create appropriate title, description, and tags
        
        Return ONLY the filled JSON template with all placeholders replaced by actual values. Make it engaging and cinematic.
        """
        
        logger.info("Sending request to Gemini API for story enhancement")
        response = gemini_model.generate_content(prompt)
        enhanced_result = response.text.strip()
        
        logger.info("Story enhancement completed successfully")
        return enhanced_result
        
    except Exception as e:
        error_msg = f"Error enhancing story with Gemini: {e}"
        logger.error(error_msg)
        return story  # Fallback to original story

def get_veo_credentials():
    """Get Google Cloud credentials for Veo API"""
    try:
        logger.info("Attempting to get Veo API credentials")
        SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, project = default(scopes=SCOPES)
        credentials.refresh(Request())
        logger.info("Successfully obtained Veo API credentials")
        return credentials.token
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail="Authentication failed")

def generate_video_with_veo(prompt: str, duration: int = 8, resolution: str = "720p") -> Dict:
    """Generate video using Veo API - adapted from voe.py"""
    try:
        logger.info(f"Starting video generation - Duration: {duration}s, Resolution: {resolution}")
        access_token = get_veo_credentials()
        
        payload = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "aspectRatio": "9:16",
                "sampleCount": 1,
                "durationSeconds": str(duration),
                "personGeneration": "allow_all",
                "addWatermark": True,
                "includeRaiReason": True,
                "generateAudio": True,
                "resolution": resolution,
            }
        }
        
        url = f"https://{API_ENDPOINT}/v1/projects/{PROJECT_ID}/locations/{LOCATION_ID}/publishers/google/models/{MODEL_ID}:predictLongRunning"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        logger.info("Sending video generation request to Veo API")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.ok:
            resp_json = response.json()
            operation_name = resp_json.get("name")
            logger.info(f"Video generation started successfully. Operation: {operation_name}")
            return {
                "success": True,
                "operation_name": operation_name,
                "message": "Video generation started"
            }
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Video generation failed: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

def poll_video_operation(operation_name: str) -> Dict:
    """Poll Veo operation status - adapted from voe.py"""
    try:
        logger.info(f"Polling operation status: {operation_name}")
        access_token = get_veo_credentials()
        
        fetch_url = f"https://{API_ENDPOINT}/v1/projects/{PROJECT_ID}/locations/{LOCATION_ID}/publishers/google/models/{MODEL_ID}:fetchPredictOperation"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        fetch_payload = {"operationName": operation_name}
        
        fetch_resp = requests.post(fetch_url, headers=headers, data=json.dumps(fetch_payload))
        
        if not fetch_resp.ok:
            error_msg = f"Polling failed: {fetch_resp.status_code} - {fetch_resp.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
            
        fetch_json = fetch_resp.json()
        
        if fetch_json.get("done"):
            if "error" in fetch_json:
                error_msg = f"Operation error: {fetch_json['error']}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
            logger.info("Video generation completed successfully")
            return {
                "success": True,
                "completed": True,
                "response": fetch_json
            }
        else:
            status = fetch_json.get("status", "unknown")
            logger.info(f"Video generation in progress - Status: {status}")
            return {
                "success": True,
                "completed": False,
                "status": status
            }
            
    except Exception as e:
        error_msg = f"Polling failed: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

def decode_and_save_video(response_data: Dict, video_id: str) -> str:
    """Decode video from response and save to drafts - adapted from decode.py"""
    try:
        logger.info(f"Starting video decoding for video_id: {video_id}")
        video_saved = False
        video_path = None
        
        # Try different possible response structures
        if "response" in response_data:
            response_content = response_data["response"]
            
            # Check for videos array
            if "videos" in response_content:
                videos = response_content["videos"]
                if videos:
                    video_base64 = videos[0]
                    if "bytesBase64Encoded" in video_base64:
                        video_b64 = video_base64["bytesBase64Encoded"]
                    else:
                        video_b64 = video_base64
                    
                    # Fix padding if needed
                    missing_padding = len(video_b64) % 4
                    if missing_padding:
                        video_b64 += "=" * (4 - missing_padding)
                    
                    video_bytes = base64.b64decode(video_b64)
                    video_path = DRAFTS_DIR / f"{video_id}.mp4"
                    
                    with open(video_path, "wb") as f:
                        f.write(video_bytes)
                    
                    video_saved = True
                    logger.info(f"Video saved from 'videos' array - Size: {len(video_bytes)} bytes")
            
            # Check for predictions array (alternative structure)
            elif "predictions" in response_content:
                predictions = response_content["predictions"]
                if predictions and len(predictions) > 0:
                    prediction = predictions[0]
                    if "videosBase64Encoded" in prediction:
                        videos = prediction["videosBase64Encoded"]
                        if videos:
                            video_info = videos[0]
                            if "bytesBase64Encoded" in video_info:
                                video_b64 = video_info["bytesBase64Encoded"]
                            elif isinstance(video_info, str):
                                video_b64 = video_info
                            else:
                                video_b64 = str(video_info)
                            
                            # Fix padding if needed
                            missing_padding = len(video_b64) % 4
                            if missing_padding:
                                video_b64 += "=" * (4 - missing_padding)
                            
                            video_bytes = base64.b64decode(video_b64)
                            video_path = DRAFTS_DIR / f"{video_id}.mp4"
                            
                            with open(video_path, "wb") as f:
                                f.write(video_bytes)
                            
                            video_saved = True
                            logger.info(f"Video saved from 'predictions' array - Size: {len(video_bytes)} bytes")
        
        if video_saved and video_path:
            # Save metadata
            file_size = os.path.getsize(video_path)
            metadata = {
                "video_id": video_id,
                "created_at": datetime.now().isoformat(),
                "file_size": file_size,
                "file_path": str(video_path)
            }
            
            metadata_path = DRAFTS_DIR / f"{video_id}_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Video decoding completed successfully - File size: {file_size} bytes")
            return str(video_path)
        else:
            error_msg = "Could not extract video data from response"
            logger.error(error_msg)
            raise Exception(error_msg)
            
    except Exception as e:
        error_msg = f"Video decoding failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

@app.get("/", response_class=JSONResponse)
async def get_api_documentation():
    """Complete API Documentation with Input/Output Formats"""
    return {
        "api_info": {
            "name": "18fps AI Video Generation API",
            "version": "1.0.0",
            "description": "Backend API for AI-powered video generation using Gemini and Veo",
            "base_url": "http://35.200.140.65:8000",
            "documentation_url": "http://35.200.140.65:8000/docs",
            "status": "online"
        },
        "endpoints": {
            "1_generate_video": {
                "method": "POST",
                "path": "/generate-video",
                "description": "Start video generation from story text",
                "input_format": {
                    "content_type": "application/json",
                    "required_fields": ["story"],
                    "optional_fields": ["style", "duration", "resolution"],
                    "example": {
                        "story": "A mysterious figure walks through a foggy forest at night",
                        "style": "cinematic",
                        "duration": 8,
                        "resolution": "720p"
                    },
                    "field_descriptions": {
                        "story": "string - Your story description (required)",
                        "style": "string - Visual style: 'cinematic', 'cartoon', 'realistic', '3d', 'hand-drawn' (default: 'cinematic')",
                        "duration": "integer - Video duration in seconds: 5, 8, 10, 15 (default: 8)",
                        "resolution": "string - Video resolution: '720p', '1080p' (default: '720p')"
                    }
                },
                "output_format": {
                    "content_type": "application/json",
                    "success_response": {
                        "video_id": "uuid-string",
                        "status": "started",
                        "message": "Video generation started successfully! Enhanced your story with AI."
                    },
                    "error_response": {
                        "detail": "Error description"
                    }
                }
            },
            "2_video_status": {
                "method": "GET",
                "path": "/video-status/{video_id}",
                "description": "Check video generation status and progress",
                "input_format": {
                    "path_parameter": "video_id (string) - UUID from generate-video response",
                    "example_url": "http://35.200.140.65:8000/video-status/12345678-1234-1234-1234-123456789abc"
                },
                "output_format": {
                    "content_type": "application/json",
                    "processing_response": {
                        "status": "processing",
                        "message": "Video generation in progress... Status: running"
                    },
                    "completed_response": {
                        "status": "completed",
                        "message": "Video generated and saved successfully!",
                        "video_path": "/drafts/{video_id}.mp4"
                    },
                    "error_response": {
                        "status": "error",
                        "message": "Error description"
                    }
                }
            },
            "3_list_drafts": {
                "method": "GET",
                "path": "/list-drafts",
                "description": "List all generated videos with metadata",
                "input_format": {
                    "parameters": "None required",
                    "example_url": "http://35.200.140.65:8000/list-drafts"
                },
                "output_format": {
                    "content_type": "application/json",
                    "response": [
                        {
                            "video_id": "uuid-string",
                            "created_at": "2025-10-02T10:30:00.000Z",
                            "file_size": 1234567,
                            "file_path": "drafts/video_id.mp4"
                        }
                    ]
                }
            },
            "4_download_video": {
                "method": "GET",
                "path": "/download-video/{video_id}",
                "description": "Download a generated video file",
                "input_format": {
                    "path_parameter": "video_id (string) - UUID of the video to download",
                    "example_url": "http://35.200.140.65:8000/download-video/12345678-1234-1234-1234-123456789abc"
                },
                "output_format": {
                    "content_type": "video/mp4",
                    "response": "Binary video file with filename: generated_video_{video_id}.mp4",
                    "error_response": {
                        "detail": "Video file not found"
                    }
                }
            },
            "5_delete_video": {
                "method": "DELETE",
                "path": "/delete-video/{video_id}",
                "description": "Delete a video and its metadata",
                "input_format": {
                    "path_parameter": "video_id (string) - UUID of the video to delete",
                    "example_url": "DELETE http://35.200.140.65:8000/delete-video/12345678-1234-1234-1234-123456789abc"
                },
                "output_format": {
                    "content_type": "application/json",
                    "success_response": {
                        "message": "Deleted video, metadata, operation_data for video {video_id}"
                    },
                    "error_response": {
                        "detail": "Video not found"
                    }
                }
            }
        },
        "usage_examples": {
            "1_basic_workflow": {
                "step_1": "POST /generate-video with story",
                "step_2": "GET /video-status/{video_id} (poll until completed)",
                "step_3": "GET /download-video/{video_id} to download",
                "step_4": "GET /list-drafts to see all videos"
            },
            "2_curl_examples": {
                "generate_video": "curl -X POST 'http://35.200.140.65:8000/generate-video' -H 'Content-Type: application/json' -d '{\"story\":\"A cat explores a magical garden\",\"style\":\"cinematic\",\"duration\":8}'",
                "check_status": "curl 'http://35.200.140.65:8000/video-status/{video_id}'",
                "list_videos": "curl 'http://35.200.140.65:8000/list-drafts'",
                "download_video": "curl -O 'http://35.200.140.65:8000/download-video/{video_id}'",
                "delete_video": "curl -X DELETE 'http://35.200.140.65:8000/delete-video/{video_id}'"
            },
            "3_javascript_example": {
                "generate_video": """
// Generate Video
const response = await fetch('http://35.200.140.65:8000/generate-video', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        story: 'A mysterious figure walks through a foggy forest at night',
        style: 'cinematic',
        duration: 8
    })
});
const result = await response.json();
console.log('Video ID:', result.video_id);

// Check Status
const statusResponse = await fetch(`http://35.200.140.65:8000/video-status/${result.video_id}`);
const status = await statusResponse.json();
console.log('Status:', status.status);""",
                "list_and_download": """
// List Videos
const listResponse = await fetch('http://35.200.140.65:8000/list-drafts');
const videos = await listResponse.json();
console.log('Available videos:', videos);

// Download Video (creates download link)
function downloadVideo(videoId) {
    const link = document.createElement('a');
    link.href = `http://35.200.140.65:8000/download-video/${videoId}`;
    link.download = `video_${videoId}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}"""
            }
        },
        "response_codes": {
            "200": "Success",
            "404": "Video not found",
            "500": "Server error (authentication, API limits, etc.)"
        },
        "features": {
            "ai_enhancement": "Stories are enhanced using Google Gemini AI with structured JSON prompts",
            "video_generation": "Videos created using Google Veo API with cinematic quality",
            "logging": "Comprehensive logging of all operations and prompts",
            "cors_enabled": "Cross-origin requests allowed from any domain",
            "file_management": "Automatic video storage and metadata tracking"
        },
        "notes": {
            "video_processing": "Video generation typically takes 30-120 seconds depending on duration and complexity",
            "polling": "Use /video-status endpoint to check progress - poll every 10-15 seconds",
            "storage": "Videos are stored on server and accessible via /download-video endpoint",
            "formats": "All videos are generated in MP4 format with 9:16 aspect ratio"
        }
    }

@app.post("/generate-video", response_model=VideoResponse)
async def generate_video(request: StoryRequest):
    """Generate a video from a story using Gemini and Veo"""
    try:
        # Create unique video ID
        video_id = str(uuid.uuid4())
        logger.info(f"Starting video generation request - Video ID: {video_id}")
        
        # Enhance story with Gemini
        enhanced_prompt = enhance_story_with_gemini(request.story, request.style)
        
        # Log the prompt interaction
        log_prompt_interaction(
            video_id=video_id,
            original_story=request.story,
            enhanced_prompt=enhanced_prompt,
            style=request.style,
            duration=request.duration
        )
        
        # Start video generation with Veo
        result = generate_video_with_veo(enhanced_prompt, request.duration, request.resolution)
        
        if result["success"]:
            # Store operation info
            active_operations[video_id] = {
                "operation_name": result["operation_name"],
                "original_story": request.story,
                "enhanced_prompt": enhanced_prompt,
                "style": request.style,
                "duration": request.duration,
                "resolution": request.resolution,
                "created_at": datetime.now().isoformat(),
                "status": "processing"
            }
            
            # Log successful operation start
            log_video_operation(
                video_id=video_id,
                operation_type="video_generation_start",
                status="success",
                message="Video generation started successfully",
                additional_data={
                    "operation_name": result["operation_name"],
                    "style": request.style,
                    "duration": request.duration,
                    "resolution": request.resolution
                }
            )
            
            logger.info(f"Video generation started successfully for video_id: {video_id}")
            return VideoResponse(
                video_id=video_id,
                status="started",
                message="Video generation started successfully! Enhanced your story with AI."
            )
        else:
            # Log failed operation start
            log_video_operation(
                video_id=video_id,
                operation_type="video_generation_start",
                status="error",
                message=result["error"]
            )
            
            logger.error(f"Video generation failed to start: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        error_msg = f"Failed to start video generation: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/video-status/{video_id}")
async def get_video_status(video_id: str):
    """Check the status of a video generation operation"""
    if video_id not in active_operations:
        logger.error(f"Video ID not found in active operations: {video_id}")
        raise HTTPException(status_code=404, detail="Video ID not found")
    
    operation_info = active_operations[video_id]
    logger.info(f"Checking status for video_id: {video_id}")
    
    try:
        # Poll the operation
        result = poll_video_operation(operation_info["operation_name"])
        
        if not result["success"]:
            active_operations[video_id]["status"] = "error"
            log_video_operation(
                video_id=video_id,
                operation_type="status_check",
                status="error",
                message=result["error"]
            )
            return {"status": "error", "message": result["error"]}
        
        if result["completed"]:
            # Video is ready, decode and save it
            try:
                video_path = decode_and_save_video(result["response"], video_id)
                active_operations[video_id]["status"] = "completed"
                active_operations[video_id]["video_path"] = video_path
                
                log_video_operation(
                    video_id=video_id,
                    operation_type="video_completion",
                    status="success",
                    message="Video generated and saved successfully",
                    additional_data={"video_path": video_path}
                )
                
                logger.info(f"Video completed successfully for video_id: {video_id}")
                return {
                    "status": "completed",
                    "message": "Video generated and saved successfully!",
                    "video_path": f"/drafts/{video_id}.mp4"
                }
            except Exception as e:
                active_operations[video_id]["status"] = "error"
                error_msg = f"Failed to decode video: {str(e)}"
                log_video_operation(
                    video_id=video_id,
                    operation_type="video_decoding",
                    status="error",
                    message=error_msg
                )
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}
        else:
            # Still processing
            status_msg = f"Video generation in progress... Status: {result.get('status', 'unknown')}"
            log_video_operation(
                video_id=video_id,
                operation_type="status_check",
                status="processing",
                message=status_msg,
                additional_data={"operation_status": result.get('status', 'unknown')}
            )
            return {
                "status": "processing",
                "message": status_msg
            }
            
    except Exception as e:
        active_operations[video_id]["status"] = "error"
        error_msg = f"Failed to check status: {str(e)}"
        log_video_operation(
            video_id=video_id,
            operation_type="status_check",
            status="error",
            message=error_msg
        )
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}

@app.get("/list-drafts")
async def list_video_drafts():
    """List all video drafts with metadata"""
    try:
        drafts = []
        for file_path in DRAFTS_DIR.glob("*_metadata.json"):
            try:
                with open(file_path, "r") as f:
                    metadata = json.load(f)
                drafts.append(metadata)
            except Exception as e:
                print(f"Error reading metadata file {file_path}: {e}")
        
        # Sort by creation date (newest first)
        drafts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return drafts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list drafts: {str(e)}")

@app.get("/download-video/{video_id}")
async def download_video(video_id: str):
    """Download a video file"""
    video_path = DRAFTS_DIR / f"{video_id}.mp4"
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"generated_video_{video_id}.mp4"
    )

@app.delete("/delete-video/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and its metadata"""
    try:
        video_path = DRAFTS_DIR / f"{video_id}.mp4"
        metadata_path = DRAFTS_DIR / f"{video_id}_metadata.json"
        
        deleted_files = []
        if video_path.exists():
            video_path.unlink()
            deleted_files.append("video")
        
        if metadata_path.exists():
            metadata_path.unlink()
            deleted_files.append("metadata")
        
        # Remove from active operations if present
        if video_id in active_operations:
            del active_operations[video_id]
            deleted_files.append("operation_data")
        
        if not deleted_files:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {"message": f"Deleted {', '.join(deleted_files)} for video {video_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting geNV AI Video Generation Backend API")
    logger.info(f"Drafts directory: {DRAFTS_DIR.absolute()}")
    logger.info(f"Logs directory: {LOGS_DIR.absolute()}")
    logger.info(f"Gemini API configured: {bool(GEMINI_API_KEY)}")
    logger.info("API Documentation available at: http://localhost:8000/docs")
    logger.info("API will be accessible at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)