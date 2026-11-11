"""Test doubles shared by the tests."""
from __future__ import annotations

import itertools
from pathlib import Path

from labelgen.container import Container, build_container
from labelgen.domain.guid import SequenceGuidProvider
from labelgen.infrastructure.repository import InMemoryLabelRepository
from labelgen.infrastructure.shell import RecordingShell
from labelgen.ui.defaults import DEFAULTS


def hex_codes():
    """Endless predictable GUID5 codes: 00001, 00002, ..."""
    return SequenceGuidProvider(f"{n:05X}" for n in itertools.count(1))


def make_container(tmp: Path, repository: InMemoryLabelRepository | None = None,
                   shell: RecordingShell | None = None) -> Container:
    return build_container(tmp, shell=shell or RecordingShell(), guid_provider=hex_codes(),
                           repository=repository or InMemoryLabelRepository())


class FakeView:
    """Implements the LabelView protocol and records everything shown."""

    def __init__(self, tmp: Path, **form):
        self.form = {**DEFAULTS, "count": "", "use_db": "0",
                     "start_box": "BX3718", "end_box": "BX3720",
                     "env_folder": str(tmp / "env"),
                     "output_folder": str(tmp / "files"),
                     "labels_folder": str(tmp / "labels_list"), **form}
        self.dialogs: list[tuple[str, str, str]] = []
        self.answers: list[bool] = []          # queued answers for ask_yes_no (default: yes)
        self.statuses: list[str] = []
        self.batch_shown: tuple | None = None
        self.clipboard = ""
        self.preview = ""

    # form
    def get_form(self):
        return dict(self.form)

    def set_fields(self, values):
        self.form.update(values)

    # dialogs
    def show_error(self, title, message):
        self.dialogs.append(("error", title, message))

    def show_info(self, title, message):
        self.dialogs.append(("info", title, message))

    def show_warning(self, title, message):
        self.dialogs.append(("warning", title, message))

    def ask_yes_no(self, title, message, warning=False):
        self.dialogs.append(("ask-warning" if warning else "ask", title, message))
        return self.answers.pop(0) if self.answers else True

    # output
    def set_status(self, text):
        self.statuses.append(text)

    def show_batch(self, print_list, folder_script, rows):
        self.batch_shown = (print_list, folder_script, list(rows))

    def clear_batch(self):
        self.batch_shown = None

    def set_clipboard(self, text):
        self.clipboard = text

    def set_connection_preview(self, text):
        self.preview = text

    # helpers for assertions
    def kinds(self, kind):
        return [d for d in self.dialogs if d[0] == kind]

    @property
    def last(self):
        return self.dialogs[-1]
