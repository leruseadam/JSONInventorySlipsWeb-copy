import logging
from docxtpl import DocxTemplate
import os
from docx.shared import Pt
from docx.enum.section import WD_SECTION
from docx.oxml import parse_xml
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
            from docx.oxml import OxmlElement, parse_xml
            from docx.oxml.ns import qn
            from docx.enum.section import WD_SECTION
            
            # Sort records by product type and then by product name
            sorted_records = sorted(records, 
                key=lambda x: (
                    str(x.get('Product Type*', '')).lower(),
                    str(x.get('Product Name*', '')).lower()
                )
            )
            
            # Calculate total pages
            total_pages = (len(sorted_records) + 3) // 4  # Ceiling division by 4
            
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

            # Create context for all records
            full_context = {
                'total_pages': total_pages,
                'pages': []
            }

            # Prepare all page contexts
            for page_idx, start_idx in enumerate(range(0, len(sorted_records), 4), 1):
                chunk = sorted_records[start_idx:start_idx + 4]
                page_context = {
                    'current_page': page_idx,
                    'page_number': f'Page {page_idx} of {total_pages}'
                }
                
                # Add records for this page
                for idx, record in enumerate(chunk, 1):
                    qty = record.get('Quantity Received*', 0)
                    try:
                        qty = float(qty)
                        qty = int(round(qty))
                    except (ValueError, TypeError):
                        qty = 0

                    page_context[f'Label{idx}'] = {
                        'AcceptedDate': record.get('Accepted Date', ''),
                        'Vendor': record.get('Vendor', 'Unknown Vendor'),
                        'ProductName': record.get('Product Name*', ''),
                        'Barcode': record.get('Barcode*', ''),
                        'QuantityReceived': str(qty)
                    }
                
                # Clear unused labels
                for idx in range(len(chunk) + 1, 5):
                    page_context[f'Label{idx}'] = {
                        'AcceptedDate': '',
                        'Vendor': '',
                        'ProductName': '',
                        'Barcode': '',
                        'QuantityReceived': ''
                    }
                
                full_context['pages'].append(page_context)
            
            # Create section breaks and render content
            for idx, page_context in enumerate(full_context['pages']):
                if idx > 0:
                    self._add_section_break()
                
                # Render content for this page
                self.doc.render(page_context, jinja_env)
                
                # Add page number to footer
                section = self.doc.docx.sections[idx]
                footer = section.footer
                paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Clear existing runs
                for run in paragraph.runs:
                    paragraph._element.remove(run._element)
                
                # Add page number
                page_number_text = paragraph.add_run(page_context['page_number'])
                page_number_text.font.name = 'Arial'
                page_number_text.font.size = Pt(10)
                
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