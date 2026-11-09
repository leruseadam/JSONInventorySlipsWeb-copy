"""Create printable inventory-slip PDFs without requiring office software."""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit


PAGE_WIDTH, PAGE_HEIGHT = letter
CARDS_PER_PAGE = 4


def _pdf_text(value):
    """Convert values to text supported by the built-in PDF fonts."""
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").encode(
        "cp1252", "replace"
    ).decode("cp1252")


def _draw_wrapped_text(pdf, value, x, top, width, font, font_size, leading, max_lines=None):
    text = _pdf_text(value)
    lines = simpleSplit(text, font, font_size, width) or [""]
    if max_lines is not None:
        lines = lines[:max_lines]
    pdf.setFont(font, font_size)
    y = top - font_size
    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading
    return top - len(lines) * leading


def _draw_slip(pdf, record, x, y, width, height):
    padding = 16
    left = x + padding
    right = x + width - padding
    top = y + height

    pdf.setStrokeColor(colors.HexColor("#233b53"))
    pdf.setLineWidth(1.1)
    pdf.roundRect(x, y, width, height, 8, stroke=1, fill=0)

    product_name = record.get("Product Name*", "")
    cursor = _draw_wrapped_text(
        pdf,
        product_name,
        left,
        top - 14,
        width - 2 * padding,
        "Helvetica-Bold",
        14,
        17,
        max_lines=3,
    )

    cursor -= 5
    pdf.setFillColor(colors.HexColor("#526579"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(left, cursor - 8, "BARCODE")
    cursor -= 15

    barcode = _pdf_text(record.get("Barcode*", ""))
    barcode_width = width - 2 * padding
    barcode_size = 11
    while barcode_size > 5 and stringWidth(barcode, "Helvetica-Bold", barcode_size) > barcode_width:
        barcode_size -= 0.5
    barcode_lines = simpleSplit(barcode, "Helvetica-Bold", barcode_size, barcode_width) or [""]
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", barcode_size)
    for line in barcode_lines:
        pdf.drawString(left, cursor - barcode_size, line)
        cursor -= max(barcode_size + 3, 12)

    cursor -= 7
    pdf.setStrokeColor(colors.HexColor("#d5dde5"))
    pdf.line(left, cursor, right, cursor)
    cursor -= 13

    fields = [
        ("Quantity", record.get("Quantity Received*", "")),
        ("Product Type", record.get("Product Type*", record.get("Inventory Type", ""))),
        ("Strain", record.get("Strain Name", "")),
        ("Vendor", record.get("Vendor", "")),
        ("Accepted Date", record.get("Accepted Date", "")),
        ("THC", record.get("THC Content", "")),
        ("CBD", record.get("CBD Content", "")),
    ]
    label_width = 77
    value_width = width - 2 * padding - label_width

    for label, value in fields:
        lines = simpleSplit(_pdf_text(value), "Helvetica", 9, value_width) or [""]
        pdf.setFillColor(colors.HexColor("#526579"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(left, cursor - 9, label)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 9)
        for line in lines:
            pdf.drawString(left + label_width, cursor - 9, line)
            cursor -= 11
        cursor -= 3


def generate_inventory_slips_pdf(selected_df, output_dir):
    """Write selected inventory records to a four-slip-per-page PDF."""
    if selected_df is None or selected_df.empty:
        raise ValueError("No products selected.")

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"{timestamp}_inventory_slips.pdf")

    margin_x = 30
    margin_y = 30
    gap_x = 18
    gap_y = 18
    card_width = (PAGE_WIDTH - 2 * margin_x - gap_x) / 2
    card_height = (PAGE_HEIGHT - 2 * margin_y - gap_y) / 2

    pdf = canvas.Canvas(output_path, pagesize=letter, pageCompression=0)
    records = selected_df.to_dict(orient="records")

    for start in range(0, len(records), CARDS_PER_PAGE):
        page_records = records[start:start + CARDS_PER_PAGE]
        positions = [
            (margin_x, margin_y + card_height + gap_y),
            (margin_x + card_width + gap_x, margin_y + card_height + gap_y),
            (margin_x, margin_y),
            (margin_x + card_width + gap_x, margin_y),
        ]
        for record, (x, y) in zip(page_records, positions):
            _draw_slip(pdf, record, x, y, card_width, card_height)
        pdf.showPage()

    pdf.save()
    return output_path
