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
    # Create a unique filename based on session ID and key
    filename = f"{session_id}_{key}_{uuid.uuid4().hex[:8]}.tmp"
    return os.path.join(TEMP_DIR, filename)

def store_data(key: str, data: Any, session_id: str) -> bool:
    """
    Store data in a temporary file with compression.
    Returns True if successful, False otherwise.
    """
    try:
        # Convert data to JSON string
        if not isinstance(data, str):
            data = json.dumps(data)
            
        # Compress the data
        compressed = zlib.compress(data.encode('utf-8'), level=9)
        
        # Get temporary file path
        filepath = _get_temp_filepath(key, session_id)
        
        # Write compressed data to file
        with open(filepath, 'wb') as f:
            f.write(compressed)
            
        # Store only the reference in session
        return filepath
        
    except Exception as e:
        logger.error(f"Error storing data: {str(e)}")
        return None

def get_data(filepath: str) -> Optional[Any]:
    """
    Retrieve and decompress data from temporary file.
    Returns None if file doesn't exist or on error.
    """
    try:
        if not os.path.exists(filepath):
            return None
            
        # Read and decompress data
        with open(filepath, 'rb') as f:
            compressed = f.read()
        
        decompressed = zlib.decompress(compressed)
        data = decompressed.decode('utf-8')
        
        # Parse JSON if possible
        try:
            return json.loads(data)
        except:
            return data
            
    except Exception as e:
        logger.error(f"Error retrieving data: {str(e)}")
        return None

def cleanup_old_files() -> None:
    """Remove temporary files older than MAX_AGE_HOURS."""
    try:
        current_time = datetime.now()
        for filename in os.listdir(TEMP_DIR):
            filepath = os.path.join(TEMP_DIR, filename)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if current_time - file_modified > timedelta(hours=MAX_AGE_HOURS):
                try:
                    os.remove(filepath)
                    logger.info(f"Removed old temporary file: {filename}")
                except:
                    pass
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def remove_data(filepath: str) -> None:
    """Remove a specific temporary file."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.error(f"Error removing file {filepath}: {str(e)}")
