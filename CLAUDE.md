# Projekt-Kontext

## Problem
Ein Analytics-Copilot beantwortet Business-Fragen auf Deutsch zu den Daten der fiktiven Habit-Tracker-App
**FocusFlow**, indem er SQL gegen eine Postgres-Datenbank schreibt und ausführt. Gemessen wird, wie oft die Zahl
stimmt und ob er bei mehrdeutigen Fragen zurückfragt statt zu raten. Verglichen werden:

- **Branch (b):** das Modell bekommt nur das Schema (`db/schema.sql`)
- **Branch (c):** Schema + Glossar mit Geschäftsdefinitionen (`docs/GLOSSAR.md`)

Die Daten enthalten absichtlich Fallen (Doppelabbuchungen, Store vs. Web, Kündigung ≠ Abo-Ende, Erstattungen,
Zeitzonen, irreführende Spalte). Details in `docs/DATA_NOTES.md`. Die Datei ist Dokumentation für Menschen und darf
**nie** Teil eines Prompts sein. `db/schema.sql` bleibt ohne erklärende Kommentare, weil es in Branch (b) das Einzige ist,
was das Modell sieht.

## Datenbank
- Neon-Projekt (Frankfurt), Datenbank `analytics`. Rollen: `analytics_admin` (befüllt, `scripts/laden.py`) und
  `analyst_ro` (nur SELECT auf die sieben Analyse-Tabellen, standardmäßig read-only, 15 s Timeout).
- Connection Strings nur in `.env` (`ANALYTICS_ADMIN_URL`, `ANALYTICS_RO_URL`), nie im Chat, in Logs oder im Repo.
  Ausgaben mit Verbindungsdaten vor dem Anzeigen maskieren.
- Das Modell führt SQL ausschließlich als `analyst_ro` aus. Jede Sitzung setzt `SET TIME ZONE 'UTC'`.
- Daten sind deterministisch (Seed in `scripts/daten_erzeugen.py`). Wer den Generator ändert, lädt neu und berechnet
  das Goldset neu (`scripts/goldset_berechnen.py`).

## Goldset
- Quelle: `evals/goldset_fragen.py` (Fragen + Referenz-SQL). Ergebnisse berechnet `scripts/goldset_berechnen.py` nach
  `evals/goldset.json` und `evals/goldset.md`. Diese beiden nicht von Hand bearbeiten.
- 27 Fragen: 14 eindeutig, 6 mehrdeutig (richtige Antwort: Rückfrage, dazu die Deutungen), 5 Fallen,
  2 unbeantwortbar (richtige Antwort: keine Daten dazu). IDs bleiben stabil.
- Vergleichsregeln stehen als Code in `scripts/vergleich.py` (festgelegt vor der ersten Messung). Nicht nachträglich
  an Ergebnisse anpassen; jede Änderung als datierte Entscheidung in docs/decisions.md.
- Referenz-SQL ohne `now()`/`current_date`: feste Daten, Stichtag 30.09.2026.

## Kosten
- Vor jedem kostenpflichtigen Schritt (Modell-Läufe, Judge) Kosten schätzen und auf Julians Okay warten.
- Branch (a) (Daten, Goldset) macht keine API-Aufrufe. Neon läuft im Free-Tier.

## Erwartete Artefakte
- README.md nach Schema (Problem, PM-Entscheidung, Architektur, Eval, Kosten/Latenz, Learnings)
- README.md auf Englisch, README_DE.md auf Deutsch, inhaltlich identisch (gleiche Zahlen, Tabellen, Fachbegriffe). Oben jeweils Sprachlink (🇩🇪 Deutsche Version / 🇬🇧 English version). Änderungen immer in beiden Dateien nachziehen.
- meta.json gepflegt (status ausschließlich: planned | active | done)
- meta.json auf Englisch (speist die Portfolio-Seite): title, summary = ein Satz „what it shows“, metrics = 1–2 Kennzahlen wörtlich aus dem README; optional demo {url, note} und screenshot (Pfad im Repo)
- evals/ mit Datensatz + Ergebnissen
- docs/decisions.md mit datierten Entscheidungen

## Erlaubte Libraries
- anthropic, psycopg, python-dotenv, pytest
- Direkt gegen das SDK, kein LangChain/LlamaIndex, kein fertiges Text-to-SQL-Framework

## Stil
- Python, einfache Skripte statt Frameworks
- Drei Zahlen im README Pflicht: Kosten/1000 Requests, p95-Latenz, Qualitätsmetrik

## Arbeitsweise
- Nie direkt auf `main` committen. Pro Arbeitspaket ein Branch (`feat/...`, `fix/...`), am Ende Pull Request per `gh`.
- Merge macht Julian selbst nach Review.
