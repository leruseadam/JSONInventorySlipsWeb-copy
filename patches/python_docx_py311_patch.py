#!/usr/bin/env python3
import os
import fileinput
import sys

def patch_file(file_path):
    with fileinput.FileInput(file_path, inplace=True, backup='.bak') as file:
        for line in file:
            if line.strip() == 'from collections import Sequence':
                print('from collections.abc import Sequence')
            else:
                print(line, end='')

def main():
    venv_path = os.environ.get('VIRTUAL_ENV')
    if not venv_path:
        print("Virtual environment not activated")
        sys.exit(1)

    # Path to the section.py file in the virtual environment
    section_py = os.path.join(venv_path, 'lib', 'python3.11', 'site-packages', 'docx', 'section.py')
    
    if os.path.exists(section_py):
        print(f"Patching {section_py}")
        patch_file(section_py)
        print("Patch applied successfully")
    else:
        print(f"Could not find {section_py}")
        sys.exit(1)

if __name__ == '__main__':
    main()
