#!/usr/bin/env python3
"""
PythonAnywhere WSGI configuration file
Copy this content to your PythonAnywhere WSGI configuration
"""

import sys
import os

# Add your project directory to the Python path
path = '/home/yourusername/JSONInventorySlipsWeb-copy'
if path not in sys.path:
    sys.path.append(path)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'your-super-secret-key-change-this'

# Import your Flask app
from wsgi import app as application

# Optional: Enable debug mode for testing (remove in production)
# application.config['DEBUG'] = True
