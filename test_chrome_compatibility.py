#!/usr/bin/env python3
"""
Test script to verify Chrome compatibility fixes
"""

import requests
import json
import sys

def test_chrome_compatibility():
    """Test the Chrome compatibility fixes"""
    
    # Test the app endpoints
    base_url = "http://localhost:8000"  # Default port
    
    print("Testing Chrome compatibility fixes...")
    
    # Test 1: Basic connectivity
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Basic connectivity: OK")
        else:
            print(f"❌ Basic connectivity: Failed (Status: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Basic connectivity: Failed ({e})")
        return False
    
    # Test 2: Security headers
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        headers = response.headers
        
        required_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options', 
            'X-XSS-Protection',
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers',
            'Access-Control-Allow-Credentials'
        ]
        
        missing_headers = []
        for header in required_headers:
            if header not in headers:
                missing_headers.append(header)
        
        if not missing_headers:
            print("✅ Security headers: OK")
        else:
            print(f"❌ Security headers: Missing {missing_headers}")
            return False
            
    except Exception as e:
        print(f"❌ Security headers test failed: {e}")
        return False
    
    # Test 3: Session debugging endpoint
    try:
        response = requests.get(f"{base_url}/debug-session", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Session debugging: OK")
            else:
                print(f"❌ Session debugging: Failed ({data.get('error', 'Unknown error')})")
                return False
        else:
            print(f"❌ Session debugging: Failed (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Session debugging test failed: {e}")
        return False
    
    # Test 4: CORS preflight
    try:
        response = requests.options(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ CORS preflight: OK")
        else:
            print(f"❌ CORS preflight: Failed (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ CORS preflight test failed: {e}")
        return False
    
    print("\n🎉 All Chrome compatibility tests passed!")
    return True

def main():
    """Main test function"""
    print("Chrome Compatibility Test Suite")
    print("=" * 40)
    
    success = test_chrome_compatibility()
    
    if success:
        print("\n✅ All tests passed! The app should work better with Chrome authentication.")
        print("\nTroubleshooting tips for Chrome users:")
        print("1. Try incognito mode (Ctrl+Shift+N or Cmd+Shift+N)")
        print("2. Clear browser cache and cookies for localhost")
        print("3. Disable Chrome extensions temporarily")
        print("4. Use the 'Test Chrome Compatibility' button on the home page")
    else:
        print("\n❌ Some tests failed. Check the app configuration.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 