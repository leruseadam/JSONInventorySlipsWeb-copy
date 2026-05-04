"""WSGI: load project ``.env`` by absolute path before ``import app`` (no chdir)."""
import os
import sys
from pathlib import Path

# Add application directory to Python path
project_home = "/home/adamcordova/JSONInventorySlipsWeb-copy"
if project_home not in sys.path:
    sys.path.insert(0, project_home)


def _load_env_file(path: Path) -> int:
    """Same rules as app.load_env_file — keep POSaBit bootstrap consistent."""
    try:
        if not path.is_file():
            return 0
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return 0
    applied = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().lstrip("\ufeff")
        if not key:
            continue
        val = val.strip()
        if val and not (val[0] in ('"', "'") and len(val) >= 2):
            if "#" in val:
                val = val.split("#", 1)[0].rstrip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        os.environ[key] = val
        applied += 1
    return applied


_env_path = Path(project_home) / ".env"
_load_env_file(_env_path)

# Optional: each value is either an absolute path to a one-line secret file, or the
# secret string itself. Empty "" skips (values from .env above are kept).
PATH_POSABIT_ORDER_PAD_TOKEN = ""
PATH_POSABIT_MENU_FEED_KEY_BOTHELL = ""
PATH_POSABIT_VENUE_TOKEN = ""


def _set_from_path_or_value(env_key: str, path_or_value: str) -> None:
    raw = (path_or_value or "").strip()
    if not raw:
        return
    if os.path.isfile(raw):
        with open(raw, encoding="utf-8") as fh:
            val = fh.read().strip()
    else:
        val = raw
    if val:
        os.environ[env_key] = val


_set_from_path_or_value("POSABIT_ORDER_PAD_TOKEN", PATH_POSABIT_ORDER_PAD_TOKEN)
_set_from_path_or_value("POSABIT_MENU_FEED_KEY_BOTHELL", PATH_POSABIT_MENU_FEED_KEY_BOTHELL)
_set_from_path_or_value("POSABIT_VENUE_TOKEN", PATH_POSABIT_VENUE_TOKEN)

# Import app as application (app.py will load the same .env again from disk)
from app import app as application
