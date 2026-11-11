"""Windows .bat that creates <root>\\<box>\\<step>\\<label> folders (backup of 'Create folders')."""
from __future__ import annotations

from labelgen.domain.models import LabelBatch
from labelgen.formatting.base import BatchFormatter


class FolderScriptFormatter(BatchFormatter):
    def __init__(self, root: str, box_step: str = "1"):
        self.root = root
        self.box_step = box_step

    def format(self, batch: LabelBatch) -> str:
        lines = ["@echo off", f'cd /d "{self.root}"']
        for box, labels in batch.labels_by_box.items():
            lines.append(f"rem ---- {box} ----")
            lines.extend(f'mkdir "{box}\\{self.box_step}\\{label.text}"' for label in labels)
        lines.append(f'echo Done. Folders created under "{self.root}"')
        return "\r\n".join(lines) + "\r\n"
