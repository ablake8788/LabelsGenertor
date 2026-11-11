"""
eBay Roll Label Generator - launcher.

    python label_app.py               open the window
    python label_app.py --selftest    self-test without the window (--check-db also tests the database)

The app itself lives in the labelgen package (see README.md for the structure).
This file stays so PyCharm, run_label_app.bat and the PyInstaller build keep working.
"""
from labelgen.main import main

if __name__ == "__main__":
    main()
