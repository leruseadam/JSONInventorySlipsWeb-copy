"""
Flask Inventory Slip Generator - Web application for generating inventory slips
from CSV and JSON data with support for Bamboo and Cultivera formats.
"""

# Standard library imports
import os
import sys
import json
import socket
import ssl
import base64
import hmac
import hashlib
import logging
import threading
import tempfile
import urllib.request
import urllib.error
import uuid
import re
import webbrowser
import time
from functools import wraps
from io import BytesIO
import zlib
from pathlib import Path
from datetime import datetime

# Third-party imports
from flask import (
    Flask, 
    render_template, 
    request, 
    redirect, 
    url_for, 
    flash, 
    jsonify, 
    session, 
    send_file, 
    send_from_directory
)
import requests
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.shared import Pt, Inches
import configparser
from werkzeug.utils import secure_filename

# For document generation
from src.utils.docgen import DocxGenerator

# Local imports
from src.utils.document_handler import DocumentHandler
from src.ui.app import InventorySlipGenerator


# Update the compression constants
MAX_CHUNK_SIZE = 500  # Reduced from 800 to be safer
MAX_TOTAL_SIZE = 3000  # Maximum total size after compression
COMPRESSION_LEVEL = 9  # Maximum compression

def compress_session_data(data, max_size=MAX_TOTAL_SIZE):
    """Compress data with improved compression, size checks, and memory efficiency"""
    try:
        # Start with basic validation
        if data is None:
            raise ValueError("Cannot compress None data")
            
        # Convert DataFrame efficiently
        if isinstance(data, pd.DataFrame):
            # Only keep essential columns and limit precision for floats
            essential_cols = ['Product Name*', 'Product Type*', 'Quantity Received*', 
                            'Barcode*', 'Accepted Date', 'Vendor', 'Strain Name']
            data = data[data.columns.intersection(essential_cols)]
            
            # Convert to JSON with minimal settings
            data = data.to_json(orient='records', 
                              date_format='iso',
                              double_precision=2,
                              default_handler=str)
        elif not isinstance(data, str):
            # For dictionaries and other objects, use minimal JSON encoding
            data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)

        # Initial compression
        compressed = zlib.compress(data.encode('utf-8'), level=COMPRESSION_LEVEL)
        
        # If too large, apply progressive reduction
        if len(compressed) > max_size:
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    # Keep essential data, limit records and field lengths
                    reduced = []
                    for item in parsed[:50]:  # Increased from 25 to 50
                        reduced_item = {}
                        for k, v in item.items():
                            # Only keep non-empty values
                            if v and str(v).strip():
                                # Truncate based on field type
                                if k in ['Product Name*', 'Vendor']:
                                    reduced_item[k] = str(v)[:100]
                                elif k in ['Barcode*', 'Strain Name']:
                                    reduced_item[k] = str(v)[:50]
                                else:
                                    reduced_item[k] = str(v)[:30]
                        reduced.append(reduced_item)
                    data = json.dumps(reduced, separators=(',', ':'), ensure_ascii=False)
                else:
                    # For single objects, limit field lengths
                    reduced = {k: str(v)[:50] for k, v in parsed.items()}
                    data = json.dumps(reduced, separators=(',', ':'), ensure_ascii=False)
                    
                # Try compression again
                compressed = zlib.compress(data.encode('utf-8'), level=COMPRESSION_LEVEL)
                
                # If still too large, apply more aggressive reduction
                if len(compressed) > max_size:
                    logger.warning("Data still too large after reduction, applying aggressive truncation")
                    if isinstance(parsed, list):
                        reduced = reduced[:25]  # Further reduce to 25 records
                        data = json.dumps(reduced, separators=(',', ':'), ensure_ascii=False)
                        compressed = zlib.compress(data.encode('utf-8'), level=COMPRESSION_LEVEL)
                        
            except json.JSONDecodeError:
                # If JSON parsing fails, truncate string with warning
                logger.warning("JSON parsing failed during compression, truncating data")
                data = data[:1000] + "...[truncated]"
                compressed = zlib.compress(data.encode('utf-8'), level=COMPRESSION_LEVEL)

        encoded = base64.b64encode(compressed).decode('utf-8')
        logger.info(f"Compressed data size: {len(encoded)} bytes")
        return encoded
        
    except Exception as e:
        logger.error(f"Compression error: {str(e)}")
        raise

def store_chunked_data(key, data):
    """Store data with improved chunking and size validation"""
    try:
        # Compress data first
        compressed = compress_session_data(data)
        
        # Clear existing chunks
        clear_chunked_data(key)
        
        # Split into smaller chunks
        chunks = [compressed[i:i + MAX_CHUNK_SIZE] for i in range(0, len(compressed), MAX_CHUNK_SIZE)]
        
        if len(chunks) > 20:  # Limit number of chunks
            raise ValueError(f"Data too large: {len(chunks)} chunks needed")
        
        # Store chunks with size validation
        session[f'{key}_chunks'] = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk_key = f'{key}_chunk_{i}'
            if len(chunk) > MAX_CHUNK_SIZE:
                raise ValueError(f"Chunk {i} exceeds maximum size")
            session[chunk_key] = chunk
            
        logger.info(f"Stored {len(chunks)} chunks for {key} (total size: {len(compressed)})")
        return True
        
    except Exception as e:
        logger.error(f"Error storing chunked data: {str(e)}")
        clear_chunked_data(key)  # Clean up on error
        return False

def get_chunked_data(key):
    """Retrieve chunked data with improved error handling"""
    try:
        num_chunks = session.get(f'{key}_chunks')
        if num_chunks is None:
            return None
            
        # Validate chunk count
        if num_chunks > 20:  # Safety check
            logger.error(f"Too many chunks for {key}: {num_chunks}")
            return None
            
        # Reconstruct data
        chunks = []
        for i in range(num_chunks):
            chunk = session.get(f'{key}_chunk_{i}')
            if chunk is None or len(chunk) > MAX_CHUNK_SIZE:
                logger.error(f"Invalid chunk {i} for {key}")
                return None
            chunks.append(chunk)
            
        # Combine and decompress
        encoded_data = ''.join(chunks)
        try:
            compressed = base64.b64decode(encoded_data)
            decompressed = zlib.decompress(compressed)
            return decompressed.decode('utf-8')
        except Exception as e:
            logger.error(f"Decompression error: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving chunked data: {str(e)}")
        return None

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CONFIG_FILE = os.path.expanduser("~/inventory_generator_config.ini")

def get_downloads_dir():
    """Get the default Downloads directory for both Windows and Mac"""
    try:
        if sys.platform == "win32":
            # First try Windows known folder path
            import winreg
            from ctypes import windll, wintypes
            CSIDL_PERSONAL = 5  # Documents
            SHGFP_TYPE_CURRENT = 0  # Get current path
            buf = wintypes.create_unicode_buffer(wintypes.MAX_PATH)
            windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
            documents = buf.value
            
            # Try registry next
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                    downloads = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
                return downloads
            except:
                # Fall back to Documents\Downloads
                return os.path.join(documents, "Downloads")
        else:
            # macOS and Linux
            return os.path.join(os.path.expanduser("~"), "Downloads")
    except:
        # Ultimate fallback - user's home directory
        return os.path.expanduser("~")

# Update the constants
DEFAULT_SAVE_DIR = get_downloads_dir()
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "inventory_generator", "uploads")

# Ensure directories exist with proper permissions
try:
    os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception as e:
    logger.error(f"Error creating directories: {str(e)}")
    # Fall back to temp directory if needed
    if not os.path.exists(DEFAULT_SAVE_DIR):
        DEFAULT_SAVE_DIR = tempfile.gettempdir()

APP_VERSION = "2.0.0"
ALLOWED_EXTENSIONS = {'csv', 'json', 'docx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size

# Add new constants for API configuration
API_CONFIGS = {
    'bamboo': {
        'base_url': 'https://api-trace.getbamboo.com/shared/manifests',
        'version': 'v1',
        'auth_type': 'bearer'
    },
    'cultivera': {
        'base_url': 'https://api.cultivera.com/api',
        'version': 'v1',
        'auth_type': 'basic'
    },
    'growflow': {
        'base_url': 'https://api.growflow.com',
        'version': 'v2',
        'auth_type': 'oauth2'
    }
}

# Initialize Flask application
app = Flask(__name__,
    static_url_path='',
    static_folder='static',
    template_folder='templates'
)
# Use a fixed secret key for development to preserve session data
app.secret_key = 'your-fixed-development-secret-key'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Add security headers and session configuration for Chrome compatibility
@app.after_request
def add_security_headers(response):
    """Add security headers to make the app work better with Chrome"""
    # Remove any existing problematic headers
    response.headers.pop('X-Frame-Options', None)
    response.headers.pop('X-Content-Type-Options', None)
    
    # Add Chrome-compatible headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Add CORS headers for local development
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Add cache control headers
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

# Import session storage utilities
import uuid
from flask_session import Session
from src.utils.session_storage import store_data, get_data, cleanup_old_files, remove_data

# Configure session for Chrome compatibility and uWSGI
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True only if using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # More permissive than 'Strict' for Chrome
    SESSION_COOKIE_PATH='/',
    PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
    SESSION_REFRESH_EACH_REQUEST=True,
    SESSION_TYPE='filesystem',  # Use filesystem instead of signed cookies
    SESSION_FILE_DIR=os.path.join(tempfile.gettempdir(), 'flask_session'),
    SESSION_FILE_THRESHOLD=500  # Maximum number of session files
)

