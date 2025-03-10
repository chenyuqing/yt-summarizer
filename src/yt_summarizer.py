import os
import sys
import requests
import re
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from loguru import logger

# Import version information
try:
    from src.version import __version__ as VERSION
except ImportError:
    # Fallback for Vercel environment
    VERSION = "0.4"

load_dotenv()

# Configure logger
logger.remove()
try:
    log_file = "/tmp/app.log" if os.environ.get('VERCEL_ENV') else "app.log"
    logger.add(log_file, rotation="500 MB", level="INFO", catch=True)
except Exception as e:
    # If file logging fails, just log to stderr
    pass
logger.add(sys.stderr, level="WARNING")

# File to store summary history - use /tmp for Vercel
HISTORY_FILE = "/tmp/summary_history.json" if os.environ.get('VERCEL_ENV') else "summary_history.json"

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    # Regular expressions to match various YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/.*?[?&]v=)([\w-]{11})',  # Standard and shortened URLs
        r'youtube\.com\/embed\/([\w-]{11})',                      # Embed URLs
        r'youtube\.com\/v\/([\w-]{11})',                          # Old embed URLs
        r'youtube\.com\/user\/\w+\/\w+\/([\w-]{11})',           # User URLs
        r'youtube\.com\/\w+\/\w+\/([\w-]{11})'                    # Other formats
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If the input is already just a video ID, return it
    if re.match(r'^[\w-]{11}$', url):
        return url
        
    raise ValueError("Could not extract YouTube video ID from URL. Please provide a valid YouTube URL.")

def get_transcript(video_id: str, api_key: str = None) -> str:
    """Fetch YouTube transcript using SearchAPI.io"""
    # Use provided API key if available, otherwise use environment variable
    searchapi_key = api_key or os.getenv("SEARCHAPI_KEY")
    
    if not searchapi_key:
        raise ValueError("SearchAPI.io API key is required. Please provide it in the form or set it in the .env file.")
        
    response = requests.get(
        "https://www.searchapi.io/api/v1/search",
        params={
            "engine": "youtube_transcripts",
            "video_id": video_id,
            "api_key": searchapi_key
        }
    )
    response.raise_for_status()
    response_data = response.json()
    
    # Check if 'transcripts' key exists in the response
    if "transcripts" not in response_data or not response_data["transcripts"]:
        raise ValueError(f"No transcripts available for video ID: {video_id}. The video might not have captions or subtitles.")
        
    return " ".join([entry["text"] for entry in response_data["transcripts"]])

def summarize_text(text: str, api_key: str = None) -> str:
    """Generate summary using Deepseek API"""
    # Use provided API key if available, otherwise use environment variable
    deepseek_key = api_key or os.getenv("DEEPSEEK_KEY")
    
    if not deepseek_key:
        raise ValueError("Deepseek API key is required. Please provide it in the form or set it in the .env file.")
        
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{
                    "role": "user",
                    "content": f"Convert this transcript into a numbered list format (1., 2., 3., etc.):\n{text}"
                }],
                "temperature": 0.7
            }
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        error_text = e.response.text
        print(f"API Error Details: {error_text}")  # Show error details
        
        # Parse the error response to extract more specific error messages
        try:
            error_json = json.loads(error_text)
            if "error" in error_json and "message" in error_json["error"]:
                error_message = error_json["error"]["message"]
                if "Authentication Fails" in error_message:
                    raise ValueError(f"Deepseek API authentication failed: {error_message}. Please check your API key.")
                else:
                    raise ValueError(f"Deepseek API error: {error_message}")
        except json.JSONDecodeError:
            pass
            
        raise
    return response.json()["choices"][0]["message"]["content"]

def ensure_directory_exists(path):
    """Ensure a directory exists, handling edge cases for serverless environments"""
    try:
        # Handle case where path is a file path by getting the directory
        directory = path if os.path.splitext(path)[1] == '' else os.path.dirname(path)
        
        # If directory is empty string, use current directory
        if not directory:
            directory = '.'
            
        # Create directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {str(e)}")
        return False

