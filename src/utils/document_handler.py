import logging
from docxtpl import DocxTemplate
import os
from docx.shared import Pt
import jinja2

logger = logging.getLogger(__name__)

class DocumentHandler:
    def __init__(self):
        self.doc = None
        
    def create_document(self, template_path):
        """Create document from template"""
        if not os.path.exists(template_path):
            raise ValueError(f"Template not found: {template_path}")
        self.doc = DocxTemplate(template_path)
        return self.doc

    def add_content_to_table(self, records):
        """Add content to document using Jinja2 templating"""
        if not records or not isinstance(records, list):
            return False

        try:
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            # Sort records by product type and then by product name
            sorted_records = sorted(records, 
                key=lambda x: (
                    str(x.get('Product Type*', '')).lower(),
                    str(x.get('Product Name*', '')).lower()
                )
            )
            
            # Calculate total pages
            total_pages = (len(sorted_records) + 3) // 4  # Ceiling division by 4
            current_page = 1
            
            # Configure Jinja2 environment once
            jinja_env = jinja2.Environment(
                block_start_string='{{%',
                block_end_string='%}}',
                variable_start_string='{{',
                variable_end_string='}}',
                comment_start_string='{#',
                comment_end_string='#}',
                autoescape=True
            )

            # Process records in groups of 4
            for page_idx, start_idx in enumerate(range(0, len(sorted_records), 4), 1):
                # Create new document page if not first page
                if page_idx > 1:
                    self.doc.add_page_break()
                
                chunk = sorted_records[start_idx:start_idx + 4]
                
                # Initialize context for this page
                context = {
                    'current_page': page_idx,
                    'total_pages': total_pages,
                    'page_number': f'Page {page_idx} of {total_pages}'
                }
                
                # Add context for each record in the chunk
                for idx, record in enumerate(chunk, 1):
                    # Get quantity and ensure it's a whole number
                    qty = record.get('Quantity Received*', 0)
                    try:
                        qty = float(qty)
                        qty = int(round(qty))  # Round to nearest whole number
                    except (ValueError, TypeError):
                        qty = 0

                    context[f'Label{idx}'] = {
                        'AcceptedDate': record.get('Accepted Date', ''),
                        'Vendor': record.get('Vendor', 'Unknown Vendor'),
                        'ProductName': record.get('Product Name*', ''),
                        'Barcode': record.get('Barcode*', ''),
                        'QuantityReceived': str(qty)
                    }
                
                # Clear unused labels
                for idx in range(len(chunk) + 1, 5):
                    context[f'Label{idx}'] = {
                        'AcceptedDate': '',
                        'Vendor': '',
                        'ProductName': '',
                        'Barcode': '',
                        'QuantityReceived': ''
                    }
                
                # Render the template for this page
                if page_idx == 1:
                    self.doc.render(context, jinja_env)
                else:
                    # For subsequent pages, we need to ensure the template is re-rendered
                    self.doc.patch_template(context)
                
                # Add page number to footer
                section = self.doc.sections[-1]  # Get the last section (current page)
                footer = section.footer
                paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Clear existing runs if any
                for run in paragraph.runs:
                    paragraph._element.remove(run._element)
                
                page_number_text = paragraph.add_run(f'Page {page_idx} of {total_pages}')
                page_number_text.font.name = 'Arial'
                page_number_text.font.size = Pt(10)
            
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