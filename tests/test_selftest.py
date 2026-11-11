import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from labelgen.infrastructure import InMemoryLabelRepository
from labelgen.selftest import run_self_test
from tests.fakes import make_container

FAKE_PYODBC = types.SimpleNamespace(version="test", drivers=lambda: ["ODBC Driver 17 for SQL Server"])


class SelfTestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "config.ini").write_text("[database]\nconnection_string = DSN=x;\n", encoding="utf-8")

    def run_it(self, check_db=False, repo=None):
        with mock.patch.dict(sys.modules, {"pyodbc": FAKE_PYODBC}):
            code = run_self_test(check_db=check_db, container=make_container(self.tmp, repo), echo=False)
        return code, (self.tmp / "selftest.log").read_text(encoding="utf-8")

    def test_passes(self):
        code, log = self.run_it()
        self.assertEqual(code, 0, log)
        self.assertIn("RESULT: PASSED", log)
        self.assertEqual(log.count("PASS  "), 6)

    def test_check_db(self):
        code, log = self.run_it(check_db=True)
        self.assertEqual(code, 0, log)
        self.assertIn("PASS  Database connection", log)

    def test_database_failure_is_reported(self):
        code, log = self.run_it(check_db=True, repo=InMemoryLabelRepository(fail_read=RuntimeError("no server")))
        self.assertEqual(code, 1)
        self.assertIn("FAIL  Database connection  - no server", log)

    def test_bad_config_fails(self):
        (self.tmp / "config.ini").write_text("[database]\nserver =\n", encoding="utf-8")
        code, log = self.run_it(check_db=True)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  config.ini", log)


class EntryPointTests(unittest.TestCase):
    def test_selftest_flag_exits_with_code(self):
        from labelgen import main as main_module
        with mock.patch.object(main_module, "run_self_test", return_value=0) as run, \
             self.assertRaises(SystemExit) as exit_:
            main_module.main(["--check-db"])
        self.assertEqual(exit_.exception.code, 0)
        run.assert_called_once_with(check_db=True)


if __name__ == "__main__":
    unittest.main()
