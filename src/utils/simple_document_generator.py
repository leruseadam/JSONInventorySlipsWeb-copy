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
import re
import zipfile
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

class SimpleDocumentGenerator:
    def __init__(self, template_path=None):
        self.doc = None
        self.template_path = template_path
        self._format_type = None  # Will store the detected placeholder format type
        if template_path:
            self._load_template()  # Load template immediately if path is provided
        
    def _analyze_template_content(self, template_path):
        """Analyze template content to find placeholders and document structure"""
        try:
            with zipfile.ZipFile(template_path) as docx:
                with docx.open('word/document.xml') as xml_content:
                    xml_str = xml_content.read().decode('utf-8')
                    
                    # Try to find any Label placeholders
                    formats_found = []
                    
                    # Search for various placeholder formats
                    patterns = [
                        (r'\{\{Label\d+\.[A-Za-z]+\}\}', 'double_braces_dot'),
                        (r'\{Label\d+\.[A-Za-z]+\}', 'single_braces_dot'),
                        (r'\{\{Label\d+[A-Za-z]+\}\}', 'double_braces_no_dot'),
                        (r'\{Label\d+[A-Za-z]+\}', 'single_braces_no_dot'),
                        (r'Label\d+\.[A-Za-z]+', 'no_braces_dot'),
                        (r'Label\d+[A-Za-z]+', 'no_braces_no_dot'),
                        (r'Label\d+ [A-Za-z]+', 'no_braces_space')
                    ]
                    
                    for pattern, format_type in patterns:
                        matches = re.findall(pattern, xml_str)
                        if matches:
                            formats_found.append({
                                'type': format_type,
                                'examples': matches[:3],
                                'count': len(matches)
                            })
                    
                    if not formats_found:
                        logger.warning(f"No standard Label placeholders found in template")
                        # Try to find any placeholder-like patterns
                        custom_patterns = re.findall(r'\{[^}]+\}|\{\{[^}]+\}\}|Label\d+[^\s<]+', xml_str)
                        if custom_patterns:
                            logger.info("Found potential custom placeholders: " + str(custom_patterns[:5]))
                    else:
                        for fmt in formats_found:
                            logger.info(f"Found {fmt['count']} placeholders of type {fmt['type']}")
                            logger.info(f"Examples: {fmt['examples']}")
                    
                    return formats_found, xml_str
            
        except Exception as e:
            logger.error(f"Error analyzing template: {str(e)}")
            return [], None
            
    def _load_template(self):
        """Load the exact inventory slip template"""
        
        def get_webapp_root():
            """Get the root directory of the web application"""
            if 'PYTHONANYWHERE_DOMAIN' in os.environ:
                return '/home/adamcordova/JSONInventorySlipsWeb-copy'
            else:
                # Local development path
                return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # First try the provided template path
        template_paths = []
        if self.template_path:
            template_paths.append(self.template_path)
            logger.info(f"Adding provided template path: {self.template_path}")
        
        # Add standard locations
        webapp_root = get_webapp_root()
        logger.info(f"Webapp root path: {webapp_root}")
        
        standard_paths = [
            os.path.join(webapp_root, 'templates', 'documents', 'InventorySlips.docx'),
            os.path.join(webapp_root, 'templates', 'InventorySlips.docx'),
            os.path.join(webapp_root, 'InventorySlips.docx'),
            # Add absolute paths for PythonAnywhere
            '/home/adamcordova/JSONInventorySlipsWeb-copy/templates/documents/InventorySlips.docx',
            '/home/adamcordova/JSONInventorySlipsWeb-copy/templates/InventorySlips.docx'
        ]
        
        template_paths.extend(standard_paths)
        for path in standard_paths:
            logger.info(f"Adding standard path: {path}")
            if os.path.exists(path):
                logger.info(f"Path exists: {path}")
            else:
                logger.warning(f"Path does not exist: {path}")

        errors = []
        for template_path in template_paths:
            try:
                logger.info(f"Trying template path: {template_path}")
                if not os.path.exists(template_path):
                    errors.append(f"File not found: {template_path}")
                    continue
                    
                with zipfile.ZipFile(template_path) as docx:
                    # Check document structure
                    file_list = docx.namelist()
                    required_files = ['word/document.xml', 'word/styles.xml']
                    for req_file in required_files:
                        if req_file not in file_list:
                            logger.error(f"Template missing required file: {req_file}")
                            raise ValueError(f"Invalid template structure: missing {req_file}")
                    
                    # Analyze template content
                    formats_found, xml_str = self._analyze_template_content(template_path)
                    
                    if not formats_found:
                        logger.error("Template missing required placeholders")
                        if xml_str:
                            logger.error("Template content sample: " + xml_str[:200])
                        raise ValueError("Template does not contain required placeholders")
                        
                    # Store the detected format type for later use
                    self._format_type = formats_found[0]['type']
                    logger.info(f"Template validated successfully using format: {self._format_type}")
                    logger.info(f"Found placeholder examples: {formats_found[0]['examples']}")
                        
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
                    if "{{Label1" in xml_str or "{Label1" in xml_str or "Label1" in xml_str:
                        logger.info(f"Found valid placeholders in {template_path}")
                        logger.info("Loading document from valid template...")
                        self.doc = Document(template_path)
                        
                        # Verify document structure
                        if len(self.doc.tables) > 0:
                            logger.info(f"Successfully loaded template with {len(self.doc.tables)} tables")
                            logger.info("Template structure:")
                            for i, table in enumerate(self.doc.tables):
                                logger.info(f"- Table {i}: {len(table.rows)} rows x {len(table.columns)} columns")
                            return
                        else:
                            logger.error("Loaded template has no tables")
                            
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
        try:
            logger.debug(f"Adding content to cell with data: {data}")
            
            # Remove existing content (if any)
            for paragraph in cell.paragraphs:
                if paragraph._element.getparent() is not None:
                    paragraph._element.getparent().remove(paragraph._element)
            
            # Product Name Section
            name_p = cell.add_paragraph()
            name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            name_p.space_after = Pt(12)  # Add space after name
            
            name_run = name_p.add_run(data.get('ProductName', ''))
            name_run.font.name = 'Arial'
            name_run.font.size = Pt(14)
            name_run.font.bold = True
            
            # Details Section
            details_p = cell.add_paragraph()
            details_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            details_p.space_after = Pt(6)  # Add space after details
            
            # Barcode
            barcode_run = details_p.add_run(f"Barcode: {data.get('Barcode', '')}")
            barcode_run.font.name = 'Arial'
            barcode_run.font.size = Pt(11)
            details_p.add_run('\n')  # Line break after barcode
            
            # Quantity
            qty_label_run = details_p.add_run("Quantity: ")
            qty_label_run.font.name = 'Arial'
            qty_label_run.font.size = Pt(11)
            
            qty_run = details_p.add_run(str(data.get('QuantityReceived', '')))
            qty_run.font.name = 'Arial'
            qty_run.font.size = Pt(12)
            qty_run.font.bold = True
            
            # Date & Vendor Section
            info_p = cell.add_paragraph()
            info_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            date_run = info_p.add_run(f"Date: {data.get('AcceptedDate', '')}")
            date_run.font.name = 'Arial'
            date_run.font.size = Pt(10)
            info_p.add_run('\n')  # Line break between date and vendor
            
            vendor_run = info_p.add_run(f"Vendor: {data.get('Vendor', '')}")
            vendor_run.font.name = 'Arial'
            vendor_run.font.size = Pt(10)
            
            # Add borders to the cell
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            
            # Set cell borders
            def set_cell_border(cell, **kwargs):
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                
                for edge in ('top', 'left', 'bottom', 'right'):
                    border_name = f'w:border_{edge}'
                    if edge in kwargs:
                        tag = f'{edge}Val'
                        border = OxmlElement('w:tblBorders')
                        border_el = OxmlElement(f'w:{edge}')
                        border_el.set(qn('w:val'), kwargs[edge])
                        border_el.set(qn('w:sz'), '4')
                        border_el.set(qn('w:space'), '0')
                        border_el.set(qn('w:color'), 'auto')
                        tcPr.append(border_el)
            
            # Add borders to cell
            set_cell_border(cell, 
                          top="single",
                          left="single",
                          bottom="single",
                          right="single")
            
            # Set cell vertical alignment to center
            from docx.enum.table import WD_ALIGN_VERTICAL
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            
            # Verify content was added
            content_length = sum(len(p.text) for p in cell.paragraphs)
            logger.debug(f"Added content to cell. Total length: {content_length} chars")
            
            if content_length == 0:
                raise ValueError("No content was added to cell")
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding label to cell: {str(e)}")
            raise
        
    def _replace_placeholder_text(self, paragraph, old_text, new_text):
        """Safely replace placeholder text in a paragraph with better formatting preservation"""
        if any(pattern in paragraph.text for pattern in [old_text, old_text.replace('.', ''), old_text.replace('.', ' ')]):
            logger.debug(f"Found placeholder pattern matching '{old_text}' in paragraph")
            # Get all text runs
            runs = paragraph.runs
            
            # Try different placeholder formats
            placeholder_variants = [
                old_text,  # Original format
                old_text.replace('.', ''),  # No dots
                old_text.replace('.', ' ')  # Spaces instead of dots
            ]
            
            for run in runs:
                original_text = run.text
                # Store original formatting
                original_font = run.font
                original_size = original_font.size
                original_name = original_font.name
                original_bold = run.bold
                original_italic = run.italic
                
                # Try each placeholder variant
                for variant in placeholder_variants:
                    if variant in run.text:
                        # Replace the text
                        run.text = run.text.replace(variant, str(new_text))
                        
                        # Reapply formatting
                        run.font.size = original_size or Pt(11)
                        run.font.name = original_name or 'Arial'
                        run.bold = original_bold
                        run.italic = original_italic
                        
                        if run.text != original_text:
                            logger.debug(f"Successfully replaced '{variant}' with '{new_text}'")
                            break
                    
                        logger.debug(f"Replaced placeholder with '{new_text}' and preserved formatting")

    def _replace_text_in_cell(self, cell, old_text, new_text):
        """Safely replace text in a table cell with content verification"""
        try:
            # Store original content
            original_text = cell.text
            
            logger.debug(f"Cell original text: {original_text[:50]}...")
            logger.debug(f"Looking for: {old_text} to replace with: {new_text}")
            
            # Try all possible placeholder variants
            placeholder_variants = [
                old_text,  # Original format
                old_text.replace('{{', '{').replace('}}', '}'),  # Single braces
                old_text.replace('.', ''),  # No dots
                old_text.replace('.', ' ')  # Spaces instead of dots
            ]
            
            # Method 1: Try replacing in existing paragraph runs
            replaced = False
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    for variant in placeholder_variants:
                        if variant in run.text:
                            # Store original formatting
                            original_font = run.font.name or 'Arial'
                            original_size = run.font.size or Pt(11)
                            original_bold = run.bold
                            original_italic = run.italic
                            
                            # Replace text
                            run.text = run.text.replace(variant, new_text)
                            
                            # Restore formatting
                            run.font.name = original_font
                            run.font.size = original_size
                            run.bold = original_bold
                            run.italic = original_italic
                            
                            replaced = True
                            logger.debug(f"Replaced '{variant}' with '{new_text}' in run")
            
            # Method 2: If no replacements made in runs, try paragraph-level replacement
            if not replaced:
                for paragraph in cell.paragraphs:
                    for variant in placeholder_variants:
                        if variant in paragraph.text:
                            # Store first run's formatting if it exists
                            format_run = paragraph.runs[0] if paragraph.runs else None
                            original_font = format_run.font.name if format_run else 'Arial'
                            original_size = format_run.font.size if format_run else Pt(11)
                            
                            # Clear paragraph content
                            for run in paragraph.runs:
                                run._element.getparent().remove(run._element)
                            
                            # Add new run with replaced text
                            new_run = paragraph.add_run(paragraph.text.replace(variant, new_text))
                            new_run.font.name = original_font
                            new_run.font.size = original_size
                            
                            replaced = True
                            logger.debug(f"Replaced '{variant}' with '{new_text}' in paragraph")
            
            # Method 3: If still no replacement, try cell-level replacement
            if not replaced:
                for variant in placeholder_variants:
                    if variant in cell.text:
                        # Store cell's first paragraph formatting
                        first_p = cell.paragraphs[0] if cell.paragraphs else None
                        first_run = first_p.runs[0] if first_p and first_p.runs else None
                        original_font = first_run.font.name if first_run else 'Arial'
                        original_size = first_run.font.size if first_run else Pt(11)
                        
                        # Clear cell content
                        cell._element.clear_content()
                        
                        # Add new paragraph with replaced text
                        p = cell.add_paragraph()
                        run = p.add_run(original_text.replace(variant, new_text))
                        run.font.name = original_font
                        run.font.size = original_size
                        
                        replaced = True
                        logger.debug(f"Replaced '{variant}' with '{new_text}' at cell level")
            
            # Verify final state
            if not cell.paragraphs:
                cell.add_paragraph()
            
            logger.debug(f"Final cell content: {cell.text[:50]}...")
            return replaced
            
        except Exception as e:
            logger.error(f"Error replacing text in cell: {str(e)}")
            try:
                # Last resort: direct text replacement
                for variant in placeholder_variants:
                    if variant in cell.text:
                        cell.text = cell.text.replace(variant, new_text)
                        return True
            except Exception as e2:
                logger.error(f"Could not recover cell content: {str(e2)}")
            return False

    def generate_document(self, records):
        """Generate document with inventory slip labels"""
        try:
            if not records:
                return False, "No records provided"
            
            logger.info("Starting document generation...")
            logger.info(f"Number of records to process: {len(records)}")
            
            # Debug environment
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Python path: {os.environ.get('PYTHONPATH', 'Not set')}")
            logger.info(f"Environment: {os.environ.get('PYTHONANYWHERE_DOMAIN', 'Local')}")
            
            # If template is not loaded, try to load it
            if not self.doc:
                if not self.template_path:
                    logger.warning("No template path provided, attempting to find template...")
                self._load_template()
                
            if not self.doc:
                raise ValueError("Failed to load document template")
                
            # Verify template was loaded correctly
            logger.info(f"Template loaded with {len(self.doc.tables)} tables")
            for i, table in enumerate(self.doc.tables):
                logger.info(f"Table {i}: {len(table.rows)} rows x {len(table.columns)} columns")
            
            # Process records in batches of 4 (labels per page)
            page_number = 1
            records_processed = 0
            
            # Get existing tables from template
            if not self.doc.tables:
                raise ValueError("No tables found in template")

            tables_per_page = len(self.doc.tables)
            logger.info(f"Found {tables_per_page} tables in template")
            
            # Calculate how many pages we need
            total_pages = (len(records) + 3) // 4
            current_tables = self.doc.tables[:]  # Make a copy of the original tables
            
            # Define the placeholder fields we need to replace
            placeholder_fields = ['ProductName', 'Barcode', 'QuantityReceived', 'AcceptedDate', 'Vendor']
            
            for i in range(0, len(records), 4):
                logger.info(f"Processing page {page_number}")
                
                # If we need more pages, add a page break and copy the template tables
                if page_number > 1:
                    self.doc.add_page_break()
                    for template_table in current_tables:
                        new_table = deepcopy(template_table._element)
                        self.doc._body._body.append(new_table)
                
                # Process records for this page
                page_records = records[i:i + 4]
                
                # For each record in this batch
                for idx, record in enumerate(page_records, start=1):
                    try:
                        # Prepare data
                        vendor = record.get('Vendor', 'Unknown')
                        if ' - ' in vendor:
                            vendor = vendor.split(' - ')[1]
                        
                        # Create replacement dictionary for this record
                        replacements = {}
                        base_data = {
                            'ProductName': str(record.get('ProductName', '')),
                            'Barcode': str(record.get('Barcode', '')),
                            'QuantityReceived': str(record.get('QuantityReceived', '')),
                            'AcceptedDate': str(record.get('AcceptedDate', '')),
                            'Vendor': vendor
                        }
                        
                        # Generate all possible placeholder formats for each field
                        for field in placeholder_fields:
                            value = base_data[field]
                            # Double braces format ({{Label1.Field}})
                            replacements[f'{{{{Label{idx}.{field}}}}}'] = value
                            # Single brace format ({Label1.Field})
                            replacements[f'{{Label{idx}.{field}}}'] = value
                            # No braces format (Label1.Field)
                            replacements[f'Label{idx}.{field}'] = value
                        
                        logger.info(f"Processing replacements for Label{idx}")
                        
                        # Replace in all paragraphs
                        for paragraph in self.doc.paragraphs:
                            for old_text, new_text in replacements.items():
                                if old_text in paragraph.text:
                                    self._replace_placeholder_text(paragraph, old_text, new_text)
                        
                        # Replace in all tables
                        for table in self.doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    for old_text, new_text in replacements.items():
                                        if old_text in cell.text:
                                            self._replace_text_in_cell(cell, old_text, new_text)
                        
                        records_processed += 1
                        logger.info(f"Processed record {records_processed}")
                            
                    except Exception as e:
                        logger.error(f"Error processing record {idx} on page {page_number}: {str(e)}")
                        raise
                        if self._add_label(cell, cell_data):
                            records_processed += 1
                            logger.info(f"Added label {records_processed} (Page {page_number}, Row {row_idx + 1})")
                        else:
                            logger.error(f"Failed to add label for record {records_processed + 1}")
                            raise ValueError(f"Content creation failed for record {records_processed + 1}")
                        
                        # Verify cell content
                        if not cell.text.strip():
                            logger.error(f"Cell content verification failed for record {records_processed}")
                            raise ValueError(f"Empty cell content for record {records_processed}")
                            
                    except Exception as e:
                        logger.error(f"Error processing record {records_processed + 1} on page {page_number}: {str(e)}")
                        raise
                
                page_number += 1
            
            # Final verification
            if records_processed == 0:
                raise ValueError("No records were processed successfully")
                
            logger.info(f"Document generation complete. Processed {records_processed} records across {page_number - 1} pages")
            return True, None
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            return False, str(e)
            
    def check_placeholders(self, replacements=None, base_fields=None, idx=None, page_num=None, page_records=None, total_pages=None):
        """Helper method to check placeholders in document"""
        try:
            if not replacements:
                return False, "No replacements dictionary provided"

            changed = False
            found_format = None
            format_samples = []
            
            def check_text_for_placeholders(text):
                nonlocal found_format
                for old_text in replacements.keys():
                    if old_text in text:
                        found_format = old_text
                        format_samples.append(old_text)
                        return True
                return False
            
            # Scan paragraphs and tables for placeholder format
            for paragraph in self.doc.paragraphs:
                check_text_for_placeholders(paragraph.text)
                
            for table in self.doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        check_text_for_placeholders(cell.text)
            
            if format_samples:
                logger.info(f"Found placeholder format examples: {format_samples[:3]}")
                # Generate new replacements using the detected format pattern
                detected_format = format_samples[0]
                format_type = 'unknown'
                if '{{' in detected_format and '}}' in detected_format:
                    format_type = 'double_braces'
                elif '{' in detected_format and '}' in detected_format:
                    format_type = 'single_braces'
                elif '.' in detected_format:
                    format_type = 'no_braces_dot'
                elif ' ' in detected_format:
                    format_type = 'no_braces_space'
                else:
                    format_type = 'no_braces_concat'
                
                logger.info(f"Detected format type: {format_type}")
                
                # Use the detected format for replacements if base_fields and idx are provided
                if base_fields and idx is not None:
                    updated_replacements = {}
                    for field, value in base_fields.items():
                        key = None
                        if format_type == 'double_braces':
                            key = f'{{{{Label{idx}.{field}}}}}'
                        elif format_type == 'single_braces':
                            key = f'{{Label{idx}.{field}}}'
                        elif format_type == 'no_braces_dot':
                            key = f'Label{idx}.{field}'
                        elif format_type == 'no_braces_space':
                            key = f'Label{idx} {field}'
                        else:
                            key = f'Label{idx}{field}'
                        updated_replacements[key] = value
                    
                    replacements = updated_replacements
                
                # Replace in paragraphs using detected format
                for paragraph in self.doc.paragraphs:
                    for old_text, new_text in replacements.items():
                        if old_text in paragraph.text:
                            logger.debug(f"Replacing {old_text} with {new_text}")
                            self._replace_placeholder_text(paragraph, old_text, new_text)
                            changed = True
                
                # Replace in tables using detected format
                for table in self.doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for old_text, new_text in replacements.items():
                                if old_text in cell.text:
                                    logger.debug(f"Replacing {old_text} with {new_text} in table cell")
                                    self._replace_text_in_cell(cell, old_text, new_text)
                                    changed = True
                                    logger.debug(f"Updated cell content: {cell.text[:50]}")

            # Clear unused placeholders on the last page
            if total_pages is not None and page_num is not None and page_num == total_pages - 1:
                for unused_idx in range(len(page_records) + 1, 5):
                    empty_replacements = {
                        f'{{{{Label{unused_idx}.AcceptedDate}}}}': '',
                        f'{{{{Label{unused_idx}.Vendor}}}}': '',
                        f'{{{{Label{unused_idx}.ProductName}}}}': '',
                        f'{{{{Label{unused_idx}.Barcode}}}}': '',
                        f'{{{{Label{unused_idx}.QuantityReceived}}}}': '',
                    }
                    # Clear in all document elements
                    for paragraph in self.doc.paragraphs:
                        for old_text in empty_replacements:
                            if old_text in paragraph.text:
                                self._replace_placeholder_text(paragraph, old_text, '')
                    for table in self.doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for old_text in empty_replacements:
                                    if old_text in cell.text:
                                        self._replace_text_in_cell(cell, old_text, '')

            if not changed:
                logger.warning("No placeholders were replaced")
            else:
                logger.info("Successfully replaced placeholders in document")

            return True, None
            
        except Exception as e:
            logger.error(f"Error checking placeholders: {str(e)}")
            return False, str(e)
            
    def save(self, filepath):
        """Save the document with validation and error handling"""
        temp_path = None
        try:
            # Pre-save validation
            logger.info("Performing pre-save document validation...")
            
            # Basic document check
            if not self.doc:
                raise ValueError("No document loaded")
                
            if not self.doc.tables:
                raise ValueError("Document contains no tables")
                
            # Log document structure
            logger.info(f"Document contains {len(self.doc.tables)} tables and {len(self.doc.paragraphs)} paragraphs")
            
            # Check if we have any content before saving
            content_summary = self._validate_document_content(self.doc)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save document
            logger.info(f"Saving document to {filepath}")
            try:
                self.doc.save(filepath)
                logger.info("Document saved successfully")
                return True, None
            except Exception as e:
                logger.error(f"Error saving document: {str(e)}")
                raise ValueError(f"Failed to save document: {str(e)}")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False, str(e)
            
    def _validate_document_content(self, doc):
        """Helper method to validate document content"""
        result = {
            'has_content': False,
            'structure': f"{len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables",
            'paragraphs': [],
            'tables': [],
            'samples': [],
            'placeholders_found': []
        }
        
        logger.info("Starting document validation...")
        logger.info(f"Document structure: {result['structure']}")
        
        # Document is valid if it has at least one table
        if len(doc.tables) > 0:
            result['has_content'] = True
            logger.info(f"Found {len(doc.tables)} tables in document")
        
        # Check paragraphs
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                result['paragraphs'].append(f"P{i}: {text[:50]}...")
                result['samples'].append(text[:50])
                
                # Check for unprocessed placeholders
                if '{{Label' in text or '{Label' in text:
                    result['placeholders_found'].append(text)
                    logger.warning(f"Found unprocessed placeholder in paragraph {i}: {text[:50]}")
        
        # Check tables
        for i, table in enumerate(doc.tables):
            logger.info(f"Checking table {i}: {len(table.rows)} rows")
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    text = cell.text.strip()
                    if text:
                        result['tables'].append(
                            f"T{i}R{row_idx}C{cell_idx}: {text[:50]}...")
                        result['samples'].append(text[:50])
                        
                        # Check for unprocessed placeholders
                        if '{{Label' in text or '{Label' in text:
                            result['placeholders_found'].append(text)
                            logger.warning(f"Found unprocessed placeholder in table {i}, cell {row_idx},{cell_idx}: {text[:50]}")
        
        # Truncate lists to prevent excessive logging
        result['paragraphs'] = result['paragraphs'][:5]
        result['tables'] = result['tables'][:5]
        result['samples'] = result['samples'][:3]
        result['placeholders_found'] = result['placeholders_found'][:5]
        
        if result['has_content']:
            logger.info("Document validation successful - found valid content")
        else:
            logger.error("Document validation failed - no valid content found")
            
        return result
