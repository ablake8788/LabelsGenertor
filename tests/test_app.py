"""App workflow tests: Run all, Save labels list, Print, Clear fields - without opening a window."""
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from tests import fake_tk

fake_tk.install()  # must happen before label_app is imported
import label_app as A  # noqa: E402
import label_db  # noqa: E402


def make_app(tmp: Path, start="BX3718", end="BX3720"):
    o = A.LabelApp.__new__(A.LabelApp)
    o.vars = {k: fake_tk.Var(v) for k, v in A.DEFAULTS.items()}
    o.vars["start_box"].set(start)
    o.vars["end_box"].set(end)
    o.vars["output_folder"].set(str(tmp / "files"))
    o.vars["labels_folder"].set(str(tmp / "labels_list"))
    o.vars["use_db"].set("0")
    o.count_var = fake_tk.Var("")
    o.labels_by_box, o.generated_at, o.saved_to_db, o.labels_path, o._syncing = {}, None, False, None, False
    o.status = fake_tk.Var("")
    o.tree = types.SimpleNamespace(delete=lambda *a: None, get_children=lambda: [], insert=lambda *a, **k: None)
    o.txt_labels = o.txt_script = None
    o._set_text = lambda w, t: None
    o._root_path = lambda: str(tmp / "staging" / "LabelsSum")
    o._open_file = lambda p: None   # don't open Notepad during tests
    return o


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        fake_tk.LOG.clear()
        fake_tk.ANSWER[0] = True
        self.inserted = []
        p1 = mock.patch.object(label_db, "existing_boxes", lambda c, b: {})
        p2 = mock.patch.object(label_db, "insert_rows", lambda c, rows: (self.inserted.extend(rows), len(rows))[1])
        p3 = mock.patch.object(A.LabelApp, "_conn_str", lambda self: "FAKE")
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def errors(self):
        return [m for m in fake_tk.LOG if m[0] == "error"]

    def test_run_all_without_db(self):
        o = make_app(self.tmp)
        o.run_all()
        self.assertEqual(self.errors(), [])
        folders = [p for p in (self.tmp / "staging" / "LabelsSum").glob("*/1/*") if p.is_dir()]
        self.assertEqual(len(folders), 84)
        self.assertEqual(len(list((self.tmp / "labels_list").glob("labels_BX3718-BX3720_*.txt"))), 1)
        self.assertEqual(len(list((self.tmp / "files").glob("create_folders_*.bat"))), 1)
        self.assertEqual(len(list((self.tmp / "files").glob("db_rows_*.csv"))), 1)
        self.assertEqual(self.inserted, [])
        self.assertIn("All done", fake_tk.LOG[-1][2])

    def test_run_all_with_db(self):
        o = make_app(self.tmp)
        o.vars["use_db"].set("1")
        o.run_all()
        self.assertEqual(self.errors(), [])
        self.assertEqual(len(self.inserted), 84)
        self.assertTrue(o.saved_to_db)
        # the folders, print list and database rows all use the same labels
        printed = (o.labels_path).read_text(encoding="utf-8")
        for row in self.inserted:
            self.assertIn(row[1], printed)
            self.assertTrue((self.tmp / "staging" / "LabelsSum" / row[8] / "1" / row[1]).is_dir())

    def test_run_all_cancel_creates_nothing(self):
        fake_tk.ANSWER[0] = False
        o = make_app(self.tmp)
        o.run_all()
        self.assertFalse((self.tmp / "staging").exists())
        self.assertEqual(o.labels_by_box, {})

    def test_run_all_db_unreachable_creates_nothing(self):
        o = make_app(self.tmp)
        o.vars["use_db"].set("1")
        with mock.patch.object(label_db, "existing_boxes", side_effect=RuntimeError("no server")):
            o.run_all()
        self.assertTrue(self.errors())
        self.assertFalse((self.tmp / "staging").exists())

    def test_run_all_warns_about_existing_boxes(self):
        o = make_app(self.tmp)
        o.vars["use_db"].set("1")
        with mock.patch.object(label_db, "existing_boxes", lambda c, b: {"BX3718": 28}):
            o.run_all()
        ask = [m for m in fake_tk.LOG if m[0] == "ask"][0]
        self.assertIn("BX3718: 28 rows", ask[2])

    def test_db_failure_keeps_batch_for_retry(self):
        o = make_app(self.tmp)
        o.vars["use_db"].set("1")
        with mock.patch.object(label_db, "insert_rows", side_effect=RuntimeError("timeout")):
            o.run_all()
        self.assertTrue(self.errors())
        self.assertFalse(o.saved_to_db)
        batch = dict(o.labels_by_box)
        o.save_to_db()  # retry with the normal insert
        self.assertEqual(o.labels_by_box, batch)
        self.assertEqual(len(self.inserted), 84)

    def test_save_labels_list(self):
        o = make_app(self.tmp, "BX3800", "BX3800")
        o.generate()
        o.save_labels_list()
        files = list((self.tmp / "labels_list").glob("labels_BX3800_*.txt"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1 + 28 + 2)

    def test_print_uses_current_batch(self):
        o = make_app(self.tmp)
        o.generate()
        first = o.labels_by_box
        with mock.patch.object(A.os, "startfile", create=True) as sf:
            o.print_labels()
            self.assertEqual(sf.call_args[0][1], "print")
            printed = Path(sf.call_args[0][0]).read_text(encoding="utf-8")
        self.assertIn(first["BX3718"][0].text, printed)
        o.generate()  # new batch must not reuse the old print file
        self.assertIsNone(o.labels_path)

    def test_clear_fields(self):
        o = make_app(self.tmp)
        o.generate()
        o.clear_fields()
        self.assertEqual((o.vars["start_box"].get(), o.vars["end_box"].get()), ("", ""))
        self.assertEqual(o.labels_by_box, {})
        self.assertIsNone(o.labels_path)
        self.assertEqual(o.vars["account"].get(), "LabelsSum")  # settings kept

    def test_bad_range_shows_error(self):
        o = make_app(self.tmp, "BX3720", "BX3718")
        o.run_all()
        self.assertTrue(self.errors())
        self.assertFalse((self.tmp / "staging").exists())


class SelfTestTests(unittest.TestCase):
    def test_self_test_passes(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "config.ini").write_text("[database]\nconnection_string = DSN=x;\n", encoding="utf-8")
        with mock.patch.object(A, "APP_DIR", tmp), \
             mock.patch.dict("sys.modules", {"pyodbc": types.SimpleNamespace(version="test", drivers=lambda: [])}):
            code = A.self_test(check_db=False)
        log = (tmp / "selftest.log").read_text(encoding="utf-8")
        self.assertEqual(code, 0, log)
        self.assertIn("RESULT: PASSED", log)


if __name__ == "__main__":
    unittest.main()
