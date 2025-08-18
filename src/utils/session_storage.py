"""
Utility functions for storing large data outside of session cookies.
Uses temporary files with compression for efficient storage.
"""

import os
import json
import zlib
import base64
import tempfile
import logging
import uuid
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Constants
MAX_AGE_HOURS = 24  # Files older than this will be cleaned up
TEMP_DIR = os.path.join(tempfile.gettempdir(), "inventory_slips_data")
os.makedirs(TEMP_DIR, exist_ok=True)

def _get_temp_filepath(key: str, session_id: str) -> str:
    """Get the temporary file path for a given key and session."""
    return os.path.join(TEMP_DIR, f"{key}_{session_id}.tmp")

def store_data(key: str, data: Any, session_id: str) -> bool:
    """Store large data in a temp file."""
    try:
        filepath = _get_temp_filepath(key, session_id)
        with open(filepath, "wb") as f:
            data_str = data if isinstance(data, str) else json.dumps(data)
            compressed = zlib.compress(data_str.encode("utf-8"), level=9)
            f.write(compressed)
        return True
    except Exception as e:
        logger.error(f"Error storing data in temp file: {str(e)}")
        return False

def get_data(filepath: str) -> Optional[Any]:
    """Retrieve and decompress data from a temp file."""
    try:
        with open(os.path.join(TEMP_DIR, filepath), "rb") as f:
            compressed = f.read()
            decompressed = zlib.decompress(compressed)
            return decompressed.decode("utf-8")
    except Exception as e:
        logger.error(f"Error reading data from temp file: {str(e)}")
        return None

def cleanup_old_files() -> None:
    """Remove temporary files older than MAX_AGE_HOURS."""
    now = datetime.now()
    for fname in os.listdir(TEMP_DIR):
        fpath = os.path.join(TEMP_DIR, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if now - mtime > timedelta(hours=MAX_AGE_HOURS):
                os.remove(fpath)
        except Exception as e:
            logger.warning(f"Could not remove temp file {fpath}: {e}")

def remove_data(filepath: str) -> None:
    """Remove a specific temporary file."""
    try:
        os.remove(os.path.join(TEMP_DIR, filepath))
    except Exception as e:
        logger.warning(f"Could not remove temp file {filepath}: {e}")
