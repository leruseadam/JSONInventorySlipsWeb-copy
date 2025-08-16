import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Configure paths for PythonAnywhere
WEBAPP_PATH = '/home/adamcordova/JSONInventorySlipsWeb-copy'  # Explicit path to your app
VENV_PATH = '/home/adamcordova/.virtualenvs/myapp'
SITE_PACKAGES = os.path.join(VENV_PATH, 'lib/python3.11/site-packages')

# Add the application directory to PYTHONPATH first
if WEBAPP_PATH not in sys.path:
    sys.path.insert(0, WEBAPP_PATH)

# Ensure src directory is in the path for package imports
SRC_PATH = os.path.join(WEBAPP_PATH, 'src')
if os.path.exists(SRC_PATH) and SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Add virtualenv site-packages
if os.path.exists(SITE_PACKAGES) and SITE_PACKAGES not in sys.path:
    sys.path.append(SITE_PACKAGES)

# Set up logging first
logger = logging.getLogger('wsgi')
logger.setLevel(logging.INFO)

# Set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = f"{WEBAPP_PATH}:{SRC_PATH}:{SITE_PACKAGES}"

# Log the final sys.path configuration
logger.info("Final Python path configuration:")
for p in sys.path:
    logger.info(f"  {p}")

# Create any missing __init__.py files
def ensure_init_files():
    """Create any missing __init__.py files in the src directory structure"""
    dirs_needing_init = [
        os.path.join(WEBAPP_PATH, 'src'),
        os.path.join(WEBAPP_PATH, 'src/utils'),
        os.path.join(WEBAPP_PATH, 'src/base'),
        os.path.join(WEBAPP_PATH, 'src/config'),
        os.path.join(WEBAPP_PATH, 'src/data'),
        os.path.join(WEBAPP_PATH, 'src/themes'),
        os.path.join(WEBAPP_PATH, 'src/ui')
    ]
    
    for dir_path in dirs_needing_init:
        init_file = os.path.join(dir_path, '__init__.py')
        try:
            if os.path.exists(dir_path) and not os.path.exists(init_file):
                with open(init_file, 'w') as f:
                    f.write('"""Package initialization."""\n')
                logger.info(f"Created missing __init__.py in {dir_path}")
        except Exception as e:
            logger.warning(f"Could not create __init__.py in {dir_path}: {e}")

# Ensure all necessary __init__.py files exist
ensure_init_files()

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
    # Log the current sys.path for debugging
    logger.info("Python path at startup:")
    for p in sys.path:
        logger.info(f"  {p}")
    
    # Change to the application directory before importing
    os.chdir(WEBAPP_PATH)
    logger.info(f"Changed working directory to: {os.getcwd()}")
    
    # Verify app.py exists
    if not os.path.exists(os.path.join(WEBAPP_PATH, 'app.py')):
        raise FileNotFoundError(f"app.py not found in {WEBAPP_PATH}")
    
    # Import the Flask application from the correct path
    import app
    application = app.app
    
    # Log successful import
    logger.info("Successfully imported app")
    
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

def wsgi_handler(environ, start_response):
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

# Replace the application variable with our handler
application = wsgi_handler

# Local development server (not used on PythonAnywhere)
if __name__ == '__main__':
    from app import app as flask_app
    flask_app.run(debug=False, use_reloader=False)
