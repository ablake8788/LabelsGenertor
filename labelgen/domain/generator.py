"""Makes a LabelBatch for a list of boxes."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable

from labelgen.domain.guid import GuidProvider, RandomGuidProvider
from labelgen.domain.models import Label, LabelBatch

MAX_ATTEMPTS = 1000


class LabelGenerator:
    """
    Generates `per_box` labels for every box. GUID5 codes are unique across the whole
    batch (and against `avoid`), so no two stickers printed together share a code.
    """

    def __init__(self, guid_provider: GuidProvider | None = None, clock: Callable[[], datetime] = datetime.now):
        self._guids = guid_provider or RandomGuidProvider()
        self._clock = clock

    def generate(self, boxes: Iterable[str], per_box: int, avoid: set[str] | None = None) -> LabelBatch:
        if per_box < 1:
            raise ValueError("Labels per box must be at least 1.")
        used = set(avoid or ())
        result: dict[str, list[Label]] = {}
        for box in boxes:
            result[box] = [Label(seq, self._unique_code(used), box) for seq in range(1, per_box + 1)]
        return LabelBatch(result, created_on=self._clock())

    def _unique_code(self, used: set[str]) -> str:
        for _ in range(MAX_ATTEMPTS):
            code = self._guids.next()
            if code not in used:
                used.add(code)
                return code
        raise RuntimeError("Could not find an unused GUID code.")
