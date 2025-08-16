"""
WSGI configuration file for PythonAnywhere deployment.
"""
import os
import sys
import logging
import traceback
from logging.handlers import RotatingFileHandler

# Set virtualenv path
VENV_PATH = os.path.expanduser('~/.virtualenvs/myapp')
PYTHON_BIN = os.path.join(VENV_PATH, 'bin/python')
SITE_PACKAGES = os.path.join(VENV_PATH, 'lib/python3.11/site-packages')

# Configure paths for PythonAnywhere
WEBAPP_PATH = '/home/adamcordova/JSONInventorySlipsWeb-copy'
VENV_PATH = '/home/adamcordova/.virtualenvs/myapp'
SITE_PACKAGES = os.path.join(VENV_PATH, 'lib/python3.11/site-packages')

# Set up logging
log_directory = '/tmp/jsoninventoryslips'
upload_directory = '/tmp/inventory_generator/uploads'

os.makedirs(log_directory, exist_ok=True)
os.makedirs(upload_directory, exist_ok=True)

log_file = os.path.join(log_directory, 'app.log')
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger('wsgi')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Add the application directory to Python path first
if WEBAPP_PATH not in sys.path:
    sys.path.insert(0, WEBAPP_PATH)

# Add src directory to Python path
src_path = os.path.join(WEBAPP_PATH, 'src')
if os.path.exists(src_path) and src_path not in sys.path:
    sys.path.insert(1, src_path)

# Add site-packages to Python path
if os.path.exists(SITE_PACKAGES) and SITE_PACKAGES not in sys.path:
    sys.path.append(SITE_PACKAGES)

# Set PYTHONPATH
os.environ['PYTHONPATH'] = f"{WEBAPP_PATH}:{src_path}:{SITE_PACKAGES}"

# Change to the application directory
os.chdir(WEBAPP_PATH)

# Configure SSL certificates
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except Exception as e:
    logger.error(f'Failed to configure SSL certificates: {str(e)}')

try:
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.path}")
    
    # Import the Flask application
    import app
    application = app.app
    
    # Configure application
    application.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=3600,
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        UPLOAD_FOLDER=upload_directory
    )
    
    # Add logging to the application
    application.logger.addHandler(handler)
    application.logger.setLevel(logging.INFO)
    application.logger.info('WSGI Startup - Application Initialized')
    
except Exception as e:
    logger.error('Failed to import application:')
    logger.error(traceback.format_exc())
    raise
