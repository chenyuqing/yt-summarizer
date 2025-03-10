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

Current version: 0.4

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

## Deployment

### Deploy to Heroku

1. Install the Heroku CLI and login:
   ```
   brew install heroku/brew/heroku  # For macOS
   heroku login
   ```

2. Create a new Heroku app:
   ```
   heroku create your-app-name
   ```

3. Add a Procfile in the root directory:
   ```
   web: gunicorn app:app
   ```

4. Set environment variables (optional, as users can now provide API keys in the interface):
   ```
   heroku config:set SEARCHAPI_KEY=your_key DEEPSEEK_KEY=your_key
   ```

5. Deploy the application:
   ```
   git push heroku main
   ```

6. Scale the web dyno:
   ```
   heroku ps:scale web=1
   ```

7. Open the application:
   ```
   heroku open
   ```

Your live application will be available at: `https://your-app-name.herokuapp.com`

### Deploy to Railway

1. Create a Railway account at https://railway.app/
2. Connect your GitHub repository
3. Create a new project from the GitHub repo
4. Railway will automatically detect the requirements.txt and deploy your app
5. Set environment variables in the Railway dashboard (optional)
6. Your app will be deployed with a public URL

### Deploy to Render

1. Create a Render account at https://render.com/
2. Create a new Web Service
3. Connect your GitHub repository
4. Configure the service:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Set environment variables (optional)
6. Deploy the service

### Production Considerations

- **Security**: Ensure your API keys are properly secured using environment variables
- **Rate Limiting**: The application includes rate limiting to prevent abuse
- **Logging**: Check application logs regularly for errors or unusual activity
- **Backups**: Regularly backup your summary history and output files
- **Monitoring**: Set up alerts for application downtime or errors

## License

MIT