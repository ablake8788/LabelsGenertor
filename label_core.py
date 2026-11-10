"""
Core logic for eBay roll label generation.

This ports usp_GenerateInvPartGuidDB_et4500_EbayRollLabelsDynamic_NoAccount
to Python and extends it to cover a RANGE of boxes (e.g. BX3718 .. BX3738).

Label format:   <seq>.<GUID5>-<BOX>      e.g.  6.26F40-BX3718
    seq   = item sequential number inside the box (1..N)
    GUID5 = first 5 characters of a new GUID (upper case, like SQL NEWID())
    BOX   = box / lot location
"""
from __future__ import annotations

import ntpath
import re
import uuid
from dataclasses import dataclass
from datetime import datetime

STAGING_SUBPATH = r"MorrisUniversalAutoGroup\PartsSale\Production\Current\0_staging"
BOX_RE = re.compile(r"^\s*([A-Za-z]*)(\d+)\s*$")
MAX_BOXES = 500


# --------------------------------------------------------------------------- boxes
def parse_box(box: str) -> tuple[str, int, int]:
    """'BX3718' -> ('BX', 3718, 4). The width keeps zero padding (BX0099 -> BX0100)."""
    m = BOX_RE.match(box or "")
    if not m:
        raise ValueError(f"Box '{box}' must look like BX3718 (letters followed by digits).")
    prefix, digits = m.group(1).upper(), m.group(2)
    return prefix, int(digits), len(digits)


def format_box(prefix: str, number: int, width: int) -> str:
    return f"{prefix}{number:0{width}d}"


def box_range(start: str, end: str | None = None, count: int | None = None) -> list[str]:
    """Inclusive list of boxes from start to end, or `count` boxes starting at start."""
    prefix, first, width = parse_box(start)
    if end:
        end_prefix, last, _ = parse_box(end)
        if end_prefix != prefix:
            raise ValueError(f"Start box prefix '{prefix}' and end box prefix '{end_prefix}' differ.")
    elif count:
        last = first + int(count) - 1
    else:
        last = first
    if last < first:
        raise ValueError("End box must be the same as or after the start box.")
    if last - first + 1 > MAX_BOXES:
        raise ValueError(f"Too many boxes ({last - first + 1}); the limit is {MAX_BOXES}.")
    return [format_box(prefix, n, width) for n in range(first, last + 1)]


# --------------------------------------------------------------------------- labels
@dataclass(frozen=True)
class Label:
    seq: int
    guid5: str
    box: str

    @property
    def text(self) -> str:
        return f"{self.seq}.{self.guid5}-{self.box}"


def new_guid5() -> str:
    return str(uuid.uuid4()).upper()[:5]


def generate_labels(boxes: list[str], per_box: int, avoid: set[str] | None = None) -> dict[str, list[Label]]:
    """
    Make `per_box` labels for every box. GUID5 values are kept unique across the
    whole run (and against `avoid`, e.g. values already in the database) so no two
    stickers in a batch share the same 5-character code.
    """
    if per_box < 1:
        raise ValueError("Labels per box must be at least 1.")
    used = set(avoid or ())
    result: dict[str, list[Label]] = {}
    for box in boxes:
        labels = []
        for seq in range(1, per_box + 1):
            g = new_guid5()
            while g in used:
                g = new_guid5()
            used.add(g)
            labels.append(Label(seq, g, box))
        result[box] = labels
    return result


# --------------------------------------------------------------------------- outputs
def root_folder(environment_folder: str, account_folder: str) -> str:
    """Same as the proc: @EnvironmetFolder + staging path + account (Windows path)."""
    return ntpath.join(environment_folder.rstrip("\\/"), STAGING_SUBPATH, account_folder)


# Roll spacer lines (edit here to change them).
_SPACER = "!-                          -!"
LIST_HEADER = ["  " + _SPACER]                 # once, at the top of the list
BOX_SEPARATOR = [" " + _SPACER, "  " + _SPACER]  # after every box, including the last


def labels_text(labels_by_box: dict[str, list[Label]]) -> str:
    """Printable labels list: header line, then each box's labels followed by the box separator."""
    lines: list[str] = list(LIST_HEADER)
    for labels in labels_by_box.values():
        lines.extend(l.text for l in labels)
        lines.extend(BOX_SEPARATOR)
    return "\n".join(lines) + "\n"


def mkdir_script(labels_by_box: dict[str, list[Label]], root: str, box_step: str) -> str:
    """Windows .bat that creates <root>\\<box>\\<step>\\<label> folders."""
    lines = ["@echo off", f'cd /d "{root}"']
    for box, labels in labels_by_box.items():
        lines.append(f"rem ---- {box} ----")
        for l in labels:
            lines.append(f'mkdir "{box}\\{box_step}\\{l.text}"')
    lines.append(f'echo Done. Folders created under "{root}"')
    return "\r\n".join(lines) + "\r\n"


def folder_paths(labels_by_box: dict[str, list[Label]], box_step: str) -> list[tuple[str, str, str]]:
    """(box, step, label) triples, for creating folders directly from Python."""
    return [(box, box_step, l.text) for box, labels in labels_by_box.items() for l in labels]


DB_COLUMNS = ["EbayAccount", "StockId", "ShortName", "LongName", "StockCategory", "StockStatus",
              "StockCondition", "LotId", "LotLocation", "CreatedBy", "CreatedOn", "PartAccountVin"]


def db_rows(labels_by_box: dict[str, list[Label]], ebay_account: str, part_account_vin: str = "",
            created_by: int = 1, created_on: datetime | None = None) -> list[tuple]:
    """Rows for dbo.InventoryPartSale, matching the proc's INSERT column for column."""
    created_on = created_on or datetime.now()
    name = f"& {ebay_account}"
    rows = []
    for box, labels in labels_by_box.items():
        for l in labels:
            rows.append((ebay_account, l.text, name, name, "PART", "1_staging", "USED",
                         l.text, box, created_by, created_on, part_account_vin or None))
    return rows
