import re
import unittest
from datetime import datetime

from labelgen.domain import (
    BoxId, BoxRange, LabelBatch, LabelGenerator, RandomGuidProvider, SequenceGuidProvider, box_range, staging_root,
)

LABEL_RE = re.compile(r"^\d{1,3}\.[0-9A-F]{5}-[A-Z]+\d+$")


class BoxTests(unittest.TestCase):
    def test_start_end_inclusive(self):
        b = box_range("BX3718", "BX3738")
        self.assertEqual(len(b), 21)
        self.assertEqual((b[0], b[-1]), ("BX3718", "BX3738"))

    def test_count(self):
        self.assertEqual(box_range("BX3718", count=3), ["BX3718", "BX3719", "BX3720"])

    def test_lowercase_and_spaces(self):
        self.assertEqual(box_range(" bx3718 ", "bx3719"), ["BX3718", "BX3719"])

    def test_zero_padding_kept(self):
        self.assertEqual(box_range("BX0099", count=2), ["BX0099", "BX0100"])

    def test_single_box(self):
        self.assertEqual(box_range("BX3718", "BX3718"), ["BX3718"])
        self.assertEqual(box_range("BX3718"), ["BX3718"])

    def test_box_id(self):
        b = BoxId.parse("bx0099")
        self.assertEqual((b.prefix, b.number, b.width, str(b)), ("BX", 99, 4, "BX0099"))
        self.assertEqual(len(BoxRange.from_text("BX1", "BX10")), 10)

    def test_errors(self):
        for args in [("BX5", "AB9"), ("BX9", "BX1"), ("xx", None), ("", None), ("BX1", "BX9999")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                box_range(*args)


class GeneratorTests(unittest.TestCase):
    def test_counts_format_and_order(self):
        batch = LabelGenerator().generate(box_range("BX3691", "BX3693"), 28)
        self.assertEqual(len(batch), 84)
        self.assertEqual(batch.boxes, ["BX3691", "BX3692", "BX3693"])
        for label in batch.labels:
            self.assertRegex(label.text, LABEL_RE)
        for box, labels in batch.labels_by_box.items():
            self.assertEqual([l.seq for l in labels], list(range(1, 29)))
            self.assertTrue(all(l.text.endswith("-" + box) for l in labels))

    def test_codes_unique_and_avoid(self):
        batch = LabelGenerator().generate(["BX1", "BX2"], 200)
        codes = [l.guid5 for l in batch.labels]
        self.assertEqual(len(codes), len(set(codes)))
        again = LabelGenerator().generate(["BX3"], 50, avoid=set(codes))
        self.assertFalse({l.guid5 for l in again.labels} & set(codes))

    def test_duplicate_codes_are_skipped(self):
        gen = LabelGenerator(SequenceGuidProvider(["AAAAA", "AAAAA", "BBBBB"]))
        self.assertEqual([l.text for l in gen.generate(["BX1"], 2).labels], ["1.AAAAA-BX1", "2.BBBBB-BX1"])

    def test_gives_up_instead_of_looping_forever(self):
        gen = LabelGenerator(SequenceGuidProvider(["AAAAA"] * 2000))
        with self.assertRaises(RuntimeError):
            gen.generate(["BX1"], 2)

    def test_per_box_must_be_positive(self):
        with self.assertRaises(ValueError):
            LabelGenerator().generate(["BX1"], 0)

    def test_clock_and_tags(self):
        when = datetime(2026, 11, 11, 9, 5, 7)
        batch = LabelGenerator(clock=lambda: when).generate(["BX3718", "BX3719"], 1)
        self.assertEqual(batch.created_on, when)
        self.assertEqual(batch.range_tag, "BX3718-BX3719")
        self.assertEqual(batch.file_tag, "BX3718-BX3719_20261111_090507")
        self.assertEqual(LabelBatch({"BX1": []}).range_tag, "BX1")

    def test_random_provider(self):
        code = RandomGuidProvider().next()
        self.assertRegex(code, r"^[0-9A-F]{5}$")


class LocationTests(unittest.TestCase):
    def test_staging_root(self):
        r = staging_root("C:\\Users\\ablak\\MorrisAutoGroup Dropbox\\Alexander Blake\\", "LabelsSum")
        self.assertEqual(r, "C:\\Users\\ablak\\MorrisAutoGroup Dropbox\\Alexander Blake\\MorrisUniversalAutoGroup"
                            "\\PartsSale\\Production\\Current\\0_staging\\LabelsSum")


if __name__ == "__main__":
    unittest.main()
