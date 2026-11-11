"""
'Run all' as a pipeline of steps.

Command pattern : each step (generate, create folders, save files, save to database) is a
                  small object with execute(); the pipeline runs them in order and stops at
                  the first failure.
Observer pattern: listeners are told when each step starts, finishes or fails (the window
                  uses this to update its status bar).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

from labelgen.domain.models import LabelBatch
from labelgen.infrastructure.shell import Shell
from labelgen.services.job import JobSettings
from labelgen.services.label_service import LabelService


@dataclass
class RunContext:
    job: JobSettings
    service: LabelService
    batch: LabelBatch | None = None
    files: list[Path] = field(default_factory=list)
    rows_saved: int = 0

    @property
    def print_list_path(self) -> Path | None:
        return self.files[0] if self.files else None


@dataclass
class RunReport:
    done: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Step(ABC):
    name = "Step"

    @abstractmethod
    def execute(self, ctx: RunContext) -> str:
        """Do the work; return a short 'what happened' line."""

    def failure_message(self, error: Exception) -> str:
        return f"{self.name} failed:\n{error}"


class GenerateStep(Step):
    name = "Generate labels"

    def execute(self, ctx: RunContext) -> str:
        ctx.batch = ctx.service.generate(ctx.job)
        return f"Generated {len(ctx.batch)} labels"

    def failure_message(self, error: Exception) -> str:
        return f"Check settings:\n{error}"


class CreateFoldersStep(Step):
    name = "Create folders"

    def execute(self, ctx: RunContext) -> str:
        return f"Created {ctx.service.create_folders(ctx.batch, ctx.job)} folders"

    def failure_message(self, error: Exception) -> str:
        return f"Stopped - file/folder error:\n{error}"


class SaveFilesStep(Step):
    """Saves the print list (+ .bat and .csv) and opens the print list so it can be printed."""

    name = "Save print list"

    def __init__(self, shell: Shell | None = None):
        self.shell = shell

    def execute(self, ctx: RunContext) -> str:
        ctx.files = ctx.service.save_files(ctx.batch, ctx.job)
        if self.shell:
            try:
                self.shell.open_file(ctx.print_list_path)
            except Exception:  # opening Notepad is a convenience, never a failure
                pass
        return f"Saved print list: {ctx.print_list_path.name}"

    def failure_message(self, error: Exception) -> str:
        return f"Stopped - file/folder error:\n{error}"


class SaveToDatabaseStep(Step):
    name = "Save to database"

    def execute(self, ctx: RunContext) -> str:
        ctx.rows_saved = ctx.service.save_to_db(ctx.batch, ctx.job)
        return f"Saved {ctx.rows_saved} rows to the database"

    def failure_message(self, error: Exception) -> str:
        return ("Database save FAILED, nothing was inserted. Labels and folders are kept; "
                f"fix the problem and click 'Save to database…' to retry this same batch.\n\n{error}")


class ProgressListener(Protocol):
    def step_started(self, step: Step) -> None: ...
    def step_finished(self, step: Step, message: str) -> None: ...
    def step_failed(self, step: Step, message: str) -> None: ...


class Pipeline:
    def __init__(self, steps: Iterable[Step], listeners: Iterable[ProgressListener] = ()):
        self.steps = list(steps)
        self.listeners = list(listeners)

    def run(self, ctx: RunContext) -> RunReport:
        report = RunReport()
        for step in self.steps:
            self._notify("step_started", step)
            try:
                message = step.execute(ctx)
            except Exception as e:  # noqa: BLE001 - each step turns its error into a clear message
                report.error = step.failure_message(e)
                self._notify("step_failed", step, report.error)
                return report
            report.done.append(message)
            self._notify("step_finished", step, message)
        return report

    def _notify(self, event: str, *args) -> None:
        for listener in self.listeners:
            getattr(listener, event, lambda *a: None)(*args)


def build_run_all_pipeline(include_db: bool, shell: Shell | None = None,
                           listeners: Iterable[ProgressListener] = ()) -> Pipeline:
    """1 generate  2 create folders  3 save + open print list  4 save to database (optional)."""
    steps: list[Step] = [GenerateStep(), CreateFoldersStep(), SaveFilesStep(shell)]
    if include_db:
        steps.append(SaveToDatabaseStep())
    return Pipeline(steps, listeners)
