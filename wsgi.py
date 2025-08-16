import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Configure paths for PythonAnywhere
WEBAPP_PATH = os.path.dirname(os.path.abspath(__file__))
VENV_PATH = '/home/leruseadam/.virtualenvs/myapp/lib/python3.11/site-packages'  # PythonAnywhere venv path

# Create tmp directories for logs and uploads
log_directory = '/tmp/jsoninventoryslips'
upload_directory = '/tmp/inventory_generator/uploads'

try:
    os.makedirs(log_directory, exist_ok=True)
    os.makedirs(upload_directory, exist_ok=True)
except Exception as e:
    print(f'Failed to create directories: {str(e)}')

# Set up paths
paths = [WEBAPP_PATH]
if VENV_PATH not in sys.path:
    paths.append(VENV_PATH)

for path in paths:
    if path not in sys.path:
        sys.path.insert(0, path)

# Configure logging with rotation
log_file = os.path.join(log_directory, 'app.log')
try:
    handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
except Exception as e:
    print(f'Failed to set up file logging: {str(e)}')
    # Fallback to stderr logging
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
handler.setFormatter(formatter)

logger = logging.getLogger('wsgi')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configure SSL certificates
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    logger.info(f'SSL certificates configured from: {certifi.where()}')
except Exception as e:
    logger.error(f'Failed to configure SSL certificates: {str(e)}')

# Use the predefined upload directory
UPLOAD_FOLDER = upload_directory

try:
    # Import the Flask application
    from app import app as application
    
    # Configure application
    application.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=3600,
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max upload
        UPLOAD_FOLDER=UPLOAD_FOLDER
    )
    
    # Add logging to the application
    application.logger.addHandler(handler)
    application.logger.setLevel(logging.INFO)
    application.logger.info('WSGI Startup - Application Initialized')

except Exception as e:
    logger.error('Failed to import application:')
    logger.error(traceback.format_exc())
    raise

def application(environ, start_response):
    """WSGI application function with error handling"""
    try:
        return application(environ, start_response)
    except Exception as e:
        logger.error(f'WSGI Error: {str(e)}', exc_info=True)
        status = '500 Internal Server Error'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return [b'An error occurred processing your request.']
    finally:
        # Clean up any temporary files
        try:
            from app import cleanup_temp_files
            cleanup_temp_files()
        except Exception as e:
            logger.warning(f'Cleanup error: {str(e)}')

# Local development server (not used on PythonAnywhere)
if __name__ == '__main__':
    application.run(debug=False, use_reloader=False)
