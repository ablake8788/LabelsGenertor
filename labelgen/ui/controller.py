"""
LabelController - the presenter. Every button in the window calls one method here.

It reads the form through the view, asks the LabelService to do the work, and tells the
view what to show. It never imports tkinter.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from labelgen.domain.boxes import box_range
from labelgen.domain.locations import staging_root
from labelgen.domain.models import LabelBatch
from labelgen.infrastructure.config import IniConfigLoader, masked
from labelgen.infrastructure.repository import installed_sql_drivers
from labelgen.infrastructure.shell import Shell
from labelgen.services.job import JobSettings
from labelgen.services.label_service import LabelService
from labelgen.services.pipeline import RunContext, Step, build_run_all_pipeline
from labelgen.ui.view import BatchState, LabelView


@dataclass
class Session:
    """The batch currently on screen."""

    batch: LabelBatch | None = None
    print_list_path: Path | None = None
    folders_created: bool = False
    saved_to_db: bool = False


class _StatusListener:
    """Observer: shows each Run all step in the status bar as it happens."""

    def __init__(self, view: LabelView):
        self.view = view

    def step_started(self, step: Step) -> None:
        self.view.set_status(f"{step.name}…")

    def step_finished(self, step: Step, message: str) -> None:
        self.view.set_status(message)

    def step_failed(self, step: Step, message: str) -> None:
        self.view.set_status(f"{step.name} failed")


class LabelController:
    def __init__(self, view: LabelView, service: LabelService, config: IniConfigLoader, shell: Shell,
                 drivers: Callable[[], list[str] | None] = installed_sql_drivers):
        self.view = view
        self.service = service
        self.config = config
        self.shell = shell
        self._drivers = drivers
        self.session = Session()

    # ------------------------------------------------------------------ helpers for the form (no dialogs)
    @staticmethod
    def count_for(start: str, end: str) -> str | None:
        """'Number of boxes' for a start/end box, or None while the input is incomplete."""
        try:
            return str(len(box_range(start, end)))
        except ValueError:
            return None

    @staticmethod
    def end_for(start: str, count: str) -> str | None:
        """'End box' for a start box and a number of boxes, or None while the input is incomplete."""
        try:
            return box_range(start, count=int(count))[-1]
        except (ValueError, TypeError):
            return None

    @staticmethod
    def root_preview(env_folder: str, account: str) -> str:
        return staging_root(env_folder, account)

    # ------------------------------------------------------------------ internals
    def _job(self) -> JobSettings | None:
        try:
            return JobSettings.from_form(self.view.get_form())
        except ValueError as e:
            self.view.show_error("Check settings", str(e))
            return None

    def _batch_or_tell(self) -> LabelBatch | None:
        if not self.session.batch:
            self.view.show_info("Nothing yet", "Click Generate labels first.")
        return self.session.batch

    def _show(self, batch: LabelBatch, job: JobSettings) -> None:
        self.session = Session(batch=batch)
        self.view.show_batch(self.service.print_list(batch),
                             self.service.folder_script(batch, job).replace("\r\n", "\n"),
                             self.service.rows(batch, job))
        self._publish()

    def _publish(self) -> None:
        """Tell the view which steps are done for the batch on screen."""
        s, b = self.session, self.session.batch
        self.view.set_batch_state(None if not b else BatchState(
            boxes=len(b.boxes), labels=len(b), first_box=b.boxes[0], last_box=b.boxes[-1],
            folders_created=s.folders_created, print_list_saved=s.print_list_path is not None,
            saved_to_db=s.saved_to_db))

    @staticmethod
    def _existing_warning(existing: dict[str, int], intro: str) -> str:
        if not existing:
            return ""
        return f"\n\n{intro}\n" + "\n".join(f"  {b}: {n} rows" for b, n in existing.items())

    # ------------------------------------------------------------------ buttons
    def generate(self) -> bool:
        job = self._job()
        if not job:
            return False
        try:
            batch = self.service.generate(job)
        except ValueError as e:
            self.view.show_error("Check settings", str(e))
            return False
        self._show(batch, job)
        self.view.set_status(f"Generated {len(batch)} labels for {len(batch.boxes)} boxes "
                             f"({batch.boxes[0]} – {batch.boxes[-1]}). Not saved to the database yet.")
        return True

    def create_folders(self) -> None:
        batch = self._batch_or_tell()
        if not batch or not (job := self._job()):
            return
        if not self.view.ask_yes_no("Create folders", f"Create {len(batch)} folders under:\n\n{job.staging_root}?"):
            return
        try:
            made = self.service.create_folders(batch, job)
        except OSError as e:
            self.view.show_error("Folder error", str(e))
            return
        self.session.folders_created = True
        self._publish()
        self.view.set_status(f"Created {made} folders under {job.staging_root}")

    def save_files(self) -> None:
        batch = self._batch_or_tell()
        if not batch or not (job := self._job()):
            return
        try:
            paths = self.service.save_files(batch, job)
        except OSError as e:
            self.view.show_error("File error", str(e))
            return
        self.session.print_list_path = paths[0]
        self._publish()
        self.view.set_status(f"Saved labels list to {paths[0].parent} and 2 files to {paths[1].parent}")
        self.view.show_info("Saved", "Saved:\n\n" + "\n".join(str(p) for p in paths))

    def save_labels_list(self) -> None:
        batch = self._batch_or_tell()
        if not batch or not (job := self._job()):
            return
        try:
            path = self.service.save_print_list(batch, job)
        except OSError as e:
            self.view.show_error("Save labels list", str(e))
            return
        self.session.print_list_path = path
        self._publish()
        self.view.set_status(f"Labels list saved: {path}")
        self.view.show_info("Save labels list", f"Saved:\n\n{path}")

    def copy_labels(self) -> None:
        batch = self._batch_or_tell()
        if not batch:
            return
        self.view.set_clipboard(self.service.print_list(batch))
        self.view.set_status("Labels copied to clipboard.")

    def print_labels(self) -> None:
        batch = self._batch_or_tell()
        if not batch or not (job := self._job()):
            return
        path = self.session.print_list_path
        try:
            if not (path and path.exists()):
                path = self.session.print_list_path = self.service.save_print_list(batch, job)
                self._publish()
        except OSError as e:
            self.view.show_error("Print", str(e))
            return
        if not self.view.ask_yes_no("Print labels", f"Print {len(batch)} labels to your default printer?\n\n{path.name}"):
            return
        try:
            self.shell.print_file(path)
        except (AttributeError, OSError) as e:
            self.view.show_error("Print", f"Could not print:\n{e}\n\nThe list is saved here:\n{path}")
            return
        self.view.set_status(f"Sent {len(batch)} labels to the printer ({path.name}).")

    def clear_fields(self) -> None:
        """Clear the box range, VIN and the batch. Folders, account and database settings are kept."""
        form = self.view.get_form()
        if self.session.batch and not self.session.saved_to_db and form.get("use_db") == "1":
            if not self.view.ask_yes_no("Clear fields", "This batch hasn't been saved to the database. Clear it anyway?"):
                return
        self.view.set_fields({"start_box": "", "end_box": "", "count": "", "vin": ""})
        self.view.clear_batch()
        self.session = Session()
        self._publish()
        self.view.set_status("Cleared. Enter a start and end box, then click Run all.")

    def save_to_db(self) -> None:
        batch = self._batch_or_tell()
        if not batch or not (job := self._job()):
            return
        if self.session.saved_to_db:
            self.view.show_warning("Already saved", "This batch was already saved. Generate a new batch first.")
            return
        try:
            existing = self.service.existing_boxes(batch.boxes)
            msg = (f"Insert {len(batch)} rows into dbo.InventoryPartSale?"
                   + self._existing_warning(existing, "WARNING - these boxes already have rows:"))
            if not self.view.ask_yes_no("Save to database", msg, warning=bool(existing)):
                return
            n = self.service.save_to_db(batch, job)
        except Exception as e:  # noqa: BLE001 - any database/config problem is shown to the user
            self.view.show_error("Database", f"Nothing was saved.\n\n{e}")
            return
        self.session.saved_to_db = True
        self._publish()
        self.view.set_status(f"Saved {n} rows to the database.")
        self.view.show_info("Database", f"Saved {n} rows.")

    # ------------------------------------------------------------------ run all
    def run_all(self) -> None:
        """1 generate  2 create folders  3 save + open print list  4 save to database (if ticked)."""
        job = self._job()
        if not job:
            return
        try:
            boxes = self.service.boxes(job)
        except ValueError as e:
            self.view.show_error("Check settings", str(e))
            return

        # Check the database BEFORE creating anything, so a problem stops the run cleanly.
        warning = ""
        if job.use_db:
            try:
                existing = self.service.existing_boxes(boxes)
            except Exception as e:  # noqa: BLE001
                self.view.show_error("Database", f"Can't reach the database, nothing was created.\n\n{e}\n\n"
                                                 "Fix the connection or untick 'Include database'.")
                return
            warning = self._existing_warning(existing, "WARNING - these boxes already have rows in the database:")

        steps = ["create the folders", "save and open the print list"] + (["save to the database"] if job.use_db else [])
        msg = (f"Generate {len(boxes) * job.per_box} labels for {len(boxes)} boxes ({boxes[0]} – {boxes[-1]}), "
               f"then {', '.join(steps)}?\n\nFolders go under:\n{job.staging_root}{warning}")
        if not self.view.ask_yes_no("Run all", msg, warning=bool(warning)):
            return

        ctx = RunContext(job, self.service)
        report = build_run_all_pipeline(job.use_db, self.shell, [_StatusListener(self.view)]).run(ctx)

        if ctx.batch:
            self._show(ctx.batch, job)
            self.session.folders_created = len(report.done) >= 2
            self.session.print_list_path = ctx.print_list_path
            self.session.saved_to_db = ctx.rows_saved > 0
            self._publish()

        text = "\n".join(f"✔ {d}" for d in report.done)
        self.view.set_status(" | ".join(report.done) + ("" if report.ok else " | ERROR"))
        if report.ok:
            self.view.show_info("Run all", f"All done.\n\n{text}")
        else:
            self.view.show_error("Run all", f"{text}\n\n✖ {report.error}".strip())

    # ------------------------------------------------------------------ database connection tab
    def refresh_connection_preview(self) -> None:
        try:
            text = masked(self.config.connection_string())
            state = "configured"
        except ValueError as e:
            text, state = f"Not set up yet: {e}", "not_set_up"
        self.view.set_connection_preview(text)
        self.view.set_db_state(state)

    def open_config(self) -> None:
        path = self.config.ensure()
        try:
            self.shell.open_file(path)
        except (AttributeError, OSError):
            self.view.show_info("config.ini", f"Open this file in a text editor:\n\n{path}")

    def test_connection(self) -> None:
        self.refresh_connection_preview()
        try:
            self.service.test_connection()
        except Exception as e:  # noqa: BLE001
            self.view.set_db_state("failed")
            self.view.show_error("Database", f"Connection failed:\n\n{e}{self._drivers_hint()}")
            return
        self.view.set_db_state("connected")
        self.view.show_info("Database", "Connection OK.")

    def _drivers_hint(self) -> str:
        drivers = self._drivers()
        if drivers is None:
            return "\n\npyodbc is not installed:  pip install pyodbc"
        listing = "\n  ".join(drivers) if drivers else "(none - install 'ODBC Driver 17 for SQL Server')"
        return f"\n\nSQL Server drivers on this PC:\n  {listing}"
