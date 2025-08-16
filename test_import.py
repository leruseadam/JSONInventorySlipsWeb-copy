import sys
import os

# Add the app directory to Python path
app_dir = '/home/adamcordova/JSONInventorySlipsWeb-copy'
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Try importing the app
try:
    import app
    print("Successfully imported app")
    print("Found app in:", os.path.abspath(app.__file__))
except ImportError as e:
    print("Failed to import app:", str(e))
    print("sys.path:", sys.path)
    print("Current directory:", os.getcwd())
