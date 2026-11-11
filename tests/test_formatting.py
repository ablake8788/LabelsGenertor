import csv
import io
import unittest
from datetime import datetime

from labelgen.domain import LabelGenerator
from labelgen.formatting import (
    BOX_SEPARATOR, DB_COLUMNS, CsvFormatter, FolderScriptFormatter, InventoryRowMapper, PrintListFormatter,
)
from tests.fakes import hex_codes


def batch(boxes=("BX3691", "BX3692"), per_box=3):
    return LabelGenerator(hex_codes(), clock=lambda: datetime(2026, 11, 11, 9, 0, 0)).generate(list(boxes), per_box)


class PrintListTests(unittest.TestCase):
    def test_exact_layout(self):
        self.assertEqual(PrintListFormatter().format(batch()), (
            "  !-                          -!\n"
            "1.00001-BX3691\n"
            "2.00002-BX3691\n"
            "3.00003-BX3691\n"
            " !-                          -!\n"
            "  !-                          -!\n"
            "1.00004-BX3692\n"
            "2.00005-BX3692\n"
            "3.00006-BX3692\n"
            " !-                          -!\n"
            "  !-                          -!\n"
        ))

    def test_custom_separators(self):
        text = PrintListFormatter(header=(), box_separator=("",)).format(batch(per_box=1))
        self.assertEqual(text, "1.00001-BX3691\n\n1.00002-BX3692\n\n")
        self.assertEqual(len(BOX_SEPARATOR), 2)


class FolderScriptTests(unittest.TestCase):
    def test_script(self):
        s = FolderScriptFormatter("C:\\root dir", "1").format(batch())
        self.assertTrue(s.startswith('@echo off\r\ncd /d "C:\\root dir"\r\n'))
        self.assertIn("rem ---- BX3691 ----\r\n", s)
        self.assertIn('mkdir "BX3691\\1\\1.00001-BX3691"\r\n', s)
        self.assertIn('mkdir "BX3692\\1\\3.00006-BX3692"\r\n', s)
        self.assertEqual(s.count("mkdir "), 6)


class DbRowTests(unittest.TestCase):
    def test_rows_match_procedure(self):
        b = batch()
        rows = InventoryRowMapper("LabelsSum", "VIN123").to_rows(b)
        self.assertEqual(len(rows), 6)
        r = dict(zip(DB_COLUMNS, rows[0]))
        self.assertEqual(r, {
            "EbayAccount": "LabelsSum", "StockId": "1.00001-BX3691", "ShortName": "& LabelsSum",
            "LongName": "& LabelsSum", "StockCategory": "PART", "StockStatus": "1_staging",
            "StockCondition": "USED", "LotId": "1.00001-BX3691", "LotLocation": "BX3691", "CreatedBy": 1,
            "CreatedOn": b.created_on, "PartAccountVin": "VIN123",
        })
        self.assertIsNone(InventoryRowMapper("X", "").to_rows(b)[0][-1])   # empty VIN -> NULL
        self.assertFalse(any(row[1].startswith("0.") for row in rows))      # no junk "0. -BOX" row

    def test_csv(self):
        text = CsvFormatter(InventoryRowMapper("LabelsSum")).format(batch())
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(tuple(rows[0]), DB_COLUMNS)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[1][1], "1.00001-BX3691")
        self.assertIn("\r\n", text)


if __name__ == "__main__":
    unittest.main()
