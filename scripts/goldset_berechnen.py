"""Berechnet die erwarteten Ergebnisse des Goldsets aus der Datenbank (als analyst_ro, nur lesend, keine API).

    .venv/bin/python scripts/goldset_berechnen.py

Liest evals/goldset_fragen.py, schreibt evals/goldset.json (Fragen, SQL, Ergebnisse) und evals/goldset.md
(Tabelle zur Durchsicht). Bricht ab, wenn eine naive Abfrage dasselbe Ergebnis liefert wie die Referenz.
"""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "evals"))
from goldset_fragen import FALLEN_BELEGE, FRAGEN  # noqa: E402


def wert(v):
    return str(v) if isinstance(v, Decimal) else v


def ausfuehren(c, sql: str) -> dict:
    cur = c.execute(sql)
    return {"spalten": [d.name for d in cur.description], "zeilen": [[wert(v) for v in z] for z in cur.fetchall()]}


def kurz(ergebnis: dict) -> str:
    """z. B. "kunden: 211" oder "DE 180 · US 126 · …" für die Tabelle."""
    z = ergebnis["zeilen"]
    if len(z) == 1 and len(z[0]) == 1:
        return f"{ergebnis['spalten'][0]}: {z[0][0]}"
    if len(z) == 1:
        return ", ".join(f"{s}: {v}" for s, v in zip(ergebnis["spalten"], z[0]))
    return " · ".join(" ".join(str(v) for v in zeile) for zeile in z)


def verbinden():
    load_dotenv(WURZEL / ".env")
    c = psycopg.connect(os.environ["ANALYTICS_RO_URL"], autocommit=True)
    c.execute("SET TIME ZONE 'UTC'")  # Datumsgrenzen der Referenz-SQL gelten in UTC
    return c


def berechnen(c) -> tuple[list[dict], list[dict]]:
    ergebnisse = []
    for f in FRAGEN:
        e = dict(f)
        if f["typ"] == "mehrdeutig":
            e["deutungen"] = [{**d, "ergebnis": ausfuehren(c, d["sql"])} for d in f["deutungen"]]
        else:
            e["ergebnis"] = ausfuehren(c, f["sql"])
        if f.get("naiv_sql"):
            e["naiv_ergebnis"] = ausfuehren(c, f["naiv_sql"])
            if e["naiv_ergebnis"]["zeilen"] == e["ergebnis"]["zeilen"]:
                sys.exit(f"{f['id']}: naive Abfrage liefert dasselbe Ergebnis, die Falle greift nicht.")
        ergebnisse.append(e)
    belege = []
    for b in FALLEN_BELEGE:
        r, n = ausfuehren(c, b["richtig_sql"]), ausfuehren(c, b["naiv_sql"])
        if r["zeilen"] == n["zeilen"]:
            sys.exit(f"Falle {b['falle']}: kein Unterschied.")
        belege.append({**b, "richtig": r, "naiv": n})
    return ergebnisse, belege


def tabelle(ergebnisse: list[dict]) -> str:
    zeilen = ["| ID | Typ | Frage | Falle | Erwartet | Naiv (Falle) |", "|---|---|---|---|---|---|"]
    for e in ergebnisse:
        if e["typ"] == "mehrdeutig":
            erwartet = f"**Rückfrage:** {e['rueckfrage']}<br>" + "<br>".join(
                f"({i}) {d['deutung']}: {kurz(d['ergebnis'])}" for i, d in enumerate(e["deutungen"], 1))
        else:
            erwartet = kurz(e["ergebnis"])
        naiv = f"{kurz(e['naiv_ergebnis'])} ({e['naiv_fehler']})" if e.get("naiv_ergebnis") else ""
        zeilen.append(f"| {e['id']} | {e['typ']} | {e['frage']} | {', '.join(e['fallen']) or '–'} | {erwartet} | {naiv} |")
    return "\n".join(zeilen)


def main() -> None:
    with verbinden() as c:
        ergebnisse, belege = berechnen(c)
    (WURZEL / "evals" / "goldset.json").write_text(
        json.dumps({"fragen": ergebnisse, "fallen_belege": belege}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (WURZEL / "evals" / "goldset.md").write_text(
        "# Goldset (berechnet, zur Durchsicht)\n\nErzeugt von `scripts/goldset_berechnen.py` aus `evals/goldset_fragen.py`. "
        "Nicht von Hand bearbeiten.\n\n" + tabelle(ergebnisse) + "\n\n## Beleg je Falle\n\n| Falle | Frage | richtig | naiv |\n|---|---|---|---|\n"
        + "\n".join(f"| {b['falle']} | {b['frage']} | {kurz(b['richtig'])} | {kurz(b['naiv'])} |" for b in belege) + "\n",
        encoding="utf-8")
    typen = [e["typ"] for e in ergebnisse]
    print(f"{len(ergebnisse)} Fragen: {typen.count('eindeutig')} eindeutig, {typen.count('mehrdeutig')} mehrdeutig, {typen.count('falle')} Fallen")
    for b in belege:
        print(f"  {b['falle']:22} richtig {kurz(b['richtig']):28} naiv {kurz(b['naiv'])}")


if __name__ == "__main__":
    main()
