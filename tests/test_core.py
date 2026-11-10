import re
import unittest

import label_core as core

LABEL_RE = re.compile(r"^\d{1,3}\.[0-9A-F]{5}-[A-Z]+\d+$")


class BoxRangeTests(unittest.TestCase):
    def test_start_end_inclusive(self):
        b = core.box_range("BX3718", "BX3738")
        self.assertEqual(len(b), 21)
        self.assertEqual((b[0], b[-1]), ("BX3718", "BX3738"))

    def test_count(self):
        self.assertEqual(core.box_range("BX3718", count=3), ["BX3718", "BX3719", "BX3720"])

    def test_lowercase_and_spaces(self):
        self.assertEqual(core.box_range(" bx3718 ", "bx3719"), ["BX3718", "BX3719"])

    def test_zero_padding_kept(self):
        self.assertEqual(core.box_range("BX0099", count=2), ["BX0099", "BX0100"])

    def test_single_box(self):
        self.assertEqual(core.box_range("BX3718", "BX3718"), ["BX3718"])

    def test_errors(self):
        for args in [("BX5", "AB9"), ("BX9", "BX1"), ("xx", None), ("", None), ("BX1", "BX9999")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                core.box_range(*args)


class LabelTests(unittest.TestCase):
    def setUp(self):
        self.lb = core.generate_labels(core.box_range("BX3691", "BX3693"), 28)
        self.all = [l for v in self.lb.values() for l in v]

    def test_counts_and_format(self):
        self.assertEqual(len(self.all), 84)
        for l in self.all:
            self.assertRegex(l.text, LABEL_RE)

    def test_sequence_restarts_per_box(self):
        for box, labels in self.lb.items():
            self.assertEqual([l.seq for l in labels], list(range(1, 29)))
            self.assertTrue(all(l.text.endswith("-" + box) for l in labels))

    def test_guid5_unique_and_avoid(self):
        g = [l.guid5 for l in self.all]
        self.assertEqual(len(g), len(set(g)))
        again = core.generate_labels(["BX1"], 50, avoid=set(g))
        self.assertFalse({l.guid5 for l in again["BX1"]} & set(g))

    def test_per_box_must_be_positive(self):
        with self.assertRaises(ValueError):
            core.generate_labels(["BX1"], 0)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.lb = core.generate_labels(core.box_range("BX3691", "BX3692"), 3)

    def test_print_list_layout(self):
        lines = core.labels_text(self.lb).splitlines()
        sep1, sep2 = core.BOX_SEPARATOR
        self.assertEqual(lines[0], "  !-                          -!")
        self.assertEqual(sep1, " !-                          -!")
        self.assertEqual(sep2, "  !-                          -!")
        # header, 3 labels, 2 separators, 3 labels, 2 separators
        self.assertEqual(len(lines), 1 + 3 + 2 + 3 + 2)
        self.assertEqual(lines[1:4], [l.text for l in self.lb["BX3691"]])
        self.assertEqual(lines[4:6], [sep1, sep2])
        self.assertEqual(lines[6:9], [l.text for l in self.lb["BX3692"]])
        self.assertEqual(lines[9:], [sep1, sep2])

    def test_root_folder(self):
        r = core.root_folder("C:\\Users\\ablak\\MorrisAutoGroup Dropbox\\Alexander Blake\\", "LabelsSum")
        self.assertEqual(r, "C:\\Users\\ablak\\MorrisAutoGroup Dropbox\\Alexander Blake\\MorrisUniversalAutoGroup"
                            "\\PartsSale\\Production\\Current\\0_staging\\LabelsSum")

    def test_mkdir_script(self):
        s = core.mkdir_script(self.lb, "C:\\root dir", "1")
        self.assertIn('cd /d "C:\\root dir"', s)
        first = self.lb["BX3691"][0].text
        self.assertIn(f'mkdir "BX3691\\1\\{first}"', s)
        self.assertEqual(s.count("mkdir "), 6)
        self.assertIn("\r\n", s)

    def test_db_rows_match_procedure(self):
        rows = core.db_rows(self.lb, "LabelsSum", "VIN123", created_by=1)
        self.assertEqual(len(rows), 6)
        r = dict(zip(core.DB_COLUMNS, rows[0]))
        self.assertEqual(r["EbayAccount"], "LabelsSum")
        self.assertEqual(r["ShortName"], "& LabelsSum")
        self.assertEqual(r["LongName"], "& LabelsSum")
        self.assertEqual((r["StockCategory"], r["StockStatus"], r["StockCondition"]), ("PART", "1_staging", "USED"))
        self.assertEqual(r["StockId"], r["LotId"])
        self.assertEqual(r["LotLocation"], "BX3691")
        self.assertEqual(r["PartAccountVin"], "VIN123")
        self.assertIsNone(core.db_rows(self.lb, "X", "")[0][-1])  # empty VIN -> NULL
        # no junk "0. -BOX" row like the stored procedure's blank row
        self.assertFalse(any(row[1].startswith("0.") for row in rows))


if __name__ == "__main__":
    unittest.main()
