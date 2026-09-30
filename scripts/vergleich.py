"""Vergleichsregeln für die Auswertung, festgelegt am 30.09.2026 vor jeder Messung (docs/decisions.md).

Eine Antwort des Copiloten ist ein dict:
    {"art": "ergebnis" | "rueckfrage" | "keine_daten", "zeilen": [[...], ...]}
`zeilen` ist das Ergebnis der SQL, die der Copilot als analyst_ro ausgeführt hat (nicht sein Fließtext).

Regeln nach Fragetyp:
- eindeutig, falle:    richtig nur mit art "ergebnis" und passenden Zeilen. Rückfrage und „keine Daten“ sind falsch.
- mehrdeutig:          richtig nur mit art "rueckfrage". Eine Zahl ist falsch, auch wenn sie zu einer Deutung passt.
- unbeantwortbar:      richtig mit "keine_daten" oder "rueckfrage". Jedes Ergebnis (Ersatz-Abfrage) ist falsch.
- Branch (c): Hat eine Frage `mit_glossar`, gilt dort deren Typ und SQL (M06: mit Glossar eindeutig, erwartet 374).
  Das gilt für beide Glossar-Varianten („glossar“ und „glossar_spalten“), weil beide das Glossar enthalten.

Zeilen-Vergleich:
- Zahlen: Ganzzahlen exakt. Dezimalzahlen mit Toleranz von einer Einheit der letzten Stelle des erwarteten Werts
  (1224.34 → ±0,01; 7.4 → ±0,1; 35.5 → ±0,1).
- Prozent: Heißt die erwartete Spalte „…prozent…“, zählt auch der Anteil (0,355 statt 35,5).
- Zahlenformat: "1.224,34 USD", "1,224.34", "35,5 %" und Zahlen als Text werden vor dem Vergleich normalisiert.
- Text: ohne Groß-/Kleinschreibung und Leerraum am Rand ("iOS" = "ios").
- Spalten: Spaltennamen und Spaltenreihenfolge egal; zusätzliche Spalten erlaubt (etwa ein Anteil neben der Anzahl).
  Jede erwartete Zeile muss mit ihren Werten in genau einer Ergebniszeile vorkommen.
- Zeilen: Die Anzahl muss stimmen. Reihenfolge egal, außer die Frage hat `reihenfolge: True` (Top-N).
- Top-1 (`top1: True`, E07 und E10): Nur die erste Ergebniszeile wird verglichen, die restliche Rangliste darf dabei
  sein. Geändert nach dem Pilot am 30.09.2026 (docs/decisions.md), ab dem vollen Lauf eingefroren.
"""

import re
from decimal import Decimal, InvalidOperation
from itertools import permutations

ARTEN = ("ergebnis", "rueckfrage", "keine_daten")


def zahl(v) -> Decimal | None:
    """Zahl aus int/float/Decimal oder Text wie "1.224,34 USD", "1,224.34", "35,5 %"; sonst None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, Decimal)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    t = re.sub(r"\s|usd|eur|\$|€|%", "", str(v).strip().lower())
    if not re.fullmatch(r"[-+]?[\d.,]+", t or "x"):
        return None
    if "," in t and "." in t:  # das letzte Trennzeichen ist das Dezimalzeichen
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".") if len(t.rsplit(",", 1)[1]) != 3 else t.replace(",", "")  # 3 Stellen: Tausender
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def toleranz(erwartet) -> Decimal:
    """Eine Einheit der letzten Nachkommastelle des erwarteten Werts; ohne Nachkommastellen exakt."""
    text = str(erwartet)
    stellen = len(text.split(".")[1]) if "." in text and not isinstance(erwartet, int) else 0
    return Decimal(1).scaleb(-stellen) if stellen else Decimal(0)


def wert_gleich(erwartet, ist, prozent: bool = False) -> bool:
    e, i = zahl(erwartet), zahl(ist)
    if e is not None:
        if i is None:
            return False
        tol = toleranz(erwartet) + Decimal("1e-9")
        return abs(i - e) <= tol or (prozent and abs(i * 100 - e) <= tol)
    return str(erwartet).strip().casefold() == str(ist).strip().casefold()


def zeile_passt(erwartet: list, ist: list, prozent_spalten: set[int]) -> bool:
    """Jeder erwartete Wert findet einen eigenen Wert in der Ergebniszeile (Spaltenreihenfolge egal, Extras erlaubt)."""
    if len(ist) < len(erwartet):
        return False
    for auswahl in permutations(range(len(ist)), len(erwartet)):
        if all(wert_gleich(e, ist[j], k in prozent_spalten) for k, (e, j) in enumerate(zip(erwartet, auswahl))):
            return True
    return False


def zeilen_gleich(erwartet: dict, ist: list[list], reihenfolge: bool = False, top1: bool = False) -> bool:
    """erwartet: {"spalten": [...], "zeilen": [[...]]} aus goldset.json; ist: Ergebniszeilen des Copiloten.
    top1: nur die erste Ergebniszeile zählt (gefragt ist der Spitzenwert, nicht die Rangliste)."""
    soll = erwartet["zeilen"]
    if top1:
        ist = ist[:1]
    if len(soll) != len(ist):
        return False
    prozent = {k for k, s in enumerate(erwartet["spalten"]) if "prozent" in s.lower()}
    if reihenfolge:
        return all(zeile_passt(e, i, prozent) for e, i in zip(soll, ist))
    frei = list(range(len(ist)))

    def zuordnen(k: int) -> bool:  # Backtracking: jede erwartete Zeile bekommt eine eigene Ergebniszeile
        if k == len(soll):
            return True
        for j in list(frei):
            if zeile_passt(soll[k], ist[j], prozent):
                frei.remove(j)
                if zuordnen(k + 1):
                    return True
                frei.append(j)
        return False

    return zuordnen(0)


def bewerten(frage: dict, antwort: dict, variante: str = "schema") -> dict:
    """frage: Eintrag aus evals/goldset.json. variante: "schema" (Branch b) oder "glossar" (Branch c).
    Gibt {"richtig": bool, "grund": str} zurück."""
    art = antwort.get("art")
    if art not in ARTEN:
        raise ValueError(f"Unbekannte Antwortart: {art!r}")
    typ, ergebnis = frage["typ"], frage.get("ergebnis")
    if variante in ("glossar", "glossar_spalten") and frage.get("mit_glossar"):
        typ, ergebnis = frage["mit_glossar"]["typ"], frage["mit_glossar"]["ergebnis"]
    if typ == "mehrdeutig":
        return {"richtig": art == "rueckfrage", "grund": "Rückfrage erwartet" if art != "rueckfrage" else "Rückfrage"}
    if typ == "unbeantwortbar":
        ok = art in ("keine_daten", "rueckfrage")
        return {"richtig": ok, "grund": "keine Daten erkannt" if ok else "Ersatz-Abfrage statt „keine Daten“"}
    if art != "ergebnis":
        return {"richtig": False, "grund": f"{art} statt Ergebnis"}
    ok = zeilen_gleich(ergebnis, antwort.get("zeilen") or [], frage.get("reihenfolge", False), frage.get("top1", False))
    return {"richtig": ok, "grund": "Ergebnis stimmt" if ok else "Ergebnis weicht ab"}
