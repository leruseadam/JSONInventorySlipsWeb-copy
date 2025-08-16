"""
WSGI configuration file for PythonAnywhere deployment.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
log_directory = '/tmp/jsoninventoryslips'
os.makedirs(log_directory, exist_ok=True)

log_file = os.path.join(log_directory, 'app.log')
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger('wsgi')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configure paths
APP_DIR = '/home/adamcordova/JSONInventorySlipsWeb-copy'
VENV_DIR = '/home/adamcordova/.virtualenvs/myapp'
SITE_PACKAGES = os.path.join(VENV_DIR, 'lib/python3.11/site-packages')

# Log initial state
logger.info(f"Initial sys.path: {sys.path}")
logger.info(f"Initial cwd: {os.getcwd()}")

# Remove any existing paths that might interfere
sys.path = [p for p in sys.path if not p.startswith('/home/adamcordova')]

# Add our paths in the correct order
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if SITE_PACKAGES not in sys.path:
    sys.path.append(SITE_PACKAGES)

# Change to the application directory
os.chdir(APP_DIR)

# Log path configuration
logger.info(f"Final sys.path: {sys.path}")
logger.info(f"Final cwd: {os.getcwd()}")
logger.info(f"Directory contents: {os.listdir(APP_DIR)}")

try:
    # Try to import the app
    import app
    logger.info(f"Successfully imported app from {app.__file__}")
    application = app.app
    
except ImportError as e:
    logger.error(f"Failed to import app: {e}")
    logger.error(f"sys.path: {sys.path}")
    logger.error(f"cwd: {os.getcwd()}")
    logger.error(f"APP_DIR contents: {os.listdir(APP_DIR)}")
    raise

# Configure the Flask application
application.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024
)

# Add logging to the application
application.logger.addHandler(handler)
application.logger.setLevel(logging.INFO)
application.logger.info('WSGI Application Initialized')
