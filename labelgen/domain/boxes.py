"""Box ids (BX3718) and inclusive box ranges (BX3718 .. BX3738)."""
from __future__ import annotations

import re
from dataclasses import dataclass

BOX_RE = re.compile(r"^\s*([A-Za-z]*)(\d+)\s*$")
MAX_BOXES = 500


@dataclass(frozen=True)
class BoxId:
    """'BX0099' -> prefix 'BX', number 99, width 4 (width keeps zero padding: BX0099 -> BX0100)."""

    prefix: str
    number: int
    width: int

    @classmethod
    def parse(cls, text: str) -> "BoxId":
        m = BOX_RE.match(text or "")
        if not m:
            raise ValueError(f"Box '{text}' must look like BX3718 (letters followed by digits).")
        return cls(m.group(1).upper(), int(m.group(2)), len(m.group(2)))

    def offset(self, n: int) -> "BoxId":
        return BoxId(self.prefix, self.number + n, self.width)

    def __str__(self) -> str:
        return f"{self.prefix}{self.number:0{self.width}d}"


class BoxRange:
    """Inclusive, validated range of boxes with the same prefix."""

    def __init__(self, start: BoxId, end: BoxId):
        if end.prefix != start.prefix:
            raise ValueError(f"Start box prefix '{start.prefix}' and end box prefix '{end.prefix}' differ.")
        if end.number < start.number:
            raise ValueError("End box must be the same as or after the start box.")
        count = end.number - start.number + 1
        if count > MAX_BOXES:
            raise ValueError(f"Too many boxes ({count}); the limit is {MAX_BOXES}.")
        self.start, self.end = start, end

    @classmethod
    def from_text(cls, start: str, end: str | None = None, count: int | None = None) -> "BoxRange":
        first = BoxId.parse(start)
        if end:
            last = BoxId.parse(end)
        elif count:
            last = first.offset(int(count) - 1)
        else:
            last = first
        return cls(first, last)

    def __len__(self) -> int:
        return self.end.number - self.start.number + 1

    def __iter__(self):
        return (str(self.start.offset(i)) for i in range(len(self)))

    @property
    def boxes(self) -> list[str]:
        return list(self)


def box_range(start: str, end: str | None = None, count: int | None = None) -> list[str]:
    """Shortcut: list of box ids from start to end, or `count` boxes from start."""
    return BoxRange.from_text(start, end, count).boxes
