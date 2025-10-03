# URL Error Fixes - "Unexpected token '<', "<html>"... is not valid JSON"

## Problem Description

The error "Unexpected token '<', "<html>"... is not valid JSON" occurs when your Flask app tries to load data from a URL (like the Cultivera URL you provided) but receives HTML content instead of JSON.

### Root Causes:

1. **DNS Resolution Failure**: The domain `files.cultivera.com` cannot be resolved
2. **Server Unavailable**: The server is down or the URL is incorrect
3. **Authentication Required**: The URL requires authentication headers
4. **Rate Limiting**: The server is blocking requests
5. **Redirect to Error Page**: The server redirects to an HTML error page

## The Cultivera URL Issue

The specific URL you provided:
```
https://files.cultivera.com/435553542D5753313835/Interop/25/38/YXRKSKT91ZMERB10/Cultivera_ORD-27654_422044.json
```

**Status**: Currently inaccessible due to DNS resolution failure.

**Expected Content**: Based on your web search results, this should return a Cultivera transfer schema JSON with:
- `document_name`: "WCIA Transfer Schema"
- `document_schema_version`: "2.1.0"
- `inventory_transfer_items`: Array of product data
- Transfer details (vendor, dates, etc.)

## Implemented Fixes

### 1. Enhanced Error Handling

**File**: `app.py` (lines 1508-1511)
```python
except requests.exceptions.ConnectionError as e:
    error_msg = f"Connection failed: Unable to connect to {url}. The server may be down or the URL may be incorrect. Please verify the URL and try again."
    logger.error(f"Connection error for URL {url}: {str(e)}")
    raise ValueError(error_msg)
```

### 2. HTML Content Detection

**File**: `app.py` (lines 1468-1470)
```python
# Check if response is HTML (error page)
if raw_text.strip().startswith('<') or 'text/html' in content_type:
    raise ValueError(f"The URL returned HTML content instead of JSON. This usually means the URL is incorrect, the server is down, or you need authentication. URL: {url}")
```

### 3. URL Testing Endpoint

**File**: `app.py` (lines 2251-2310)
- New `/test-url` endpoint to test URL accessibility
- Checks content type, status codes, and response format
- Provides detailed error information

### 4. Frontend URL Testing Tool

**File**: `templates/index.html` (lines 60-89, 275-321)
- Added URL testing interface on the home page
- Users can test URLs before attempting to load data
- Shows detailed results including content type and preview

## How to Use the Fixes

### 1. Test URLs Before Loading

1. Go to the home page of your app
2. Scroll down to the "URL Testing" section
3. Enter the problematic URL
4. Click "Test URL"
5. Review the results to understand the issue

### 2. Common Error Messages and Solutions

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "Connection failed: Cannot reach URL" | DNS resolution failure or server down | Check URL spelling, try later, or contact URL provider |
| "URL returns HTML content instead of JSON" | Server returned error page | URL may be incorrect, expired, or require authentication |
| "Request timed out" | Server is slow or overloaded | Try again later or check server status |
| "HTTP error 404" | URL doesn't exist | Verify the URL is correct and still valid |
| "HTTP error 401/403" | Authentication required | Add proper API keys or authentication headers |

### 3. For the Specific Cultivera URL

Since the URL is currently inaccessible, you have these options:

1. **Use the JSON data directly**: Copy the JSON content from your web search results and paste it into the "Paste JSON Data" field
2. **Contact Cultivera**: Ask them about the correct URL format or if there are authentication requirements
3. **Check for URL updates**: The URL might have changed or expired

## Testing the Fixes

### 1. Test with Working URLs

Try these test URLs to verify the fixes work:

```bash
# Test with a working JSON API
curl "https://jsonplaceholder.typicode.com/posts/1"

# Test with a CSV file
curl "https://raw.githubusercontent.com/datasets/csv-sample/master/data/sample.csv"
```

### 2. Test Error Handling

Try these URLs to test error handling:

```bash
# Non-existent domain
https://nonexistent-domain-12345.com/data.json

# Non-existent path
https://httpbin.org/nonexistent.json

# HTML page (not JSON)
https://httpbin.org/html
```

## Future Improvements

### 1. Authentication Support

Add support for API keys and authentication headers:

```python
# In load_from_url function
if 'api_key' in request.form:
    headers['Authorization'] = f'Bearer {request.form["api_key"]}'
```

### 2. Retry Logic

Add automatic retry for transient failures:

```python
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

### 3. Caching

Add caching for frequently accessed URLs:

```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@cache.memoize(timeout=300)  # 5 minutes
def load_from_url_cached(url):
    return load_from_url(url)
```

## Troubleshooting Guide

### For Users:

1. **Always test URLs first** using the new URL testing tool
2. **Check the error message** - it now provides specific guidance
3. **Try alternative methods**:
   - Copy/paste JSON data directly
   - Use CSV upload if available
   - Contact the data provider for updated URLs

### For Developers:

1. **Monitor logs** for connection errors and DNS failures
2. **Implement fallback mechanisms** for critical data sources
3. **Add user-friendly error messages** that guide users to solutions
4. **Consider implementing retry logic** for transient failures

## Summary

The fixes address the core issue where URLs return HTML error pages instead of JSON data. The enhanced error handling now:

- ✅ Detects HTML content and provides clear error messages
- ✅ Distinguishes between different types of connection failures
- ✅ Provides a URL testing tool for users
- ✅ Gives specific guidance on how to resolve each type of error

The app will now handle URL loading errors gracefully and provide users with actionable information to resolve issues.
