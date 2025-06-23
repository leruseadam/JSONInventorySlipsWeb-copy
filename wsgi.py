import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Configure paths
WEBAPP_PATH = '/home/adamcordova/JSONInventorySlipsWeb-copy'

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(WEBAPP_PATH, 'wsgi.log'))
    ]
)
logger = logging.getLogger('wsgi')

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
