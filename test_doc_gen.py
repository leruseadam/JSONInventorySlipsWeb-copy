import os
import logging
from src.utils.simple_document_generator import SimpleDocumentGenerator

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_doc_generation():
    # Test data
    records = [
        {
            'ProductName': 'Test Product 1',
            'Barcode': '123456',
            'AcceptedDate': '2025-08-16',
            'QuantityReceived': '10',
            'Vendor': 'Test Vendor'
        },
        {
            'ProductName': 'Test Product 2',
            'Barcode': '789012',
            'AcceptedDate': '2025-08-16',
            'QuantityReceived': '20',
            'Vendor': 'Test Vendor'
        }
    ]

    # Generate document
    generator = SimpleDocumentGenerator()
    success, error = generator.generate_document(records)
    
    if not success:
        logger.error(f"Failed to generate document: {error}")
        return False
        
    # Try to save the document
    output_path = os.path.join('test_output.docx')
    success, error = generator.save(output_path)
    
    if not success:
        logger.error(f"Failed to save document: {error}")
        return False
        
    logger.info(f"Document generated successfully at {output_path}")
    return True

if __name__ == '__main__':
    test_doc_generation()
