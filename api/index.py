from flask import Flask, request, jsonify, Response
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle distutils.version deprecation in newer Python versions
# This needs to be done before importing flask_limiter
sys.modules['distutils'] = type('', (), {})()
sys.modules['distutils.version'] = type('', (), {})()
sys.modules['distutils.version'].LooseVersion = lambda x: x

# Handle pkg_resources issues
sys.modules['pkg_resources'] = type('', (), {})()
sys.modules['pkg_resources'].get_distribution = lambda x: type('', (), {'version': '0.0.0'})()

# Import the Flask app
from src.yt_summarizer import app as flask_app

def handler(request, context):
    """
    Serverless function handler for Vercel
    
    This function adapts the Flask app to work with Vercel's serverless environment
    by converting the request format to what Flask expects.
    """
    # Extract request components
    path = request.get('path', '/')
    http_method = request.get('method', 'GET')
    headers = request.get('headers', {})
    body = request.get('body', '')
    query_params = request.get('query', {})
    
    # Create a WSGI environment dictionary that Flask can understand
    environ = {
        'PATH_INFO': path,
        'REQUEST_METHOD': http_method,
        'QUERY_STRING': '&'.join([f"{k}={v}" for k, v in query_params.items()]),
        'wsgi.input': body,
        'wsgi.url_scheme': 'https',
        'CONTENT_LENGTH': str(len(body) if body else 0),
        'CONTENT_TYPE': headers.get('content-type', 'text/plain'),
        'SERVER_NAME': 'vercel',
        'SERVER_PORT': '443',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'HTTP_HOST': headers.get('host', 'localhost'),
    }
    
    # Add HTTP headers to the environment
    for key, value in headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            environ[f'HTTP_{key}'] = value
    
    # Capture the response from the Flask app
    response_status = []
    response_headers = []
    
    def start_response(status, headers):
        response_status.append(status)
        response_headers.extend(headers)
    
    # Call the Flask app with the WSGI environment
    response_body = b''.join(flask_app(environ, start_response))
    
    # Parse the status code
    status_code = int(response_status[0].split(' ')[0]) if response_status else 200
    
    # Convert headers to a dictionary
    headers_dict = {k: v for k, v in response_headers}
    
    # Ensure API endpoints always return JSON content type
    if path != '/' and 'Content-Type' not in headers_dict:
        headers_dict['Content-Type'] = 'application/json'
    
    # Return the response in the format Vercel expects
    return {
        'statusCode': status_code,
        'headers': headers_dict,
        'body': response_body.decode('utf-8') if isinstance(response_body, bytes) else response_body
    }