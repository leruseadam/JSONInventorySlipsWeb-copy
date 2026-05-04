"""PythonAnywhere WSGI config using explicit environment variables."""
import os
import sys

# Add application directory to Python path
project_home = "/home/adamcordova/JSONInventorySlipsWeb-copy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# POSaBit settings set directly in WSGI (no .env dependency).
# Fill in real values on the server and reload the web app.
os.environ["USE_POSABIT_PRODUCTS"] = "true"
os.environ["POSABIT_ORDER_PAD_TOKEN"] = ""
os.environ["POSABIT_MENU_FEED_KEY_BOTHELL"] = ""
os.environ["POSABIT_VENUE_TOKEN"] = ""
os.environ["POSABIT_API_BASE_URL"] = "https://app.posabit.com/api"

# Import app as application (app.py will load the same .env again from disk)
from app import app as application
