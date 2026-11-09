from io import StringIO
import unittest

import pandas as pd

from app import dataframe_from_records_json, process_csv_data


class BarcodePreservationTests(unittest.TestCase):
    def test_csv_barcode_is_preserved_through_session_json_roundtrip(self):
        barcode = "000123456789012345678901234567890123456789012345678901234567"
        csv_data = f"Product Name,Barcode\nProduct A,{barcode}\n"

        imported = pd.read_csv(StringIO(csv_data), dtype=str)
        processed, message = process_csv_data(imported)
        restored = dataframe_from_records_json(processed.to_json(orient="records"))

        self.assertEqual(message, "Success")
        self.assertEqual(processed.loc[0, "Barcode*"], barcode)
        self.assertEqual(restored.loc[0, "Barcode*"], barcode)


if __name__ == "__main__":
    unittest.main()
