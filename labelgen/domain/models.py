"""Value objects for labels and a generated batch."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Label:
    """One sticker:  <seq>.<GUID5>-<BOX>   e.g.  6.26F40-BX3718"""

    seq: int
    guid5: str
    box: str

    @property
    def text(self) -> str:
        return f"{self.seq}.{self.guid5}-{self.box}"


@dataclass
class LabelBatch:
    """All labels made in one run, grouped by box (in box order)."""

    labels_by_box: dict[str, list[Label]]
    created_on: datetime = field(default_factory=datetime.now)

    @property
    def boxes(self) -> list[str]:
        return list(self.labels_by_box)

    @property
    def labels(self) -> list[Label]:
        return [label for labels in self.labels_by_box.values() for label in labels]

    def __len__(self) -> int:
        return sum(len(v) for v in self.labels_by_box.values())

    @property
    def range_tag(self) -> str:
        """'BX3718' for one box, 'BX3718-BX3738' for a range - used in file names."""
        boxes = self.boxes
        return boxes[0] if len(boxes) == 1 else f"{boxes[0]}-{boxes[-1]}"

    @property
    def file_tag(self) -> str:
        return f"{self.range_tag}_{self.created_on:%Y%m%d_%H%M%S}"
