"""Auswertung der Messläufe (evals/laeufe/*.jsonl), ohne API.

    .venv/bin/python scripts/auswerten.py evals/laeufe/20261001-*.jsonl

Bewertet jeden Lauf neu mit scripts/vergleich.py (die Regeln stehen fest, die gespeicherte Bewertung dient nur zur
Kontrolle) und gibt je Modell und Variante aus: Trefferquote gesamt und je Fragetyp, die fünf Fallen-Fragen,
Kosten je 1000 Requests, p50/p95-Dauer, pass^k (Frage in allen k Wiederholungen richtig) und eine Matrix
Frage × Wiederholung.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vergleich import bewerten  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]
TYPEN = [("eindeutig", "E"), ("mehrdeutig", "M"), ("falle", "F"), ("unbeantwortbar", "U")]


def perzentil(werte: list[float], q: float) -> float | None:
    """Nächster Rang, wie in UC7."""
    if not werte:
        return None
    s = sorted(werte)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def laden(pfade: list[Path]) -> list[dict]:
    return [json.loads(z) for p in pfade for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


def neu_bewerten(lauf: dict, fragen: dict) -> bool:
    if lauf["antwort"]["art"] is None:
        return False
    return bewerten(fragen[lauf["frage_id"]], lauf["antwort"], lauf["variante"])["richtig"]


def kennzahlen(laeufe: list[dict], fragen: dict) -> dict:
    richtig = [neu_bewerten(l, fragen) for l in laeufe]
    abweichend = sum(r != l["bewertung"]["richtig"] for r, l in zip(richtig, laeufe))
    je_typ = {}
    for typ, _ in TYPEN:
        r = [ok for ok, l in zip(richtig, laeufe) if l["typ"] == typ]
        je_typ[typ] = (sum(r), len(r))
    fallen = {}
    for ok, l in zip(richtig, laeufe):
        if l["typ"] == "falle":
            a, b = fallen.get(l["frage_id"], (0, 0))
            fallen[l["frage_id"]] = (a + ok, b + 1)
    je_frage = defaultdict(list)
    for ok, l in zip(richtig, laeufe):
        je_frage[l["frage_id"]].append(ok)
    dauern = [l["dauer_s"] for l in laeufe]
    return {"richtig": sum(richtig), "n": len(laeufe), "je_typ": je_typ, "fallen": dict(sorted(fallen.items())),
            "kosten_je_1000": 1000 * sum(l["kosten_usd"] for l in laeufe) / len(laeufe),
            "kosten_gesamt": sum(l["kosten_usd"] for l in laeufe),
            "pass_k": sum(all(v) for v in je_frage.values()), "fragen": len(je_frage),
            "wdh": max(len(v) for v in je_frage.values()), "p50": perzentil(dauern, 0.5), "p95": perzentil(dauern, 0.95),
            "sql_je_frage": sum(len(l["sql_ausfuehrungen"]) for l in laeufe) / len(laeufe),
            "fehler": sum(bool(l["fehler"]) for l in laeufe), "abweichend": abweichend}


def bericht(laeufe: list[dict], fragen: dict) -> str:
    gruppen = defaultdict(list)
    for l in laeufe:
        gruppen[(l["modell"], l["variante"])].append(l)
    zeilen = ["| Modell | Variante | richtig | pass^k | E | M | F | U | Kosten/1000 Req. | p50 | p95 | SQL/Frage | Fehler |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    matrizen = []
    for (modell, variante), gruppe in sorted(gruppen.items()):
        k = kennzahlen(gruppe, fragen)
        typ = " | ".join(f"{a}/{b}" for a, b in k["je_typ"].values())
        zeilen.append(f"| {modell} | {variante} | {k['richtig']}/{k['n']} ({100 * k['richtig'] / k['n']:.0f} %) | "
                      f"{k['pass_k']}/{k['fragen']} (k={k['wdh']}) | {typ} | "
                      f"{k['kosten_je_1000']:.2f} USD | {k['p50']:.1f} s | {k['p95']:.1f} s | {k['sql_je_frage']:.1f} | {k['fehler']} |")
        if k["abweichend"]:
            zeilen.append(f"| ⚠ {k['abweichend']} gespeicherte Bewertungen weichen von der Neubewertung ab | | | | | | | | | | | | |")
        wdh = sorted({l["wiederholung"] for l in gruppe})
        matrix = [f"\n### {modell} · {variante}\n", "| Frage | " + " | ".join(f"Wdh. {w}" for w in wdh) + " |",
                  "|---|" + "---|" * len(wdh)]
        for fid in sorted({l["frage_id"] for l in gruppe}):
            zellen = []
            for w in wdh:
                l = next((x for x in gruppe if x["frage_id"] == fid and x["wiederholung"] == w), None)
                zellen.append("–" if l is None else ("✓" if neu_bewerten(l, fragen) else f"✗ {l['antwort']['art'] or 'keine'}"))
            matrix.append(f"| {fid} | " + " | ".join(zellen) + " |")
        matrizen += matrix
    return "\n".join(zeilen + matrizen)


def main() -> None:
    pfade = [Path(p) for p in sys.argv[1:]]
    if not pfade:
        sys.exit("Pfade zu JSONL-Dateien angeben.")
    fragen = {f["id"]: f for f in json.loads((WURZEL / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]}
    print(bericht(laden(pfade), fragen))


if __name__ == "__main__":
    main()
