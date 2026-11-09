"""Create printable inventory-slip PDFs without requiring office software."""

import os
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    _REPORTLAB_IMPORT_ERROR = None
except ImportError as exc:
    colors = letter = stringWidth = canvas = simpleSplit = None
    _REPORTLAB_IMPORT_ERROR = exc


PAGE_WIDTH, PAGE_HEIGHT = (letter if letter is not None else (612, 792))
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
    """Draw one of the original DOCX form slips, including its blank log grid."""
    padding = 7
    left = x + padding
    right = x + width - padding
    top = y + height
    content_width = right - left

    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.65)
    pdf.rect(x, y, width, height, stroke=1, fill=0)

    # Original template header: accepted date and vendor share the top line.
    header_y = top - 16
    date_text = _pdf_text(record.get("Accepted Date", ""))
    vendor_text = _pdf_text(record.get("Vendor", ""))
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(left, header_y, date_text)
    if vendor_text:
        pdf.drawCentredString((left + right) / 2, header_y, vendor_text)

    # Product name and SKU follow the original bold-name / bold-SKU hierarchy.
    cursor = _draw_wrapped_text(
        pdf, record.get("Product Name*", ""), left, header_y - 5,
        content_width, "Helvetica-Bold", 11, 12, max_lines=2,
    ) - 2
    barcode = _pdf_text(record.get("Barcode*", ""))
    barcode_size = 10.5
    while barcode_size > 6 and stringWidth(f"SKU: {barcode}", "Helvetica-Bold", barcode_size) > content_width:
        barcode_size -= 0.5
    pdf.setFont("Helvetica", barcode_size)
    pdf.drawString(left, cursor - barcode_size, "SKU: ")
    pdf.setFont("Helvetica-Bold", barcode_size)
    pdf.drawString(left + stringWidth("SKU: ", "Helvetica", barcode_size), cursor - barcode_size, barcode)
    cursor -= 20

    # Old inventory count and handling instructions from the template.
    section_top = cursor - 2
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(left, section_top - 9, "Old Units Remaining:")
    instruction = (
        "All employees must check Inventory Data prior to processing orders. "
        'Write the total # of "Old" Products here.'
    )
    instruction_lines = simpleSplit(instruction, "Helvetica", 6.2, content_width - 5)
    instruction_y = section_top - 19
    pdf.setFont("Helvetica", 6.2)
    for line in instruction_lines[:2]:
        pdf.drawString(left, instruction_y, line)
        instruction_y -= 8
    write_line_y = instruction_y - 3
    pdf.setLineWidth(0.45)
    pdf.line(left, write_line_y, right, write_line_y)

    # Inventory counts and initials, arranged like the template's four cells.
    counts_top = write_line_y - 5
    count_widths = [0.27, 0.27, 0.26, 0.20]
    count_labels = [
        "Qty. Issued:",
        "Qty Received:",
        "Initials:",
        "Date Issued:",
    ]
    count_values = [
        "(Remainder should be in multiples of five)",
        _pdf_text(record.get("Quantity Received*", "")),
        "",
        "",
    ]
    column_x = left
    count_box_height = 30
    for fraction, label, value in zip(count_widths, count_labels, count_values):
        column_width = content_width * fraction
        pdf.rect(column_x, counts_top - count_box_height, column_width, count_box_height)
        pdf.setFont("Helvetica-Bold", 6.4 if label == "Qty. Issued:" else 7)
        pdf.drawCentredString(column_x + column_width / 2, counts_top - 9, label)
        if label == "Qty. Issued:":
            note_lines = simpleSplit(value, "Helvetica", 5.2, column_width - 4)
            pdf.setFont("Helvetica", 5.2)
            for line_index, line in enumerate(note_lines[:2]):
                pdf.drawCentredString(
                    column_x + column_width / 2,
                    counts_top - 16 - line_index * 6,
                    line,
                )
        elif value:
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(column_x + column_width / 2, counts_top - 23, value)
        column_x += column_width

    # Six handwritten rows with the same Date / Shift / Initials / Qty / Reason fields.
    grid_top = counts_top - count_box_height - 6
    header_height = 14
    row_height = 24
    grid_columns = [0.15, 0.19, 0.17, 0.12, 0.37]
    headers = ["Date:", "Shift:", "Initials:", "Qty:", "Reason:"]
    column_edges = [left]
    for fraction in grid_columns:
        column_edges.append(column_edges[-1] + content_width * fraction)

    grid_bottom = grid_top - header_height - 6 * row_height
    pdf.setLineWidth(0.45)
    pdf.rect(left, grid_bottom, content_width, header_height + 6 * row_height)
    pdf.setFillColor(colors.HexColor("#eeeeee"))
    pdf.rect(left, grid_top - header_height, content_width, header_height, stroke=0, fill=1)
    pdf.setFillColor(colors.black)
    for edge in column_edges[1:-1]:
        pdf.line(edge, grid_bottom, edge, grid_top)
    pdf.line(left, grid_top - header_height, right, grid_top - header_height)
    for row_index in range(1, 6):
        row_y = grid_top - header_height - row_index * row_height
        pdf.line(left, row_y, right, row_y)

    pdf.setFont("Helvetica-Bold", 6.2)
    for label, x0, x1 in zip(headers, column_edges, column_edges[1:]):
        pdf.drawCentredString((x0 + x1) / 2, grid_top - 9.5, label)

    for row_index in range(6):
        row_top = grid_top - header_height - row_index * row_height
        shift_x0, shift_x1 = column_edges[1], column_edges[2]
        pdf.setFont("Helvetica-Oblique", 5.8)
        pdf.drawCentredString((shift_x0 + shift_x1) / 2, row_top - 11, "AM   MID   PM")

        reason_x0, reason_x1 = column_edges[4], column_edges[5]
        pdf.setFont("Helvetica", 5.1)
        for box_x, baseline, label in (
            (reason_x0 + 2, row_top - 9, "Online Order?"),
            (reason_x0 + 48, row_top - 9, "Request?"),
            (reason_x0 + 2, row_top - 19, "General Restock?"),
        ):
            pdf.rect(box_x, baseline - 1, 5, 5)
            pdf.drawString(box_x + 7, baseline, label)


