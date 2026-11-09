import base64
import json
import tempfile
import unittest
import zlib
from unittest.mock import patch

import pandas as pd

import app as app_module
from src.utils.pdf_generator import generate_inventory_slips_pdf


class InventorySlipPDFTests(unittest.TestCase):
    def test_pdf_contains_exact_barcode_text(self):
        barcode = "0001234567890123456789012345"
        records = pd.DataFrame([{
            "Product Name*": "Test product",
            "Barcode*": barcode,
            "Quantity Received*": "2",
            "Product Type*": "Flower",
            "Vendor": "Test vendor",
            "Accepted Date": "2026-11-09",
        }])

        with tempfile.TemporaryDirectory() as output_dir:
            pdf_path = generate_inventory_slips_pdf(records, output_dir)
            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()

        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"))
        stream_start = pdf_bytes.index(b"\nstream\n") + len(b"\nstream\n")
        stream_end = pdf_bytes.index(b"endstream", stream_start)
        encoded_stream = pdf_bytes[stream_start:stream_end].strip()
        content_stream = zlib.decompress(
            base64.a85decode(encoded_stream, adobe=True)
        )
        self.assertIn(f"({barcode}) Tj".encode("ascii"), content_stream)

    def test_pdf_endpoint_returns_pdf_without_format_field(self):
        selected_records = [{
            "Product Name*": "Test product",
            "Barcode*": "001234567890",
            "Quantity Received*": "1",
            "Product Type*": "Flower",
        }]

        with tempfile.TemporaryDirectory() as output_dir:
            config = {"PATHS": {"output_dir": output_dir}}
            with (
                patch.object(app_module, "is_session_valid", return_value=True),
                patch.object(
                    app_module,
                    "get_chunked_data",
                    return_value=json.dumps(selected_records),
                ),
                patch.object(app_module, "update_session_activity"),
                patch.object(app_module, "load_config", return_value=config),
            ):
                response = app_module.app.test_client().post(
                    "/generate-slips-pdf",
                    data={"selected_indices[]": "0"},
                )
                response_data = response.data
                response_mimetype = response.mimetype
                content_disposition = response.headers["Content-Disposition"]
                response.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_mimetype, "application/pdf")
        self.assertTrue(response_data.startswith(b"%PDF-"))
        self.assertIn(".pdf", content_disposition)


if __name__ == "__main__":
    unittest.main()
