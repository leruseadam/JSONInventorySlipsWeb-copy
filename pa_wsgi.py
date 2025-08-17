"""PythonAnywhere WSGI Configuration"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Configure paths for PythonAnywhere
WEBAPP_PATH = '/home/adamcordova/JSONInventorySlipsWeb-copy'
LOG_PATH = os.path.join(WEBAPP_PATH, 'logs')

# Ensure the logs directory exists
os.makedirs(LOG_PATH, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            os.path.join(LOG_PATH, 'wsgi.log'),
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
    ]
)
logger = logging.getLogger('wsgi')

# Log important environment information
logger.info(f"WEBAPP_PATH: {WEBAPP_PATH}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"sys.path: {sys.path}")

# Add application directory to Python path
if WEBAPP_PATH not in sys.path:
    sys.path.insert(0, WEBAPP_PATH)
    logger.info(f'Added {WEBAPP_PATH} to Python path')

# Import the Flask application
try:
    from app import app as application
    logger.info('Successfully imported application')
except Exception as e:
    logger.error('Failed to import application:')
    logger.error(str(e))
    raise
