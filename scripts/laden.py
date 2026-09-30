"""Lädt die erzeugten Daten als analytics_admin in Neon und setzt die Rechte für analyst_ro.

    .venv/bin/python scripts/laden.py

Legt alle Tabellen neu an (db/schema.sql), füllt sie per COPY und gibt analyst_ro ausschließlich SELECT
auf die Analyse-Tabellen, bei customers ohne die Spalte email (Branch e). Deterministisch: Jeder Lauf erzeugt
dieselben Daten (fester Seed). Nur die Rechte neu setzen, ohne Daten neu zu laden: --nur-rechte.
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
# Personenbezogen, für Analysen nicht nötig: analyst_ro darf sie nicht lesen (docs/decisions.md, Branch e).
GESPERRTE_SPALTEN = {"customers": ["email"]}


def rechte_setzen(c) -> None:
    """SELECT für analyst_ro: ganze Tabellen, außer bei gesperrten Spalten nur die erlaubten Spalten einzeln."""
    c.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
    c.execute(sql.SQL("REVOKE ALL ON {} FROM analyst_ro").format(sql.SQL(", ").join(map(sql.Identifier, TABELLEN))))
    for t in TABELLEN:
        gesperrt = GESPERRTE_SPALTEN.get(t)
        if not gesperrt:
            c.execute(sql.SQL("GRANT SELECT ON {} TO analyst_ro").format(sql.Identifier(t)))
            continue
        spalten = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = "
                                           "'public' AND table_name = %s ORDER BY ordinal_position", (t,))]
        erlaubt = [s for s in spalten if s not in gesperrt]
        c.execute(sql.SQL("GRANT SELECT ({}) ON {} TO analyst_ro").format(
            sql.SQL(", ").join(map(sql.Identifier, erlaubt)), sql.Identifier(t)))


def main() -> None:
    load_dotenv(WURZEL / ".env")
    if "--nur-rechte" in sys.argv:
        with psycopg.connect(os.environ["ANALYTICS_ADMIN_URL"]) as c:
            rechte_setzen(c)
        print("Rechte für analyst_ro neu gesetzt (customers ohne email).")
        return
    daten = erzeugen()
    with psycopg.connect(os.environ["ANALYTICS_ADMIN_URL"]) as c:  # eine Transaktion: alles oder nichts
        for t in reversed(TABELLEN):
            c.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(t)))
        c.execute((WURZEL / "db" / "schema.sql").read_text())
        for t in TABELLEN:
            with c.cursor().copy(sql.SQL("COPY {} FROM STDIN").format(sql.Identifier(t))) as copy:
                for zeile in daten[t]:
                    copy.write_row(zeile)
        rechte_setzen(c)
    with psycopg.connect(os.environ["ANALYTICS_ADMIN_URL"], autocommit=True) as c:
        c.execute("ANALYZE")
        for t in TABELLEN:
            print(f"{t:20} {c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(t))).fetchone()[0]:>7}")


if __name__ == "__main__":
    main()
