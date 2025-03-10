#!/usr/bin/env python
# Entry point for the YouTube Summarizer application

from src.yt_summarizer import app

# For local development only
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)