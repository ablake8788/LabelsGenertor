import tempfile
import unittest
from pathlib import Path

import label_config as cfg


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        cfg.ensure_config(self.dir)
        self.ini = self.dir / "config.ini"
        self.template = self.ini.read_text(encoding="utf-8")

    def write(self, **values):
        t = self.template
        for k, v in values.items():
            lines = [f"{k} = {v}" if line.split("=")[0].strip() == k and not line.startswith(";") else line
                     for line in t.splitlines()]
            t = "\n".join(lines) + "\n"
        self.ini.write_text(t, encoding="utf-8")

    def test_template_created(self):
        self.assertTrue(self.ini.exists())
        self.assertIn("[database]", self.template)

    def test_missing_server(self):
        with self.assertRaisesRegex(ValueError, "server"):
            cfg.load_connection_string(self.dir)

    def test_sql_login_needs_user(self):
        self.write(server="sql.example.com")
        with self.assertRaisesRegex(ValueError, "username"):
            cfg.load_connection_string(self.dir)

    def test_sql_login(self):
        self.write(server="sql.example.com", username="u1", password="p;a}ss")
        s = cfg.load_connection_string(self.dir)
        self.assertIn("SERVER=sql.example.com;", s)
        self.assertIn("DATABASE=DB_9BB9A7_prestige;", s)
        self.assertIn("UID=u1;", s)
        self.assertIn("PWD={p;a}}ss};", s)
        self.assertIn("TrustServerCertificate=yes", s)

    def test_windows_login(self):
        self.write(server="PC\\SQLEXPRESS", trusted_connection="yes")
        s = cfg.load_connection_string(self.dir)
        self.assertIn("Trusted_Connection=yes", s)
        self.assertNotIn("UID=", s)

    def test_full_connection_string_wins(self):
        self.write(server="ignored", connection_string="DSN=MyDsn;")
        self.assertEqual(cfg.load_connection_string(self.dir), "DSN=MyDsn;")

    def test_masked_hides_password(self):
        self.assertEqual(cfg.masked("UID=u;PWD={p;a}}ss};Encrypt=no;"), "UID=u;PWD=*****;Encrypt=no;")
        self.assertEqual(cfg.masked("UID=u;Password=abc;X=1"), "UID=u;Password=*****;X=1")


if __name__ == "__main__":
    unittest.main()
