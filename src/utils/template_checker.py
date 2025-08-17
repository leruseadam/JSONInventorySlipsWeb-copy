"""Helper module to check Word templates for placeholders"""
import zipfile
from xml.etree import ElementTree as ET

def check_template_placeholders(template_path):
    """Check if a Word template contains the required placeholders in its raw XML"""
    try:
        with zipfile.ZipFile(template_path) as docx:
            # Read main document content
            with docx.open('word/document.xml') as xml_content:
                xml_str = xml_content.read().decode('utf-8')
                # Look for Label1 placeholders in raw XML
                has_label1 = "{{Label1" in xml_str or "Label1" in xml_str
                return has_label1, xml_str
    except Exception as e:
        return False, str(e)
