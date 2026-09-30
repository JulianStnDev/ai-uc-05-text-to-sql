🇬🇧 [English version](README.md)

# UC5 — Text-to-SQL: Ein Analytics-Copilot auf Daten mit Fallen

> Stand: in Arbeit. Branch (a) ist fertig: Datenbank, Daten und Goldset. Gemessen ist noch kein Modell.

## Problem
Produkt- und Support-Teams der fiktiven Habit-Tracker-App FocusFlow stellen Business-Fragen („Wie viel Umsatz hatten wir im Q2?“, „Wie viele Kunden haben im August gekündigt?“) und warten Tage auf einen Analysten. Ein Copilot, der SQL schreibt und ausführt, könnte in Sekunden antworten, aber nur, wenn die Zahl stimmt. Text-to-SQL scheitert selten an der Syntax. Es scheitert an Geschäftsregeln, die das Schema nicht zeigt: Doppelabbuchungen, Store-Käufe in einer eigenen Tabelle, Kündigung vs. Abo-Ende, Erstattungen, Zeitzonen, eine irreführend benannte Spalte. Und er soll bei mehrdeutigen Fragen zurückfragen statt zu raten.

## PM-Entscheidung
Plan in drei Branches, jeweils ein Pull Request:
- **(a) Daten und Goldset (fertig):** eigene Neon-Postgres-Datenbank mit realistischen, aber erfundenen Daten und sechs in die Daten eingebauten Fallen; 25 Business-Fragen auf Deutsch mit Referenz-SQL und aus der Datenbank berechneten Ergebnissen.
- **(b) Nur Schema:** Das Modell sieht die Tabellendefinitionen und sonst nichts.
- **(c) Schema + Glossar:** Das Modell bekommt zusätzlich die Geschäftsdefinitionen ([docs/GLOSSAR.md](docs/GLOSSAR.md)).

Die Frage ist, wie viel ein Glossar gegenüber dem Schema allein bringt. Vor jedem kostenpflichtigen Schritt gibt es eine Kostenschätzung.

Warum eine echte Datenbank mit Rollen statt einer Regel im Prompt: Der Copilot führt SQL als `analyst_ro` aus, der nur SELECT auf die sieben Analyse-Tabellen darf. Postgres weist INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE und ALTER ab, auch wenn die Sitzung auf Lesen und Schreiben umgestellt wird (per Test belegt). Entscheidungen: [docs/decisions.md](docs/decisions.md).

## Architekturskizze
```
evals/goldset_fragen.py ──▶ scripts/goldset_berechnen.py ──(analyst_ro, UTC)──▶ Neon Postgres "analytics" (Frankfurt)
                                        │                                           ▲
                                        ▼                                           │ analytics_admin
                        evals/goldset.json, evals/goldset.md        scripts/daten_erzeugen.py → scripts/laden.py (Seed 20260930)
```
- `db/schema.sql`: sieben Tabellen, ohne erklärende Kommentare (in Branch b das Einzige, was das Modell sieht).
- `docs/DATA_NOTES.md`: die Fallen, nur für Menschen, nie Teil eines Prompts.
- `docs/GLOSSAR.md`: Geschäftsdefinitionen (Entwurf), bekommt das Modell erst in Branch (c).

## Daten
600 Kunden, 265 Abos, 94 Kündigungen, 400 Web-Zahlungen, 366 Store-Käufe, 33 Erstattungen, 26.798 Logins zwischen 01.10.2025 und 30.09.2026, deterministisch (fester Seed). Jede Falle ändert das Ergebnis einer naiven Abfrage messbar:

| Falle | Frage | richtig | naiv |
|---|---|---|---|
| Doppelabbuchungen | Web-Umsatz Sep. vor Erstattungen | 613,46 USD | 686,44 USD |
| Store vs. Web | Umsatz Q2 2026 | 3.109,63 USD | 1.592,48 USD |
| Kündigung ≠ Abo-Ende | Kunden mit Kündigung im August | 55 | 18 |
| Erstattungen | Umsatz Mai 2026 | 1.224,34 USD | 1.344,34 USD |
| Zeitzone | Logins zwischen 6 und 9 Uhr | 6.696 | 3.695 |
| Irreführende Spalte | Laufende Pro-Abos am 30.09. | 201 | 254 |

## Evaluationsergebnisse
Goldset: 25 Fragen auf Deutsch, 15 eindeutig, 5 mehrdeutig (richtige Antwort: eine Rückfrage, dazu jede Deutung mit SQL und Ergebnis), 5 gezielt auf die Fallen. Tabelle: [evals/goldset.md](evals/goldset.md). Messungen folgen in Branch (b) und (c).

## Kosten & Latenz
- Kosten pro 1000 Requests: folgt (Branch b)
- p95-Latenz: folgt (Branch b)
- Qualitätsmetrik: folgt (Branch b)
- Branch (a) machte keine API-Aufrufe. Neon läuft im Free-Tier.

## Lokal ausführen
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
NEON_OWNER_URL=... .venv/bin/python scripts/setup_db.py   # einmalig: Datenbank, Rollen, schreibt .env
.venv/bin/python scripts/laden.py                          # Tabellen anlegen und füllen (deterministisch)
.venv/bin/python scripts/goldset_berechnen.py              # erwartete Ergebnisse als analyst_ro
.venv/bin/python -m pytest                                 # Daten, Rechte, Goldset (ohne API)
```

## Learnings
- **Jede Falle braucht eine Gegenabfrage.** Erst wenn die naive Abfrage mit genau einem Fehler eine andere Zahl liefert, ist die Falle echt. Das Skript bricht sonst ab.
- **Realismus an den Zahlen prüfen.** Die erste Fassung der Login-Daten hatte 586 von 600 Kunden im September aktiv, weil Gratis-Nutzer nie einschliefen. Die Kennzahl wäre wertlos gewesen.
- **Sitzungs-Zeitzone festlegen.** Datumsgrenzen wie `'2026-05-01'` hängen von der Zeitzone der Sitzung ab; alle Skripte setzen UTC.

## Was ich anders machen würde
Folgt zum Abschluss des Use Cases.
