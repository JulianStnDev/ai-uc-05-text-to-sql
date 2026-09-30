# Entscheidungen

<!-- Format:
## YYYY-MM-DD: Kurztitel
Kontext, Optionen, Entscheidung, Begründung
-->

## 2026-09-18: Status-Vokabular für meta.json

Kontext: meta.json legt "status": "planned" fest, ohne definierte erlaubte Werte —
das driftet über mehrere Repos auseinander (planned/in-progress/wip/...).

Optionen: (a) einfach: planned → active → done, (b) zusätzlich mit
parked/abandoned für verworfene Use Cases, (c) feiner: research →
building → evaluating → shipped.

Entscheidung: (a) — planned, active, done. Zusätzlich in CLAUDE.md verankert.

Begründung: Bei einem Solo-Portfolio mit meist einem aktiven Repo lohnt sich
keine feinere Staffelung. CLAUDE.md-Verankerung, damit der Agent das Vokabular
bei jedem neuen Repo automatisch mitliest statt dass ich mich erinnern muss.

## 2026-09-30: Datenbasis in Neon mit zwei Rollen

Kontext: Der Copilot soll SQL schreiben und ausführen. Was er ausführt, darf nie etwas verändern, auch nicht bei einem
Prompt-Fehler oder einer bösartigen Frage.

Optionen: (a) SQLite-Datei im Repo, (b) eigene Datenbank im bestehenden Neon-Projekt (Frankfurt, Free-Tier),
(c) eigenes Neon-Projekt.

Entscheidung: (b). Datenbank `analytics` mit zwei Rollen: `analytics_admin` besitzt und befüllt sie, `analyst_ro` darf
nur verbinden und SELECT auf die sieben Analyse-Tabellen. Zusätzlich ist `analyst_ro` standardmäßig read-only und hat
15 s Statement-Timeout. PUBLIC hat weder CONNECT noch TEMP noch Rechte im Schema.

Begründung: Postgres statt SQLite, weil echte Rechte auf Datenbankebene die Sicherung sind, nicht der Prompt. Neon ist
schon da (UC7), kostet nichts und liegt in Frankfurt. Ein eigenes Projekt hätte nur eine zweite Verwaltung bedeutet.
Getrennte Datenbank statt Schema in `neondb`, damit UC7-Daten und Analyse-Daten sich nicht berühren.

Belegt durch `tests/test_rechte.py`: INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE, ALTER scheitern an den Rechten,
auch wenn die Sitzung auf READ WRITE umgestellt wird. Auf die UC7-Tabellen in `neondb` hat `analyst_ro` keinen Zugriff.

## 2026-09-30: Fallen in den Daten, naive Abfrage mit genau einem Fehler

Kontext: Text-to-SQL scheitert selten an der Syntax, sondern an Geschäftsregeln, die im Schema nicht stehen.

Entscheidung: sechs Fallen im Datengenerator (Doppelabbuchungen, Store-Käufe nur in `store_transactions`, Kündigung ≠
Abo-Ende, Erstattungen, UTC vs. Ortszeit, `is_premium` heißt „hatte je Pro“). Für jede Falle gibt es eine naive Abfrage,
die sich von der Referenz nur in genau diesem einen Fehler unterscheidet. Das Skript bricht ab, wenn eine naive Abfrage
dieselbe Zahl liefert. Details nur in `docs/DATA_NOTES.md`, nie im Prompt.

Daten deterministisch (Seed 20260930), 600 Kunden, 12 Monate. Zwei Nachbesserungen vor dem Goldset: Kulanz-Erstattungen
treffen nie eine Doppelabbuchung (sonst wäre die Umsatzdefinition unscharf), und Gratis-Nutzer werden nach einigen Wochen
inaktiv (vorher waren 586 von 600 Kunden im September aktiv, jetzt 374).

## 2026-09-30: Goldset 15/5/5, Stichtag fest

25 Fragen auf Deutsch: 15 eindeutig, 5 mehrdeutig, 5 Fallen. Mehrdeutige Fragen haben als richtige Antwort eine
Rückfrage, dazu jede Deutung mit SQL und Ergebnis. Das Glossar legt bewusst nicht fest, was „verloren“, „regelmäßig“,
„am besten“ oder „letztes Quartal“ heißt, damit diese Fragen auch in Branch (c) mehrdeutig bleiben. Referenz-SQL nutzt nie
`now()`, sondern feste Daten (Stichtag 30.09.2026), und läuft als `analyst_ro` mit `SET TIME ZONE 'UTC'`.
Fünf Fallen-Fragen für sechs Fallen: Die Erstattungs-Falle steckt in E05, E06 und M02 und ist in DATA_NOTES belegt.

## 2026-09-30: Goldset nach Durchsicht, Vergleichsregeln vor der ersten Messung

Durchsicht durch Julian:
- E09 („aktive Kunden am 30.09.“) wird M06. Ohne Glossar ist „aktiv“ mehrdeutig. Mit Glossar (Branch c) ist die Frage
  eindeutig, erwartet 374 (`mit_glossar`).
- M02 ersetzt durch „Wie viele Kunden haben wir?“ (Deutungen: alle Konten 600, Pro-Kunden 201, aktive Kunden 374).
  Damit die Frage auch in Branch (c) mehrdeutig bleibt, nennt das Glossar „Kunde“ allein ausdrücklich mehrdeutig
  statt es als „jedes Konto“ zu definieren.
- Neu: zwei unbeantwortbare Fragen, U01 Marketingkanal der Neukunden, U02 NPS. Richtige Antwort: keine Daten dazu.
  Eine Ersatz-Abfrage mit ähnlicher Spalte (`subscriptions.channel`, Kündigungsgründe) ist falsch.
- Erstattungs-Falle ohne eigene Frage und F01 bleiben wie sie sind.
- Damit 27 Fragen: 14 eindeutig, 6 mehrdeutig, 5 Fallen, 2 unbeantwortbar. IDs bleiben stabil (E09 fehlt).

Vergleichsregeln, als Code in `scripts/vergleich.py` und festgelegt, bevor irgendetwas gemessen wird:
- Verglichen wird das Ergebnis der ausgeführten SQL, nicht der Fließtext.
- Rundung: Ganzzahlen exakt, Dezimalzahlen ± eine Einheit der letzten Stelle des erwarteten Werts.
- Prozent: Bei Spalten „…prozent…“ zählt auch der Anteil (0,355 statt 35,5).
- Zahlenformat: deutsches und englisches Format, Währungs- und Prozentzeichen werden normalisiert.
- Spaltennamen und -reihenfolge egal, zusätzliche Spalten erlaubt, Zeilenzahl muss stimmen.
- Zeilenreihenfolge nur bei `reihenfolge: True` (E02, Top 5).
- Rückfragen: bei M und U richtig, bei E und F falsch. „Keine Daten“ nur bei U richtig. Bei M ist eine Zahl falsch,
  auch wenn sie zu einer Deutung passt.

Selbsttest (`tests/test_vergleich.py`): Jede Referenz gilt als richtig. Jede naive Antwort der Fallen gilt als falsch,
die Toleranz verschluckt also keine Falle. Jede Deutung einer M-Frage gilt ohne Rückfrage als falsch.

