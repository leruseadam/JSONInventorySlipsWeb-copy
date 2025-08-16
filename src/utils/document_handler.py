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
            # Initialize context
            context = {}
            
            # Create context for the first 4 records (or fewer if less available)
            chunk = records[:4]
            
            # Add context for each record in the chunk
            for idx, record in enumerate(chunk, 1):
                context[f'Label{idx}'] = {
                    'AcceptedDate': record.get('Accepted Date', ''),
                    'Vendor': record.get('Vendor', 'Unknown Vendor'),
                    'ProductName': record.get('Product Name*', ''),
                    'Barcode': record.get('Barcode*', ''),
                    'QuantityReceived': str(record.get('Quantity Received*', ''))
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
            
            # Configure Jinja2 environment
            jinja_env = jinja2.Environment(
                block_start_string='{{%',
                block_end_string='%}}',
                variable_start_string='{{',
                variable_end_string='}}',
                comment_start_string='{#',
                comment_end_string='#}',
                autoescape=True
            )
            
            # Render the template with the context
            self.doc.render(context, jinja_env)

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