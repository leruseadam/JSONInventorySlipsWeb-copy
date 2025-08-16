#!/bin/bash

# Print commands and their arguments as they are executed
set -x

echo "Starting server check..."

# Check for app.py in home directory
echo "Checking for app.py in home directory..."
ls -la ~/app.py*

# Check project directory
echo "Checking project directory..."
ls -la ~/JSONInventorySlipsWeb-copy

# Check virtualenv
echo "Checking virtualenv packages..."
source ~/.virtualenvs/myapp/bin/activate
pip freeze | grep -i docx

# Check WSGI file
echo "Checking WSGI configuration..."
cat /var/www/www_jsoninventoryslips_com_wsgi.py

# Check Python path
echo "Checking Python path..."
python3 -c "import sys; print('\n'.join(sys.path))"

echo "Server check complete!"
