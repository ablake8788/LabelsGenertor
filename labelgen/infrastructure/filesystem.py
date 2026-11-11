"""Creating label folders and writing batch files to disk."""
from __future__ import annotations

from pathlib import Path

from labelgen.domain.models import LabelBatch


class FolderCreator:
    """Creates <root>\\<box>\\<step>\\<label> for every label. Existing folders are left alone."""

    @staticmethod
    def paths(batch: LabelBatch, root: str | Path, box_step: str) -> list[Path]:
        root = Path(root)
        return [root / label.box / box_step / label.text for label in batch.labels]

    def create(self, batch: LabelBatch, root: str | Path, box_step: str) -> int:
        made = 0
        for path in self.paths(batch, root, box_step):
            if not path.exists():
                path.mkdir(parents=True)
                made += 1
        return made


class BatchFileWriter:
    """Writes one batch's files with names that include the box range and the time it was generated."""

    def write_print_list(self, batch: LabelBatch, folder: str | Path, text: str) -> Path:
        return self._write(Path(folder) / f"labels_{batch.file_tag}.txt", text.encode("utf-8"))

    def write_folder_script(self, batch: LabelBatch, folder: str | Path, text: str) -> Path:
        # cmd.exe reads .bat files in the ANSI code page
        return self._write(Path(folder) / f"create_folders_{batch.file_tag}.bat", text.encode("cp1252", "replace"))

    def write_csv(self, batch: LabelBatch, folder: str | Path, text: str) -> Path:
        return self._write(Path(folder) / f"db_rows_{batch.file_tag}.csv", text.encode("utf-8"))

    @staticmethod
    def _write(path: Path, data: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path
