import logging
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import re

logger = logging.getLogger(__name__)

class DocumentHandler:
    def __init__(self):
        self.doc = None
        
    def create_document(self, template_path):
        """Create document from template"""
        if not os.path.exists(template_path):
            raise ValueError(f"Template not found: {template_path}")
        self.doc = Document(template_path)
        return self.doc

    def add_content_to_table(self, records):
        """Add content to document replacing placeholders"""
        if not records or not isinstance(records, list):
            return False

        try:
            # Process records in chunks of 4 (for template layout)
            for chunk_index, i in enumerate(range(0, len(records), 4)):
                chunk = records[i:i + 4]
                
                if chunk_index > 0:
                    # Add page break between chunks
                    self.doc.add_page_break()
                
                # Get all paragraphs from document and tables
                all_elements = []
                for paragraph in self.doc.paragraphs:
                    all_elements.append(('paragraph', paragraph))
                for table in self.doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                all_elements.append(('table_cell', paragraph))

                # Replace placeholders for each record in chunk
                    for idx, record in enumerate(chunk, 1):
                        replacements = {
                            f'Label{idx}.AcceptedDate': record.get('Accepted Date', ''),
                            f'Label{idx}.Vendor': record.get('Vendor', 'Unknown Vendor'),
                            f'Label{idx}.ProductName': record.get('Product Name*', ''),
                            f'Label{idx}.Barcode': record.get('Barcode*', ''),
                            f'Label{idx}.QuantityReceived': str(record.get('Quantity Received*', ''))
                        }

                        # Process each element
                        for element_type, paragraph in all_elements:
                            # Join all runs into one text first
                            full_text = ''.join(run.text for run in paragraph.runs)
                            needs_update = False
                            
                            # Create a copy of the text for checking
                            working_text = full_text

                            # Check and replace all placeholders
                            for placeholder, value in replacements.items():
                                placeholder_pattern = f'{{{{{placeholder}}}}}'
                                if placeholder_pattern in working_text:
                                    working_text = working_text.replace(placeholder_pattern, str(value))
                                    needs_update = True                        # If we found and replaced a placeholder, update all runs
                        if needs_update:
                            # Clear existing runs
                            while len(paragraph.runs) > 0:
                                paragraph._p.remove(paragraph.runs[0]._r)
                            
                            # Add new run with replaced text
                            run = paragraph.add_run(working_text)
                            run.font.name = 'Arial'
                            run.font.size = Pt(11)
                            
                            # Clear any trailing whitespace/newlines
                            paragraph._p.remove_all_tags('w:lastRenderedPageBreak')

                # Clean up unused placeholders
                for idx in range(len(chunk) + 1, 5):
                    replacements = {
                        f'Label{idx}.AcceptedDate': '',
                        f'Label{idx}.Vendor': '',
                        f'Label{idx}.ProductName': '',
                        f'Label{idx}.Barcode': '',
                        f'Label{idx}.QuantityReceived': ''
                    }

                    for element_type, paragraph in all_elements:
                        full_text = ''.join(run.text for run in paragraph.runs)
                        needs_update = False

                        for placeholder, value in replacements.items():
                            placeholder_pattern = f'{{{{{placeholder}}}}}'
                            if placeholder_pattern in full_text:
                                full_text = full_text.replace(placeholder_pattern, '')
                                needs_update = True

                        if needs_update:
                            for run in paragraph.runs:
                                run.text = ''
                            if full_text.strip():  # Only add non-empty text
                                run = paragraph.add_run(full_text)
                                run.font.name = 'Arial'
                                run.font.size = Pt(11)

            return True

        except Exception as e:
            logger.error(f"Failed to add content: {str(e)}")
            return False

    def save_document(self, filepath):
        """Save document"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            self.doc.save(filepath)
            return True
        except Exception as e:
            logger.error(f"Failed to save document: {str(e)}")
            return False