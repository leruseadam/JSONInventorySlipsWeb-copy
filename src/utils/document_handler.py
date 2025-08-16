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
                        # First collect all text from all runs
                        runs_text = []
                        original_runs = list(paragraph.runs)
                        for run in original_runs:
                            runs_text.append(run.text)
                        full_text = ''.join(runs_text)
                        
                        # Check if any replacements are needed
                        working_text = full_text
                        needs_update = False
                        
                        # Try different placeholder patterns
                        for placeholder, value in replacements.items():
                            patterns = [
                                f'{{{{ {placeholder} }}}}',  # {{ Label1.ProductName }}
                                f'{{{{{placeholder}}}}}',    # {{Label1.ProductName}}
                                f'{{ {placeholder} }}',      # {{ Label1.ProductName }}
                                f'{{{placeholder}}}',        # {Label1.ProductName}
                            ]
                            for pattern in patterns:
                                if pattern in working_text:
                                    working_text = working_text.replace(pattern, str(value))
                                    needs_update = True                        # If we found and replaced a placeholder, update all runs
                        if needs_update:
                            # Store the formatting from the first run
                            first_run_format = None
                            if original_runs:
                                first_run = original_runs[0]
                                first_run_format = {
                                    'font_name': first_run.font.name,
                                    'font_size': first_run.font.size,
                                    'bold': first_run.bold,
                                    'italic': first_run.italic
                                }

                            # Store original paragraph alignment
                            alignment = paragraph.alignment
                            
                            # Clear the paragraph completely
                            p = paragraph._p
                            while len(p):
                                p.remove(p[0])
                            
                            # Add new run with replaced text
                            new_run = paragraph.add_run(working_text)
                            
                            # Apply stored formatting or default formatting
                            if first_run_format:
                                new_run.font.name = first_run_format['font_name'] or 'Arial'
                                new_run.font.size = first_run_format['font_size'] or Pt(11)
                                new_run.bold = first_run_format['bold']
                                new_run.italic = first_run_format['italic']
                            else:
                                new_run.font.name = 'Arial'
                                new_run.font.size = Pt(11)
                                
                            # Restore paragraph alignment
                            paragraph.alignment = alignment

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