#!/usr/bin/env python3
"""
Deployment helper script for PythonAnywhere
Creates necessary directories and configures paths
"""

import os
import sys
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_directories():
    """Create necessary directories for the application"""
    directories = [
        '/tmp/jsoninventoryslips',
        '/tmp/inventory_generator/uploads',
        '/tmp/flask_session',
        '/tmp/inventory_slips_data'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

def verify_paths():
    """Verify all necessary paths and files exist"""
    required_files = [
        'app.py',
        'wsgi.py',
        'requirements.txt',
        'src/utils/session_storage.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        raise FileNotFoundError(f"Missing required files: {', '.join(missing_files)}")
    
    logger.info("All required files present")

def setup_virtualenv():
    """Print instructions for setting up virtualenv on PythonAnywhere"""
    print("\nPythonAnywhere Setup Instructions:")
    print("1. Go to the PythonAnywhere dashboard")
    print("2. Open a Bash console")
    print("3. Run the following commands:")
    print("\nmkvirtualenv --python=/usr/bin/python3.11 myapp")
    print("pip install -r requirements.txt\n")

def print_wsgi_instructions():
    """Print instructions for configuring the WSGI file"""
    print("\nWSGI Configuration Instructions:")
    print("1. Go to the Web tab in PythonAnywhere")
    print("2. Click on your web app")
    print("3. Go to the Code section")
    print("4. Click on the WSGI configuration file")
    print("5. Replace the contents with your wsgi.py file")
    print("6. Update the following paths in the WSGI file:")
    print("   - WEBAPP_PATH = '/home/yourusername/JSONInventorySlipsWeb-copy'")
    print("   - VENV_PATH = '/home/yourusername/.virtualenvs/myapp'\n")

def main():
    try:
        logger.info("Starting deployment preparation...")
        
        # Verify we have all necessary files
        verify_paths()
        
        # Create required directories
        create_directories()
        
        # Print setup instructions
        setup_virtualenv()
        print_wsgi_instructions()
        
        print("\nDeployment preparation completed successfully!")
        print("Follow the instructions above to complete the deployment on PythonAnywhere.")
        
    except Exception as e:
        logger.error(f"Deployment preparation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
