"""The labels list that goes to the roll printer."""
from __future__ import annotations

from labelgen.domain.models import LabelBatch
from labelgen.formatting.base import BatchFormatter

# Roll spacer lines (edit here to change them).
SPACER = "!-                          -!"
LIST_HEADER = ("  " + SPACER,)                   # once, at the top of the list
BOX_SEPARATOR = (" " + SPACER, "  " + SPACER)    # after every box, including the last


class PrintListFormatter(BatchFormatter):
    """
    Header line, then each box's labels in order followed by the box separator:

          !-                          -!
        1.C8C5E-BX3718
        ...
        28.87061-BX3718
         !-                          -!
          !-                          -!
        1.D7B57-BX3719
    """

    def __init__(self, header: tuple[str, ...] = LIST_HEADER, box_separator: tuple[str, ...] = BOX_SEPARATOR):
        self.header = header
        self.box_separator = box_separator

    def format(self, batch: LabelBatch) -> str:
        lines: list[str] = list(self.header)
        for labels in batch.labels_by_box.values():
            lines.extend(label.text for label in labels)
            lines.extend(self.box_separator)
        return "\n".join(lines) + "\n"
