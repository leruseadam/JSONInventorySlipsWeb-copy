#!/usr/bin/env python3
"""
Production version of the Flask app with web deployment optimizations
"""

import os
import sys
from app import app

# Production configuration
app.config.update(
    DEBUG=False,
    SECRET_KEY=os.environ.get('SECRET_KEY', 'your-production-secret-key-change-this'),
    SESSION_COOKIE_SECURE=True,  # Enable for HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,
)

# Update security headers for production
@app.after_request
def add_production_security_headers(response):
    """Add production security headers"""
    # Remove any existing problematic headers
    response.headers.pop('X-Frame-Options', None)
    response.headers.pop('X-Content-Type-Options', None)
    
    # Add production security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # CORS headers for production
    response.headers['Access-Control-Allow-Origin'] = '*'  # Configure appropriately for your domain
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Cache control headers
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
