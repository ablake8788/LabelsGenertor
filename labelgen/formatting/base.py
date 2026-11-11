from __future__ import annotations

from abc import ABC, abstractmethod

from labelgen.domain.models import LabelBatch


class BatchFormatter(ABC):
    """Turns a LabelBatch into text (a file's contents)."""

    @abstractmethod
    def format(self, batch: LabelBatch) -> str: ...
