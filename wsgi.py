import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Configure paths for both local and PythonAnywhere environments
if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    # PythonAnywhere path
    WEBAPP_PATH = '/home/adamcordova/JSONInventorySlipsWeb-copy'
else:
    # Local development path
    WEBAPP_PATH = os.path.dirname(os.path.abspath(__file__))

LOG_PATH = os.path.join(WEBAPP_PATH, 'logs')

# Create logs directory if it doesn't exist
try:
    os.makedirs(LOG_PATH, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create logs directory: {e}")

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

# Add application directory to Python path
if WEBAPP_PATH not in sys.path:
    sys.path.insert(0, WEBAPP_PATH)
    logger.info(f'Added {WEBAPP_PATH} to Python path')

try:
    # Import the Flask application
    from app import app as application
    logger.info('Successfully imported application')

except Exception as e:
    logger.error('Failed to import application:')
    logger.error(traceback.format_exc())
    raise

# This is the important part for PythonAnywhere
if __name__ == '__main__':
    application.run(debug=False, use_reloader=False)
