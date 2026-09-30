"""Legt im bestehenden Neon-Projekt die Datenbank `analytics` und zwei Rollen an (einmalig, idempotent).

    NEON_OWNER_URL=... .venv/bin/python scripts/setup_db.py

- analytics_admin: besitzt die Datenbank, befüllt sie (scripts/laden.py)
- analyst_ro:      darf nur verbinden und SELECT auf die Analyse-Tabellen (Rechte setzt scripts/laden.py)

NEON_OWNER_URL ist der Connection String der Projekt-Owner-Rolle (Neon-Console). Das Skript erzeugt die
Passwörter selbst und schreibt ANALYTICS_ADMIN_URL und ANALYTICS_RO_URL in .env. Es gibt keine
Zugangsdaten aus. Existiert eine Rolle schon, bekommt sie ein neues Passwort (die .env wird aktualisiert).
"""

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

ENV = Path(__file__).resolve().parents[1] / ".env"
DB = "analytics"


def url_fuer(owner_url: str, rolle: str, passwort: str) -> str:
    teile = urlsplit(owner_url)
    host = teile.netloc.rsplit("@", 1)[1]
    return urlunsplit((teile.scheme, f"{rolle}:{quote(passwort, safe='')}@{host}", f"/{DB}", teile.query, ""))


def rolle_anlegen(c, rolle: str, passwort: str) -> None:
    befehl = "ALTER ROLE {} WITH LOGIN PASSWORD {}" if c.execute(
        "SELECT 1 FROM pg_roles WHERE rolname=%s", (rolle,)).fetchone() else "CREATE ROLE {} WITH LOGIN PASSWORD {}"
    c.execute(sql.SQL(befehl).format(sql.Identifier(rolle), sql.Literal(passwort)))


def env_setzen(werte: dict[str, str]) -> None:
    zeilen = [z for z in (ENV.read_text().splitlines() if ENV.exists() else []) if z.split("=", 1)[0] not in werte]
    zeilen += [f"{k}={v}" for k, v in werte.items()]
    ENV.write_text("\n".join(zeilen) + "\n")
    ENV.chmod(0o600)


def main() -> None:
    owner_url = os.environ.get("NEON_OWNER_URL")
    if not owner_url:
        sys.exit("NEON_OWNER_URL fehlt.")
    pw_admin, pw_ro = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with psycopg.connect(owner_url, autocommit=True) as c:
        rolle_anlegen(c, "analytics_admin", pw_admin)
        rolle_anlegen(c, "analyst_ro", pw_ro)
        # Ab Postgres 16 darf der Ersteller eine Rolle verwalten, aber nicht automatisch in ihrem Namen handeln.
        c.execute("GRANT analytics_admin TO CURRENT_USER")
        if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB,)).fetchone():
            c.execute(sql.SQL("CREATE DATABASE {} OWNER analytics_admin").format(sql.Identifier(DB)))
        # Zweite Sicherung neben den Rechten: Sitzungen von analyst_ro sind standardmäßig nur lesend und kurz.
        c.execute("ALTER ROLE analyst_ro SET default_transaction_read_only = on")
        c.execute("ALTER ROLE analyst_ro SET statement_timeout = '15s'")
        # Datumsgrenzen wie '2026-05-01' gelten in der Zeitzone der Sitzung: fest UTC, sonst sind Ergebnisse nicht reproduzierbar.
        c.execute("ALTER ROLE analyst_ro SET timezone = 'UTC'")
        c.execute("ALTER ROLE analytics_admin SET timezone = 'UTC'")
    with psycopg.connect(url_fuer(owner_url, "analytics_admin", pw_admin), autocommit=True) as c:
        # Niemand außer den beiden Rollen verbindet sich; kein TEMP für PUBLIC.
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DB)))
        c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO analyst_ro").format(sql.Identifier(DB)))
        c.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        c.execute("GRANT USAGE ON SCHEMA public TO analyst_ro")
    env_setzen({"ANALYTICS_ADMIN_URL": url_fuer(owner_url, "analytics_admin", pw_admin),
                "ANALYTICS_RO_URL": url_fuer(owner_url, "analyst_ro", pw_ro)})
    print(f"Datenbank {DB!r} und Rollen analytics_admin, analyst_ro eingerichtet; Zugangsdaten in .env.")


if __name__ == "__main__":
    main()
