"""Patch docxcompose to work with newer python-docx versions."""
import os
import fileinput
import sys

def patch_properties_py(file_path):
    with fileinput.FileInput(file_path, inplace=True, backup='.bak') as file:
        for line in file:
            if line.strip() == 'from docx.oxml import parse_xml':
                print('from utils.docx.compat import parse_xml')
            else:
                print(line, end='')

def main():
    venv_path = os.environ.get('VIRTUAL_ENV')
    if not venv_path:
        print("Virtual environment not activated")
        sys.exit(1)

    # Path to the properties.py file in the virtual environment
    properties_py = os.path.join(venv_path, 'lib', 'python3.11', 'site-packages', 'docxcompose', 'properties.py')
    
    if os.path.exists(properties_py):
        print(f"Patching {properties_py}")
        patch_properties_py(properties_py)
        print("Patch applied successfully")
    else:
        print(f"Could not find {properties_py}")
        sys.exit(1)

if __name__ == '__main__':
    main()
