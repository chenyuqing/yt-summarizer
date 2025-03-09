import os
import sys
import requests
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template

# Import version information
from version import __version__ as VERSION

load_dotenv()

# File to store summary history
HISTORY_FILE = "summary_history.json"

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

def get_transcript(video_id: str) -> str:
    """Fetch YouTube transcript using SearchAPI.io"""
    response = requests.get(
        "https://www.searchapi.io/api/v1/search",
        params={
            "engine": "youtube_transcripts",
            "video_id": video_id,
            "api_key": os.getenv("SEARCHAPI_KEY")
        }
    )
    response.raise_for_status()
    response_data = response.json()
    
    # Check if 'transcripts' key exists in the response
    if "transcripts" not in response_data or not response_data["transcripts"]:
        raise ValueError(f"No transcripts available for video ID: {video_id}. The video might not have captions or subtitles.")
        
    return " ".join([entry["text"] for entry in response_data["transcripts"]])

def summarize_text(text: str) -> str:
    """Generate summary using Deepseek API"""
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('DEEPSEEK_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{
                    "role": "user",
                    "content": f"Convert this transcript into markdown bullet points:\n{text}"
                }],
                "temperature": 0.7
            }
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"API Error Details: {e.response.text}")  # Show error details
        raise
    return response.json()["choices"][0]["message"]["content"]

def load_history():
    """Load summary history from file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_to_history(video_id, url, summary):
    """Save summary to history file"""
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
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', version=VERSION)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'version': VERSION
    })

@app.route('/summarize', methods=['POST'])
def summarize_video():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'Missing YouTube URL'}), 400
        
        # Extract video ID    
        video_id = extract_video_id(url)
        
        # Update progress
        progress_update("Fetching transcript...")
        transcript = get_transcript(video_id)
        
        # Update progress
        progress_update("Generating summary...")
        summary = summarize_text(transcript)
        
        # Save summary to file
        with open(f"{video_id}_summary.md", "w") as f:
            f.write(summary)
        
        # Save to history
        save_to_history(video_id, url, summary)
            
        return jsonify({
            'summary': summary,
            'video_id': video_id
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except requests.HTTPError as e:
        return jsonify({'error': f"API Error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': f"Unexpected error: {str(e)}"}), 500

@app.route('/progress', methods=['GET'])
def progress_update(message=None):
    """Update or get progress status"""
    progress_file = "progress_status.json"
    
    if message and request.method == 'POST':
        with open(progress_file, "w") as f:
            json.dump({"message": message, "timestamp": datetime.now().isoformat()}, f)
        return jsonify({"status": "updated"})
    
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r") as f:
                return jsonify(json.load(f))
        return jsonify({"message": "Ready", "timestamp": datetime.now().isoformat()})
    except Exception:
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
        
        with open(f"{video_id}_summary.md", "w") as f:
            f.write(summary)
        
        # Save to history
        save_to_history(video_id, f"https://youtube.com/watch?v={video_id}", summary)
            
        print(f"Summary saved to {video_id}_summary.md")
        print("="*50)
        print(summary)
        
    except Exception as e:
        sys.exit(f"Error: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)
