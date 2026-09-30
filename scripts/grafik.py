"""Ergebnisgrafik „richtig je Fragetyp“ als SVG, ohne API und ohne Plot-Bibliothek.

    .venv/bin/python scripts/grafik.py

Liest alle vollständigen Messläufe aus evals/laeufe/ (alle 27 Fragen, mindestens 3 Wiederholungen; Pilot und
Teilläufe zählen nicht), je Modell und Variante den neuesten. Bewertet neu mit scripts/vergleich.py und schreibt
docs/img/ergebnis_{de,en}_{hell,dunkel}.svg. Farbe = Modell, Muster = Variante: voll = nur Schema, Schraffur = mit
Glossar (Branch c), Punkte = mit Glossar im Antwortformat „karte“ (Branch d), Kreuzschraffur mit Sternchen = Zusatzvariante mit Spaltenverzeichnis (nach der Messung ergänzt, auf
dieses Goldset hin optimiert; Fußnote in der Grafik). Weitere Läufe erscheinen automatisch als weitere Balken.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auswerten import laden, neu_bewerten  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]
TYPEN = ["eindeutig", "mehrdeutig", "falle", "unbeantwortbar"]
TEXTE = {
    "de": {"titel": "Anteil richtiger Antworten je Fragetyp",
           "typen": ["eindeutig", "mehrdeutig", "Fallen", "unbeantwortbar"],
           "varianten": {"schema": "nur Schema", "glossar": "Schema + Glossar", "glossar_spalten": "+ Spaltenverzeichnis*",
                         "glossar_karte": "+ Antwortkarte"},
           "fussnote": "* nach der Messung ergänzt, auf dieses Goldset hin optimiert", "fragen": "Fragen", "laeufe": "Läufe"},
    "en": {"titel": "Share of correct answers by question type",
           "typen": ["unambiguous", "ambiguous", "traps", "unanswerable"],
           "varianten": {"schema": "schema only", "glossar": "schema + glossary", "glossar_spalten": "+ column notes*",
                         "glossar_karte": "+ answer card"},
           "fussnote": "* added after the measurement, tuned to this goldset", "fragen": "questions", "laeufe": "runs"},
}
MODELLNAMEN = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-5-5": "Sonnet 5.5"}
# Farbe folgt dem Modell, nie dem Rang (validiert mit dem dataviz-Validator: CVD-ΔE ≥ 19, hell und dunkel).
FARBEN = {"hell": ["#2a78d6", "#1baf7a", "#eb6834", "#e87ba4"], "dunkel": ["#3987e5", "#199e70", "#d95926", "#d55181"]}
TINTE = {"hell": {"text": "#1f2328", "leise": "#59636e", "gitter": "#d8dee4"},
         "dunkel": {"text": "#e6edf3", "leise": "#9198a1", "gitter": "#30363d"}}  # GitHub-Hintergründe


def vollstaendige_laeufe(fragen: dict) -> list[dict]:
    """Je (Modell, Variante) der neueste Lauf mit allen Fragen und mindestens 3 Wiederholungen."""
    neueste = {}
    for pfad in sorted((WURZEL / "evals" / "laeufe").glob("*.jsonl")):
        laeufe = laden([pfad])
        if not laeufe or {l["frage_id"] for l in laeufe} != set(fragen) or max(l["wiederholung"] for l in laeufe) < 3:
            continue
        variante = laeufe[0]["variante"] + ("_karte" if laeufe[0].get("format") == "karte" else "")
        schluessel = (laeufe[0]["modell"], variante)
        neueste[schluessel] = laeufe  # Dateinamen beginnen mit Zeitstempel, sortiert = der letzte gewinnt
    serien = []
    rang = {"schema": 0, "glossar": 1, "glossar_karte": 2, "glossar_spalten": 3}
    for (modell, variante), laeufe in sorted(neueste.items(), key=lambda x: (x[0][0], rang.get(x[0][1], 9), x[0][1])):
        je_typ = defaultdict(lambda: [0, 0])
        for l in laeufe:
            je_typ[l["typ"]][0] += neu_bewerten(l, fragen)
            je_typ[l["typ"]][1] += 1
        serien.append({"modell": modell, "variante": variante, "je_typ": dict(je_typ),
                       "wdh": max(l["wiederholung"] for l in laeufe)})
    return serien


def svg(serien: list[dict], fragen: dict, sprache: str, modus: str) -> str:
    t, tinte = TEXTE[sprache], TINTE[modus]
    modelle = sorted({s["modell"] for s in serien})
    farbe = {m: FARBEN[modus][i % len(FARBEN[modus])] for i, m in enumerate(modelle)}
    zeilen_legende = len(modelle)
    fussnote = any(s["variante"] == "glossar_spalten" for s in serien)
    breite, links, rechts, oben, unten = 720, 44, 16, 50 + 20 * zeilen_legende + 16, 56 + 18 * fussnote
    hoehe_plot = 220
    hoehe = oben + hoehe_plot + unten
    balken, luecke = 24, 6
    gruppe = (breite - links - rechts) / len(TYPEN)
    y = lambda p: oben + hoehe_plot * (1 - p)  # noqa: E731

    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{breite}" height="{hoehe}" viewBox="0 0 {breite} {hoehe}" '
             f'font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif" role="img" '
             f'aria-label="{t["titel"]}">',
             f'<title>{t["titel"]}</title>', "<defs>"]
    for i, m in enumerate(modelle):
        teile.append(f'<pattern id="schraffur-{i}" width="6" height="6" patternUnits="userSpaceOnUse" '
                     f'patternTransform="rotate(45)"><rect width="6" height="6" fill="{farbe[m]}" fill-opacity="0.25"/>'
                     f'<line x1="0" y1="0" x2="0" y2="6" stroke="{farbe[m]}" stroke-width="3"/></pattern>')
        teile.append(f'<pattern id="punkte-{i}" width="6" height="6" patternUnits="userSpaceOnUse">'
                     f'<rect width="6" height="6" fill="{farbe[m]}" fill-opacity="0.25"/>'
                     f'<circle cx="3" cy="3" r="1.6" fill="{farbe[m]}"/></pattern>')
        teile.append(f'<pattern id="kreuz-{i}" width="7" height="7" patternUnits="userSpaceOnUse" '
                     f'patternTransform="rotate(45)"><rect width="7" height="7" fill="{farbe[m]}" fill-opacity="0.2"/>'
                     f'<line x1="0" y1="0" x2="0" y2="7" stroke="{farbe[m]}" stroke-width="2"/>'
                     f'<line x1="0" y1="0" x2="7" y2="0" stroke="{farbe[m]}" stroke-width="2"/></pattern>')

    def fuellung(s: dict) -> str:
        i = modelle.index(s["modell"])
        return {"schema": farbe[s["modell"]], "glossar": f"url(#schraffur-{i})",
                "glossar_karte": f"url(#punkte-{i})"}.get(s["variante"], f"url(#kreuz-{i})")
    teile.append("</defs>")
    teile.append(f'<text x="{links}" y="24" font-size="15" font-weight="600" fill="{tinte["text"]}">{t["titel"]}</text>')

    # Legende: eine Zeile je Modell, daneben die Varianten. Muster wie am Balken, Text in Textfarbe.
    max_je_zeile = max(sum(s["modell"] == m for s in serien) for m in modelle)
    for zeile, m in enumerate(modelle):
        zeile_y = 48 + zeile * 20
        teile.append(f'<text x="{links}" y="{zeile_y}" font-size="12" font-weight="600" fill="{tinte["text"]}">'
                     f'{MODELLNAMEN.get(m, m)}</text>')
        for k, s in enumerate(x for x in serien if x["modell"] == m):
            x = links + 90 + k * min(190, (breite - links - rechts - 90) // max_je_zeile)
            teile.append(f'<rect x="{x}" y="{zeile_y - 10}" width="12" height="12" rx="2" fill="{fuellung(s)}"/>')
            teile.append(f'<text x="{x + 18}" y="{zeile_y}" font-size="12" fill="{tinte["text"]}">'
                         f'{t["varianten"].get(s["variante"], s["variante"])}</text>')

    for p in (0, 0.25, 0.5, 0.75, 1):
        teile.append(f'<line x1="{links}" x2="{breite - rechts}" y1="{y(p):.1f}" y2="{y(p):.1f}" '
                     f'stroke="{tinte["gitter"]}" stroke-width="1"/>')
        teile.append(f'<text x="{links - 8}" y="{y(p) + 4:.1f}" font-size="11" text-anchor="end" '
                     f'fill="{tinte["leise"]}">{int(p * 100)} %</text>')

    breite_gruppe = len(serien) * balken + (len(serien) - 1) * luecke
    for g, typ in enumerate(TYPEN):
        mitte = links + gruppe * (g + 0.5)
        start = mitte - breite_gruppe / 2
        for i, s in enumerate(serien):
            richtig, n = s["je_typ"].get(typ, (0, 0))
            anteil = richtig / n if n else 0
            bx, top = start + i * (balken + luecke), y(anteil)
            h = oben + hoehe_plot - top
            r = min(4, h)  # 4 px rund am Datenende, eckig an der Grundlinie
            pfad = (f"M{bx:.1f},{oben + hoehe_plot} V{top + r:.1f} Q{bx:.1f},{top:.1f} {bx + r:.1f},{top:.1f} "
                    f"H{bx + balken - r:.1f} Q{bx + balken:.1f},{top:.1f} {bx + balken:.1f},{top + r:.1f} "
                    f"V{oben + hoehe_plot} Z") if h > 0 else ""
            name = f'{MODELLNAMEN.get(s["modell"], s["modell"])} · {t["varianten"].get(s["variante"], s["variante"])}'
            if pfad:
                teile.append(f'<path d="{pfad}" fill="{fuellung(s)}"><title>{name}: {richtig}/{n} {t["laeufe"]}</title></path>')
            teile.append(f'<text x="{bx + balken / 2:.1f}" y="{top - 6:.1f}" font-size="10.5" text-anchor="middle" '
                         f'fill="{tinte["text"]}">{anteil * 100:.0f}\u202f%</text>')
        anzahl = sum(f["typ"] == typ for f in fragen.values())
        teile.append(f'<text x="{mitte:.1f}" y="{oben + hoehe_plot + 20}" font-size="12" text-anchor="middle" '
                     f'fill="{tinte["text"]}">{t["typen"][g]}</text>')
        teile.append(f'<text x="{mitte:.1f}" y="{oben + hoehe_plot + 36}" font-size="11" text-anchor="middle" '
                     f'fill="{tinte["leise"]}">{anzahl} {t["fragen"]} × {serien[0]["wdh"]}</text>')
    if fussnote:
        teile.append(f'<text x="{links}" y="{hoehe - 8}" font-size="11" fill="{tinte["leise"]}">{t["fussnote"]}</text>')
    teile.append("</svg>")
    return "\n".join(teile) + "\n"


def main() -> None:
    fragen = {f["id"]: f for f in json.loads((WURZEL / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]}
    serien = vollstaendige_laeufe(fragen)
    if not serien:
        sys.exit("Keine vollständigen Läufe in evals/laeufe/.")
    ziel = WURZEL / "docs" / "img"
    ziel.mkdir(parents=True, exist_ok=True)
    for sprache in TEXTE:
        for modus in FARBEN:
            pfad = ziel / f"ergebnis_{sprache}_{modus}.svg"
            pfad.write_text(svg(serien, fragen, sprache, modus), encoding="utf-8")
            print(pfad.relative_to(WURZEL))
    for s in serien:
        print(s["modell"], s["variante"], {k: f"{a}/{b}" for k, (a, b) in s["je_typ"].items()})


if __name__ == "__main__":
    main()
