"""
Opening and printing files - Adapter over Windows' shell (os.startfile).

WindowsShell  : production
RecordingShell: tests - remembers what would have been opened or printed
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class Shell(Protocol):
    def open_file(self, path: Path) -> None: ...
    def print_file(self, path: Path) -> None: ...


class WindowsShell:
    def open_file(self, path: Path) -> None:
        os.startfile(str(path))  # type: ignore[attr-defined]  # Windows only

    def print_file(self, path: Path) -> None:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]  # default printer


class RecordingShell:
    def __init__(self, fail: Exception | None = None):
        self.opened: list[Path] = []
        self.printed: list[Path] = []
        self.fail = fail

    def open_file(self, path: Path) -> None:
        if self.fail:
            raise self.fail
        self.opened.append(Path(path))

    def print_file(self, path: Path) -> None:
        if self.fail:
            raise self.fail
        self.printed.append(Path(path))
