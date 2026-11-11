"""
Repository pattern: the rest of the app talks to LabelRepository, never to pyodbc directly.

SqlServerLabelRepository : production (dbo.InventoryPartSale via pyodbc)
InMemoryLabelRepository  : tests and dry runs
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Sequence

from labelgen.formatting.db_rows import DB_COLUMNS

TABLE = "dbo.InventoryPartSale"


class LabelRepository(ABC):
    @abstractmethod
    def existing_boxes(self, boxes: Sequence[str]) -> dict[str, int]:
        """Boxes that already have rows -> row count."""

    @abstractmethod
    def insert(self, rows: Sequence[tuple]) -> int:
        """Insert all rows in one transaction (all or nothing). Returns the number inserted."""

    def ping(self) -> None:
        """Raise if the database can't be reached."""
        self.existing_boxes(["__ping__"])


def _pyodbc_connect(conn_str: str):
    try:
        import pyodbc
    except ImportError as e:
        raise RuntimeError("pyodbc is not installed. Run:  pip install pyodbc") from e
    return pyodbc.connect(conn_str, autocommit=False)


class SqlServerLabelRepository(LabelRepository):
    def __init__(self, connection_string: str, connect: Callable[[str], object] = _pyodbc_connect):
        self._conn_str = connection_string
        self._connect = connect

    def existing_boxes(self, boxes: Sequence[str]) -> dict[str, int]:
        boxes = list(boxes)
        if not boxes:
            return {}
        sql = (f"SELECT LotLocation, COUNT(*) FROM {TABLE} "
               f"WHERE LotLocation IN ({','.join('?' * len(boxes))}) GROUP BY LotLocation")
        cn = self._connect(self._conn_str)
        try:
            return {r[0]: r[1] for r in cn.cursor().execute(sql, boxes).fetchall()}
        finally:
            cn.close()

    def insert(self, rows: Sequence[tuple]) -> int:
        cols = ",".join(f"[{c}]" for c in DB_COLUMNS)
        sql = f"INSERT INTO {TABLE} ({cols}) VALUES ({','.join('?' * len(DB_COLUMNS))})"
        cn = self._connect(self._conn_str)
        try:
            cur = cn.cursor()
            cur.fast_executemany = True
            cur.executemany(sql, list(rows))
            cn.commit()
            return len(rows)
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()


class InMemoryLabelRepository(LabelRepository):
    def __init__(self, existing: dict[str, int] | None = None, fail_insert: Exception | None = None,
                 fail_read: Exception | None = None):
        self.rows: list[tuple] = []
        self.existing = dict(existing or {})
        self.fail_insert = fail_insert
        self.fail_read = fail_read

    def existing_boxes(self, boxes: Sequence[str]) -> dict[str, int]:
        if self.fail_read:
            raise self.fail_read
        counts = dict(self.existing)
        for row in self.rows:
            counts[row[8]] = counts.get(row[8], 0) + 1
        return {b: counts[b] for b in boxes if counts.get(b)}

    def insert(self, rows: Sequence[tuple]) -> int:
        if self.fail_insert:
            raise self.fail_insert
        self.rows.extend(rows)
        return len(rows)


def installed_sql_drivers() -> list[str] | None:
    """SQL Server ODBC drivers on this PC, or None when pyodbc isn't installed."""
    try:
        import pyodbc
    except ImportError:
        return None
    return [d for d in pyodbc.drivers() if "SQL Server" in d]