# Ensure session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize Flask-Session
Session(app)

# Clean up old temporary files on startup
cleanup_old_files()

# Initialize session ID if needed
@app.before_request
def init_session():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

# Helper function to get resource path (for templates)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Load configurations or create default
def load_config():
    config = configparser.ConfigParser()
    
    # Default configurations
    config['PATHS'] = {
        'template_path': os.path.join(os.path.dirname(__file__), "templates/documents/InventorySlips.docx"),
        'output_dir': DEFAULT_SAVE_DIR,  # Use the new DEFAULT_SAVE_DIR
        'recent_files': '',
        'recent_urls': ''
    }
    
    config['SETTINGS'] = {
        'items_per_page': '4',
        'auto_open': 'true',
        'theme': 'dark',
        'font_size': '12'
    }
    
    # Load existing config if it exists
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # Create config file with defaults
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

# Helper to adjust font sizes after rendering
def adjust_table_font_sizes(doc_path):
    """
    Post-process a DOCX file to dynamically adjust font size inside table cells based on thresholds.
    """
    thresholds = [
        (30, 12),   # <=30 chars → 12pt
        (45, 10),   # <=45 chars → 10pt
        (60, 8),    # <=60 chars → 8pt
        (float('inf'), 7)  # >60 chars → 7pt
    ]

    def get_font_size(text_len):
        for limit, size in thresholds:
            if text_len <= limit:
                return size
        return 7  # Fallback

    try:
        doc = Document(doc_path)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        text = paragraph.text.strip()
                        if not text:
                            continue

                        # If line is Product Name (first line), force 10pt
                        if paragraph == cell.paragraphs[0]:
                            font_size = 10
                        else:
                            font_size = get_font_size(len(text))

                        for run in paragraph.runs:
                            try:
                                run.font.size = Pt(font_size)
                            except Exception as e:
                                logger.warning(f"Could not set font size for run: {e}")
                                continue

        # Save to a temporary file first
        temp_path = doc_path + ".font_adjust.tmp"
        doc.save(temp_path)
        
        # Validate the document after font adjustments
        if validate_docx(temp_path):
            import shutil
            shutil.move(temp_path, doc_path)
        else:
            logger.warning("Document validation failed after font adjustment, keeping original")
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error adjusting font sizes: {str(e)}")
        # If font adjustment fails, the document should still be usable
        if os.path.exists(temp_path):
            os.remove(temp_path)

# Open files after saving
def open_file(path):
    """Open files using the default system application"""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":  # macOS
            os.system(f'open "{path}"')
        else:  # linux variants
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        logger.error(f"Error opening file: {e}")
        flash(f"Error opening file: {e}", "error")

# Split records into chunks
def chunk_records(records, chunk_size=4):
    for i in range(0, len(records), chunk_size):
        yield records[i:i + chunk_size]

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Process and save inventory slips
def run_full_process_inventory_slips(selected_df, config, status_callback=None, progress_callback=None):
    if selected_df.empty:
        if status_callback:
            status_callback("Error: No data selected.")
        return False, "No data selected."

def run_full_process_inventory_slips(selected_df, config, status_callback=None, progress_callback=None):
    """Generate inventory slips using template-based DocumentHandler"""
    try:
        from src.utils.document_handler import DocumentHandler

        if selected_df.empty:
            if status_callback:
                status_callback("Error: No data selected.")
            return False, "No data selected."

        # Get vendor name from first row
        vendor_name = selected_df['Vendor'].iloc[0] if not selected_df.empty else "Unknown"
        
        # Get today's date
        today_date = datetime.now().strftime("%Y%m%d")
        
        # Clean vendor name (remove special characters and spaces)
        vendor_name = "".join(c for c in vendor_name if c.isalnum() or c.isspace()).strip()
        
        # Create filename
        outname = f"{today_date}_{vendor_name}_Slips.docx"
        outpath = os.path.join(config['PATHS']['output_dir'], outname)
        
        if status_callback:
            status_callback("Processing data...")

        # Initialize document handler
        doc_handler = DocumentHandler()
        
        # Load template
        template_path = os.path.join(os.path.dirname(__file__), "templates/documents/InventorySlips.docx")
        if not os.path.exists(template_path):
            return False, f"Template not found at {template_path}"
            
        doc_handler.create_document(template_path)

        # Process records in chunks of 4 (for template layout)
        records = []
        for chunk_start in range(0, len(selected_df), 4):
            chunk = selected_df.iloc[chunk_start:chunk_start+4]
            for _, row in chunk.iterrows():
                # Get vendor info, using full vendor name if available
                vendor_name = row.get("Vendor", "")
                if " - " in vendor_name:
                    vendor_name = vendor_name.split(" - ")[1]
                
                record = {
                    "Product Name*": str(row.get("Product Name*", ""))[:100],
                    "Barcode*": str(row.get("Barcode*", ""))[:50],
                    "Accepted Date": str(row.get("Accepted Date", ""))[:20],
                    "Quantity Received*": str(row.get("Quantity Received*", ""))[:20],
                    "Vendor": str(vendor_name or "Unknown Vendor")[:50],
                    "Product Type*": str(row.get("Product Type*", ""))[:50]
                }
                records.append(record)

        if status_callback:
            status_callback("Generating document...")

        # Add content to document
        if not doc_handler.add_content_to_table(records):
            return False, "Failed to add content to document"

        if status_callback:
            status_callback("Saving document...")

        # Save document
        if doc_handler.save_document(outpath):
            if os.path.exists(outpath):
                # Adjust font sizes
                if status_callback:
                    status_callback("Adjusting formatting...")
                adjust_table_font_sizes(outpath)

                if progress_callback:
                    progress_callback(100)

                return True, outpath

        return False, "Failed to create document"

    except Exception as e:
        if status_callback:
            status_callback(f"Error: {str(e)}")
        logger.error(f"Error in run_full_process_inventory_slips: {str(e)}")
        return False, str(e)

# Parse Bamboo transfer schema JSON
def parse_bamboo_data(json_data):
    if not json_data:
        return pd.DataFrame()
    
    try:
        # Get vendor information
        from_license_number = json_data.get("from_license_number", "")
        from_license_name = json_data.get("from_license_name", "")
        vendor_meta = f"{from_license_number} - {from_license_name}"
        
        # Get transfer date
        raw_date = json_data.get("est_arrival_at", "") or json_data.get("transferred_at", "")
        accepted_date = raw_date.split("T")[0] if "T" in raw_date else raw_date
        
        # Process inventory items
        items = json_data.get("inventory_transfer_items", [])
        logger.info(f"Bamboo data: found {len(items)} inventory_transfer_items")
        records = []
        
        for item in items:
            # Extract THC and CBD content from lab_result_data if available
            thc_content = ""
            cbd_content = ""
            
            lab_data = item.get("lab_result_data", {})
            if lab_data and "potency" in lab_data:
                for potency_item in lab_data["potency"]:
                    if potency_item.get("type") == "total-thc":
                        thc_content = f"{potency_item.get('value', '')}%"
                    elif potency_item.get("type") == "total-cbd":
                        cbd_content = f"{potency_item.get('value', '')}%"
            
            records.append({
                "Product Name*": item.get("product_name", ""),
                "Product Type*": item.get("inventory_type", ""),
                "Quantity Received*": item.get("qty", ""),
                "Barcode*": item.get("inventory_id", "") or item.get("external_id", ""),
                "Accepted Date": accepted_date,
                "Vendor": vendor_meta,
                "Strain Name": item.get("strain_name", ""),
                "THC Content": thc_content,
                "CBD Content": cbd_content,
                "Source System": "Bamboo"
            })
        
        return pd.DataFrame(records)
    
    except Exception as e:
        raise ValueError(f"Failed to parse Bamboo transfer data: {e}")

# Parse Cultivera JSON
def parse_cultivera_data(json_data):
    if not json_data:
        return pd.DataFrame()
    
    try:
        # Check if Cultivera format
        if not json_data.get("data") or not isinstance(json_data.get("data"), dict):
            raise ValueError("Not a valid Cultivera format")
        
        data = json_data.get("data", {})
        manifest = data.get("manifest", {})
        
        # Get vendor information
        from_license = manifest.get("from_license", {})
        vendor_name = from_license.get("name", "")
        vendor_license = from_license.get("license_number", "")
        vendor_meta = f"{vendor_license} - {vendor_name}" if vendor_license and vendor_name else "Unknown Vendor"
        
        # Get transfer date
        created_at = manifest.get("created_at", "")
        accepted_date = created_at.split("T")[0] if "T" in created_at else created_at
        
        # Process inventory items
        items = manifest.get("items", [])
        records = []
        
        for item in items:
            # Extract product info
            product = item.get("product", {})
            
            # Extract THC and CBD content
            thc_content = ""
            cbd_content = ""
            
            test_results = item.get("test_results", [])
            if test_results:
                for result in test_results:
                    if "thc" in result.get("type", "").lower():
                        thc_content = f"{result.get('percentage', '')}%"
                    elif "cbd" in result.get("type", "").lower():
                        cbd_content = f"{result.get('percentage', '')}%"
            
            records.append({
                "Product Name*": product.get("name", ""),
                "Product Type*": product.get("category", ""),
                "Quantity Received*": item.get("quantity", ""),
                "Barcode*": item.get("barcode", "") or item.get("id", ""),
                "Accepted Date": accepted_date,
                "Vendor": vendor_meta,
                "Strain Name": product.get("strain_name", ""),
                "THC Content": thc_content,
                "CBD Content": cbd_content,
                "Source System": "Cultivera"
            })
        
        return pd.DataFrame(records)
    
    except Exception as e:
        raise ValueError(f"Failed to parse Cultivera data: {e}")

