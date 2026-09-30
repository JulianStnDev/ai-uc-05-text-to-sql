"""Messlauf: jede Goldset-Frage durch den Copiloten, Ergebnis sofort bewertet und als JSONL gespeichert.

    .venv/bin/python scripts/baseline.py --modell haiku --budget 0.50                  # Pilot: 27 Fragen × 1
    .venv/bin/python scripts/baseline.py --modell sonnet --wiederholungen 3 --budget 5  # voller Lauf
    .venv/bin/python scripts/baseline.py --modell haiku --fragen F01 U01 --budget 0.10

KOSTET GELD (Anthropic-API). Vorher schätzen und Julians Okay einholen (CLAUDE.md). Der Lauf zeigt zuerst die
Schätzung und startet nur mit --ja. Er bricht ab, bevor die nächste Frage das Budget überschreiten könnte.
Jede Zeile wird sofort geschrieben, ein Abbruch verliert also nichts.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copilot import MODELLE, beantworten, verbinden  # noqa: E402
from vergleich import bewerten  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]
# Schätzung je Frage in USD (docs/decisions.md, 2026-09-30), bis der Pilot echte Werte liefert.
SCHAETZUNG = {"haiku": 0.010, "sonnet": 0.034}
OBERGRENZE_JE_FRAGE = {"haiku": 0.05, "sonnet": 0.15}  # für die Budget-Prüfung vor jeder Frage


def fragen_laden(ids: list[str] | None) -> list[dict]:
    fragen = json.loads((WURZEL / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]
    if ids:
        unbekannt = set(ids) - {f["id"] for f in fragen}
        if unbekannt:
            sys.exit(f"Unbekannte Fragen: {sorted(unbekannt)}")
        fragen = [f for f in fragen if f["id"] in ids]
    return fragen


def bewertung(frage: dict, lauf: dict, variante: str) -> dict:
    if lauf["antwort"]["art"] is None:
        return {"richtig": False, "grund": f"keine Antwort ({lauf['fehler']})"}
    return bewerten(frage, lauf["antwort"], variante)


def ausfuehren(client, conn, fragen, modell, variante, wiederholungen, budget, ziel: Path, ausgabe=print) -> dict:
    """Führt die Läufe aus und hängt je Lauf eine JSONL-Zeile an `ziel` an. Gibt eine Zusammenfassung zurück."""
    summe, richtig, n = 0.0, 0, 0
    for w in range(1, wiederholungen + 1):
        for f in fragen:
            if summe + OBERGRENZE_JE_FRAGE[modell] > budget:
                ausgabe(f"Budget {budget:.2f} USD erreicht ({summe:.4f} USD verbraucht), Abbruch vor {f['id']} (Wdh. {w}).")
                return {"laeufe": n, "richtig": richtig, "kosten_usd": summe, "abgebrochen": True}
            lauf = beantworten(client, conn, f["frage"], modell, variante)
            b = bewertung(f, lauf, variante)
            zeile = {"zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"), "frage_id": f["id"], "typ": f["typ"],
                     "wiederholung": w, "modell": MODELLE[modell]["id"], "variante": variante, **lauf, "bewertung": b}
            with ziel.open("a", encoding="utf-8") as datei:
                datei.write(json.dumps(zeile, ensure_ascii=False, default=str) + "\n")
            summe, n, richtig = summe + lauf["kosten_usd"], n + 1, richtig + b["richtig"]
            ausgabe(f"{f['id']} Wdh. {w}: {'✓' if b['richtig'] else '✗'} {b['grund']:32} {lauf['kosten_usd']:.4f} USD "
                    f"{lauf['dauer_s']:5.1f} s  Summe {summe:.4f} USD")
    return {"laeufe": n, "richtig": richtig, "kosten_usd": summe, "abgebrochen": False}


def main() -> None:
    p = argparse.ArgumentParser(description="Messlauf gegen das Goldset (kostet API-Geld).")
    p.add_argument("--modell", choices=sorted(MODELLE), required=True)
    p.add_argument("--variante", choices=["schema", "glossar", "glossar_spalten"], default="schema")
    p.add_argument("--wiederholungen", type=int, default=1)
    p.add_argument("--fragen", nargs="*")
    p.add_argument("--budget", type=float, required=True, help="harte Obergrenze in USD für diesen Lauf")
    p.add_argument("--ja", action="store_true", help="ohne --ja wird nur die Schätzung gezeigt")
    a = p.parse_args()

    fragen = fragen_laden(a.fragen)
    n = len(fragen) * a.wiederholungen
    print(f"{n} Läufe ({len(fragen)} Fragen × {a.wiederholungen}) mit {MODELLE[a.modell]['id']}, Variante {a.variante}: "
          f"geschätzt {n * SCHAETZUNG[a.modell]:.2f} USD, Budget {a.budget:.2f} USD.")
    if not a.ja:
        print("Nur Schätzung. Zum Starten --ja angeben (nach Freigabe).")
        return
    load_dotenv(WURZEL / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY fehlt in .env.")
    import anthropic
    ziel = WURZEL / "evals" / "laeufe" / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}_{a.modell}_{a.variante}.jsonl"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with verbinden(os.environ["ANALYTICS_RO_URL"]) as conn:
        z = ausfuehren(anthropic.Anthropic(), conn, fragen, a.modell, a.variante, a.wiederholungen, a.budget, ziel)
    print(f"\n{z['richtig']}/{z['laeufe']} richtig, {z['kosten_usd']:.4f} USD, Protokoll: {ziel.relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