def generate_inventory_slips_pdf(selected_df, output_dir):
    """Write selected inventory records to a four-slip-per-page PDF."""
    if _REPORTLAB_IMPORT_ERROR is not None:
        raise RuntimeError(
            "PDF generation is unavailable because ReportLab is not installed. "
            "Install the project dependencies in the web app's virtualenv and reload it."
        ) from _REPORTLAB_IMPORT_ERROR

    if selected_df is None or selected_df.empty:
        raise ValueError("No products selected.")

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"{timestamp}_inventory_slips.pdf")

    # Match the DOCX's centered letter-page table: two 3.65-inch slips per row.
    gap_x = 7.45
    gap_y = 14
    card_width = 262.75
    card_heights = [320, 328]
    total_width = card_width * 2 + gap_x
    margin_x = (PAGE_WIDTH - total_width) / 2
    bottom_y = 58

    pdf = canvas.Canvas(output_path, pagesize=letter, pageCompression=1)
    records = selected_df.to_dict(orient="records")

    for start in range(0, len(records), CARDS_PER_PAGE):
        page_records = records[start:start + CARDS_PER_PAGE]
        upper_y = bottom_y + card_heights[0] + gap_y
        positions = [
            (margin_x, upper_y, card_heights[1]),
            (margin_x + card_width + gap_x, upper_y, card_heights[1]),
            (margin_x, bottom_y, card_heights[0]),
            (margin_x + card_width + gap_x, bottom_y, card_heights[0]),
        ]
        for record, (x, y, card_height) in zip(page_records, positions):
            _draw_slip(pdf, record, x, y, card_width, card_height)
        pdf.showPage()

    pdf.save()
    return output_path
