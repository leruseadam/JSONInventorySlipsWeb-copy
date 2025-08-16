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

logger = logging.getLogger(__name__)

class SimpleDocumentGenerator:
    def __init__(self):
        self.doc = None
        
    def _load_template(self):
        """Load the exact inventory slip template"""
        # Try multiple template locations
        potential_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                        'templates', 'documents', 'InventorySlips.docx'),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                        'templates', 'documents', 'InventorySlips_old.docx'),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                        'templates', 'documents', 'template_check.docx')
        ]
        
        template_errors = []
        # Try each path
        for template_path in potential_paths:
            if os.path.exists(template_path):
                logger.info(f"Loading template from: {template_path}")
                try:
                    self.doc = Document(template_path)
                    # Verify the template structure
                    for p in self.doc.paragraphs:
                        if "{{Label1" in p.text:
                            logger.info(f"Successfully loaded template: {template_path}")
                            return
                    template_errors.append(f"{template_path}: Template structure not valid")
                except Exception as e:
                    template_errors.append(f"{template_path}: {str(e)}")
                    continue
            else:
                template_errors.append(f"{template_path}: File not found")
        
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
            
            # Store the template first page
            template_page = None
            for p in self.doc.paragraphs:
                if "{{Label1" in p.text:
                    template_page = p._element.getparent()
                    break
            
            if not template_page:
                return False, "Template format not recognized"
            
            # Process records in groups of 4
            for i in range(0, len(records), 4):
                page_records = records[i:i + 4]
                
                # For pages after the first one, copy the template
                if i > 0:
                    self.doc.add_page_break()
                    new_page = deepcopy(template_page)
                    template_page.addnext(new_page)
                
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
                    
                    # Replace in all paragraphs and tables
                    for paragraph in self.doc.paragraphs:
                        for run in paragraph.runs:
                            for old_text, new_text in replacements.items():
                                if old_text in run.text:
                                    run.text = run.text.replace(old_text, str(new_text))
                    
                    for table in self.doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for paragraph in cell.paragraphs:
                                    for run in paragraph.runs:
                                        for old_text, new_text in replacements.items():
                                            if old_text in run.text:
                                                run.text = run.text.replace(old_text, str(new_text))
                
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
                        for paragraph in self.doc.paragraphs:
                            for run in paragraph.runs:
                                for old_text, new_text in empty_replacements.items():
                                    if old_text in run.text:
                                        run.text = run.text.replace(old_text, '')
                        
                        for table in self.doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    for paragraph in cell.paragraphs:
                                        for run in paragraph.runs:
                                            for old_text, new_text in empty_replacements.items():
                                                if old_text in run.text:
                                                    run.text = run.text.replace(old_text, '')
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            return False, str(e)
            
    def save(self, filepath):
        """Save the document"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save document
            self.doc.save(filepath)
            
            # Verify the file exists and is readable
            if not os.path.exists(filepath):
                return False, "Failed to create document file"
                
            # Try to open the file to verify it's not corrupted
            test_doc = Document(filepath)
            if not test_doc.tables:
                return False, "Generated document appears to be invalid"
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            return False, str(e)
