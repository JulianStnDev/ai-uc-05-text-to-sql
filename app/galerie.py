"""Galerie: die gemessenen vollen Läufe aus evals/laeufe/ als anklickbare Beispiele, ohne API-Kosten.

Vorstufe für das Replay beim Online-Gang (Branch f). Gezeigt werden nur vollständige Läufe (alle Fragen, mindestens drei
Wiederholungen), bewertet mit den eingefrorenen Regeln aus scripts/vergleich.py.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))
from vergleich import bewerten  # noqa: E402

NAMEN = {("claude-haiku-4-5", "schema", "kurz"): "Haiku · schema",
         ("claude-haiku-4-5", "glossar", "kurz"): "Haiku · glossary",
         ("claude-haiku-4-5", "glossar", "karte"): "Haiku · glossary · answer card",
         ("claude-haiku-4-5", "glossar_spalten", "kurz"): "Haiku · glossary + column notes*",
         ("claude-sonnet-5-5", "schema", "kurz"): "Sonnet · schema",
         ("claude-sonnet-5-5", "glossar", "kurz"): "Sonnet · glossary"}


@dataclass
class Lauf:
    schluessel: str             # Dateiname ohne .jsonl, stabil als URL-Teil
    name: str
    zeilen: dict = field(default_factory=dict)   # (frage_id, wiederholung) → Protokollzeile mit „richtig“


def laden(wurzel: Path = WURZEL) -> tuple[list[dict], list[Lauf]]:
    fragen = json.loads((wurzel / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]
    nach_id = {f["id"]: f for f in fragen}
    laeufe = []
    for pfad in sorted((wurzel / "evals" / "laeufe").glob("*.jsonl")):
        zeilen = [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]
        if not zeilen or {z["frage_id"] for z in zeilen} != set(nach_id) or max(z["wiederholung"] for z in zeilen) < 3:
            continue
        erste = zeilen[0]
        k = (erste["modell"], erste["variante"], erste.get("format", "kurz"))
        lauf = Lauf(pfad.stem, NAMEN.get(k, " · ".join(k)))
        for z in zeilen:
            z["richtig"] = bool(z["antwort"]["art"]) and bewerten(nach_id[z["frage_id"]], z["antwort"], z["variante"])["richtig"]
            lauf.zeilen[(z["frage_id"], z["wiederholung"])] = z
        laeufe.append(lauf)
    reihenfolge = list(NAMEN.values())
    laeufe.sort(key=lambda l: reihenfolge.index(l.name) if l.name in reihenfolge else 99)
    return fragen, laeufe


def erwartet(frage: dict, variante: str) -> str:
    """Kurzbeschreibung der erwarteten Antwort für die Galerie-Karte."""
    typ, ergebnis = frage["typ"], frage.get("ergebnis")
    if variante.startswith("glossar") and frage.get("mit_glossar"):
        typ, ergebnis = frage["mit_glossar"]["typ"], frage["mit_glossar"]["ergebnis"]
    if typ == "mehrdeutig":
        return "a clarifying question"
    if typ == "unbeantwortbar":
        return "“no data on this”"
    return " · ".join(" ".join(str(v) for v in z) for z in ergebnis["zeilen"])