def parse_growflow_data(json_data):
    """Parse GrowFlow JSON format into common fields"""
    try:
        if not ('inventory_transfer_items' in json_data and 
                'from_license_number' in json_data and 
                'from_license_name' in json_data):
            return pd.DataFrame()
        
        vendor_meta = f"{json_data.get('from_license_number', '')} - {json_data.get('from_license_name', 'Unknown Vendor')}"
        raw_date = json_data.get("est_arrival_at", "") or json_data.get("transferred_at", "")
        accepted_date = raw_date.split("T")[0] if "T" in raw_date else raw_date
        
        items = json_data.get("inventory_transfer_items", [])
        mapped_data = []
        
        for item in items:
            potency_data = item.get("lab_result_data", {}).get("potency", [])
            thc_value = next((p.get('value') for p in potency_data if p.get('type') in ["total-thc", "thc"]), 0)
            cbd_value = next((p.get('value') for p in potency_data if p.get('type') in ["total-cbd", "cbd"]), 0)
            
            mapped_item = {
                "Product Name*": item.get("product_name", ""),
                "Product Type*": item.get("inventory_type", ""),
                "Quantity Received*": item.get("qty", ""),
                "Barcode*": item.get("product_sku", "") or item.get("inventory_id", ""),
                "Accepted Date": accepted_date,
                "Vendor": vendor_meta,
                "Strain Name": item.get("strain_name", ""),
                "THC Content": f"{thc_value}%",
                "CBD Content": f"{cbd_value}%",
                "Source System": "GrowFlow"
            }
            mapped_data.append(mapped_item)
        
        return pd.DataFrame(mapped_data)
    
    except Exception as e:
        logger.error(f"Error parsing GrowFlow data: {str(e)}")
        return pd.DataFrame()

def parse_inventory_json(json_data):
    """
    Detects and parses JSON format accordingly
    Returns tuple of (DataFrame, format_type)
    """
    if not json_data:
        return None, "No data provided"
    
    try:
        # Parse string to JSON if needed
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
            
        # Try parsing as Bamboo
        if "inventory_transfer_items" in json_data:
            return parse_bamboo_data(json_data), "Bamboo"
            
        # Try parsing as Cultivera 
        elif "data" in json_data and isinstance(json_data["data"], dict) and "manifest" in json_data["data"]:
            return parse_cultivera_data(json_data), "Cultivera"
            
        # Try parsing as GrowFlow
        elif "document_schema_version" in json_data:
            return parse_growflow_data(json_data), "GrowFlow"
            
        else:
            return None, "Unknown JSON format"
            
    except json.JSONDecodeError:
        return None, "Invalid JSON data"
    except Exception as e:
        return None, f"Error parsing data: {str(e)}"

# Process CSV data
def process_csv_data(df):
    try:
        # Strip whitespace from column names
        df.columns = [col.strip() for col in df.columns]
        logger.info(f"Original columns: {df.columns.tolist()}")
        
        # First, ensure column names are unique by adding a suffix if needed
        df.columns = [f"{col}_{i}" if df.columns.tolist().count(col) > 1 else col 
                     for i, col in enumerate(df.columns)]
        logger.info(f"Columns after ensuring uniqueness: {df.columns.tolist()}")
        
        # Map column names to expected format
        col_map = {
            "Product Name*": "Product Name*",
            "Product Name": "Product Name*",
            "Quantity Received": "Quantity Received*",
            "Quantity*": "Quantity Received*",
            "Quantity": "Quantity Received*",
            "Lot Number*": "Barcode*",
            "Barcode": "Barcode*",
            "Lot Number": "Barcode*",
            "Accepted Date": "Accepted Date",
            "Vendor": "Vendor",
            "Strain Name": "Strain Name",
            "Product Type*": "Product Type*",
            "Product Type": "Product Type*",
            "Inventory Type": "Product Type*"
        }
        
        # Now rename columns according to our mapping
        new_columns = {}
        target_counts = {}  # Keep track of how many times we've used each target name
        
        for col in df.columns:
            base_col = col.split('_')[0]  # Remove any suffix
            if base_col in col_map:
                target_name = col_map[base_col]
                # If we've seen this target name before, add a suffix
                if target_name in target_counts:
                    target_counts[target_name] += 1
                    new_columns[col] = f"{target_name}_{target_counts[target_name]}"
                else:
                    target_counts[target_name] = 0
                    new_columns[col] = target_name
            else:
                new_columns[col] = col
        
        logger.info(f"Column mapping: {new_columns}")
        df = df.rename(columns=new_columns)
        logger.info(f"Columns after renaming: {df.columns.tolist()}")
        
        # Ensure required columns exist
        required_cols = ["Product Name*", "Barcode*"]
        missing_cols = [col for col in required_cols if not any(col in c for c in df.columns)]
        
        if missing_cols:
            return None, f"CSV is missing required columns: {', '.join(missing_cols)}"
        
        # Set default values for missing columns
        if not any("Vendor" in c for c in df.columns):
            df["Vendor"] = "Unknown Vendor"
        else:
            vendor_col = next(c for c in df.columns if "Vendor" in c)
            df[vendor_col] = df[vendor_col].fillna("Unknown Vendor")
        
        if not any("Accepted Date" in c for c in df.columns):
            today = datetime.today().strftime("%Y-%m-%d")
            df["Accepted Date"] = today
        
        if not any("Product Type*" in c for c in df.columns):
            df["Product Type*"] = "Unknown"
        
        if not any("Strain Name" in c for c in df.columns):
            df["Strain Name"] = ""
        
        # Sort if possible
        try:
            sort_cols = []
            if any("Product Type*" in c for c in df.columns):
                sort_cols.append(next(c for c in df.columns if "Product Type*" in c))
            if any("Product Name*" in c for c in df.columns):
                sort_cols.append(next(c for c in df.columns if "Product Name*" in c))
            
            if sort_cols:
                df = df.sort_values(sort_cols, ascending=[True, True])
        except:
            pass  # If sorting fails, continue without sorting
        
        # Final check for duplicate columns
        if len(df.columns) != len(set(df.columns)):
            duplicates = [col for col in df.columns if df.columns.tolist().count(col) > 1]
            logger.error(f"Duplicate columns found: {duplicates}")
            return None, f"Duplicate columns found: {', '.join(duplicates)}"
        
        return df, "Success"
    
    except Exception as e:
        logger.error(f"Error in process_csv_data: {str(e)}", exc_info=True)
        return None, f"Failed to process CSV data: {e}"

def limit_dataframe_for_session(df, max_rows=25):
    """Limit DataFrame size to prevent session cookie from becoming too large"""
    if len(df) > max_rows:
        logger.warning(f"DataFrame has {len(df)} rows, limiting to {max_rows} for session storage")
        return df.head(max_rows)
    return df

def store_chunked_data(key, data):
    """Store data with improved chunking and size validation"""
    try:
        # Compress data first
        compressed = compress_session_data(data)
        
        # Clear existing chunks
        clear_chunked_data(key)
        
        # Split into smaller chunks
        chunks = [compressed[i:i + MAX_CHUNK_SIZE] for i in range(0, len(compressed), MAX_CHUNK_SIZE)]
        
        if len(chunks) > 20:  # Limit number of chunks
            raise ValueError(f"Data too large: {len(chunks)} chunks needed")
        
        # Store chunks with size validation
        session[f'{key}_chunks'] = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk_key = f'{key}_chunk_{i}'
            if len(chunk) > MAX_CHUNK_SIZE:
                raise ValueError(f"Chunk {i} exceeds maximum size")
            session[chunk_key] = chunk
            
        logger.info(f"Stored {len(chunks)} chunks for {key} (total size: {len(compressed)})")
        return True
        
    except Exception as e:
        logger.error(f"Error storing chunked data: {str(e)}")
        clear_chunked_data(key)  # Clean up on error
        return False

def get_chunked_data(key):
    """Retrieve chunked data with improved error handling"""
    try:
        num_chunks = session.get(f'{key}_chunks')
        if num_chunks is None:
            return None
            
        # Validate chunk count
        if num_chunks > 20:  # Safety check
            logger.error(f"Too many chunks for {key}: {num_chunks}")
            return None
            
        # Reconstruct data
        chunks = []
        for i in range(num_chunks):
            chunk = session.get(f'{key}_chunk_{i}')
            if chunk is None or len(chunk) > MAX_CHUNK_SIZE:
                logger.error(f"Invalid chunk {i} for {key}")
                return None
            chunks.append(chunk)
            
        # Combine and decompress
        encoded_data = ''.join(chunks)
        try:
            compressed = base64.b64decode(encoded_data)
            decompressed = zlib.decompress(compressed)
            return decompressed.decode('utf-8')
        except Exception as e:
            logger.error(f"Decompression error: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving chunked data: {str(e)}")
        return None

