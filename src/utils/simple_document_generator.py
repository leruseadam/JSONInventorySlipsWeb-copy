"""
SimpleDocumentGenerator - Creates Word documents using the exact inventory slip template
"""
import logging
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy
import os
import zipfile
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

class SimpleDocumentGenerator:
    def __init__(self, template_path=None):
        self.doc = None
        self.template_path = template_path
        
    def _load_template(self):
        """Load the exact inventory slip template"""
        
        # If template_path was provided in __init__, try it first
        if self.template_path and os.path.exists(self.template_path):
            logger.info(f"Using provided template path: {self.template_path}")
            try:
                with zipfile.ZipFile(self.template_path) as docx:
                    # Check document structure
                    file_list = docx.namelist()
                    required_files = ['word/document.xml', 'word/styles.xml']
                    for req_file in required_files:
                        if req_file not in file_list:
                            logger.error(f"Template missing required file: {req_file}")
                            raise ValueError(f"Invalid template structure: missing {req_file}")
                    
                    # Check for placeholders
                    with docx.open('word/document.xml') as xml_content:
                        xml_str = xml_content.read().decode('utf-8')
                        if "{{Label1" not in xml_str:
                            logger.error("Template missing required Label1 placeholder")
                            raise ValueError("Template does not contain required placeholders")
                        logger.info("Template structure validated successfully")
                        
                    self.doc = Document(self.template_path)
                    
                    # Verify document loaded correctly
                    if not self.doc.paragraphs and not self.doc.tables:
                        logger.error("Template has no content elements")
                        raise ValueError("Template appears to be empty")
                        
                    logger.info(f"Template loaded successfully with {len(self.doc.paragraphs)} paragraphs and {len(self.doc.tables)} tables")
                    return
            except Exception as e:
                logger.warning(f"Could not use provided template: {str(e)}")
        
        # Try multiple template locations as fallback
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # From src/utils
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),  # From project root
            os.path.join(os.path.expanduser('~'), 'Desktop', 'JSONInventorySlipsWeb-copy'),  # From desktop
            os.path.join(os.path.expanduser('~'), 'JSONInventorySlipsWeb-copy'),  # From home
            os.path.join(os.path.expanduser('~'), 'JSONInventorySlipsWeb'),  # From home without -copy
            '/home/adamcordova/JSONInventorySlipsWeb-copy'  # PythonAnywhere path
        ]
        
        potential_paths = []
        for base_path in base_paths:
            potential_paths.extend([
                os.path.join(base_path, 'templates', 'documents', 'InventorySlips.docx'),
                os.path.join(base_path, 'templates', 'documents', 'InventorySlips.backup.docx'),
                os.path.join(base_path, 'templates', 'documents', 'InventorySlips_old.docx')
            ])
        
        template_errors = []
        # Try each path
        for template_path in potential_paths:
            if not os.path.exists(template_path):
                template_errors.append(f"{template_path}: File not found")
                continue
            
            logger.info(f"Loading template from: {template_path}")
            try:
                with zipfile.ZipFile(template_path) as docx:
                    with docx.open('word/document.xml') as xml_content:
                        xml_str = xml_content.read().decode('utf-8')
                        # Look for Label1 placeholders in raw XML
                        if "{{Label1" in xml_str:
                            logger.info(f"Found valid placeholders in {template_path}")
                            self.doc = Document(template_path)
                            return
                        template_errors.append(f"{template_path}: Could not find Label1 placeholders in template")
            except Exception as e:
                logger.error(f"Error reading template {template_path}: {str(e)}")
                template_errors.append(f"{template_path}: {str(e)}")
        
        # If we get here, no valid template was found
        error_details = "\n".join(template_errors)
        raise ValueError(f"No valid template found. Errors:\n{error_details}")
            
    def _create_table(self, rows=2, cols=2):
        """Create a table with specified dimensions"""
        table = self.doc.add_table(rows=rows, cols=cols)
        table.style = 'Table Grid'
        table.autofit = False

        # Calculate available width
        usable_width = Inches(10)  # 11" - 1" for margins
        
        # Set equal column widths
        col_width = usable_width / cols
        for column in table.columns:
            for cell in column.cells:
                cell.width = col_width
        return table
        
    def _add_page_number(self, current_page, total_pages):
        """Add page number to footer"""
        footer = self.doc.sections[-1].footer
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        page_number = paragraph.add_run(f'Page {current_page} of {total_pages}')
        page_number.font.name = 'Arial'
        page_number.font.size = Pt(10)
        
    def _add_label(self, cell, data):
        """Add formatted content to a cell with improved layout"""
        # Clear any existing content
        cell._element.clear_content()
        
        # Add spacing at top
        p = cell.add_paragraph()
        p.add_run().add_break()
        
        # Product Name - centered and larger
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_run = p.add_run(data.get('ProductName', ''))
        name_run.font.name = 'Arial'
        name_run.font.size = Pt(14)
        name_run.font.bold = True
        
        # Add some space after product name
        p.add_run().add_break()
        
        # Details section - centered
        details = cell.add_paragraph()
        details.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Barcode
        barcode_run = details.add_run(f"Barcode: {data.get('Barcode', '')}\n")
        barcode_run.font.name = 'Arial'
        barcode_run.font.size = Pt(11)
        
        # Quantity - bold
        qty = data.get('QuantityReceived', '')
        qty_run = details.add_run(f"Quantity: ")
        qty_run.font.name = 'Arial'
        qty_run.font.size = Pt(11)
        qty_val_run = details.add_run(f"{qty}\n")
        qty_val_run.font.name = 'Arial'
        qty_val_run.font.size = Pt(12)
        qty_val_run.font.bold = True
        
        # Add a line break for spacing
        details.add_run().add_break()
        
        # Date and Vendor on separate lines for clarity
        date_vendor = cell.add_paragraph()
        date_vendor.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        date_run = date_vendor.add_run(f"Date: {data.get('AcceptedDate', '')}\n")
        date_run.font.name = 'Arial'
        date_run.font.size = Pt(10)
        
        vendor_run = date_vendor.add_run(f"Vendor: {data.get('Vendor', '')}")
        vendor_run.font.name = 'Arial'
        vendor_run.font.size = Pt(10)
        
        # Add bottom spacing
        p = cell.add_paragraph()
        p.add_run().add_break()
        
    def _replace_placeholder_text(self, paragraph, old_text, new_text):
        """Safely replace placeholder text in a paragraph with better formatting preservation"""
        if old_text in paragraph.text:
            logger.debug(f"Found placeholder '{old_text}' in paragraph")
            # Get all text runs
            runs = paragraph.runs
            for run in runs:
                if old_text in run.text:
                    # Store original formatting
                    original_font = run.font
                    original_size = original_font.size
                    original_name = original_font.name
                    original_bold = run.bold
                    original_italic = run.italic
                    
                    # Replace text
                    run.text = run.text.replace(old_text, str(new_text))
                    
                    # Reapply formatting
                    run.font.size = original_size or Pt(11)  # Default to 11pt if not set
                    run.font.name = original_name or 'Arial'  # Default to Arial if not set
                    run.bold = original_bold
                    run.italic = original_italic
                    
                    logger.debug(f"Replaced placeholder with '{new_text}' and preserved formatting")

    def _replace_text_in_cell(self, cell, old_text, new_text):
        """Safely replace text in a table cell with content verification"""
        try:
            had_content = bool(cell.text.strip())
            original_text = cell.text
            
            # Replace in existing paragraphs
            for paragraph in cell.paragraphs:
                self._replace_placeholder_text(paragraph, old_text, new_text)
            
            # Verify content was replaced
            if had_content and old_text in original_text:
                # If we had content but replacement failed, try direct approach
                if not cell.text.strip():
                    logger.warning(f"Cell content was lost during replacement. Attempting direct replacement.")
                    # Clear cell
                    cell._element.clear_content()
                    # Add new paragraph with content
                    p = cell.add_paragraph()
                    run = p.add_run(new_text)
                    run.font.name = 'Arial'
                    run.font.size = Pt(11)
                    
            # Verify the cell has proper structure
            if not cell.paragraphs:
                cell.add_paragraph()
                
            logger.debug(f"Cell content after replacement: '{cell.text[:50]}...'")
        except Exception as e:
            logger.error(f"Error replacing text in cell: {str(e)}")
            # Try to recover
            try:
                cell.text = str(new_text)
            except:
                logger.error("Could not recover cell content")

    def generate_document(self, records):
        """Generate document using the exact template"""
        try:
            if not records:
                return False, "No records provided"

            logger.info("Starting document generation...")
            logger.info(f"Number of records to process: {len(records)}")

            # Load the template for each new document
            try:
                self._load_template()
            except Exception as e:
                logger.error(f"Failed to load template: {str(e)}")
                return False, f"Template error: {str(e)}"
            
            # Calculate total pages needed
            total_pages = (len(records) + 3) // 4  # Ceiling division by 4
            current_page = 1
            
            logger.info(f"Will generate {total_pages} pages")
            
            # Process records in groups of 4
            for i in range(0, len(records), 4):
                page_records = records[i:i + 4]
                
                if i > 0:
                    self.doc.add_page_break()
                
                # Replace placeholders for each record
                for idx, record in enumerate(page_records, 1):
                    vendor = record.get('Vendor', 'Unknown')
                    if ' - ' in vendor:  # Clean up vendor name if it has license
                        vendor = vendor.split(' - ')[1]
                        
                    replacements = {
                        f'{{{{Label{idx}.AcceptedDate}}}}': record.get('AcceptedDate', ''),
                        f'{{{{Label{idx}.Vendor}}}}': vendor,
                        f'{{{{Label{idx}.ProductName}}}}': record.get('ProductName', ''),
                        f'{{{{Label{idx}.Barcode}}}}': record.get('Barcode', ''),
                        f'{{{{Label{idx}.QuantityReceived}}}}': str(record.get('QuantityReceived', '')),
                    }
                    
                    # Replace in paragraphs
                    for paragraph in self.doc.paragraphs:
                        for old_text, new_text in replacements.items():
                            self._replace_placeholder_text(paragraph, old_text, new_text)
                    
                    # Replace in tables
                    for table in self.doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for old_text, new_text in replacements.items():
                                    self._replace_text_in_cell(cell, old_text, new_text)
                
                # Clear unused labels on the last page
                if i + 4 > len(records):
                    for idx in range(len(page_records) + 1, 5):
                        empty_replacements = {
                            f'{{{{Label{idx}.AcceptedDate}}}}': '',
                            f'{{{{Label{idx}.Vendor}}}}': '',
                            f'{{{{Label{idx}.ProductName}}}}': '',
                            f'{{{{Label{idx}.Barcode}}}}': '',
                            f'{{{{Label{idx}.QuantityReceived}}}}': '',
                        }
                        
                        # Clear in paragraphs
                        for paragraph in self.doc.paragraphs:
                            for old_text, new_text in empty_replacements.items():
                                self._replace_placeholder_text(paragraph, old_text, '')
                        
                        # Clear in tables
                        for table in self.doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    for old_text, new_text in empty_replacements.items():
                                        self._replace_text_in_cell(cell, old_text, '')
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            return False, str(e)
            
    def save(self, filepath):
        """Save the document with validation and error handling"""
        temp_path = None
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Create temp file first
            temp_path = f"{filepath}.tmp"
            self.doc.save(temp_path)
            
            # Verify the temp file
            try:
                test_doc = Document(temp_path)
                logger.info(f"Validating document at {temp_path}")
                logger.info(f"Document has {len(test_doc.paragraphs)} paragraphs and {len(test_doc.tables)} tables")
                
                # Check document structure
                if not test_doc.paragraphs and not test_doc.tables:
                    logger.error("Generated document has no paragraphs or tables")
                    raise ValueError("Generated document appears to be empty")
                
                # More detailed content validation
                found_content = False
                content_details = []
                
                # Check paragraphs
                for i, paragraph in enumerate(test_doc.paragraphs):
                    text = paragraph.text.strip()
                    if text:
                        found_content = True
                        content_details.append(f"Found text in paragraph {i}: {text[:50]}...")
                        break
                
                # Check tables even if we found content in paragraphs
                table_content = []
                for i, table in enumerate(test_doc.tables):
                    for row_idx, row in enumerate(table.rows):
                        for cell_idx, cell in enumerate(row.cells):
                            text = cell.text.strip()
                            if text:
                                found_content = True
                                table_content.append(f"Table {i}, Row {row_idx}, Cell {cell_idx}: {text[:50]}...")
                                
                # Log what we found
                if content_details:
                    logger.info("Found content in paragraphs:\n" + "\n".join(content_details))
                if table_content:
                    logger.info("Found content in tables:\n" + "\n".join(table_content))
                
                if not found_content:
                    logger.error("No text content found in document")
                    # Try to repair the document
                    for table in test_doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                # Add test content to verify cell is writable
                                p = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()
                                try:
                                    p.add_run("Test").font.size = Pt(11)
                                    found_content = True
                                except Exception as e:
                                    logger.error(f"Could not write to cell: {e}")
                    
                    if not found_content:
                        raise ValueError("Generated document contains no text content and could not be repaired")
                    
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise ValueError(f"Document validation failed: {str(e)}")
                
            # Move temp file to final location
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(temp_path, filepath)
            
            # Final verification
            if not os.path.exists(filepath):
                raise ValueError("Failed to move document to final location")
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False, str(e)
