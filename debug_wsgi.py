import os
import sys

def debug_info():
    """Return debug information about the environment"""
    info = []
    info.append("Current working directory: " + os.getcwd())
    info.append("\nPython path:")
    for p in sys.path:
        info.append("  " + p)
    info.append("\nEnvironment variables:")
    for k, v in sorted(os.environ.items()):
        info.append(f"  {k}={v}")
    info.append("\nDirectory contents:")
    try:
        info.append(str(os.listdir('.')))
    except Exception as e:
        info.append(f"Error listing directory: {e}")
    return "\n".join(info)

def application(environ, start_response):
    """Basic WSGI application that shows debug info"""
    debug = debug_info()
    
    headers = [('Content-type', 'text/plain')]
    start_response('200 OK', headers)
    
    return [debug.encode('utf-8')]
