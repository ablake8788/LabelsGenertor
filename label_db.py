"""
Database step: insert generated labels into dbo.InventoryPartSale (SQL Server).

Requires:  pip install pyodbc   (plus "ODBC Driver 17/18 for SQL Server")
Example connection string:
  DRIVER={ODBC Driver 17 for SQL Server};SERVER=myserver;DATABASE=DB_9BB9A7_prestige;Trusted_Connection=yes;
"""
from __future__ import annotations

from label_core import DB_COLUMNS


def _connect(conn_str: str):
    try:
        import pyodbc
    except ImportError as e:
        raise RuntimeError("pyodbc is not installed. Run:  pip install pyodbc") from e
    return pyodbc.connect(conn_str, autocommit=False)


def existing_boxes(conn_str: str, boxes: list[str]) -> dict[str, int]:
    """Boxes that already have rows in InventoryPartSale -> row count (to warn before inserting)."""
    if not boxes:
        return {}
    placeholders = ",".join("?" * len(boxes))
    sql = (f"SELECT LotLocation, COUNT(*) FROM dbo.InventoryPartSale "
           f"WHERE LotLocation IN ({placeholders}) GROUP BY LotLocation")
    with _connect(conn_str) as cn:
        return {r[0]: r[1] for r in cn.cursor().execute(sql, boxes).fetchall()}


def insert_rows(conn_str: str, rows: list[tuple]) -> int:
    """Insert all rows in ONE transaction: everything is saved or nothing is."""
    cols = ",".join(f"[{c}]" for c in DB_COLUMNS)
    sql = f"INSERT INTO dbo.InventoryPartSale ({cols}) VALUES ({','.join('?' * len(DB_COLUMNS))})"
    cn = _connect(conn_str)
    try:
        cur = cn.cursor()
        cur.fast_executemany = True
        cur.executemany(sql, rows)
        cn.commit()
        return len(rows)
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()
