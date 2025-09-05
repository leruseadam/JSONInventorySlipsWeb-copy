"""
SimpleDocumentGenerator - Creates Word documents without using templates
for more reliable document generation
"""
import logging
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import os

logger = logging.getLogger(__name__)

class SimpleDocumentGenerator:
    def __init__(self):
        self.doc = Document()
        self._setup_document()
        
    def _setup_document(self):
        """Set up initial document properties"""
        # Set larger top/bottom margins for better appearance
        sections = self.doc.sections
        for section in sections:
            section.top_margin = Inches(1.25)
            section.bottom_margin = Inches(1.25)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
            
    def _create_table(self, rows=2, cols=2):
        """Create a table with specified dimensions"""
        table = self.doc.add_table(rows=rows, cols=cols)
        table.style = 'Table Grid'
        table.autofit = False
        # Set column widths
        for cell in table.columns[0].cells:
            cell.width = Inches(3.5)
        for cell in table.columns[1].cells:
            cell.width = Inches(3.5)
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
        """Add formatted and centered content to a cell"""
        # Product Name
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_run = p.add_run(data.get('ProductName', ''))
        name_run.font.name = 'Arial'
        name_run.font.size = Pt(12)
        name_run.font.bold = True

        # Barcode
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        barcode_run = p.add_run(f"Barcode: {data.get('Barcode', '')}")
        barcode_run.font.name = 'Arial'
        barcode_run.font.size = Pt(10)

        # Quantity
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        qty_run = p.add_run(f"Quantity: {data.get('QuantityReceived', '')}")
        qty_run.font.name = 'Arial'
        qty_run.font.size = Pt(10)

        # Date and Vendor
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_vendor_run = p.add_run(f"Date: {data.get('AcceptedDate', '')} | Vendor: {data.get('Vendor', '')}")
        date_vendor_run.font.name = 'Arial'
        date_vendor_run.font.size = Pt(9)
        
    def generate_document(self, records):
        """Generate document with inventory labels"""
        try:
            if not records:
                return False, "No records provided"
                
            # Calculate total pages
            total_pages = (len(records) + 3) // 4  # Ceiling division by 4
            current_page = 1
            
            # Process records in groups of 4
            for i in range(0, len(records), 4):
                # Create 2x2 table for this page
                table = self._create_table(rows=2, cols=2)
                
                # Get records for this page (up to 4)
                page_records = records[i:i+4]
                
                # Fill table cells
                cell_index = 0
                for record in page_records:
                    row = cell_index // 2
                    col = cell_index % 2
                    cell = table.cell(row, col)
                    self._add_label(cell, record)
                    cell_index += 1
                
                # Add page number
                self._add_page_number(current_page, total_pages)
                
                # Add page break if not last page
                if current_page < total_pages:
                    self.doc.add_section(WD_SECTION.NEW_PAGE)
                    
                current_page += 1
                
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
