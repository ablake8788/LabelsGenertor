"""Every button's behaviour, through the controller with a fake window."""
import shutil
import tempfile
import unittest
from pathlib import Path

from labelgen.infrastructure import InMemoryLabelRepository, RecordingShell
from labelgen.services import JobSettings
from labelgen.ui import LabelController
from tests.fakes import FakeView, make_container


class ControllerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = InMemoryLabelRepository()
        self.shell = RecordingShell()
        self.c = make_container(self.tmp, self.repo, self.shell)
        self.view = FakeView(self.tmp)
        self.ctl = LabelController(self.view, self.c.service, self.c.config, self.shell, drivers=lambda: ["ODBC Driver 17 for SQL Server"])

    @property
    def staging(self) -> Path:
        return Path(JobSettings.from_form(self.view.get_form()).staging_root)

    def label_folders(self):
        return [p for p in self.staging.glob("*/1/*") if p.is_dir()]


class FormHelperTests(ControllerTestCase):
    def test_linked_fields(self):
        self.assertEqual(LabelController.count_for("BX3718", "BX3738"), "21")
        self.assertIsNone(LabelController.count_for("BX3718", "BX37"))
        self.assertEqual(LabelController.end_for("BX3718", "3"), "BX3720")
        self.assertIsNone(LabelController.end_for("BX3718", ""))
        self.assertTrue(LabelController.root_preview("C:\\x", "LabelsSum").endswith("0_staging\\LabelsSum"))


class RunAllTests(ControllerTestCase):
    def test_without_db(self):
        self.ctl.run_all()
        self.assertEqual(self.view.kinds("error"), [])
        self.assertEqual(len(self.label_folders()), 84)
        self.assertEqual(len(list((self.tmp / "labels_list").glob("labels_BX3718-BX3720_*.txt"))), 1)
        self.assertEqual(len(list((self.tmp / "files").glob("create_folders_*.bat"))), 1)
        self.assertEqual(len(list((self.tmp / "files").glob("db_rows_*.csv"))), 1)
        self.assertEqual(self.repo.rows, [])
        self.assertIn("All done", self.view.last[2])
        self.assertEqual(len(self.shell.opened), 1)
        self.assertIsNotNone(self.view.batch_shown)

    def test_with_db_everything_matches(self):
        self.view.form["use_db"] = "1"
        self.ctl.run_all()
        self.assertEqual(self.view.kinds("error"), [])
        self.assertEqual(len(self.repo.rows), 84)
        self.assertTrue(self.ctl.session.saved_to_db)
        printed = self.ctl.session.print_list_path.read_text(encoding="utf-8")
        for row in self.repo.rows:     # folders, print list and database rows use the same labels
            self.assertIn(row[1], printed)
            self.assertTrue((self.staging / row[8] / "1" / row[1]).is_dir())

    def test_status_bar_follows_steps(self):
        self.ctl.run_all()
        self.assertIn("Generate labels…", self.view.statuses)
        self.assertIn("Created 84 folders", self.view.statuses)

    def test_cancel_creates_nothing(self):
        self.view.answers = [False]
        self.ctl.run_all()
        self.assertFalse(self.staging.exists())
        self.assertIsNone(self.ctl.session.batch)

    def test_db_unreachable_creates_nothing(self):
        self.view.form["use_db"] = "1"
        self.repo.fail_read = RuntimeError("no server")
        self.ctl.run_all()
        self.assertIn("Can't reach the database", self.view.kinds("error")[0][2])
        self.assertFalse(self.staging.exists())

    def test_warns_about_existing_boxes(self):
        self.view.form["use_db"] = "1"
        self.repo.existing = {"BX3718": 28}
        self.ctl.run_all()
        ask = self.view.kinds("ask-warning")[0]
        self.assertIn("BX3718: 28 rows", ask[2])

    def test_db_failure_keeps_batch_for_retry(self):
        self.view.form["use_db"] = "1"
        self.repo.fail_insert = RuntimeError("timeout")
        self.ctl.run_all()
        self.assertIn("Database save FAILED", self.view.kinds("error")[0][2])
        self.assertFalse(self.ctl.session.saved_to_db)
        batch = self.ctl.session.batch
        self.repo.fail_insert = None
        self.ctl.save_to_db()                       # retry the SAME batch
        self.assertIs(self.ctl.session.batch, batch)
        self.assertEqual(len(self.repo.rows), 84)
        self.assertTrue(self.ctl.session.saved_to_db)

    def test_bad_range(self):
        self.view.form.update(start_box="BX3720", end_box="BX3718")
        self.ctl.run_all()
        self.assertEqual(self.view.kinds("error")[0][1], "Check settings")
        self.assertFalse(self.staging.exists())

    def test_missing_account_reported(self):
        self.view.form["account"] = ""
        self.ctl.run_all()
        self.assertIn("Account folder is required", self.view.kinds("error")[0][2])


