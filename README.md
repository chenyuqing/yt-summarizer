# YouTube Video Summarizer

A web application that generates concise summaries of YouTube videos using AI.

## Features

- Extract transcripts from YouTube videos
- Generate markdown bullet-point summaries using Deepseek AI
- Track summary history
- Display progress updates during summarization
- Save summaries to local files
- User-friendly web interface

## Version Information

Current version: 0.2

See [VERSION_HISTORY.md](VERSION_HISTORY.md) for detailed changelog.

## Setup

1. Ensure you have Python installed
2. Clone this repository
3. Activate the virtual environment:
   ```
   source bin/activate
   ```
4. Create a `.env` file with your API keys:
   ```
   SEARCHAPI_KEY=your_searchapi_key
   DEEPSEEK_KEY=your_deepseek_key
   ```
5. Run the application:
   ```
   python yt_summarizer.py
   ```
6. Open your browser and navigate to `http://localhost:5001`

## Command Line Usage

You can also use the tool from the command line:

```
python yt_summarizer.py [YOUTUBE_VIDEO_ID]
```

## Version Management

This project uses semantic versioning. Version information is centralized in `version.py` and referenced throughout the application.

To update the version:

1. Modify the version information in `version.py`
2. Update the changelog in `VERSION_HISTORY.md`

## License

MIT