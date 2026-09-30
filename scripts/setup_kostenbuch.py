"""Legt im Neon-Projekt die Datenbank `uc5_app` und die Rolle `uc5_app` für das Kostenbuch der Web-App an (einmalig).

    .venv/bin/python scripts/setup_kostenbuch.py      # liest NEON_OWNER_URL aus .env

- uc5_app besitzt nur die Datenbank uc5_app (Tabelle `kosten`, legt die App selbst an). Kein Zugriff auf `analytics`.
- Die App braucht den Owner-Zugang nie: Sie liest nur ANALYTICS_RO_URL und KOSTEN_DB_URL (app/einstellungen.py).
  NEON_OWNER_URL kann nach diesem Skript wieder aus der .env gelöscht werden.

Das Skript erzeugt das Passwort selbst, schreibt KOSTEN_DB_URL in .env und gibt keine Zugangsdaten aus. Existiert die
Rolle schon, bekommt sie ein neues Passwort.
"""

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_db import ENV, env_setzen, rolle_anlegen  # noqa: E402

DB = ROLLE = "uc5_app"


def url(owner_url: str, passwort: str) -> str:
    teile = urlsplit(owner_url)
    host = teile.netloc.rsplit("@", 1)[1]
    return urlunsplit((teile.scheme, f"{ROLLE}:{quote(passwort, safe='')}@{host}", f"/{DB}", teile.query, ""))


def main() -> None:
    load_dotenv(ENV)
    owner_url = os.environ.get("NEON_OWNER_URL")
    if not owner_url:
        sys.exit("NEON_OWNER_URL fehlt in .env.")
    passwort = secrets.token_urlsafe(24)
    with psycopg.connect(owner_url, autocommit=True) as c:
        rolle_anlegen(c, ROLLE, passwort)
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,)).fetchone():
            c.execute(sql.SQL("GRANT {} TO CURRENT_USER").format(sql.Identifier(ROLLE)))  # nötig für OWNER auf Neon
            c.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DB), sql.Identifier(ROLLE)))
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DB)))
        # uc5_app darf nicht in die Analyse-Datenbank (dort ist CONNECT für PUBLIC schon entzogen, setup_db.py)
        assert not c.execute("SELECT has_database_privilege(%s, 'analytics', 'CONNECT')", (ROLLE,)).fetchone()[0]
    kosten_url = url(owner_url, passwort)
    with psycopg.connect(kosten_url, autocommit=True) as c:
        c.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
    env_setzen({"KOSTEN_DB_URL": kosten_url})
    print("Datenbank und Rolle uc5_app eingerichtet; KOSTEN_DB_URL in .env. NEON_OWNER_URL kann jetzt gelöscht werden.")


if __name__ == "__main__":
    main()
