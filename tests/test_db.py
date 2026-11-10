"""Database layer tests with a fake pyodbc - nothing touches the real server."""
import sys
import types
import unittest

import label_core as core
import label_db


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fast_executemany = False

    def execute(self, sql, params):
        self.conn.calls.append(("execute", sql, list(params)))
        return self

    def fetchall(self):
        return [("BX3718", 5)]

    def executemany(self, sql, rows):
        if self.conn.fail:
            raise RuntimeError("insert failed")
        self.conn.calls.append(("executemany", sql, list(rows)))


class FakeConn:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []
        self.committed = self.rolled_back = self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class DbTests(unittest.TestCase):
    def setUp(self):
        self.conns = []
        self.fail = False
        fake = types.ModuleType("pyodbc")

        def connect(conn_str, autocommit=False):
            c = FakeConn(self.fail)
            self.conns.append((conn_str, autocommit, c))
            return c

        fake.connect = connect
        self._old = sys.modules.get("pyodbc")
        sys.modules["pyodbc"] = fake
        self.rows = core.db_rows(core.generate_labels(["BX3718", "BX3719"], 3), "LabelsSum", "")

    def tearDown(self):
        if self._old is None:
            sys.modules.pop("pyodbc", None)
        else:
            sys.modules["pyodbc"] = self._old

    def test_insert_commits_all_rows_in_one_transaction(self):
        self.assertEqual(label_db.insert_rows("CS", self.rows), 6)
        conn_str, autocommit, c = self.conns[0]
        self.assertEqual(conn_str, "CS")
        self.assertFalse(autocommit)
        kind, sql, rows = c.calls[0]
        self.assertEqual(kind, "executemany")
        self.assertIn("INSERT INTO dbo.InventoryPartSale", sql)
        for col in core.DB_COLUMNS:
            self.assertIn(f"[{col}]", sql)
        self.assertEqual(sql.count("?"), len(core.DB_COLUMNS))
        self.assertEqual(len(rows), 6)
        self.assertTrue(c.committed and c.closed and not c.rolled_back)

    def test_insert_failure_rolls_back(self):
        self.fail = True
        with self.assertRaises(RuntimeError):
            label_db.insert_rows("CS", self.rows)
        c = self.conns[0][2]
        self.assertTrue(c.rolled_back and c.closed and not c.committed)

    def test_existing_boxes(self):
        self.assertEqual(label_db.existing_boxes("CS", ["BX3718", "BX3719"]), {"BX3718": 5})
        kind, sql, params = self.conns[0][2].calls[0]
        self.assertIn("WHERE LotLocation IN (?,?)", sql)
        self.assertEqual(params, ["BX3718", "BX3719"])

    def test_existing_boxes_empty_list_skips_db(self):
        self.assertEqual(label_db.existing_boxes("CS", []), {})
        self.assertEqual(self.conns, [])


if __name__ == "__main__":
    unittest.main()