def clear_chunked_data(key):
    """Remove all chunks for a given key"""
    try:
        num_chunks = session.get(f'{key}_chunks')
        if num_chunks is not None:
            for i in range(num_chunks):
                session.pop(f'{key}_chunk_{i}', None)
        session.pop(f'{key}_chunks', None)
    except Exception as e:
        logger.error(f"Error clearing chunked data: {str(e)}")

def cleanup_temp_files():
    """Clean up any temporary files that might be left behind"""
    try:
        import glob
        temp_patterns = [
            os.path.join(DEFAULT_SAVE_DIR, "*.tmp"),
            os.path.join(DEFAULT_SAVE_DIR, "*.font_adjust.tmp"),
            os.path.join(UPLOAD_FOLDER, "*.tmp")
        ]
        
        for pattern in temp_patterns:
            for temp_file in glob.glob(pattern):
                try:
                    os.remove(temp_file)
                    logger.info(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not remove temporary file {temp_file}: {e}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def create_robust_inventory_slip(selected_df, config, status_callback=None):
    """Generate inventory slip using DocxGenerator"""
    try:
        # Import our new generator
        from src.utils.docgen import DocxGenerator
        
        # Get vendor name 
        vendor_name = selected_df['Vendor'].iloc[0] if not selected_df.empty else "Unknown"
        if " - " in vendor_name:
            vendor_name = vendor_name.split(" - ")[1]
        vendor_name = "".join(c for c in vendor_name if c.isalnum() or c.isspace()).strip()
        
        # Create filename
        today_date = datetime.now().strftime("%Y%m%d")
        outname = f"{today_date}_{vendor_name}_OrderSheet.docx"
        outpath = os.path.join(config['PATHS']['output_dir'], outname)

        # Create generator
        generator = DocxGenerator()
        
        if status_callback:
            status_callback("Creating document...")

        # Generate document with records
        records = selected_df.to_dict('records')
        generator.generate_inventory_slip(
            records=records,
            vendor_name=vendor_name,
            date=today_date,
            rows_per_page=20
        )
        
        if status_callback:
            status_callback("Saving document...")
        
        # Save document
        if generator.save(outpath):
            if os.path.exists(outpath):
                return True, outpath
        
        return False, "Failed to create document"

    except Exception as e:
        logger.error(f"Error in create_robust_inventory_slip: {str(e)}")
        if os.path.exists(outpath):
            try:
                os.remove(outpath)
            except:
                pass
        return False, str(e)

@app.route('/paste-json', methods=['POST'])
def paste_json():
    try:
        data = request.get_json()
        pasted_json = data.get('json_data', '')
        if not pasted_json:
            return jsonify({'success': False, 'message': 'No JSON data provided.'}), 400

        try:
            parsed = json.loads(pasted_json)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Invalid JSON: {str(e)}'}), 400

        result_df, format_type = parse_inventory_json(parsed)
        if result_df is None or result_df.empty:
            return jsonify({'success': False, 'message': 'Could not process pasted JSON data.'}), 400

        # Clear previous files if they exist
        if 'df_path' in session:
            remove_data(session['df_path'])
        if 'raw_path' in session:
            remove_data(session['raw_path'])
            
        # Store DataFrame data
        df_json = result_df.to_json(orient='records')
        df_path = store_data('df_json', df_json, session.id)
        if not df_path:
            return jsonify({'success': False, 'message': 'Failed to store data'}), 500
        session['df_path'] = df_path
        
        # Store raw JSON data
        raw_data = pasted_json if len(pasted_json) < 10000 else {"type": "large_json", "size": len(pasted_json)}
        raw_path = store_data('raw_json', raw_data, session.id)
        if raw_path:
            session['raw_path'] = raw_path
            
        # Store format type in session (small enough to keep in cookie)
        session['format_type'] = format_type

        return jsonify({'success': True, 'redirect': url_for('data_view')})
    except Exception as e:
        logger.error(f"Error in paste-json: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/upload-csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        try:
            df = pd.read_csv(filepath)
            processed_df, msg = process_csv_data(df)
            if processed_df is None:
                flash(msg)
                return redirect(url_for('index'))
            
            # Store data using chunked storage
            store_chunked_data('df_json', processed_df)
            # Only store raw data if it's small enough
            raw_json = df.to_json(orient='records', default_handler=str)
            if len(raw_json) < 2000:
                store_chunked_data('raw_json', raw_json)
            else:
                store_chunked_data('raw_json', {"type": "large_csv", "rows": len(df), "columns": list(df.columns)})
            session['format_type'] = 'CSV'
            
            flash('CSV uploaded and processed successfully')
            return redirect(url_for('data_view'))
        except Exception as e:
            flash(f'Failed to process CSV: {str(e)}')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type')
        return redirect(url_for('index'))

# Then, update the URL loading function
@app.route('/load-url', methods=['POST'])
def load_url():
    try:
        url = request.form.get('url')
        if not url:
            flash('Please enter a URL')
            return redirect(url_for('index'))

        logger.info(f"URL loaded: {url}")
        logger.info(f"Attempting to load URL: {url}")
        result_df, format_type, raw_data = load_from_url(url)

        if result_df is None:
            logger.error(f"load_from_url returned None for DataFrame. Possible network or format error.")
            flash('Failed to load data from URL. Please check the file size, format, or try again later.')
            return redirect(url_for('index'))

        # Initialize session if needed
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            
        # Clear any existing data
        if 'df_path' in session:
            remove_data(session['df_path'])
        if 'raw_path' in session:
            remove_data(session['raw_path'])
            
        # Don't clear entire session, just data paths
        session.pop('df_path', None)
        session.pop('raw_path', None)

        # Limit very large datasets
        if len(result_df) > 200:
            logger.warning(f"Large dataset detected ({len(result_df)} rows). Limiting to first 200 rows.")
            result_df = result_df.head(200)

        try:
            # Store DataFrame data with session ID
            df_json = result_df.to_json(orient='records', date_format='iso')
            df_path = store_data('df_json', df_json, session['session_id'])
            if not df_path:
                logger.error("Failed to store DataFrame data")
                flash('Error storing data. Please try again.')
                return redirect(url_for('index'))
            session['df_path'] = df_path
            logger.info(f"DataFrame stored at {df_path}")
            
            # Store format type (small enough for session)
            session['format_type'] = format_type
            
            # Store minimal raw data for debugging
            if raw_data:
                try:
                    minimal_data = {
                        'type': format_type,
                        'size': len(json.dumps(raw_data)),
                        'row_count': len(result_df)
                    }
                    raw_path = store_data('raw_json', minimal_data, session.id)
                    if raw_path:
                        session['raw_path'] = raw_path
                except Exception as e:
                    logger.warning(f"Could not store raw data info: {e}")
            
            # Log storage details
            logger.info(f"Data stored successfully, format_type={format_type}")
            
        except Exception as e:
            logger.error(f"Error compressing/storing data: {e}")
            flash('Error storing data. Please try again.')
            return redirect(url_for('index'))

        logger.info(f"Successfully loaded and stored data from URL: {url}")
        response = redirect(url_for('data_view'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    except Exception as e:
        logger.error(f"Exception in /load-url: {str(e)}", exc_info=True)
        flash(f'Error loading data: {str(e)}')
        return redirect(url_for('index'))
    
def handle_bamboo_url(url):
    try:
        result_df, format_type, raw_data = load_from_url(url)
        if result_df is None or result_df.empty:
            flash('Could not process Bamboo data from URL', 'error')
            return redirect(url_for('index'))
        
        # Clear any existing data
        if 'df_path' in session:
            remove_data(session['df_path'])
        if 'raw_path' in session:
            remove_data(session['raw_path'])
            
        # Store DataFrame data
        df_json = result_df.to_json(orient='records')
        df_path = store_data('df_json', df_json, session.id)
        if not df_path:
            flash('Failed to store data', 'error')
            return redirect(url_for('index'))
        session['df_path'] = df_path
        
        # Store raw data for transfer info extraction
        if raw_data:
            raw_path = store_data('raw_json', raw_data, session.id)
            if raw_path:
                session['raw_path'] = raw_path
        
        session['format_type'] = format_type
        flash(f'{format_type} data loaded successfully', 'success')
        return redirect(url_for('data_view'))
    except Exception as e:
        logger.error(f'Error loading Bamboo URL: {str(e)}', exc_info=True)
        flash(f'Error loading Bamboo data: {str(e)}', 'error')
        return redirect(url_for('index'))

def load_from_url(url):
    # Log the URL being loaded for debugging
    logger.info(f"Loading data from URL: {url}")
    """Download JSON or CSV data from a URL and return as DataFrame, format_type, and raw_data."""
    import traceback
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    import urllib3
    import socket
    import ssl
    import certifi
    from urllib3.connection import HTTPConnection

    # Configure global SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True

    # Configure urllib3 to use the secure context by default
    urllib3.util.ssl_.DEFAULT_CERTS = certifi.where()
    
    # Optionally import SOCKS support
    try:
        import socks
        from urllib3.contrib.socks import SOCKSProxyManager
        SOCKS_AVAILABLE = True
    except ImportError:
        SOCKS_AVAILABLE = False
        logger.info("SOCKS proxy support not available - falling back to direct/HTTP proxy")
    
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs['ssl_context'] = ssl_context
            return super(SSLAdapter, self).init_poolmanager(*args, **kwargs)
            
        def proxy_manager_for(self, *args, **kwargs):
            kwargs['ssl_context'] = ssl_context
            return super(SSLAdapter, self).proxy_manager_for(*args, **kwargs)
    
    def try_direct_connection(url, timeout=60):
        """Try to connect directly without proxy"""
        try:
            session = requests.Session()
            
            class SSLAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    kwargs['ssl_context'] = ssl_context
                    return super().init_poolmanager(*args, **kwargs)

            # Use our custom adapter with proper SSL context
            adapter = SSLAdapter(max_retries=3)
            session.mount('https://', adapter)
            
            # Set verify to the path to certificates, never a boolean
            cert_path = certifi.where()
            if not isinstance(cert_path, str):
                logger.error("Invalid certificate path from certifi")
                raise ValueError("Invalid SSL certificate path")
                
            session.verify = cert_path
            
            response = session.get(url, timeout=timeout)
            response.raise_for_status()  # Raise exception for bad status codes
            return response
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL verification failed: {str(e)}")
            # Always fail on SSL errors in production
            if os.environ.get('FLASK_ENV') != 'development':
                raise
            
            # Only attempt unverified connection in development
            logger.warning("Development environment detected - attempting unverified connection")
            try:
                session = requests.Session()
                response = session.get(url, timeout=timeout, verify=False)
                response.raise_for_status()
                return response
            except Exception as fallback_e:
                logger.error(f"Unverified connection also failed: {str(fallback_e)}")
                return None
                
        except Exception as e:
            logger.error(f"Direct connection failed: {str(e)}")
            return None
            
    def try_socks_connection(url, timeout=60):
        """Try to connect using SOCKS proxy"""
        if not SOCKS_AVAILABLE:
            logger.warning("SOCKS proxy support not available")
            return None
            
        try:
            proxy = SOCKSProxyManager(
                'socks5h://proxy.pythonanywhere.com:3128',
                username=None,
                password=None,
                timeout=urllib3.Timeout(connect=timeout, read=timeout),
                ssl_context=ssl_context,
                ca_certs=certifi.where()
            )
            response = proxy.request('GET', url)
            return response
        except urllib3.exceptions.SSLError as e:
            logger.warning(f"SOCKS proxy SSL error: {str(e)}")
            # Fall back to unverified only in development
            if os.environ.get('FLASK_ENV') == 'development':
                logger.warning("Development environment detected - attempting unverified SOCKS connection")
                proxy = urllib3.SOCKSProxyManager(
                    'socks5h://proxy.pythonanywhere.com:3128',
                    username=None,
                    password=None,
                    timeout=urllib3.Timeout(connect=timeout, read=timeout),
                    ssl_context=ssl._create_unverified_context()
                )
                return proxy.request('GET', url)
            return None
        except Exception as e:
            logger.warning(f"SOCKS proxy connection failed: {str(e)}")
            return None
            
    # Never suppress SSL warnings
    import urllib3
    urllib3.util.ssl_.DEFAULT_CERTS = certifi.where()

    # Try different connection methods in order
    logger.info("Attempting to load URL with multiple methods...")
    
    # 1. Try direct connection first with proper SSL verification
    logger.info("Trying direct connection with SSL verification...")
    response = try_direct_connection(url)
    if response and response.status_code == 200:
        logger.info("Direct connection successful")
        return process_response(response)
        
    # 2. Try HTTP proxy with SSL verification
    logger.info("Trying HTTP proxy with SSL verification...")
    session = requests.Session()
    
    # More aggressive retry strategy with lower timeouts
    retries = Retry(
        total=3,  # Reduced total retries to fail faster
        backoff_factor=0.5,  # Shorter backoff between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        raise_on_status=True,
        respect_retry_after_header=True
    )
    
    # Configure proxy settings with shorter timeout
    proxies = {
        'http': 'http://proxy.pythonanywhere.com:3128',
        'https': 'http://proxy.pythonanywhere.com:3128',
    }
    
    # Configure session with custom SSL adapter
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs['ssl_context'] = ssl_context
            kwargs['timeout'] = urllib3.Timeout(connect=20, read=40)  # Shorter timeouts
            return super().init_poolmanager(*args, **kwargs)
        
        def proxy_manager_for(self, *args, **kwargs):
            kwargs['ssl_context'] = ssl_context
            kwargs['timeout'] = urllib3.Timeout(connect=20, read=40)  # Shorter timeouts
            return super().proxy_manager_for(*args, **kwargs)
    
    # Use our custom adapter with optimized settings
    adapter = SSLAdapter(
        max_retries=retries,
        pool_connections=5,   # Reduced pool size
        pool_maxsize=5,      # Reduced pool size
        pool_block=False     # Don't block when pool is full
    )
    
    session.mount('https://', adapter)
    session.verify = certifi.where()
    
    try:
        # Use more granular timeout settings
        response = session.get(
            url,
            timeout=(20, 40),  # Shorter timeouts (connect, read)
            proxies=proxies,
            verify=certifi.where(),  # Use certifi path explicitly
            stream=True,
            allow_redirects=True,
            headers={
                'User-Agent': 'InventorySlipsBot/1.0',
                'Accept': 'application/json, text/csv, */*',
                'Connection': 'close'  # Don't keep connection alive
            }
        )
        
        if response.status_code == 200:
            logger.info("HTTP proxy connection successful")
            return process_response(response)
    except Exception as e:
        logger.warning(f"HTTP proxy failed: {str(e)}")
    
    # 3. Try SOCKS proxy
    logger.info("Trying SOCKS proxy...")
    response = try_socks_connection(url)
    if response and response.status_code == 200:
        logger.info("SOCKS proxy connection successful")
        return process_response(response)
    
    # If all methods fail, raise error
    raise ValueError("All connection methods failed")

def process_response(response):
    """Process the response from any connection method"""
    try:
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'application/json' in content_type or str(response.url).lower().endswith('.json'):
            data = response.json()
            df, format_type = parse_inventory_json(data)
            return df, format_type, data
            
        elif 'text/csv' in content_type or str(response.url).lower().endswith('.csv'):
            df = pd.read_csv(BytesIO(response.content))
            df, msg = process_csv_data(df)
            return df, 'CSV', None
            
        else:
            # Try to parse as JSON first, then CSV
            try:
                data = response.json()
                df, format_type = parse_inventory_json(data)
                return df, format_type, data
            except Exception as e_json:
                try:
                    df = pd.read_csv(BytesIO(response.content))
                    df, msg = process_csv_data(df)
                    return df, 'CSV', None
                except Exception as e_csv:
                    raise ValueError(f"Unsupported data format or failed to parse. JSON error: {e_json}, CSV error: {e_csv}")
    except Exception as e:
        logger.error(f"Error processing response: {str(e)}")
        raise
    
    # Create a custom connection class with longer timeouts
    class CustomHTTPConnection(HTTPConnection):
        def __init__(self, *args, **kwargs):
            timeout = kwargs.pop('timeout', None)
            super().__init__(*args, **kwargs)
            if timeout is None:
                timeout = socket.getdefaulttimeout()
            # Force longer timeouts
            self.timeout = timeout
            
        def connect(self):
            # Set TCP keepalive on the socket
            sock = socket.create_connection(
                (self._dns_host, self.port),
                timeout=self.timeout,
                source_address=None
            )
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Linux specific: set TCP keepalive parameters
            try:
                sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60)
                sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 10)
                sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 6)
            except AttributeError:
                pass  # Not on Linux
            self.sock = sock
    
    class CustomPoolManager(urllib3.PoolManager):
        def _new_pool(self, scheme, host, port, request_context=None):
            kwargs = self.connection_pool_kw.copy()
            kwargs['timeout'] = 300  # 5 minutes total timeout
            kwargs['retries'] = 3
            pool = urllib3.HTTPConnectionPool(
                host,
                port,
                timeout=300,
                strict=True,
                **kwargs
            )
            pool.ConnectionCls = CustomHTTPConnection
            return pool
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; InventorySlipsBot/1.0)',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        respect_retry_after_header=True
    )
    
    # Use custom connection pool
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=1,  # Limit connections
        pool_maxsize=1,
        pool_block=True
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    # Add proxy support for PythonAnywhere
    proxies = {
        'http': 'http://proxy.pythonanywhere.com:3128',
        'https': 'http://proxy.pythonanywhere.com:3128',
    }
    
    try:
        # Skip HEAD request and go straight for the data
        response = session.get(
            url,
            timeout=300,  # Single long timeout
            headers=headers,
            verify=False,
            proxies=proxies,
            stream=True  # Always use streaming
        )
        
        # Read in small chunks with progress logging
        content = b''
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1KB
        
        if total_size > 0:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    content += chunk
                    if len(content) % (1024 * 1024) == 0:  # Log every MB
                        logger.info(f"Downloaded {len(content) // (1024*1024)}MB of {total_size // (1024*1024)}MB")
        else:
            # If no content length, just read chunks
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    content += chunk
                    
        response._content = content  # Set content for json() to work
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            logger.error(f"Response headers: {response.headers}")
            logger.error(f"Exception details: {str(e)}")
            return None, None, None  # Prevent 502 by returning gracefully
        content_type = response.headers.get('Content-Type', '').lower()
        if 'application/json' in content_type or url.lower().endswith('.json'):
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Error parsing JSON from URL: {url}\n{traceback.format_exc()}")
                raise ValueError(f"Could not parse JSON from URL: {e}")
            try:
                df, format_type = parse_inventory_json(data)
            except Exception as e:
                logger.error(f"Error processing inventory JSON: {traceback.format_exc()}")
                raise ValueError(f"Could not process inventory JSON: {e}")
            return df, format_type, data
        elif 'text/csv' in content_type or url.lower().endswith('.csv'):
            try:
                df = pd.read_csv(BytesIO(response.content))
                df, msg = process_csv_data(df)
            except Exception as e:
                logger.error(f"Error parsing CSV from URL: {url}\n{traceback.format_exc()}")
                raise ValueError(f"Could not parse CSV from URL: {e}")
            return df, 'CSV', None
        else:
            # Try to parse as JSON first, then CSV
            try:
                data = response.json()
                df, format_type = parse_inventory_json(data)
                return df, format_type, data
            except Exception as e_json:
                logger.error(f"Error parsing fallback JSON from URL: {url}\n{traceback.format_exc()}")
                try:
                    df = pd.read_csv(BytesIO(response.content))
                    df, msg = process_csv_data(df)
                    return df, 'CSV', None
                except Exception as e_csv:
                    logger.error(f"Error parsing fallback CSV from URL: {url}\n{traceback.format_exc()}")
                    raise ValueError(f"Unsupported data format or failed to parse. JSON error: {e_json}, CSV error: {e_csv}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error loading URL: {url}\n{traceback.format_exc()}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Network error response: {e.response.text}")
            logger.error(f"Network error headers: {e.response.headers}")
        logger.error(f"Exception details: {str(e)}")
        raise ValueError(f"Network error loading URL: {e}")
    except Exception as e:
        logger.error(f"General error loading data from URL: {url}\n{traceback.format_exc()}")
        raise ValueError(f"Failed to load data from URL: {e}")
    