class ButtonTests(ControllerTestCase):
    def test_buttons_need_a_batch_first(self):
        for action in (self.ctl.create_folders, self.ctl.save_files, self.ctl.save_labels_list,
                       self.ctl.copy_labels, self.ctl.print_labels, self.ctl.save_to_db):
            self.view.dialogs.clear()
            action()
            self.assertEqual(self.view.last[1], "Nothing yet")

    def test_generate_shows_batch(self):
        self.assertTrue(self.ctl.generate())
        print_list, script, rows = self.view.batch_shown
        self.assertEqual(len(rows), 84)
        self.assertNotIn("\r\n", script)
        self.assertTrue(print_list.startswith("  !-"))
        self.assertIn("Not saved to the database yet", self.view.statuses[-1])

    def test_generate_bad_per_box(self):
        self.view.form["per_box"] = "x"
        self.assertFalse(self.ctl.generate())
        self.assertEqual(self.view.last[0], "error")

    def test_create_folders(self):
        self.ctl.generate()
        self.ctl.create_folders()
        self.assertEqual(len(self.label_folders()), 84)

    def test_create_folders_cancel(self):
        self.ctl.generate()
        self.view.answers = [False]
        self.ctl.create_folders()
        self.assertFalse(self.staging.exists())

    def test_save_labels_list(self):
        self.view.form.update(start_box="BX3800", end_box="BX3800")
        self.ctl.generate()
        self.ctl.save_labels_list()
        files = list((self.tmp / "labels_list").glob("labels_BX3800_*.txt"))
        self.assertEqual(len(files), 1)
        self.assertEqual(len(files[0].read_text(encoding="utf-8").splitlines()), 1 + 28 + 2)

    def test_save_files(self):
        self.ctl.generate()
        self.ctl.save_files()
        self.assertEqual(self.view.last[1], "Saved")
        self.assertEqual(len(list((self.tmp / "files").iterdir())), 2)

    def test_copy_labels(self):
        self.ctl.generate()
        self.ctl.copy_labels()
        self.assertEqual(self.view.clipboard, self.view.batch_shown[0])

    def test_print_uses_current_batch(self):
        self.ctl.generate()
        first = self.ctl.session.batch.labels[0].text
        self.ctl.print_labels()
        self.assertEqual(len(self.shell.printed), 1)
        self.assertIn(first, self.shell.printed[0].read_text(encoding="utf-8"))
        self.ctl.generate()                          # a new batch must not reuse the old print file
        self.assertIsNone(self.ctl.session.print_list_path)

    def test_print_failure_tells_where_the_file_is(self):
        self.shell.fail = OSError("no printer")
        self.ctl.generate()
        self.ctl.print_labels()
        self.assertIn("The list is saved here", self.view.last[2])

    def test_clear_fields(self):
        self.ctl.generate()
        self.ctl.clear_fields()
        self.assertEqual((self.view.form["start_box"], self.view.form["end_box"]), ("", ""))
        self.assertIsNone(self.ctl.session.batch)
        self.assertIsNone(self.view.batch_shown)
        self.assertEqual(self.view.form["account"], "LabelsSum")   # settings kept

    def test_clear_fields_asks_when_not_saved_to_db(self):
        self.view.form["use_db"] = "1"
        self.ctl.generate()
        self.view.answers = [False]
        self.ctl.clear_fields()
        self.assertIsNotNone(self.ctl.session.batch)

    def test_save_to_db_once(self):
        self.ctl.generate()
        self.ctl.save_to_db()
        self.assertEqual(self.view.last, ("info", "Database", "Saved 84 rows."))
        self.ctl.save_to_db()
        self.assertEqual(self.view.last[1], "Already saved")
        self.assertEqual(len(self.repo.rows), 84)


