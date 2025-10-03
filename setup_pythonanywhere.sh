#!/bin/bash

echo "🐍 Setting up Inventory Slip Generator on PythonAnywhere..."

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Please run this script from your project directory"
    exit 1
fi

echo "📦 Creating deployment package..."

# Create a clean deployment package (excluding unnecessary files)
mkdir -p pythonanywhere_deploy
cp -r app.py wsgi.py app_production.py requirements.txt runtime.txt static templates src utils pythonanywhere_deploy/
cp pythonanywhere_wsgi.py pythonanywhere_deploy/

# Create a simple requirements file for PythonAnywhere
cat > pythonanywhere_deploy/requirements_pa.txt << EOF
Flask>=2.0.0
requests>=2.26.0
pandas>=1.3.0
python-docx>=0.8.11
docxtpl>=0.16.0
docxcompose>=1.3.3
Werkzeug>=2.0.0
configparser>=5.0.0
EOF

# Create setup instructions
cat > pythonanywhere_deploy/SETUP_INSTRUCTIONS.txt << EOF
PYTHONANYWHERE SETUP INSTRUCTIONS
==================================

1. Upload all files in this directory to PythonAnywhere
2. Create virtual environment:
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements_pa.txt

3. Configure Web App:
   - Go to Web tab
   - Add new web app (Flask)
   - Set path to: /home/yourusername/JSONInventorySlipsWeb-copy/wsgi.py

4. Copy pythonanywhere_wsgi.py content to WSGI configuration

5. Set environment variables:
   SECRET_KEY=your-secret-key-here
   FLASK_ENV=production

6. Reload web app

See PYTHONANYWHERE_SETUP.md for detailed instructions.
EOF

# Create zip file
cd pythonanywhere_deploy
zip -r ../pythonanywhere_deploy.zip . -x "*.pyc" "__pycache__/*"
cd ..

echo "✅ Deployment package created: pythonanywhere_deploy.zip"
echo ""
echo "📋 Next steps:"
echo "1. Upload pythonanywhere_deploy.zip to PythonAnywhere"
echo "2. Extract it in your home directory"
echo "3. Follow the setup instructions in SETUP_INSTRUCTIONS.txt"
echo "4. Or see PYTHONANYWHERE_SETUP.md for detailed guide"
echo ""
echo "🌐 Your PythonAnywhere URL will be:"
echo "https://yourusername.pythonanywhere.com"
