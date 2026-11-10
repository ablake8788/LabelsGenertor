"""
Reads the database connection from config.ini (kept next to label_app.py, or next to the .exe).
If config.ini is missing, a template is created on first start.
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

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


def config_path(app_dir: Path) -> Path:
    return Path(app_dir) / "config.ini"


def ensure_config(app_dir: Path) -> Path:
    p = config_path(app_dir)
    if not p.exists():
        p.write_text(TEMPLATE, encoding="utf-8")
    return p


def _yes(v: str) -> bool:
    return str(v).strip().lower() in ("1", "yes", "true", "y", "on")


def load_connection_string(app_dir: Path) -> str:
    """Build the ODBC connection string from config.ini. Raises ValueError with a clear message."""
    p = ensure_config(app_dir)
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(p, encoding="utf-8")
    if not cp.has_section("database"):
        raise ValueError(f"{p.name} has no [database] section.")
    d = cp["database"]

    full = d.get("connection_string", "").strip()
    if full:
        return full

    server = d.get("server", "").strip()
    if not server:
        raise ValueError(f"No server set. Open {p.name} and fill in 'server ='.")
    parts = [
        f"DRIVER={{{d.get('driver', 'ODBC Driver 17 for SQL Server').strip()}}}",
        f"SERVER={server}",
        f"DATABASE={d.get('database', '').strip()}",
    ]
    if _yes(d.get("trusted_connection", "no")):
        parts.append("Trusted_Connection=yes")
    else:
        user = d.get("username", "").strip()
        if not user:
            raise ValueError(f"trusted_connection = no, so {p.name} needs 'username =' and 'password ='.")
        pwd = d.get("password", "")
        parts += [f"UID={user}", "PWD={" + pwd.replace("}", "}}") + "}"]
    parts.append(f"Encrypt={'yes' if _yes(d.get('encrypt', 'no')) else 'no'}")
    if _yes(d.get("trust_server_certificate", "yes")):
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts) + ";"


def masked(conn_str: str) -> str:
    """Connection string safe to show on screen (password hidden, including {braced; values})."""
    return re.sub(r"(?i)\b(PWD|Password)=(\{(?:[^}]|\}\})*\}|[^;]*)", r"\1=*****", conn_str)
