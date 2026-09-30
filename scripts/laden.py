"""Lädt die erzeugten Daten als analytics_admin in Neon und setzt die Rechte für analyst_ro.

    .venv/bin/python scripts/laden.py

Legt alle Tabellen neu an (db/schema.sql), füllt sie per COPY und gibt analyst_ro ausschließlich SELECT
auf die Analyse-Tabellen. Deterministisch: Jeder Lauf erzeugt dieselben Daten (fester Seed).
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daten_erzeugen import erzeugen  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]
TABELLEN = ["customers", "subscriptions", "cancellations", "payments", "refunds", "store_transactions", "logins"]


def main() -> None:
    load_dotenv(WURZEL / ".env")
    daten = erzeugen()
    with psycopg.connect(os.environ["ANALYTICS_ADMIN_URL"]) as c:  # eine Transaktion: alles oder nichts
        for t in reversed(TABELLEN):
            c.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(t)))
        c.execute((WURZEL / "db" / "schema.sql").read_text())
        for t in TABELLEN:
            with c.cursor().copy(sql.SQL("COPY {} FROM STDIN").format(sql.Identifier(t))) as copy:
                for zeile in daten[t]:
                    copy.write_row(zeile)
        c.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
        c.execute(sql.SQL("GRANT SELECT ON {} TO analyst_ro").format(sql.SQL(", ").join(map(sql.Identifier, TABELLEN))))
    with psycopg.connect(os.environ["ANALYTICS_ADMIN_URL"], autocommit=True) as c:
        c.execute("ANALYZE")
        for t in TABELLEN:
            print(f"{t:20} {c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(t))).fetchone()[0]:>7}")


if __name__ == "__main__":
    main()
