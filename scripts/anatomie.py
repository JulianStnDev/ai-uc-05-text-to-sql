"""Experimente für docs/ANATOMIE.md: Rohmitschnitte einzelner Läufe und ein Satz mehr im Prompt.

    .venv/bin/python scripts/anatomie.py --budget 0.20        # nur Schätzung
    .venv/bin/python scripts/anatomie.py --budget 0.20 --ja   # ausführen (kostet Geld, nach Freigabe)

1. Mitschnitt: U01 und U02 mit Haiku, U01 mit Sonnet (Thinking als Zusammenfassung sichtbar). Jeder API-Aufruf roh
   als JSON nach evals/anatomie/mitschnitt_<frage>_<modell>.json.
2. Ein Satz Prompt: U01 und M02 je 5 × mit Haiku und ZUSATZ am Ende des System-Prompts, als JSONL nach
   evals/anatomie/zusatz_haiku.jsonl (nicht in evals/laeufe/, damit es nie als Messlauf zählt).

Die Bewertung nutzt dieselben Regeln wie die Messung (scripts/vergleich.py).
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
ZIEL = WURZEL / "evals" / "anatomie"
ZUSATZ = ("Wenn die Daten eine Frage nicht beantworten oder sie mehrdeutig ist, sag das oder frag nach, statt eine "
          "ähnliche Spalte oder eine eigene Deutung zu verwenden.")
MITSCHNITTE = [("U01", "haiku"), ("U02", "haiku"), ("U01", "sonnet")]
ZUSATZ_FRAGEN, ZUSATZ_WDH = ["U01", "M02"], 5
# Geschätzt aus dem vollen Lauf (Mittel je Frage, Sonnet mit Cache-Schreiben), Obergrenze für die Budget-Prüfung.
SCHAETZUNG = {("U01", "haiku"): 0.0067, ("U02", "haiku"): 0.0054, ("M02", "haiku"): 0.0046, ("U01", "sonnet"): 0.0110}
OBERGRENZE_JE_LAUF = {"haiku": 0.05, "sonnet": 0.15}


def main() -> None:
    p = argparse.ArgumentParser(description="Experimente für docs/ANATOMIE.md (kostet API-Geld).")
    p.add_argument("--budget", type=float, required=True)
    p.add_argument("--ja", action="store_true")
    a = p.parse_args()

    plan = [("mitschnitt", f, m, 1) for f, m in MITSCHNITTE]
    plan += [("zusatz", f, "haiku", w) for w in range(1, ZUSATZ_WDH + 1) for f in ZUSATZ_FRAGEN]
    schaetzung = sum(SCHAETZUNG[(f, m)] for _, f, m, _ in plan)
    print(f"{len(plan)} Läufe ({len(MITSCHNITTE)} Mitschnitte, {len(ZUSATZ_FRAGEN)} × {ZUSATZ_WDH} mit Zusatz): "
          f"geschätzt {schaetzung:.3f} USD, Budget {a.budget:.2f} USD.")
    if not a.ja:
        print("Nur Schätzung. Zum Starten --ja angeben (nach Freigabe).")
        return
    load_dotenv(WURZEL / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY fehlt in .env.")
    import anthropic
    client = anthropic.Anthropic()
    fragen = {f["id"]: f for f in json.loads((WURZEL / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]}
    ZIEL.mkdir(parents=True, exist_ok=True)
    summe = 0.0
    with verbinden(os.environ["ANALYTICS_RO_URL"]) as conn:
        for art, fid, modell, w in plan:
            if summe + OBERGRENZE_JE_LAUF[modell] > a.budget:
                print(f"Budget {a.budget:.2f} USD erreicht ({summe:.4f} USD verbraucht), Abbruch vor {art} {fid}.")
                break
            mitschnitt = [] if art == "mitschnitt" else None
            lauf = beantworten(client, conn, fragen[fid]["frage"], modell, zusatz=ZUSATZ if art == "zusatz" else None,
                               thinking_anzeigen=(art == "mitschnitt"), mitschnitt=mitschnitt)
            b = (bewerten(fragen[fid], lauf["antwort"]) if lauf["antwort"]["art"]
                 else {"richtig": False, "grund": f"keine Antwort ({lauf['fehler']})"})
            zeile = {"zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"), "experiment": art,
                     "frage_id": fid, "typ": fragen[fid]["typ"], "wiederholung": w, "modell": MODELLE[modell]["id"],
                     "variante": "schema", "zusatz": ZUSATZ if art == "zusatz" else None, **lauf, "bewertung": b}
            if art == "mitschnitt":
                zeile["aufrufe_roh"] = mitschnitt
                (ZIEL / f"mitschnitt_{fid}_{modell}.json").write_text(
                    json.dumps(zeile, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
            else:
                with (ZIEL / "zusatz_haiku.jsonl").open("a", encoding="utf-8") as datei:
                    datei.write(json.dumps(zeile, ensure_ascii=False, default=str) + "\n")
            summe += lauf["kosten_usd"]
            print(f"{art:10} {fid} {modell:6} Wdh. {w}: {'✓' if b['richtig'] else '✗'} {lauf['antwort']['art']:12} "
                  f"{lauf['kosten_usd']:.4f} USD  Summe {summe:.4f} USD")
    print(f"\nKosten {summe:.4f} USD, Dateien in {ZIEL.relative_to(WURZEL)}/")


if __name__ == "__main__":
    main()
