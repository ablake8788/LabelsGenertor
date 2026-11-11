import shutil
import tempfile
import unittest
from pathlib import Path

from labelgen.infrastructure import InMemoryLabelRepository, RecordingShell
from labelgen.services import (
    CreateFoldersStep, GenerateStep, JobSettings, Pipeline, RunContext, SaveFilesStep, SaveToDatabaseStep,
    build_run_all_pipeline,
)
from tests.fakes import FakeView, make_container


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = InMemoryLabelRepository()
        self.shell = RecordingShell()
        self.c = make_container(self.tmp, self.repo, self.shell)
        self.service = self.c.service

    def job(self, **form):
        return JobSettings.from_form(FakeView(self.tmp, **form).get_form())

    @property
    def staging(self):
        return Path(self.job().staging_root)


class JobSettingsTests(ServiceTestCase):
    def test_from_form(self):
        job = self.job(box_step="", use_db="1", per_box=" 28 ")
        self.assertEqual((job.box_step, job.use_db, job.per_box), ("1", True, 28))
        self.assertTrue(job.staging_root.endswith("0_staging\\LabelsSum"))

    def test_bad_per_box(self):
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.job(per_box="abc")

    def test_print_list_folder_falls_back_to_output(self):
        self.assertEqual(self.job(labels_folder="").print_list_folder, str(self.tmp / "files"))


class LabelServiceTests(ServiceTestCase):
    def test_generate_requires_account(self):
        with self.assertRaisesRegex(ValueError, "Account"):
            self.service.generate(self.job(account=" "))

    def test_files_go_to_two_folders(self):
        job = self.job()
        batch = self.service.generate(job)
        txt, bat, csv = self.service.save_files(batch, job)
        self.assertEqual(txt.parent, self.tmp / "labels_list")
        self.assertEqual({bat.parent, csv.parent}, {self.tmp / "files"})
        self.assertEqual(txt.read_text(encoding="utf-8"), self.service.print_list(batch))

    def test_save_to_db_uses_form_account_and_vin(self):
        job = self.job(vin="VIN9")
        batch = self.service.generate(job)
        self.assertEqual(self.service.save_to_db(batch, job), 84)
        self.assertEqual({(r[0], r[11]) for r in self.repo.rows}, {("LabelsSum", "VIN9")})
        self.assertEqual(self.service.existing_boxes(["BX3718", "BX9999"]), {"BX3718": 28})


class PipelineTests(ServiceTestCase):
    class Listener:
        def __init__(self):
            self.events = []

        def step_started(self, step):
            self.events.append(("start", step.name))

        def step_finished(self, step, message):
            self.events.append(("done", step.name))

        def step_failed(self, step, message):
            self.events.append(("fail", step.name))

    def test_run_all_with_db(self):
        listener = self.Listener()
        ctx = RunContext(self.job(), self.service)
        report = build_run_all_pipeline(True, self.shell, [listener]).run(ctx)
        self.assertTrue(report.ok, report.error)
        self.assertEqual(report.done[0], "Generated 84 labels")
        self.assertEqual(report.done[1], "Created 84 folders")
        self.assertTrue(report.done[2].startswith("Saved print list: labels_BX3718-BX3720_"))
        self.assertEqual(report.done[3], "Saved 84 rows to the database")
        self.assertEqual(self.shell.opened, [ctx.print_list_path])   # print list opened for printing
        self.assertEqual(len(self.repo.rows), 84)
        self.assertEqual([e[0] for e in listener.events], ["start", "done"] * 4)

    def test_without_db_has_three_steps(self):
        p = build_run_all_pipeline(False)
        self.assertEqual([type(s) for s in p.steps], [GenerateStep, CreateFoldersStep, SaveFilesStep])
        self.assertIsInstance(build_run_all_pipeline(True).steps[-1], SaveToDatabaseStep)

    def test_stops_at_first_failure(self):
        self.repo.fail_insert = RuntimeError("timeout")
        listener = self.Listener()
        ctx = RunContext(self.job(), self.service)
        report = build_run_all_pipeline(True, self.shell, [listener]).run(ctx)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.done), 3)
        self.assertIn("Database save FAILED", report.error)
        self.assertIn("timeout", report.error)
        self.assertEqual(listener.events[-1], ("fail", "Save to database"))
        self.assertIsNotNone(ctx.batch)   # batch kept for a retry

    def test_generate_failure_message(self):
        report = Pipeline([GenerateStep(), CreateFoldersStep()]).run(RunContext(self.job(account=""), self.service))
        self.assertEqual(report.done, [])
        self.assertTrue(report.error.startswith("Check settings:"))
        self.assertFalse(self.staging.exists())

    def test_open_failure_is_not_an_error(self):
        ctx = RunContext(self.job(), self.service)
        report = build_run_all_pipeline(False, RecordingShell(fail=OSError("no notepad"))).run(ctx)
        self.assertTrue(report.ok, report.error)


if __name__ == "__main__":
    unittest.main()
