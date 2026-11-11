"""
Database settings from config.ini (next to label_app.py, or next to the .exe).
If config.ini is missing, a template is created on first use.
"""
from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "config.ini"

TEMPLATE = """\
; ---------------------------------------------------------------------------
;  Label Generator - database settings
;  Fill in [database], save this file, then click "Reload config.ini" in the app
;  (or restart it). Lines starting with ; are comments.
; ---------------------------------------------------------------------------
[database]
; ODBC driver installed on this PC. Usually one of:
;   ODBC Driver 18 for SQL Server
;   ODBC Driver 17 for SQL Server
;   SQL Server
driver = ODBC Driver 17 for SQL Server

; SQL Server name, e.g.  MYPC\\SQLEXPRESS   or   sql1234.site4now.net   or   10.0.0.5,1433
server =

database = DB_9BB9A7_prestige

; yes = Windows login (no username/password)
; no  = SQL login, fill username and password below
trusted_connection = no
username =
password =

; ODBC Driver 18 encrypts by default; keep trust_server_certificate = yes unless your server has a valid certificate.
encrypt = no
trust_server_certificate = yes

; Optional: a complete ODBC connection string. When filled, it is used INSTEAD of the fields above.
connection_string =
"""


class ConfigError(ValueError):
    """config.ini is missing something; the message says what to fix."""


def _yes(value: str) -> bool:
    return str(value).strip().lower() in ("1", "yes", "true", "y", "on")


@dataclass(frozen=True)
class DatabaseConfig:
    driver: str = "ODBC Driver 17 for SQL Server"
    server: str = ""
    database: str = ""
    trusted_connection: bool = False
    username: str = ""
    password: str = ""
    encrypt: bool = False
    trust_server_certificate: bool = True
    connection_string: str = ""

    def to_connection_string(self, source: str = CONFIG_NAME) -> str:
        """ODBC connection string. Raises ConfigError with a clear message when something is missing."""
        if self.connection_string:
            return self.connection_string
        if not self.server:
            raise ConfigError(f"No server set. Open {source} and fill in 'server ='.")
        parts = [f"DRIVER={{{self.driver}}}", f"SERVER={self.server}", f"DATABASE={self.database}"]
        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if not self.username:
                raise ConfigError(f"trusted_connection = no, so {source} needs 'username =' and 'password ='.")
            parts += [f"UID={self.username}", "PWD={" + self.password.replace("}", "}}") + "}"]
        parts.append(f"Encrypt={'yes' if self.encrypt else 'no'}")
        if self.trust_server_certificate:
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts) + ";"


class IniConfigLoader:
    """Reads config.ini fresh on every call, so edits apply without restarting the app."""

    def __init__(self, app_dir: Path):
        self.path = Path(app_dir) / CONFIG_NAME

    def ensure(self) -> Path:
        if not self.path.exists():
            self.path.write_text(TEMPLATE, encoding="utf-8")
        return self.path

    def load(self) -> DatabaseConfig:
        self.ensure()
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(self.path, encoding="utf-8")
        if not cp.has_section("database"):
            raise ConfigError(f"{self.path.name} has no [database] section.")
        d = cp["database"]
        return DatabaseConfig(
            driver=d.get("driver", DatabaseConfig.driver).strip(),
            server=d.get("server", "").strip(),
            database=d.get("database", "").strip(),
            trusted_connection=_yes(d.get("trusted_connection", "no")),
            username=d.get("username", "").strip(),
            password=d.get("password", ""),
            encrypt=_yes(d.get("encrypt", "no")),
            trust_server_certificate=_yes(d.get("trust_server_certificate", "yes")),
            connection_string=d.get("connection_string", "").strip(),
        )

    def connection_string(self) -> str:
        return self.load().to_connection_string(self.path.name)


def masked(conn_str: str) -> str:
    """Connection string safe to show on screen (password hidden, including {braced; values})."""
    return re.sub(r"(?i)\b(PWD|Password)=(\{(?:[^}]|\}\})*\}|[^;]*)", r"\1=*****", conn_str)