# Update data view to handle chunked data properly
@app.route('/data-view')
def data_view():
    try:
        # Log session state for debugging
        logger.info(f"Session keys at start of data_view: {list(session.keys())}")
        logger.info(f"Session ID: {session.get('session_id')}")
        
        # Ensure session is initialized
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            logger.info(f"New session ID created: {session['session_id']}")
        
        # Get data file paths from session
        df_path = session.get('df_path')
        format_type = session.get('format_type')
        
        if not df_path:
            logger.error("No data path found in session")
            flash('No data available. Please load data first.')
            return redirect(url_for('index'))
            
        # Verify the file exists
        if not os.path.exists(df_path):
            logger.error(f"Data file not found at path: {df_path}")
            flash('Data file not found. Please reload your data.')
            return redirect(url_for('index'))
            
        # Retrieve data from temporary storage
        start_time = time.time()
        df_json = get_data(df_path)
        
        # Log time taken to retrieve data
        logger.info(f"Time taken to retrieve data: {time.time() - start_time:.2f} seconds")
        
        if df_json is None:
            logger.error("Failed to retrieve data from storage")
            flash('Error loading data. Please try again.')
            return redirect(url_for('index'))
            
        logger.info(f"Retrieved data length: {len(df_json) if df_json else 0}")
        
        try:
            if isinstance(df_json, str):
                from io import StringIO
                df = pd.read_json(StringIO(df_json), orient='records')
            elif isinstance(df_json, list):
                df = pd.DataFrame(df_json)
            else:
                logger.error(f"Unexpected data type: {type(df_json)}")
                flash('Error: Invalid data format')
                return redirect(url_for('index'))

            # Validate DataFrame
            if df.empty:
                logger.error("Empty DataFrame created")
                flash('Error: No data found in the loaded file')
                return redirect(url_for('index'))

            # Debug logging
            logger.info(f"DataFrame shape: {df.shape}")
            logger.info(f"DataFrame columns: {df.columns.tolist()}")
            logger.info(f"First 3 rows of DataFrame: {df.head(3).to_dict(orient='records')}")
            logger.info(f"First row vendor: {df.iloc[0].get('Vendor', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error parsing JSON data: {str(e)}", exc_info=True)
            flash('Error loading data. Please try again.')
            return redirect(url_for('index'))
        
        # Debug logging
        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
        if not df.empty:
            logger.info(f"First row data: {df.iloc[0].to_dict()}")
            logger.info(f"First row keys: {list(df.iloc[0].keys())}")
        
        # Extract transfer information from the DataFrame (first row)
        transfer_info = {
            'vendor': 'Unknown',
            'manifest_id': 'N/A',
            'accepted_date': 'N/A'
        }
        
        if not df.empty:
            first_row = df.iloc[0]
            logger.info(f"Extracting from first row: {first_row.to_dict()}")
            
            # Use the exact column names that exist in the data
            if 'Vendor' in first_row:
                transfer_info['vendor'] = str(first_row['Vendor'])
                logger.info(f"Vendor: {transfer_info['vendor']}")
            
            if 'Barcode*' in first_row:
                transfer_info['manifest_id'] = str(first_row['Barcode*'])
                logger.info(f"Manifest ID (Barcode): {transfer_info['manifest_id']}")
            
            if 'Accepted Date' in first_row:
                transfer_info['accepted_date'] = str(first_row['Accepted Date'])
                logger.info(f"Accepted Date: {transfer_info['accepted_date']}")
        
        logger.info(f"Final transfer info: {transfer_info}")
        
        # Format data for template
        products = []
        for idx, row in df.iterrows():
            product = {
                'id': idx,
                'name': str(row.get('Product Name*', '')),
                'strain': str(row.get('Strain Name', '')),
                'sku': str(row.get('Barcode*', '')),
                'quantity': str(row.get('Quantity Received*', '')),
                'source': format_type or 'Unknown',
                'vendor': str(row.get('Vendor', 'Unknown')),
                'manifest_id': str(row.get('Barcode*', 'N/A')),
                'accepted_date': str(row.get('Accepted Date', 'N/A'))
            }
            products.append(product)

        # Load configuration
        config = load_config()

        return render_template(
            'data_view.html',
            products=products,
            format_type=format_type,
            theme=config['SETTINGS'].get('theme', 'dark'),
            version=APP_VERSION
        )
    except Exception as e:
        logger.error(f'Error in data_view: {str(e)}', exc_info=True)
        flash('Error loading data. Please try again.')
        return redirect(url_for('index'))

