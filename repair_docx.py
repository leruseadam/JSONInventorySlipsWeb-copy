from src.utils.docx_validator import DocxValidator
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repair_docx.py <path_to_corrupted_docx>")
        sys.exit(1)
    file_path = sys.argv[1]
    success, repaired_path = DocxValidator.repair_document(file_path)
    if success:
        print(f"Successfully repaired: {repaired_path}")
    else:
        print("Failed to repair document.")
