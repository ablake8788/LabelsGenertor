"""
GUID codes for labels - Strategy pattern.

RandomGuidProvider  : production, first 5 characters of a new GUID (like SQL NEWID()).
SequenceGuidProvider: tests, returns fixed codes so results are predictable.
"""
from __future__ import annotations

import uuid
from typing import Iterable, Iterator, Protocol


class GuidProvider(Protocol):
    def next(self) -> str: ...


class RandomGuidProvider:
    def next(self) -> str:
        return str(uuid.uuid4()).upper()[:5]


class SequenceGuidProvider:
    def __init__(self, codes: Iterable[str]):
        self._codes: Iterator[str] = iter(codes)

    def next(self) -> str:
        return next(self._codes)
