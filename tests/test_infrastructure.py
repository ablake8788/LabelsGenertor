import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from labelgen.domain import LabelGenerator
from labelgen.formatting import DB_COLUMNS, InventoryRowMapper
from labelgen.infrastructure import (
    BatchFileWriter, ConfigError, FolderCreator, InMemoryLabelRepository, IniConfigLoader, JsonSettingsStore,
    SqlServerLabelRepository, masked,
)
from tests.fakes import hex_codes


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)


# ---------------------------------------------------------------------- config.ini
class ConfigTests(TempDirTest):
    def setUp(self):
        super().setUp()
        self.loader = IniConfigLoader(self.tmp)
        self.template = self.loader.ensure().read_text(encoding="utf-8")

    def write(self, **values):
        lines = []
        for line in self.template.splitlines():
            key = line.split("=")[0].strip()
            lines.append(f"{key} = {values[key]}" if key in values and not line.startswith(";") else line)
        self.loader.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_template_created(self):
        self.assertTrue(self.loader.path.exists())
        self.assertIn("[database]", self.template)

    def test_missing_server(self):
        with self.assertRaisesRegex(ConfigError, "server"):
            self.loader.connection_string()

    def test_sql_login_needs_user(self):
        self.write(server="sql.example.com")
        with self.assertRaisesRegex(ConfigError, "username"):
            self.loader.connection_string()

    def test_sql_login(self):
        self.write(server="sql.example.com", username="u1", password="p;a}ss")
        s = self.loader.connection_string()
        for part in ["DRIVER={ODBC Driver 17 for SQL Server};", "SERVER=sql.example.com;",
                     "DATABASE=DB_9BB9A7_prestige;", "UID=u1;", "PWD={p;a}}ss};", "Encrypt=no;",
                     "TrustServerCertificate=yes;"]:
            self.assertIn(part, s)

    def test_windows_login(self):
        self.write(server="PC\\SQLEXPRESS", trusted_connection="yes")
        s = self.loader.connection_string()
        self.assertIn("Trusted_Connection=yes", s)
        self.assertNotIn("UID=", s)

    def test_full_connection_string_wins(self):
        self.write(server="ignored", connection_string="DSN=MyDsn;")
        self.assertEqual(self.loader.connection_string(), "DSN=MyDsn;")

    def test_no_section(self):
        self.loader.path.write_text("[other]\n", encoding="utf-8")
        with self.assertRaises(ConfigError):
            self.loader.load()

    def test_masked(self):
        self.assertEqual(masked("UID=u;PWD={p;a}}ss};Encrypt=no;"), "UID=u;PWD=*****;Encrypt=no;")
        self.assertEqual(masked("UID=u;Password=abc;X=1"), "UID=u;Password=*****;X=1")


# ---------------------------------------------------------------------- SQL Server repository (fake pyodbc)
class FakeCursor:
    def __init__(self, conn):
        self.conn, self.fast_executemany = conn, False

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


class SqlServerRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conns, self.fail = [], False
        b = LabelGenerator(hex_codes()).generate(["BX3718", "BX3719"], 3)
        self.rows = InventoryRowMapper("LabelsSum").to_rows(b)

    def repo(self):
        def connect(conn_str):
            c = FakeConn(self.fail)
            self.conns.append((conn_str, c))
            return c
        return SqlServerLabelRepository("CS", connect)

    def test_insert_one_transaction(self):
        self.assertEqual(self.repo().insert(self.rows), 6)
        conn_str, c = self.conns[0]
        self.assertEqual(conn_str, "CS")
        kind, sql, rows = c.calls[0]
        self.assertEqual(kind, "executemany")
        self.assertIn("INSERT INTO dbo.InventoryPartSale", sql)
        for col in DB_COLUMNS:
            self.assertIn(f"[{col}]", sql)
        self.assertEqual(sql.count("?"), len(DB_COLUMNS))
        self.assertEqual(len(rows), 6)
        self.assertTrue(c.committed and c.closed and not c.rolled_back)

    def test_insert_failure_rolls_back(self):
        self.fail = True
        with self.assertRaises(RuntimeError):
            self.repo().insert(self.rows)
        c = self.conns[0][1]
        self.assertTrue(c.rolled_back and c.closed and not c.committed)

    def test_existing_boxes(self):
        self.assertEqual(self.repo().existing_boxes(["BX3718", "BX3719"]), {"BX3718": 5})
        kind, sql, params = self.conns[0][1].calls[0]
        self.assertIn("WHERE LotLocation IN (?,?)", sql)
        self.assertEqual(params, ["BX3718", "BX3719"])
        self.assertTrue(self.conns[0][1].closed)

    def test_existing_boxes_empty_skips_db(self):
        self.assertEqual(self.repo().existing_boxes([]), {})
        self.assertEqual(self.conns, [])


class InMemoryRepositoryTests(unittest.TestCase):
    def test_counts_inserted_rows(self):
        repo = InMemoryLabelRepository(existing={"BX1": 2})
        rows = InventoryRowMapper("A").to_rows(LabelGenerator(hex_codes()).generate(["BX2"], 3))
        repo.insert(rows)
        self.assertEqual(repo.existing_boxes(["BX1", "BX2", "BX3"]), {"BX1": 2, "BX2": 3})


# ---------------------------------------------------------------------- disk
class FilesystemTests(TempDirTest):
    def setUp(self):
        super().setUp()
        self.batch = LabelGenerator(hex_codes(), clock=lambda: datetime(2026, 11, 11, 9, 0, 0)).generate(["BX1", "BX2"], 2)

    def test_folders_created_once(self):
        fc = FolderCreator()
        self.assertEqual(fc.create(self.batch, self.tmp, "1"), 4)
        self.assertTrue((self.tmp / "BX1" / "1" / "1.00001-BX1").is_dir())
        self.assertEqual(fc.create(self.batch, self.tmp, "1"), 0)   # existing folders are left alone

    def test_file_names_and_encodings(self):
        w = BatchFileWriter()
        txt = w.write_print_list(self.batch, self.tmp / "a", "x\n")
        bat = w.write_folder_script(self.batch, self.tmp / "b", "echo é\r\n")
        csv = w.write_csv(self.batch, self.tmp / "b", "c\r\n")
        self.assertEqual(txt.name, "labels_BX1-BX2_20261111_090000.txt")
        self.assertEqual(bat.name, "create_folders_BX1-BX2_20261111_090000.bat")
        self.assertEqual(csv.name, "db_rows_BX1-BX2_20261111_090000.csv")
        self.assertEqual(bat.read_bytes(), "echo é\r\n".encode("cp1252"))
        self.assertEqual(csv.read_bytes(), b"c\r\n")


class SettingsTests(TempDirTest):
    def test_round_trip_and_bad_file(self):
        store = JsonSettingsStore(self.tmp / "s.json")
        self.assertEqual(store.load(), {})
        store.save({"start_box": "BX1"})
        self.assertEqual(store.load(), {"start_box": "BX1"})
        (self.tmp / "s.json").write_text("not json", encoding="utf-8")
        self.assertEqual(store.load(), {})


if __name__ == "__main__":
    unittest.main()
