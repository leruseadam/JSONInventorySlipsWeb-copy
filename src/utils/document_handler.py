import logging
from docxtpl import DocxTemplate
import os
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
        """Add content to document using Jinja2 templating"""
        if not records or not isinstance(records, list):
            return False

        try:
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docxcompose.composer import Composer
            
            # Sort records by product type and then by product name
            sorted_records = sorted(records, 
                key=lambda x: (
                    str(x.get('Product Type*', '')).lower(),
                    str(x.get('Product Name*', '')).lower()
                )
            )
            
            # Calculate total pages
            total_pages = (len(sorted_records) + 3) // 4  # Ceiling division by 4

            # Store template path for creating new pages
            template_path = self.doc.docx.path

            # Keep first page document as master
            master = self.doc.docx
            composer = Composer(master)

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
                chunk = sorted_records[start_idx:min(start_idx + 4, len(sorted_records))]
                
                # Create new document for each page after the first
                if page_idx > 1:
                    self.doc = DocxTemplate(template_path)

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
                
                # Render the template
                self.doc.render(context, jinja_env)
                
                # Add page number to footer
                footer = self.doc.docx.sections[0].footer
                paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Clear existing runs
                for run in paragraph.runs:
                    paragraph._element.remove(run._element)
                
                page_number_text = paragraph.add_run(f'Page {page_idx} of {total_pages}')
                page_number_text.font.name = 'Arial'
                page_number_text.font.size = Pt(10)

                # Add the page to the composer if it's not the first page
                if page_idx > 1:
                    composer.append(self.doc.docx)
            
            # Set the composed document back as the final document
            self.doc.docx = composer.doc
            return True

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
        """Save document with validation and repair"""
        try:
            # Create a temporary file first
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, "temp.docx")
            
            try:
                # Save to temporary file
                self.doc.save(temp_path)
                
                # Validate the document
                is_valid, validated_path = DocxValidator.validate_document(temp_path)
                
                if not is_valid:
                    logger.warning("Document validation failed, attempting repair...")
                    success, repaired_path = DocxValidator.repair_document(temp_path)
                    
                    if not success:
                        logger.error("Document repair failed")
                        return False
                        
                # Create target directory if needed
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Copy the valid document to final destination
                shutil.copy2(temp_path if is_valid else repaired_path, filepath)
                
                # Validate final document
                final_valid, _ = DocxValidator.validate_document(filepath)
                if not final_valid:
                    logger.error("Final document validation failed")
                    return False
                    
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