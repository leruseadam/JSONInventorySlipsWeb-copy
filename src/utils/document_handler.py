import logging
from docxtpl import DocxTemplate
import os
from docx import Document
from docx.shared import Pt
from docx.enum.section import WD_SECTION
from docx.oxml import parse_xml
import jinja2
from .docx_validator import DocxValidator
import tempfile
import shutil

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
        """Add content to document using Jinja2 templating with improved stability"""
        if not records or not isinstance(records, list):
            return False

        try:
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            import tempfile
            import os
            import shutil
            
            # Sort records by product type and then by product name
            sorted_records = sorted(records, 
                key=lambda x: (
                    str(x.get('Product Type*', '')).lower(),
                    str(x.get('Product Name*', '')).lower()
                )
            )
            
            # Calculate total pages
            total_pages = (len(sorted_records) + 3) // 4  # Ceiling division by 4
            
            # Create a temporary directory for intermediate files
            temp_dir = tempfile.mkdtemp()
            template_path = self.doc.docx.path
            final_doc = None
            
            try:
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
                for page_idx, start_idx in enumerate(range(0, len(sorted_records)), 1):
                    # Create a fresh template for each page
                    page_doc = DocxTemplate(template_path)
                    
                    # Get records for this page
                    chunk = sorted_records[start_idx:min(start_idx + 4, len(sorted_records))]
                    
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
                            qty = int(round(qty))
                        except (ValueError, TypeError):
                            qty = 0
                            
                        # Clean vendor name
                        vendor = record.get('Vendor', 'Unknown Vendor')
                        if ' - ' in vendor:
                            vendor = vendor.split(' - ')[1]

                        context[f'Label{idx}'] = {
                            'AcceptedDate': record.get('Accepted Date', ''),
                            'Vendor': vendor,
                            'ProductName': record.get('Product Name*', '')[:100],
                            'Barcode': record.get('Barcode*', '')[:50],
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
                    page_doc.render(context, jinja_env)
                    
                    # Add page number to footer
                    footer = page_doc.docx.sections[0].footer
                    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    paragraph.clear()  # Clear any existing content
                    
                    page_number_text = paragraph.add_run(f'Page {page_idx} of {total_pages}')
                    page_number_text.font.name = 'Arial'
                    page_number_text.font.size = Pt(10)
                    
                    # Save this page
                    page_path = os.path.join(temp_dir, f'page_{page_idx}.docx')
                    page_doc.save(page_path)
                    
                    # For first page, keep it as the base
                    if page_idx == 1:
                        final_doc = page_doc
                    else:
                        # Add content from this page to the final document
                        from docxcompose.composer import Composer
                        if not hasattr(final_doc, 'composer'):
                            final_doc.composer = Composer(final_doc.docx)
                        final_doc.composer.append(page_doc.docx)
                
                # Set the final composed document
                if hasattr(final_doc, 'composer'):
                    self.doc.docx = final_doc.composer.doc
                else:
                    self.doc.docx = final_doc.docx
                
                return True
                
            finally:
                # Clean up temporary files
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary files: {e}")

        except Exception as e:
            logger.error(f"Failed to add content: {str(e)}")
            return False

    def _add_section_break(self):
        """Add a section break to create a new page"""
        section = self.doc.docx.add_section(WD_SECTION.NEW_PAGE)
        # Copy the previous section's settings
        previous_section = self.doc.docx.sections[-2]
        section._sectPr.append(parse_xml(previous_section._sectPr.xml))
        return section

    def save_document(self, filepath):
        """Save document with validation"""
        try:
            # Create a temporary file first
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, "temp.docx")
            
            try:
                # Save to temporary file first
                self.doc.save(temp_path)
                
                # Verify the document is valid
                test_doc = Document(temp_path)
                if not test_doc.sections:
                    raise ValueError("Generated document has no sections")
                
                # Create target directory if needed
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Copy the verified document to final destination
                shutil.copy2(temp_path, filepath)
                return True
                
            finally:
                # Clean up temporary files
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to save document: {str(e)}")
            return False