class BatchStateTests(ControllerTestCase):
    def test_badges_follow_each_step(self):
        self.ctl.generate()
        st = self.view.batch_state
        self.assertEqual((st.boxes, st.labels, st.first_box, st.last_box), (3, 84, "BX3718", "BX3720"))
        self.assertEqual((st.folders_created, st.print_list_saved, st.saved_to_db), (False, False, False))
        self.ctl.create_folders()
        self.assertTrue(self.view.batch_state.folders_created)
        self.ctl.save_labels_list()
        self.assertTrue(self.view.batch_state.print_list_saved)
        self.ctl.save_to_db()
        self.assertTrue(self.view.batch_state.saved_to_db)
        self.ctl.clear_fields()
        self.assertIsNone(self.view.batch_state)

    def test_run_all_marks_all_steps(self):
        self.view.form["use_db"] = "1"
        self.ctl.run_all()
        st = self.view.batch_state
        self.assertEqual((st.folders_created, st.print_list_saved, st.saved_to_db), (True, True, True))

    def test_run_all_db_failure_marks_only_done_steps(self):
        self.view.form["use_db"] = "1"
        self.repo.fail_insert = RuntimeError("timeout")
        self.ctl.run_all()
        st = self.view.batch_state
        self.assertEqual((st.folders_created, st.print_list_saved, st.saved_to_db), (True, True, False))

    def test_new_batch_resets_badges(self):
        self.ctl.generate()
        self.ctl.create_folders()
        self.ctl.generate()
        self.assertFalse(self.view.batch_state.folders_created)


class ConnectionTabTests(ControllerTestCase):
    def test_db_badge_states(self):
        self.ctl.refresh_connection_preview()
        self.assertEqual(self.view.db_state, "not_set_up")
        self.c.config.path.write_text("[database]\nconnection_string = DSN=x;\n", encoding="utf-8")
        self.ctl.refresh_connection_preview()
        self.assertEqual(self.view.db_state, "configured")
        self.ctl.test_connection()
        self.assertEqual(self.view.db_state, "connected")
        self.repo.fail_read = RuntimeError("down")
        self.ctl.test_connection()
        self.assertEqual(self.view.db_state, "failed")

    def test_preview_not_set_up(self):
        self.ctl.refresh_connection_preview()
        self.assertTrue(self.view.preview.startswith("Not set up yet"))

    def test_preview_masks_password(self):
        self.c.config.ensure()
        self.c.config.path.write_text("[database]\nconnection_string = UID=u;PWD=secret;\n", encoding="utf-8")
        self.ctl.refresh_connection_preview()
        self.assertEqual(self.view.preview, "UID=u;PWD=*****;")

    def test_test_connection(self):
        self.ctl.test_connection()
        self.assertEqual(self.view.last, ("info", "Database", "Connection OK."))
        self.repo.fail_read = RuntimeError("login failed")
        self.ctl.test_connection()
        self.assertIn("login failed", self.view.last[2])
        self.assertIn("ODBC Driver 17 for SQL Server", self.view.last[2])

    def test_open_config(self):
        self.ctl.open_config()
        self.assertEqual(self.shell.opened, [self.c.config.path])


if __name__ == "__main__":
    unittest.main()
