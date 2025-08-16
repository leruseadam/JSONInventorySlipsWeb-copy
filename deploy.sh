#!/bin/bash

# Print commands and their arguments as they are executed
set -x

echo "Starting deployment..."

# Change to the application directory
cd ~/JSONInventorySlipsWeb-copy

# Fetch and pull latest changes
echo "Pulling latest changes..."
git fetch origin
git reset --hard origin/main

# Activate virtual environment
echo "Activating virtual environment..."
source ~/.virtualenvs/myapp/bin/activate

# Remove problematic packages first
echo "Removing problematic packages..."
pip uninstall -y docxtpl docxcompose

# Install/upgrade requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Clean up any cached Python files
echo "Cleaning up cached files..."
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete

# Touch the WSGI file to trigger a reload
echo "Reloading application..."
touch /var/www/www_jsoninventoryslips_com_wsgi.py

echo "Deployment complete!"
