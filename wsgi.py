import os
import sys

# Add application directory to Python path
project_home = "/home/adamcordova/JSONInventorySlipsWeb-copy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Optional: paths to one-line text files (each file = one secret, no newline after value).
# Leave as "" to skip; app.py still loads .env next to app.py when present.
PATH_POSABIT_ORDER_PAD_TOKEN = ""
PATH_POSABIT_MENU_FEED_KEY_BOTHELL = ""
PATH_POSABIT_VENUE_TOKEN = ""


def _apply_token_file(env_name: str, file_path: str) -> None:
    if not file_path or not os.path.isfile(file_path):
        return
    with open(file_path, encoding="utf-8") as fh:
        val = fh.read().strip()
    if val:
        os.environ[env_name] = val


_apply_token_file("POSABIT_ORDER_PAD_TOKEN", PATH_POSABIT_ORDER_PAD_TOKEN)
_apply_token_file("POSABIT_MENU_FEED_KEY_BOTHELL", PATH_POSABIT_MENU_FEED_KEY_BOTHELL)
_apply_token_file("POSABIT_VENUE_TOKEN", PATH_POSABIT_VENUE_TOKEN)

# Import app as application
from app import app as application
