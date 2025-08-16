# Virtual Environment Setup Guide

## Quick Commands

### Activate Virtual Environment
```bash
workon myapp  # If using virtualenvwrapper
# OR
source ~/.virtualenvs/myapp/bin/activate  # Direct path activation
```

### Deactivate Virtual Environment
```bash
deactivate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Virtual Environment Location
The virtual environment is located at:
```bash
/home/adamcordova/.virtualenvs/myapp
```

### Run the App
```bash
python app.py
```

## If You Need to Recreate the Virtual Environment

### Step 1: Remove old environment
```bash
rm -rf venv
```

### Step 2: Create new environment
```bash
python3 -m venv venv
```

### Step 3: Activate environment
```bash
source venv/bin/activate
```

### Step 4: Upgrade pip
```bash
pip install --upgrade pip
```

### Step 5: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 6: Test the app
```bash
python -c "import app; print('✅ App works!')"
```

## Current Status

✅ Virtual environment is working  
✅ All dependencies are installed  
✅ App imports successfully  
✅ Flask app can be created  

## Troubleshooting

If you get import errors:
1. Make sure the virtual environment is activated (you should see `(venv)` in your terminal)
2. Run `pip install -r requirements.txt` to install missing packages
3. Check that you're in the correct directory

## Dependencies Installed

- Flask 3.0.0
- requests 2.31.0
- pandas 2.1.0
- python-docx 1.0.0
- docxtpl 0.16.7
- docxcompose 1.4.0
- Werkzeug 3.0.0
- configparser 6.0.0
- Python 3.11

## Running the App

1. Activate the virtual environment: `source venv/bin/activate`
2. Run the app: `python app.py`
3. Open your browser to the URL shown in the terminal
4. The app will automatically try different ports if the default is busy

## Chrome Compatibility

The app now includes fixes for Chrome authentication issues:
- Security headers configured
- Session cookies set to 'Lax' SameSite policy
- CORS headers for localhost
- Chrome-specific browser flags
- Session debugging tools

## PythonAnywhere Configuration

### Static Files
Configure the following static file mappings in PythonAnywhere:

```
URL: /static/
Directory: /home/leruseadam/JSONInventorySlipsWeb-copy/static

URL: /css/
Directory: /home/leruseadam/JSONInventorySlipsWeb-copy/static/css

URL: /js/
Directory: /home/leruseadam/JSONInventorySlipsWeb-copy/static/js

URL: /images/
Directory: /home/leruseadam/JSONInventorySlipsWeb-copy/static/images
```

### WSGI Configuration
Make sure your WSGI file points to:
```
/home/leruseadam/JSONInventorySlipsWeb-copy/wsgi.py
```

### Virtual Environment
Path to virtualenv:
```
/home/leruseadam/.virtualenvs/myapp
``` 