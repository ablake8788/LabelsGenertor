"""
Self-test without the window:   LabelGenerator.exe --selftest   (--check-db also tests the database)

Checks label generation, print list, folder creation, database rows, config.ini and pyodbc.
Writes selftest.log next to the app. Exit code 0 = passed, 1 = failed.
"""
from __future__ import annotations

import re
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from labelgen.container import Container, build_container
from labelgen.formatting.db_rows import DB_COLUMNS
from labelgen.formatting.print_list import BOX_SEPARATOR, LIST_HEADER
from labelgen.infrastructure.config import masked
from labelgen.services.job import JobSettings

LABEL_RE = re.compile(r"\d{1,3}\.[0-9A-F]{5}-BX\d{4}")


class SelfTest:
    def __init__(self, container: Container, echo: bool = True):
        self.c = container
        self.echo = echo
        self.log: list[str] = [f"Label Generator self-test  {datetime.now():%Y-%m-%d %H:%M:%S}",
                               f"App folder: {container.app_dir}"]
        self.failed = 0
        self.state: dict = {}

    def check(self, name: str, fn: Callable[[], str | None]) -> bool:
        try:
            detail = fn()
            self.log.append(f"PASS  {name}" + (f"  - {detail}" if detail else ""))
            return True
        except Exception as e:  # noqa: BLE001 - report every failure
            self.failed += 1
            self.log.append(f"FAIL  {name}  - {e}")
            self.log.append("      " + traceback.format_exc().strip().replace("\n", "\n      "))
            return False

    # ------------------------------------------------------------------ checks
    def _job(self, root: str) -> JobSettings:
        return JobSettings(start_box="BX0099", end_box="BX0101", per_box=28, box_step="1", account="LabelsSum",
                           env_folder=root, vin="", output_folder=root, labels_folder=root, use_db=False)

    def generate(self) -> str:
        job = self._job("")
        assert self.c.service.boxes(job) == ["BX0099", "BX0100", "BX0101"]
        batch = self.state["batch"] = self.c.service.generate(job)
        texts = [label.text for label in batch.labels]
        assert len(texts) == 84 and len(set(texts)) == 84
        bad = [t for t in texts if not LABEL_RE.fullmatch(t)]
        assert not bad, bad[:3]
        return f"{len(texts)} labels, e.g. {texts[0]}"

    def print_list(self) -> str:
        lines = self.c.service.print_list(self.state["batch"]).splitlines()
        assert lines[0] == LIST_HEADER[0]
        assert lines.count(BOX_SEPARATOR[0]) == 3
        assert len(lines) == len(LIST_HEADER) + 84 + 3 * len(BOX_SEPARATOR)
        return f"{len(lines)} lines"

    def folders_and_files(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            job = self._job(tmp)
            made = self.c.service.create_folders(self.state["batch"], job)
            files = self.c.service.save_files(self.state["batch"], job)
            assert made == 84, made
            assert all(p.exists() for p in files)
        return "84 folders and 3 files written and removed in a temp folder"

    def rows(self) -> str:
        r = self.c.service.rows(self.state["batch"], self._job(""))
        assert len(r) == 84 and len(r[0]) == len(DB_COLUMNS)
        assert r[0][1] == r[0][7] and r[0][8] == "BX0099"
        return f"{len(r)} rows x {len(DB_COLUMNS)} columns"

    def config(self) -> str:
        self.state["conn"] = self.c.config.connection_string()
        return masked(self.state["conn"])

    def driver(self) -> str:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        return f"pyodbc {pyodbc.version}; drivers: {', '.join(drivers) or 'NONE'}"

    def database(self) -> str:
        self.c.service.test_connection()
        return "connected, read-only query OK (nothing written)"

    # ------------------------------------------------------------------ run
    def run(self, check_db: bool = False) -> int:
        if self.check("Generate labels", self.generate):
            self.check("Print list format", self.print_list)
            self.check("Create folders + save files", self.folders_and_files)
            self.check("Database rows", self.rows)
        config_ok = self.check("config.ini", self.config)
        self.check("pyodbc", self.driver)
        if check_db:
            if config_ok:
                self.check("Database connection", self.database)
            else:
                self.failed += 1
                self.log.append("FAIL  Database connection  - skipped, config.ini is not valid")
        self.log.append(f"RESULT: {'PASSED' if not self.failed else f'FAILED ({self.failed})'}")
        self._write()
        return 0 if not self.failed else 1

    def _write(self) -> None:
        text = "\n".join(self.log) + "\n"
        try:
            (self.c.app_dir / "selftest.log").write_text(text, encoding="utf-8")
        except OSError:
            pass
        if self.echo:
            try:
                print(text)
            except Exception:  # windowed .exe has no console
                pass


def run_self_test(app_dir: Path | None = None, check_db: bool = False, container: Container | None = None,
                  echo: bool = True) -> int:
    return SelfTest(container or build_container(app_dir), echo).run(check_db)
