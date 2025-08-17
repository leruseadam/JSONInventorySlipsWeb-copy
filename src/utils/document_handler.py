import logging
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import re
import tempfile
from .docx_validator import validate_docx
import gc
import signal
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass

@contextmanager
def timeout(seconds):
    """Cross-platform timeout context manager"""
    # Check if SIGALRM is available (Unix-like systems)
    has_sigalrm = hasattr(signal, 'SIGALRM')
    
    if has_sigalrm:
        def handler(signum, frame):
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
            
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        
    try:
        yield
    finally:
        if has_sigalrm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

class DocumentHandler:
    def __init__(self):
        self.doc = None
        self.temp_files = []
        
    def cleanup(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_file}: {e}")
        self.temp_files = []
        gc.collect()  # Force garbage collection

    def create_document(self, template_path):
        """Create document from template with improved path resolution and validation"""
        def try_alternate_paths(base_path):
            # Get webapp root path
            if 'PYTHONANYWHERE_DOMAIN' in os.environ:
                webapp_root = '/home/adamcordova/JSONInventorySlipsWeb-copy'
            else:
                webapp_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
            alternates = [
                base_path,
                os.path.join(webapp_root, "templates", "documents", "InventorySlips.docx"),
                os.path.join(webapp_root, "templates", "InventorySlips.docx"),
                os.path.join(os.path.dirname(base_path), "documents", "InventorySlips.docx"),
                os.path.join(os.path.dirname(base_path), "templates", "documents", "InventorySlips.docx"),
                os.path.join(os.path.dirname(base_path), "templates", "InventorySlips.docx")
            ]
            for path in alternates:
                logger.info(f"Trying template path: {path}")
                if os.path.exists(path):
                    return path
            return None

        try:
            # Try original path first
            actual_path = try_alternate_paths(template_path)
            if not actual_path:
                raise ValueError(f"Template not found at any location starting from: {template_path}")

            logger.info(f"Using template at: {actual_path}")
            
            with timeout(30):  # 30 seconds timeout
                # Create document with proper error handling
                try:
                    temp_doc = Document(actual_path)
                except Exception as e:
                    logger.error(f"Error loading template: {e}")
                    raise ValueError(f"Failed to load template: {e}")
                
                # Save to temporary file for validation
                temp_dir = tempfile.gettempdir()
                # Create a subdirectory with proper permissions
                if 'PYTHONANYWHERE_DOMAIN' in os.environ:
                    temp_dir = os.path.join(temp_dir, 'inventory_generator')
                    os.makedirs(temp_dir, mode=0o755, exist_ok=True)
                    
                temp_path = os.path.join(temp_dir, f'temp_doc_{int(time.time())}.docx')
                logger.info(f"Saving temporary copy to: {temp_path}")
                try:
                    temp_doc.save(temp_path)
                    # Set file permissions
                    os.chmod(temp_path, 0o644)
                    self.temp_files.append(temp_path)
                except Exception as e:
                    logger.error(f"Error saving temporary document: {e}")
                    raise ValueError(f"Failed to save temporary document: {e}")
                
                # Validate with relaxed settings for template
                if not validate_docx(temp_path):
                    logger.error("Template validation failed")
                    raise ValueError("Template validation failed")
                
                self.doc = temp_doc
                return self.doc
                
        except TimeoutError as e:
            self.cleanup()
            raise ValueError(f"Template loading timed out: {e}")
        except Exception as e:
            self.cleanup()
            raise ValueError(f"Failed to create document: {e}")

    def add_content_to_table(self, records):
        """Add content to document replacing placeholders with improved memory management"""
        if not records or not isinstance(records, list):
            return False

        try:
            # Process records in smaller chunks to manage memory
            chunk_size = 4  # Process 4 records at a time
            total_chunks = (len(records) + chunk_size - 1) // chunk_size
            
            for chunk_index in range(total_chunks):
                start_idx = chunk_index * chunk_size
                chunk = records[start_idx:start_idx + chunk_size]
                
                # Create a new temporary file for each chunk
                temp_path = os.path.join(tempfile.gettempdir(), f'chunk_{chunk_index}_{int(time.time())}.docx')
                self.temp_files.append(temp_path)
                
                with timeout(60):  # 60 seconds timeout per chunk
                    if chunk_index > 0:
                        self.doc.add_page_break()
                    
                    # Find all paragraphs and tables in the document
                    all_paragraphs = []
                    for paragraph in self.doc.paragraphs:
                        all_paragraphs.append(paragraph)
                    for table in self.doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for paragraph in cell.paragraphs:
                                    all_paragraphs.append(paragraph)

                    # Replace placeholders for each record in chunk
                    for idx, record in enumerate(chunk, 1):
                        replacements = {
                            f'{{{{Label{idx}.AcceptedDate}}}}': str(record.get('Accepted Date', '')),
                            f'{{{{Label{idx}.Vendor}}}}': str(record.get('Vendor', 'Unknown Vendor')),
                            f'{{{{Label{idx}.ProductName}}}}': str(record.get('Product Name*', '')),
                            f'{{{{Label{idx}.Barcode}}}}': str(record.get('Barcode*', '')),
                            f'{{{{Label{idx}.QuantityReceived}}}}': str(record.get('Quantity Received*', ''))
                        }
                        
                        # Apply replacements in all paragraphs
                        for paragraph in all_paragraphs:
                            for run in paragraph.runs:
                                for old_text, new_text in replacements.items():
                                    if old_text in run.text:
                                        run.text = run.text.replace(old_text, str(new_text))
                                        run.font.name = 'Arial'
                                        run.font.size = Pt(11)

                    # Clean up unused placeholders for this chunk
                    for idx in range(len(chunk) + 1, chunk_size + 1):
                        empty_replacements = {
                            f'{{{{Label{idx}.AcceptedDate}}}}': '',
                            f'{{{{Label{idx}.Vendor}}}}': '',
                            f'{{{{Label{idx}.ProductName}}}}': '',
                            f'{{{{Label{idx}.Barcode}}}}': '',
                            f'{{{{Label{idx}.QuantityReceived}}}}': ''
                        }
                        
                        for paragraph in all_paragraphs:
                            for run in paragraph.runs:
                                for old_text, new_text in empty_replacements.items():
                                    if old_text in run.text:
                                        run.text = run.text.replace(old_text, '')
                    
                    # Save intermediate result
                    self.doc.save(temp_path)
                    # Clear some memory
                    gc.collect()

            return True

        except Exception as e:
            logger.error(f"Failed to add content: {str(e)}")
            return False

    def save_document(self, filepath):
        """Save document with validation and proper permissions"""
        try:
            with timeout(30):  # 30 seconds timeout
                # Create output directory with proper permissions
                output_dir = os.path.dirname(filepath)
                os.makedirs(output_dir, mode=0o755, exist_ok=True)
                
                # Save to a temporary directory with known good permissions
                temp_dir = os.path.join(tempfile.gettempdir(), 'inventory_generator')
                os.makedirs(temp_dir, mode=0o755, exist_ok=True)
                temp_path = os.path.join(temp_dir, f'final_doc_{int(time.time())}.docx')
                self.temp_files.append(temp_path)
                
                # Save document
                logger.info(f"Saving document to temporary path: {temp_path}")
                self.doc.save(temp_path)
                # Set temporary file permissions
                os.chmod(temp_path, 0o644)
                
                # Validate the document
                if not validate_docx(temp_path):
                    raise ValueError("Generated document failed validation")
                    
                # If validation passes, move to final location
                import shutil
                shutil.move(temp_path, filepath)
                
                # Clean up
                self.cleanup()
                return True
        except TimeoutError as e:
            logger.error(f"Document save timed out: {str(e)}")
            self.cleanup()
            return False
        except Exception as e:
            logger.error(f"Failed to save document: {str(e)}")
            self.cleanup()
            return False

    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup()