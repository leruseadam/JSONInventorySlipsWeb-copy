import os
import sys
import json
import datetime
from docx import Document
from docx.shared import Pt
from io import BytesIO

from .docgen import DocxGenerator

def chunk_records(records, chunk_size=4):
    """Split records into chunks of specified size"""
    for i in range(0, len(records), chunk_size):
        yield records[i:i + chunk_size]

def adjust_table_font_sizes(doc_path):
    """
    Post-process a DOCX file to dynamically adjust font size inside table cells based on thresholds.
    """
    thresholds = [
        (30, 12),   # <=30 chars → 12pt
        (45, 10),   # <=45 chars → 10pt
        (60, 8),    # <=60 chars → 8pt
        (float('inf'), 7)  # >60 chars → 7pt
    ]

    def get_font_size(text_len):
        for limit, size in thresholds:
            if text_len <= limit:
                return size
        return 7  # Fallback

    doc = Document(doc_path)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    text = paragraph.text.strip()
                    if not text:
                        continue

                    # If line is Product Name (first line), force 10pt
                    if paragraph == cell.paragraphs[0]:
                        font_size = 10
                    else:
                        font_size = get_font_size(len(text))

                    for run in paragraph.runs:
                        run.font.size = Pt(font_size)

    doc.save(doc_path)

def open_file(path):
    """Open a file using the system's default application"""
    try:
        if sys.platform == "darwin":
            os.system(f'open "{path}"')
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        print(f"Error opening file: {e}")

def format_json_text(text):
    """Format JSON text for better readability"""
    try:
        if not text.strip():
            return text
        
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        return text
    except Exception:
        return text

def run_full_process_inventory_slips(selected_df, config, status_callback=None, progress_callback=None):
    """Process and generate inventory slips"""
    if selected_df.empty:
        if status_callback:
            status_callback("Error: No data selected.")
        return False, "No data selected."

    try:
        # Get settings from config
        items_per_page = int(config['SETTINGS'].get('items_per_page', '4'))
        output_dir = config['PATHS'].get('output_dir')
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                return False, f"Failed to create output directory: {e}"
        
        if status_callback:
            status_callback("Processing data...")
        
        # Get records
        records = selected_df.to_dict(orient="records")
        
        if status_callback:
            status_callback("Creating document...")
        
        # Create generator
        generator = DocxGenerator()
        
        # Get first vendor name for the filename
        vendor_name = records[0].get('Vendor', 'Unknown')
        if ' - ' in vendor_name:
            vendor_name = vendor_name.split(' - ')[1]
        vendor_name = "".join(c for c in vendor_name if c.isalnum() or c.isspace()).strip()
        
        # Create filename
        now = datetime.datetime.now().strftime("%Y%m%d")
        outname = f"{now}_{vendor_name}_OrderSheet.docx"
        outpath = os.path.join(output_dir, outname)
        
        # Progress calculation - 3 main steps
        if progress_callback:
            progress_callback(33)  # Data processing done
        
        # Generate document with records
        generator.generate_inventory_slip(
            records=records,
            vendor_name=vendor_name,
            date=now,
            rows_per_page=items_per_page
        )
        
        if progress_callback:
            progress_callback(66)  # Document generation done
        
        if status_callback:
            status_callback("Saving document...")
        
        # Save document
        if not generator.save(outpath):
            return False, "Failed to save document"
        
        if status_callback:
            status_callback("Adjusting formatting...")
        
        adjust_table_font_sizes(outpath)
        
        if progress_callback:
            progress_callback(100)  # Complete progress
        
        if status_callback:
            status_callback(f"Saved to: {outpath}")
        
        # Open file if configured
        auto_open = config['SETTINGS'].getboolean('auto_open', True)
        if auto_open:
            open_file(outpath)
        
        return True, outpath
    
    except Exception as e:
        if status_callback:
            status_callback(f"Error: {e}")
        return False, str(e) 