@app.route('/generate-slips', methods=['POST'])
def generate_slips():
    """Generate inventory slips using simple document generation"""
    try:
        # Get selected products
        selected_indices = request.form.getlist('selected_indices[]')
        
        if not selected_indices:
            flash('No products selected.')
            return redirect(url_for('data_view'))
        
        # Convert indices to integers
        selected_indices = [int(idx) for idx in selected_indices]
        logger.info(f"Selected indices: {selected_indices}")
        
        # Load data from temporary storage
        df_path = session.get('df_path')
        if not df_path:
            flash('No data available. Please load data first.')
            return redirect(url_for('index'))
            
        df_json = get_data(df_path)
        if df_json is None:
            flash('Failed to retrieve data. Please try again.')
            return redirect(url_for('index'))
        
        # Convert JSON to DataFrame
        try:
            if isinstance(df_json, list):
                df = pd.DataFrame(df_json)
            else:
                from io import StringIO
                df = pd.read_json(StringIO(df_json), orient='records')
        except Exception as e:
            logger.error(f"Error converting JSON to DataFrame: {str(e)}")
            flash('Error loading data. Please try again.')
            return redirect(url_for('data_view'))
        
        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
        
        # Get only selected rows
        selected_df = df.iloc[selected_indices].copy()
        logger.info(f"Selected DataFrame shape: {selected_df.shape}")
        
        # Load configuration
        config = load_config()
        
        # Generate the file using simple document generator
        from src.utils.simple_document_generator import SimpleDocumentGenerator
        
        # Get vendor name from first row
        vendor_name = selected_df['Vendor'].iloc[0] if not selected_df.empty else "Unknown"
        today_date = datetime.now().strftime("%Y%m%d")
        
        # Clean vendor name for filename
        vendor_name = "".join(c for c in vendor_name if c.isalnum() or c.isspace()).strip()
        
        # Create filename
        outname = f"{today_date}_{vendor_name}_Slips.docx"
        outpath = os.path.join(config['PATHS']['output_dir'], outname)
        
        # Prepare records
        records = []
        for _, row in selected_df.iterrows():
            qty = row.get('Quantity Received*', 0)
            try:
                qty = float(qty)
                qty = int(round(qty))
            except (ValueError, TypeError):
                qty = 0
                
            vendor = row.get('Vendor', '')
            if ' - ' in vendor:
                vendor = vendor.split(' - ')[1]
                
            records.append({
                'ProductName': str(row.get('Product Name*', ''))[:100],
                'Barcode': str(row.get('Barcode*', ''))[:50],
                'AcceptedDate': str(row.get('Accepted Date', ''))[:20],
                'QuantityReceived': str(qty),
                'Vendor': str(vendor or 'Unknown Vendor')[:50]
            })
        
        # Generate document
        generator = SimpleDocumentGenerator()
        success, error = generator.generate_document(records)
        
        if success:
            success, error = generator.save(outpath)
            if success:
                result = outpath
            else:
                result = f"Failed to save document: {error}"
                success = False
        else:
            result = f"Failed to generate document: {error}"
        
        if success:
            logger.info(f"Document generated successfully: {result}")
            # Validate the generated file
            if not validate_docx(result):
                logger.error("Generated document failed validation")
                flash('Generated document appears to be corrupted. Please try again.')
                return redirect(url_for('data_view'))
            
            # Return the file for download
            return send_file(
                result,
                as_attachment=True,
                download_name=os.path.basename(result),
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        else:
            logger.error(f"Document generation failed: {result}")
            flash(f'Failed to generate inventory slips: {result}')
            return redirect(url_for('data_view'))
    
    except Exception as e:
        logger.error(f"Error in generate_slips: {str(e)}", exc_info=True)
        flash(f'Error generating slips: {str(e)}')
        return redirect(url_for('data_view'))

# To this:
@app.route('/generate_robust_slips_docx', methods=['POST'])
def generate_robust_slips_docx():
    """Generate robust inventory slips without complex template rendering"""
    try:
        # Get selected products
        selected_indices = request.form.getlist('selected_indices[]')
        
        if not selected_indices:
            flash('No products selected.')
            return redirect(url_for('data_view'))
        
        # Convert indices to integers
        selected_indices = [int(idx) for idx in selected_indices]
        logger.info(f"Selected indices for robust slip: {selected_indices}")
        
        # Load data from session using chunked data
        df_json = get_chunked_data('df_json')
        
        if df_json is None:
            flash('No data available. Please load data first.')
            return redirect(url_for('data_view'))
        
        # Convert JSON to DataFrame
        try:
            if isinstance(df_json, list):
                df = pd.DataFrame(df_json)
            else:
                from io import StringIO
                df = pd.read_json(StringIO(df_json), orient='records')
        except Exception as e:
            logger.error(f"Error converting JSON to DataFrame: {str(e)}")
            flash('Error loading data. Please try again.')
            return redirect(url_for('data_view'))
        
        # Get only selected rows
        selected_df = df.iloc[selected_indices].copy()
        logger.info(f"Selected DataFrame shape for robust slip: {selected_df.shape}")
        
        # Load configuration
        config = load_config()
        
        # Generate the robust file
        def status_callback(msg):
            logger.info(f"Robust slip status: {msg}")
        
        logger.info("Starting robust document generation...")
        success, result = create_robust_inventory_slip(
            selected_df,
            config,
            status_callback
        )
        
        if success:
            logger.info(f"Robust document generated successfully: {result}")
            # Return the file for download
            return send_file(
                result,
                as_attachment=True,
                download_name=os.path.basename(result),
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        else:
            logger.error(f"Robust document generation failed: {result}")
            flash(f'Failed to generate robust inventory slips: {result}')
            return redirect(url_for('data_view'))
    
    except Exception as e:
        logger.error(f"Error in generate_robust_slips: {str(e)}", exc_info=True)
        flash(f'Error generating robust slips: {str(e)}')
        return redirect(url_for('data_view'))

@app.route('/show-result')
def show_result():
    # Get output file path from session
    output_file = session.get('output_file', None)
    
    if not output_file or not os.path.exists(output_file):
        flash('No output file available.')
        return redirect(url_for('index'))
    
    # Get filename for display
    filename = os.path.basename(output_file)
    
    # Load configuration
    config = load_config()
    
    return render_template(
        'result.html',
        filename=filename,
        theme=config['SETTINGS'].get('theme', 'dark'),
        version=APP_VERSION
    )

@app.route('/download-file')
def download_file():
    # Get output file path from session
    output_file = session.get('output_file', None)
    
    if not output_file or not os.path.exists(output_file):
        flash('No output file available.')
        return redirect(url_for('index'))
    
    # Return the file for download
    return send_file(output_file, as_attachment=True)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    config = load_config()
    
    if request.method == 'POST':
        # Update settings from form
        if 'items_per_page' in request.form:
            config['SETTINGS']['items_per_page'] = request.form['items_per_page']
        
        if 'theme' in request.form:
            config['SETTINGS']['theme'] = request.form['theme']
        
        if 'api_key' in request.form:
            if 'API' not in config:
                config['API'] = {}
            config['API']['bamboo_key'] = request.form['api_key']
        
        if 'output_dir' in request.form:
            output_dir = request.form['output_dir']
            if output_dir and os.path.exists(output_dir):
                config['PATHS']['output_dir'] = output_dir
        
        # Save updated config
        save_config(config)
        flash('Settings saved successfully')
        return redirect(url_for('index'))
    
    return render_template(
        'settings.html',
        config=config,
        theme=config['SETTINGS'].get('theme', 'dark'),
        version=APP_VERSION
    )

def require_api_key(f):
    """Decorator to require API key for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = load_config()
        api_type = request.args.get('api_type', 'bamboo')
        
        if 'API' not in config or f'{api_type}_key' not in config['API']:
            flash(f'No API key configured for {api_type}. Please add it in settings.')
            return redirect(url_for('settings'))
        return f(*args, **kwargs)
    return decorated_function

class APIClient:
    def __init__(self, api_type, config):
        self.api_type = api_type
        self.config = config
        self.api_config = API_CONFIGS.get(api_type)
        if not self.api_config:
            raise ValueError(f"Unsupported API type: {api_type}")
        
    def get_headers(self):
        """Get headers for API request based on API type"""
        headers = {
            'User-Agent': f'InventorySlipGenerator/{APP_VERSION}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        api_key = self.config['API'].get(f'{self.api_type}_key')
        if not api_key:
            return headers
            
        if self.api_config['auth_type'] == 'bearer':
            headers['Authorization'] = f'Bearer {api_key}'
        elif self.api_config['auth_type'] == 'basic':
            encoded = base64.b64encode(f'{api_key}:'.encode()).decode()
            headers['Authorization'] = f'Basic {encoded}'
        
        return headers
    
    def make_request(self, endpoint, method='GET', params=None, data=None):
        """Make API request with proper error handling"""
        url = f"{self.api_config['base_url']}/{self.api_config['version']}/{endpoint}"
        headers = self.get_headers()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise

# Add these new routes

@app.route('/api/fetch-transfers', methods=['POST'])
@require_api_key
def fetch_transfers():
    """Fetch transfer data from selected API"""
    try:
        api_type = request.form.get('api_type', 'bamboo')
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        
        config = load_config()
        client = APIClient(api_type, config)
        
        # Fetch data based on API type
        if api_type == 'bamboo':
            data = client.make_request('transfers', params={'start_date': date_from, 'end_date': date_to})
            result_df = parse_bamboo_data(data)
        elif api_type == 'cultivera':
            data = client.make_request('manifests', params={'fromDate': date_from, 'toDate': date_to})
            result_df = parse_cultivera_data(data)
        elif api_type == 'growflow':
            data = client.make_request('inventory/transfers', params={'dateStart': date_from, 'dateEnd': date_to})
            result_df = parse_growflow_data(data)
        else:
            return jsonify({'error': 'Unsupported API type'}), 400
        
        if result_df is None or result_df.empty:
            return jsonify({'error': 'No data found'}), 404
            
        # Store in session
        session['df_json'] = result_df.to_json(orient='records')
        session['format_type'] = api_type
        session['raw_json'] = json.dumps(data)
        
        return jsonify({
            'success': True,
            'message': f'Successfully fetched {len(result_df)} records',
            'redirect': url_for('data_view')
        })
        
    except Exception as e:
        logger.error(f"API fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-key', methods=['POST'])
def validate_api_key():
    """Validate API key for selected service"""
    try:
        api_type = request.form.get('api_type')
        api_key = request.form.get('api_key')
        
        if not api_type or not api_key:
            return jsonify({'valid': False, 'message': 'Missing required parameters'}), 400
            
        config = load_config()
        client = APIClient(api_type, {'API': {f'{api_type}_key': api_key}})
        
        if 'API' not in config:
            config['API'] = {}
        config['API'][f'{api_type}_key'] = api_key
        save_config(config)
        
        return jsonify({
            'valid': True,
            'message': f'{api_type.title()} API key validated and saved'
        })
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return jsonify({
                'valid': False,
                'message': 'Invalid API key'
            }), 401
        return jsonify({
            'valid': False,
            'message': f'API error: {str(e)}'
        }), e.response.status_code
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': f'Validation error: {str(e)}'
        }), 500
        

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Manage API settings"""
    config = load_config()
    
    if request.method == 'POST':
        api_type = request.form.get('api_type')
        api_key = request.form.get('api_key')
        
        if api_type and api_key:
            if 'API' not in config:
                config['API'] = {}
            config['API'][f'{api_type}_key'] = api_key
            save_config(config)
            
            flash(f'{api_type.title()} API key updated successfully')
            return redirect(url_for('settings'))
            
    # Get current API keys
    api_keys = {
        'bamboo': config.get('API', {}).get('bamboo_key', ''),
        'cultivera': config.get('API', {}).get('cultivera_key', ''),
        'growflow': config.get('API', {}).get('growflow_key', '')
    }
    
    return render_template(
        'api_settings.html',
        api_keys=api_keys,
        theme=config['SETTINGS'].get('theme', 'dark'),
        version=APP_VERSION
    )

# Add these error handlers

class APIError(Exception):
    """Base class for API-related errors"""
    pass

class APIAuthError(APIError):
    """Authentication error"""
    pass

class APIRateLimit(APIError):
    """Rate limit exceeded"""
    pass

class APIDataError(APIError):
    """Data processing error"""
    pass

@app.errorhandler(APIError)
def handle_api_error(error):
    """Handle API errors gracefully"""
    if isinstance(error, APIAuthError):
        flash(f'Authentication error: {error}', 'error')
    elif isinstance(error, APIRateLimit):
        flash(f'Rate limit exceeded: {error}', 'warning')
    elif isinstance(error, APIDataError):
        flash(f'Data error: {error}', 'error')
    else:
        flash(f'API error: {error}', 'error')
    return redirect(url_for('api_settings'))

@app.route('/test-chunked-data')
def test_chunked_data():
    """Test route to debug chunked data storage"""
    try:
        # Test storing and retrieving data
        test_data = {"test": "data", "number": 123}
        logger.info("Testing chunked data storage...")
        
        store_chunked_data('test_key', json.dumps(test_data))
        retrieved_data = get_chunked_data('test_key')
        
        logger.info(f"Test data: {test_data}")
        logger.info(f"Retrieved data: {retrieved_data}")
        
        # Check session contents
        session_keys = [k for k in session.keys() if k.startswith('test_key')]
        logger.info(f"Session keys for test_key: {session_keys}")
        
        return jsonify({
            'success': True,
            'original': test_data,
            'retrieved': retrieved_data,
            'session_keys': session_keys
        })
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/debug-session')
def debug_session():
    """Debug session issues for Chrome compatibility"""
    try:
        # Get session info
        session_info = {
            'session_id': session.get('_id', 'Not set'),
            'session_keys': list(session.keys()),
            'session_size': len(str(session)),
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'chrome_version': None
        }
        
        # Try to detect Chrome version
        user_agent = request.headers.get('User-Agent', '')
        if 'Chrome/' in user_agent:
            try:
                chrome_version = user_agent.split('Chrome/')[1].split(' ')[0]
                session_info['chrome_version'] = chrome_version
            except:
                session_info['chrome_version'] = 'Unknown'
        
        # Test session storage
        test_key = 'chrome_test'
        session[test_key] = 'test_value'
        session_info['test_storage'] = session.get(test_key) == 'test_value'
        
        return jsonify({
            'success': True,
            'session_info': session_info,
            'headers': dict(request.headers)
        })
    except Exception as e:
        logger.error(f"Session debug failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/about')
def about():
    """About page"""
    config = load_config()
    return render_template('about.html', config=config, version=APP_VERSION)

@app.route('/')
def index():
    # Load configuration for the template
    config = load_config()
    return render_template('index.html', config=config, version=APP_VERSION)

@app.route('/', methods=['OPTIONS'])
def handle_options():
    """Handle OPTIONS requests for CORS preflight"""
    response = app.make_default_options_response()
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/search_json_or_api', methods=['POST'])
def search_json_or_api():
    """Handle both JSON paste and API URL functionality"""
    try:
        search_input = request.form.get('search_input', '').strip()
        
        if not search_input:
            flash('Please enter JSON data or an API URL.')
        search_input = request.form.get('search_input', '').strip()
        
        if not search_input:
            flash('Please enter JSON data or an API URL.')
            return redirect(url_for('index'))
        
        # Check if it looks like a URL
        if search_input.startswith(('http://', 'https://')):
            # Handle as API URL
            return load_from_url(search_input)
        else:
            # Handle as JSON data
            return paste_json_data(search_input)
            
    except Exception as e:
        logger.error(f"Error in search_json_or_api: {str(e)}")
        flash(f'Error processing input: {str(e)}')
        return redirect(url_for('index'))

def paste_json_data(json_text):
    """Handle JSON data processing"""
    try:
        if not json_text.strip():
            flash('Please enter JSON data.')
            return redirect(url_for('index'))
        
        # Parse JSON
        try:
            json_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON format: {str(e)}')
            return redirect(url_for('index'))
        
        # Determine format and process
        if 'transfers' in json_data:
            # Bamboo format
            df = parse_bamboo_data(json_data)
            format_type = 'Bamboo'
        elif 'manifest' in json_data:
            # Cultivera format
            df = parse_cultivera_data(json_data)
            format_type = 'Cultivera'
        elif 'data' in json_data and isinstance(json_data['data'], list):
            # GrowFlow format
            df = parse_growflow_data(json_data)
            format_type = 'GrowFlow'
        else:
            # Generic inventory format
            df = parse_inventory_json(json_data)
            format_type = 'Generic'
        
        if df is None or df.empty:
            flash('No valid data found in JSON.')
            return redirect(url_for('index'))
        
        # Store data in session
        store_chunked_data('df_json', df)
        session['format_type'] = format_type
        
        flash(f'Successfully loaded {len(df)} items from {format_type} data.')
        return redirect(url_for('data_view'))
        
    except Exception as e:
        logger.error(f"Error in paste_json_data: {str(e)}")
        flash(f'Error processing JSON data: {str(e)}')
        return redirect(url_for('index'))

@app.route('/open_downloads', methods=['GET'])
def open_downloads():
    """Open the downloads folder"""
    try:
        config = load_config()
        downloads_path = config['PATHS']['output_dir']
        
        # Open the folder
        open_file(downloads_path)
        
        return jsonify({'success': True, 'message': 'Downloads folder opened'})
    except Exception as e:
        logger.error(f"Error opening downloads folder: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

def validate_docx(file_path):
    """Validate that a Word document is readable and not corrupted"""
    try:
        if not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path)
        if file_size < 1000:  # Too small to be a valid Word document
            return False
        
        # Try to open and read the document
        doc = Document(file_path)
        
        # Check if document has any content
        if len(doc.paragraphs) == 0 and len(doc.tables) == 0:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Document validation failed for {file_path}: {str(e)}")
        return False

@app.route('/clear_data')
def clear_data():
    """Clear all session data"""
    try:
        # Clear all chunked data
        for key in ['df_json', 'raw_json']:
            clear_chunked_data(key)
        
        # Clear other session data
        session.pop('format_type', None)
        
        flash('All data has been cleared successfully.', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}")
        flash('Error clearing data. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/select_directory', methods=['POST'])
def select_directory():
    """Select output directory"""
    try:
        # For now, return the default downloads directory
        # In a full implementation, this would open a file dialog
        config = load_config()
        downloads_path = config['PATHS']['output_dir']
        
        return jsonify({
            'success': True,
            'directory': downloads_path,
            'message': f'Using default directory: {downloads_path}'
        })
    except Exception as e:
        logger.error(f"Error selecting directory: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/fetch_api', methods=['POST'])
def fetch_api():
    """Fetch data from API"""
    try:
        # This would handle API data fetching
        # For now, redirect to the search_json_or_api route
        return redirect(url_for('search_json_or_api'))
    except Exception as e:
        logger.error(f"Error fetching API data: {str(e)}")
        flash(f'Error fetching API data: {str(e)}', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    try:
        # Clean up any temporary files from previous runs
        cleanup_temp_files()
        
        # Try different ports in case default is taken
        ports = [8000, 8001, 8080, 8081, 8888, 9000]
        
        for port in ports:
            try:
                print(f"Attempting to start server on port {port}...")
                
                # Open browser with more reliable method
                def open_browser():
                    try:
                        # Try Chrome first with --new-window flag
                        chrome_path = ""
                        if sys.platform == "darwin":  # macOS
                            chrome_path = r'open -a /Applications/Google\ Chrome.app %s'
                        elif sys.platform == "win32":  # Windows
                            chrome_path = 'C:/Program Files/Google/Chrome/Application/chrome.exe %s'
                        
                        url = f'http://localhost:{port}'
                        
                        # Add Chrome flags to handle authentication issues
                        chrome_flags = [
                            '--disable-web-security',
                            '--disable-features=VizDisplayCompositor',
                            '--disable-site-isolation-trials',
                            '--disable-features=TranslateUI',
                            '--disable-ipc-flooding-protection',
                            '--no-first-run',
                            '--no-default-browser-check',
                            '--disable-default-apps'
                        ]
                        
                        if chrome_path:
                            # Try to open with Chrome flags
                            try:
                                import subprocess
                                if sys.platform == "darwin":  # macOS
                                    cmd = ['open', '-a', 'Google Chrome', '--args'] + chrome_flags + [url]
                                elif sys.platform == "win32":  # Windows
                                    cmd = ['chrome.exe'] + chrome_flags + [url]
                                else:
                                    cmd = ['google-chrome'] + chrome_flags + [url]
                                
                                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                print(f"Opened Chrome with authentication-friendly flags")
                            except Exception as e:
                                print(f"Failed to open Chrome with flags: {e}")
                                # Fallback to webbrowser
                                webbrowser.get(chrome_path).open(url, new=2)
                        else:
                            webbrowser.open(url, new=2)
                    except Exception as e:
                        print(f"Error opening browser: {e}")
                        # Fallback to default browser
                        webbrowser.open(f'http://localhost:{port}', new=2)

                # Delay browser opening slightly
                threading.Timer(2.0, open_browser).start()
                
                app.run(
                    host='localhost',
                    port=port,
                    debug=True,
                    use_reloader=False  # Prevent duplicate browser windows
                )
                break  # If server starts successfully, break the loop
                
            except OSError as e:
                print(f"Port {port} is in use, trying next port...")
                if port == ports[-1]:  # If we've tried all ports
                    print("Could not find an available port. Please try again or manually specify a port.")
                    print("Available ports to try manually: 5001, 5002, 5003, 8000, 8001, 8080, 8081, 8888, 9000")
                continue
                
    except Exception as e:
        print(f"Failed to start server: {str(e)}")
        sys.exit(1)
