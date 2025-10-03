# Web Deployment Guide

## Quick Deploy Options

### Option 1: Heroku (Recommended for beginners)

1. **Install Heroku CLI**
   ```bash
   # macOS
   brew install heroku/brew/heroku
   
   # Or download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Create Heroku App**
   ```bash
   heroku create your-app-name
   ```

3. **Set Environment Variables**
   ```bash
   heroku config:set SECRET_KEY=your-super-secret-key-here
   ```

4. **Deploy**
   ```bash
   git add .
   git commit -m "Deploy to production"
   git push heroku main
   ```

### Option 2: Railway

1. **Connect GitHub Repository**
   - Go to [railway.app](https://railway.app)
   - Connect your GitHub account
   - Select this repository

2. **Configure Environment**
   - Set `SECRET_KEY` environment variable
   - Railway will auto-detect Python and install dependencies

3. **Deploy**
   - Railway will automatically deploy on every push to main branch

### Option 3: Render

1. **Create Web Service**
   - Go to [render.com](https://render.com)
   - Create new Web Service
   - Connect GitHub repository

2. **Configure**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn wsgi:app`
   - Environment: Python 3

3. **Set Environment Variables**
   - `SECRET_KEY`: Your secret key

### Option 4: PythonAnywhere

1. **Upload Files**
   - Upload all files to your PythonAnywhere account
   - Place in `/home/yourusername/mysite/`

2. **Create Web App**
   - Go to Web tab
   - Create new web app
   - Choose Flask
   - Point to your `wsgi.py` file

3. **Configure WSGI**
   ```python
   import sys
   path = '/home/yourusername/mysite'
   if path not in sys.path:
       sys.path.append(path)
   
   from wsgi import app as application
   ```

## Production Checklist

- [ ] Change `SECRET_KEY` to a secure random string
- [ ] Set `DEBUG=False`
- [ ] Configure proper CORS origins
- [ ] Set up HTTPS (most platforms do this automatically)
- [ ] Test all functionality
- [ ] Set up monitoring/logging

## Environment Variables

Set these in your deployment platform:

```
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=production
PORT=5000
```

## Testing Your Deployment

1. **Test Basic Functionality**
   - Visit your deployed URL
   - Test data import (CSV/JSON)
   - Test document generation

2. **Test Chrome Compatibility**
   - Use the built-in compatibility test
   - Test in incognito mode
   - Test with different browsers

## Troubleshooting

### Common Issues

1. **"Unexpected token '<', "<html>"... is not valid JSON"**
   - This usually means the server returned HTML instead of JSON
   - Check your API endpoints are working
   - Verify CORS settings

2. **Session Issues**
   - Make sure `SECRET_KEY` is set
   - Check session cookie settings
   - Verify HTTPS is enabled

3. **File Upload Issues**
   - Check file size limits
   - Verify upload directory permissions
   - Test with smaller files first

### Debug Mode

To enable debug mode temporarily:
```python
app.config['DEBUG'] = True
```

## Security Considerations

- Never commit secrets to git
- Use environment variables for sensitive data
- Enable HTTPS in production
- Regularly update dependencies
- Monitor for security vulnerabilities

## Performance Optimization

- Use a production WSGI server (Gunicorn)
- Enable gzip compression
- Optimize static file serving
- Consider using a CDN for static assets
