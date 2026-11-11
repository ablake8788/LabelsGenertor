"""
LabelService - Facade.

One simple object the UI (and the self-test) uses for everything: generate a batch,
make its outputs, create folders, write files and save to the database. It hides the
generator, formatters, file writer, folder creator and repository behind it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from labelgen.domain.generator import LabelGenerator
from labelgen.domain.models import LabelBatch
from labelgen.formatting import CsvFormatter, FolderScriptFormatter, InventoryRowMapper, PrintListFormatter
from labelgen.infrastructure.filesystem import BatchFileWriter, FolderCreator
from labelgen.infrastructure.repository import LabelRepository
from labelgen.services.job import JobSettings


class LabelService:
    def __init__(
        self,
        generator: LabelGenerator,
        repository_factory: Callable[[], LabelRepository],
        folders: FolderCreator | None = None,
        files: BatchFileWriter | None = None,
        print_formatter: PrintListFormatter | None = None,
    ):
        self._generator = generator
        self._repository_factory = repository_factory   # called per use, so config.ini edits apply at once
        self._folders = folders or FolderCreator()
        self._files = files or BatchFileWriter()
        self._print = print_formatter or PrintListFormatter()

    # ------------------------------------------------------------------ generate + outputs
    def boxes(self, job: JobSettings) -> list[str]:
        return job.box_range().boxes

    def generate(self, job: JobSettings) -> LabelBatch:
        if not job.account:
            raise ValueError("Account folder is required.")
        return self._generator.generate(self.boxes(job), job.per_box)

    def print_list(self, batch: LabelBatch) -> str:
        return self._print.format(batch)

    def folder_script(self, batch: LabelBatch, job: JobSettings) -> str:
        return FolderScriptFormatter(job.staging_root, job.box_step).format(batch)

    def rows(self, batch: LabelBatch, job: JobSettings) -> list[tuple]:
        return self._mapper(job).to_rows(batch)

    @staticmethod
    def _mapper(job: JobSettings) -> InventoryRowMapper:
        return InventoryRowMapper(job.account, job.vin)

    # ------------------------------------------------------------------ disk
    def create_folders(self, batch: LabelBatch, job: JobSettings) -> int:
        return self._folders.create(batch, job.staging_root, job.box_step)

    def save_print_list(self, batch: LabelBatch, job: JobSettings) -> Path:
        return self._files.write_print_list(batch, job.print_list_folder, self.print_list(batch))

    def save_files(self, batch: LabelBatch, job: JobSettings) -> list[Path]:
        """Print list -> Labels list folder; folder .bat and rows .csv -> Save files to. Returns [txt, bat, csv]."""
        txt = self.save_print_list(batch, job)
        bat = self._files.write_folder_script(batch, job.output_folder, self.folder_script(batch, job))
        csv = self._files.write_csv(batch, job.output_folder, CsvFormatter(self._mapper(job)).format(batch))
        return [txt, bat, csv]

    # ------------------------------------------------------------------ database
    def existing_boxes(self, boxes: list[str]) -> dict[str, int]:
        return self._repository_factory().existing_boxes(boxes)

    def save_to_db(self, batch: LabelBatch, job: JobSettings) -> int:
        return self._repository_factory().insert(self.rows(batch, job))

    def test_connection(self) -> None:
        self._repository_factory().ping()