def load_history():
    """Load summary history from file"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.error(f"Error loading history file: {str(e)}")
    return []

def save_to_history(video_id, url, summary):
    """Save summary to history file"""
    try:
        history = load_history()
        
        # Create history entry
        entry = {
            "video_id": video_id,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "summary_file": f"{video_id}_summary.md"
        }
        
        # Add to history and save
        history.append(entry)
        
        # Ensure directory exists before writing file
        ensure_directory_exists(os.path.dirname(HISTORY_FILE) or '.')
        
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving to history: {str(e)}")
        # Continue execution even if history save fails

# Create Flask app with correct template folder path
try:
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app = Flask(__name__, template_folder=template_dir)
except Exception as e:
    # Fallback for Vercel environment
    app = Flask(__name__, template_folder='templates')
    logger.error(f"Error setting template directory: {str(e)}")

# Configure rate limiting with in-memory storage for Vercel compatibility
try:
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
except Exception as e:
    # Fallback with minimal configuration
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"]
    )
    logger.error(f"Error configuring rate limiter: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html', version=VERSION)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'version': VERSION
    })

# Create a separate utility function for updating progress
def update_progress_status(message):
    """Update progress status file"""
    progress_file = "/tmp/progress_status.json" if os.environ.get('VERCEL_ENV') else "progress_status.json"
    try:
        # Ensure directory exists before writing file
        ensure_directory_exists(os.path.dirname(progress_file) or '.')
        
        with open(progress_file, "w") as f:
            json.dump({"message": message, "timestamp": datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        logger.error(f"Error updating progress: {str(e)}")
        return False

@app.route('/summarize', methods=['POST'])
@limiter.limit("5 per minute")
def summarize_video():
    try:
        # Check if request has JSON data
        if not request.is_json:
            logger.warning(f"Invalid request format from {request.remote_addr}")
            return jsonify({'error': 'Invalid request format. JSON required'}), 400
            
        url = request.json.get('url')
        if not url:
            logger.warning(f"Missing YouTube URL in request from {request.remote_addr}")
            return jsonify({'error': 'Missing YouTube URL'}), 400
            
        # Get API keys from request if provided
        deepseek_key = request.json.get('deepseek_key')
        searchapi_key = request.json.get('searchapi_key')
        
        # Extract video ID    
        video_id = extract_video_id(url)
        logger.info(f"Processing video ID: {video_id} from IP: {request.remote_addr}")
        
        # Update progress
        try:
            update_progress_status("Fetching transcript...")
        except Exception as e:
            logger.error(f"Error updating progress status: {str(e)}")
            # Continue even if progress update fails
            
        # Get transcript with error handling
        try:
            transcript = get_transcript(video_id, searchapi_key)
        except Exception as e:
            logger.error(f"Error getting transcript: {str(e)}")
            return jsonify({'error': f"Failed to get transcript: {str(e)}"}), 400
        
        # Update progress
        try:
            update_progress_status("Generating summary...")
        except Exception as e:
            logger.error(f"Error updating progress status: {str(e)}")
            # Continue even if progress update fails
        
        # Generate summary with error handling
        try:
            summary = summarize_text(transcript, deepseek_key)
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return jsonify({'error': f"Failed to generate summary: {str(e)}"}), 400
        
        # Save summary to file
        output_dir = "/tmp/output" if os.environ.get('VERCEL_ENV') else "output"
        try:
            # Ensure the output directory exists using our helper function
            ensure_directory_exists(output_dir)
            
            summary_path = os.path.join(output_dir, f"{video_id}_summary.md")
            with open(summary_path, "w") as f:
                f.write(summary)
        except Exception as e:
            logger.error(f"Error saving summary file: {str(e)}")
            # Continue even if file save fails - this is non-critical
        
        # Save to history
        try:
            save_to_history(video_id, url, summary)
        except Exception as e:
            logger.error(f"Error saving to history: {str(e)}")
            # Continue even if history save fails
            
        logger.info(f"Successfully generated summary for video ID: {video_id}")
            
        return jsonify({
            'summary': summary,
            'video_id': video_id
        })
    except ValueError as e:
        # This will now catch our more specific API authentication errors
        logger.warning(f"Value error during summarization: {str(e)} for request from {request.remote_addr}")
        return jsonify({'error': str(e)}), 400
    except requests.HTTPError as e:
        # Try to extract more specific error information from the response
        try:
            response_json = e.response.json()
            if 'error' in response_json and 'message' in response_json['error']:
                error_message = response_json['error']['message']
                logger.error(f"API Error: {error_message} for request from {request.remote_addr}")
                return jsonify({'error': f"API Error: {error_message}"}), 400 if 'authentication' in error_message.lower() else 500
        except (ValueError, AttributeError, KeyError):
            pass
        logger.error(f"HTTP Error during API request: {str(e)} for request from {request.remote_addr}")
        return jsonify({'error': f"API Error: {str(e)}"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error during summarization: {str(e)} for request from {request.remote_addr}")
        return jsonify({'error': f"Unexpected error: {str(e)}"}), 500

@app.route('/progress', methods=['GET'])
def progress_update():
    """Get progress status"""
    progress_file = "/tmp/progress_status.json" if os.environ.get('VERCEL_ENV') else "progress_status.json"
    
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r") as f:
                return jsonify(json.load(f))
        return jsonify({"message": "Ready", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"Error reading progress file: {str(e)}")
        return jsonify({"message": "Ready", "timestamp": datetime.now().isoformat()})

@app.route('/history', methods=['GET'])
def get_history():
    """Get summary history"""
    history = load_history()
    return jsonify(history)

# 添加全局JSON响应处理
def add_cors_headers(response):
    if request.path == '/':
        return response
    response.headers['Content-Type'] = 'application/json'
    return response

app.after_request(add_cors_headers)

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")
    return jsonify({'error': 'Internal server error'}), 500

def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: python yt_summarizer.py [YOUTUBE_VIDEO_ID]")
            
        video_id = sys.argv[1]
        print(f"Fetching transcript for video {video_id}...")
        transcript = get_transcript(video_id)
        
        print("Generating summary...")
        summary = summarize_text(transcript)
        
        # Ensure output directory exists
        output_dir = "output"
        ensure_directory_exists(output_dir)
        summary_path = os.path.join(output_dir, f"{video_id}_summary.md")
        
        with open(summary_path, "w") as f:
            f.write(summary)
        
        # Save to history
        save_to_history(video_id, f"https://youtube.com/watch?v={video_id}", summary)
            
        print(f"Summary saved to {summary_path}")
        print("="*50)
        print(summary)
        
    except Exception as e:
        sys.exit(f"Error: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)
