#!/bin/bash

# Print commands and their arguments as they are executed
set -x

echo "Starting deployment fixes..."

# Backup the old app.py if it exists
if [ -f ~/app.py ]; then
    echo "Backing up existing app.py..."
    mv ~/app.py ~/app.py.bak
fi

# Update the WSGI file
echo "Updating WSGI configuration..."
cat > /var/www/www_jsoninventoryslips_com_wsgi.py << 'EOF'
import os
import sys

# Add application directory to Python path
project_home = '/home/adamcordova/JSONInventorySlipsWeb-copy'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import app as application
from app import app as application
EOF

# Remove old files and clone fresh
echo "Removing old repository..."
rm -rf ~/JSONInventorySlipsWeb-copy

echo "Cloning fresh repository..."
cd ~
git clone https://github.com/leruseadam/JSONInventorySlipsWeb-copy.git

# Clean up virtualenv
echo "Cleaning up virtualenv..."
source ~/.virtualenvs/myapp/bin/activate
pip uninstall -y docxtpl docxcompose
pip install --upgrade pip
pip install -r ~/JSONInventorySlipsWeb-copy/requirements.txt

# Clean Python cache
echo "Cleaning Python cache..."
find ~/JSONInventorySlipsWeb-copy -type f -name "*.pyc" -delete
find ~/JSONInventorySlipsWeb-copy -type d -name "__pycache__" -delete

# Reload the application
echo "Touching WSGI file to reload..."
touch /var/www/www_jsoninventoryslips_com_wsgi.py

echo "Deployment fixes complete!"
