import os
import sys

# Add application directory to Python path
project_home = "/home/adamcordova/JSONInventorySlipsWeb-copy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# So the worker cwd is the repo (helps Flask and finding .env)
os.chdir(project_home)

# API tokens: put them in project_home/.env (same folder as app.py), then:
_env = os.path.join(project_home, ".env")
if os.path.isfile(_env):
    try:
        from dotenv import load_dotenv

        load_dotenv(_env, override=True)
    except ImportError:
        pass  # app.py still loads .env with its built-in parser on import

# Optional: override or add without a file (do not commit real values)
# os.environ["POSABIT_ORDER_PAD_TOKEN"] = "your-token"
# os.environ["POSABIT_MENU_FEED_KEY_BOTHELL"] = "your-feed-uuid"

# Import app as application
from app import app as application
