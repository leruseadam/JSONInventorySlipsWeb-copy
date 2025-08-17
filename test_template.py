import os
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from utils.simple_document_generator import SimpleDocumentGenerator
import logging

logging.basicConfig(level=logging.DEBUG)

def analyze_template(path):
    """Analyze a template file for placeholders"""
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return False
        
    try:
        with zipfile.ZipFile(path) as docx:
            with docx.open('word/document.xml') as xml_content:
                xml_str = xml_content.read().decode('utf-8')
                print(f"\nAnalyzing template: {path}")
                print("Looking for required placeholders:")
                
                required_placeholders = [
                    "{{Label1.ProductName}}",
                    "{{Label1.Barcode}}",
                    "{{Label1.AcceptedDate}}",
                    "{{Label1.Vendor}}",
                    "{{Label1.QuantityReceived}}"
                ]
                
                found = []
                missing = []
                
                for placeholder in required_placeholders:
                    if placeholder in xml_str:
                        found.append(placeholder)
                        print(f"✅ Found: {placeholder}")
                    else:
                        missing.append(placeholder)
                        print(f"❌ Missing: {placeholder}")
                
                if missing:
                    print("\n❌ Template is missing required placeholders:")
                    for placeholder in missing:
                        print(f"  - {placeholder}")
                    return False
                else:
                    print("\n✅ All required placeholders found!")
                    return True
                    
    except Exception as e:
        print(f"❌ Error analyzing template: {str(e)}")
        return False

def test_template():
    print("Testing template validation...")
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "templates", "documents")
                              
    templates_to_check = [
        "InventorySlips.docx",
        "InventorySlips.backup.docx",
        "InventorySlips_old.docx"
    ]
    
    valid_template_found = False
    
    for template in templates_to_check:
        path = os.path.join(template_dir, template)
        if analyze_template(path):
            valid_template_found = True
            print(f"\n✅ Found valid template: {template}")
            break
    
    if not valid_template_found:
        print("\n❌ No valid template found. Please fix the template placeholders.")

if __name__ == "__main__":
    test_template()
