# PythonAnywhere Deployment Guide

## Step-by-Step Setup

### 1. Create PythonAnywhere Account
1. Go to [pythonanywhere.com](https://pythonanywhere.com)
2. Sign up for a free account (or paid if you need more resources)
3. Verify your email address

### 2. Upload Your Files

#### Option A: Using Git (Recommended)
1. **In PythonAnywhere Console:**
   ```bash
   cd ~
   git clone https://github.com/leruseadam/JSONInventorySlipsWeb-copy.git
   cd JSONInventorySlipsWeb-copy
   ```

#### Option B: Manual Upload
1. **Zip your local files:**
   ```bash
   # In your local directory
   zip -r inventory-app.zip . -x "venv/*" "__pycache__/*" "*.pyc" ".git/*"
   ```
2. **Upload via PythonAnywhere Files tab:**
   - Go to Files tab
   - Navigate to `/home/yourusername/`
   - Upload `inventory-app.zip`
   - Extract it

### 3. Set Up Virtual Environment

1. **Open Bash Console in PythonAnywhere**
2. **Navigate to your project:**
   ```bash
   cd ~/JSONInventorySlipsWeb-copy
   ```

3. **Create virtual environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### 4. Configure Web App

1. **Go to Web tab in PythonAnywhere**
2. **Click "Add a new web app"**
3. **Choose "Flask"**
4. **Select Python version 3.11**
5. **Set the path to:** `/home/yourusername/JSONInventorySlipsWeb-copy/wsgi.py`

### 5. Configure WSGI File

1. **Go to Web tab → WSGI configuration file**
2. **Replace the content with:**
   ```python
   import sys
   import os

   # Add your project directory to the Python path
   path = '/home/yourusername/JSONInventorySlipsWeb-copy'
   if path not in sys.path:
       sys.path.append(path)

   # Import your Flask app
   from wsgi import app as application

   # Optional: Set environment variables
   os.environ['FLASK_ENV'] = 'production'
   ```

### 6. Set Up Static Files

1. **Go to Web tab → Static files**
2. **Add static file mapping:**
   - URL: `/static/`
   - Directory: `/home/yourusername/JSONInventorySlipsWeb-copy/static/`

### 7. Configure Environment Variables

1. **Go to Web tab → Environment variables**
2. **Add these variables:**
   ```
   SECRET_KEY=your-super-secret-key-here-change-this
   FLASK_ENV=production
   ```

### 8. Reload Web App

1. **Go to Web tab**
2. **Click "Reload" button**

## Testing Your Deployment

### 1. Test Basic Functionality
- Visit your PythonAnywhere URL: `https://yourusername.pythonanywhere.com`
- Test the home page loads
- Try importing sample data

### 2. Test Data Import
- Use the Cultivera URL: `https://files.cultivera.com/435553542D5753313835/Interop/25/38/YXRKSKT91ZMERB10/Cultivera_ORD-27654_422044.json`
- Test CSV upload
- Test JSON paste functionality

### 3. Test Document Generation
- Select some products
- Generate inventory slips
- Download the Word document

## Troubleshooting

### Common Issues

1. **Import Errors:**
   ```bash
   # Check if virtual environment is activated
   source venv/bin/activate
   pip list
   ```

2. **Static Files Not Loading:**
   - Check static file mapping in Web tab
   - Ensure `/static/` URL maps to correct directory

3. **Permission Errors:**
   ```bash
   # Fix file permissions
   chmod 755 ~/JSONInventorySlipsWeb-copy
   chmod 644 ~/JSONInventorySlipsWeb-copy/*.py
   ```

4. **Memory Issues:**
   - Free accounts have limited memory
   - Consider upgrading if you get memory errors

### Debug Mode

To enable debug mode temporarily:
1. **Edit your WSGI file:**
   ```python
   import sys
   import os

   path = '/home/yourusername/JSONInventorySlipsWeb-copy'
   if path not in sys.path:
       sys.path.append(path)

   from wsgi import app as application
   application.config['DEBUG'] = True
   ```

2. **Reload the web app**

## File Structure on PythonAnywhere

```
/home/yourusername/
├── JSONInventorySlipsWeb-copy/
│   ├── app.py
│   ├── wsgi.py
│   ├── app_production.py
│   ├── requirements.txt
│   ├── static/
│   ├── templates/
│   └── venv/
```

## Security Notes

1. **Change the SECRET_KEY** in environment variables
2. **Don't commit secrets** to git
3. **Use HTTPS** (PythonAnywhere provides this automatically)
4. **Regularly update dependencies**

## Performance Tips

1. **Use the production app:**
   ```python
   from app_production import app as application
   ```

2. **Enable gzip compression** in Web tab settings

3. **Monitor resource usage** in the Web tab

## Support

- PythonAnywhere documentation: https://help.pythonanywhere.com/
- PythonAnywhere forums: https://www.pythonanywhere.com/forums/
