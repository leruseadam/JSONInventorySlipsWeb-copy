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
                
                # Define all possible placeholder variants
                label_variants = []
                for i in range(1, 5):  # Labels 1-4
                    fields = ['ProductName', 'Barcode', 'QuantityReceived', 'AcceptedDate', 'Vendor']
                    for field in fields:
                        # Add all possible formats
                        label_variants.extend([
                            f'{{{{Label{i}.{field}}}}}',  # Double braces with dot
                            f'{{Label{i}.{field}}}',      # Single braces with dot
                            f'{{Label{i}{field}}}',       # Single braces no dot
                            f'{{Label{i} {field}}}',      # Single braces with space
                            f'Label{i}.{field}',          # No braces with dot
                            f'Label{i}{field}',           # No braces no dot
                            f'Label{i} {field}'           # No braces with space
                        ])
                
                # Look for any of the variants
                found_placeholders = []
                for variant in label_variants:
                    if variant in xml_str:
                        found_placeholders.append(variant)
                
                # Return results
                has_label1 = any(variant.startswith(('{{Label1', '{Label1', 'Label1')) for variant in found_placeholders)
                return has_label1, {
                    'found_formats': found_placeholders,
                    'xml_sample': xml_str[:1000]  # First 1000 chars for analysis
                }
    except Exception as e:
        return False, str(e)
