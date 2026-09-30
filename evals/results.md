# Evaluationsergebnisse

Goldset: 27 Fragen (`evals/goldset.md`), Vergleichsregeln in `scripts/vergleich.py`, nach dem Pilot kalibriert und seit
dem vollen Lauf eingefroren (docs/decisions.md, 30.09.2026). Pilot: `evals/pilot.md`.

## Branch (b): nur Schema, voller Lauf am 30.09.2026

Je Modell 27 Fragen × 3 Wiederholungen. Protokolle:
[`laeufe/20260930-134104_haiku_schema.jsonl`](laeufe/20260930-134104_haiku_schema.jsonl),
[`laeufe/20260930-134106_sonnet_schema.jsonl`](laeufe/20260930-134106_sonnet_schema.jsonl).
Tabelle und Matrizen erzeugt von `scripts/auswerten.py`. pass^3 heißt: Die Frage ist in allen drei Wiederholungen richtig.

| | Haiku 4.5 | Sonnet 5.5 (effort medium) |
|---|---|---|
| richtig (81 Läufe) | 47/81 (58 %) | **74/81 (91 %)** |
| pass^3 (27 Fragen) | 14/27 | **24/27** |
| eindeutig | 32/42 | 39/42 |
| mehrdeutig: Rückfrage | 9/18 | 17/18 |
| Fallen | 3/15 | 12/15 |
| unbeantwortbar | 3/6 | 6/6 |
| Kosten gesamt | 0,53 USD | 0,77 USD |
| Kosten je 1.000 Fragen | 6,54 USD | 9,51 USD |
| p50 / p95 | 4,7 s / 9,9 s | 5,3 s / 11,5 s |

Kosten zusammen 1,30 USD (Budgets 1,00 und 3,50 USD, Schätzung 1,80–3,00 USD). Sonnet ist je Frage nur rund 45 % teurer
als Haiku, trotz doppeltem Tokenpreis: Das Prompt-Caching greift (290.000 gelesene Cache-Tokens), und Sonnet braucht
weniger Aufrufe (1,9 statt 2,1 je Frage). Bei Haiku greift der Cache nicht (Prompt unter 4.096 Tokens).

### Wo Sonnet besser ist

- **Fallen (12/15 statt 3/15):** Sonnet erkennt Kündigung ≠ Abo-Ende (E04, F03), Doppelabbuchungen (F01), Zeitzone (F04)
  und die irreführende Spalte (F05) in jeder Wiederholung. Es prüft die Daten mit Probe-Abfragen und nennt die naive
  Zahl oft zur Einordnung mit („Nach UTC gerechnet wären es 3.695 Logins“). Haiku erkennt keine dieser Fallen stabil.
- **Rückfragen (17/18 statt 9/18):** Haiku fragt bei M01, M03 und M05 immer nach, bei M02, M04 und M06 nie. Das
  Verhalten ist stabil, aber es hängt von der Frage ab. Sonnet fragt fast immer nach, Ausnahme ist einmal M02
  („600 Kunden“, mit dem Hinweis, dass es auch anders gemeint sein kann).
- **Unbeantwortbar (6/6 statt 3/6):** Haiku ersetzt bei U01 den fehlenden Marketingkanal jedes Mal durch den Abo-Kanal.
  Sonnet erklärt, dass `subscriptions.channel` der Abrechnungskanal ist und nicht der Akquisekanal.
- **E12 (Median in Tagen):** Sonnet rechnet mit exakter Zeitdifferenz, Haiku immer mit Kalendertagen (8,0 statt 7,4).

### Wo Sonnet nicht besser ist

- **Umsatz (E05 0/3, F02 0/3, bei Haiku ebenfalls 0/3):** Beide Modelle scheitern an der Umsatzdefinition, Sonnet aber
  anders. Es findet alle Bausteine (Store-Tabelle, Doppelabbuchungen, Erstattungen, Brutto gegenüber Auszahlung). In 3 von
  6 Läufen fragt es dann zurück, ob der Umsatz brutto oder netto gemeint ist und ob Erstattungen abgezogen werden sollen.
  In den anderen 3 Läufen legt es sich fest, aber anders als die Referenz: Kundenpreis statt Auszahlung, oder alle
  Erstattungen abgezogen, auch die für schon bereinigte Doppelabbuchungen (F02: 3.081,67 statt 3.109,63, genau 27,96 USD
  Differenz). Ohne Glossar ist „Umsatz“ tatsächlich nicht eindeutig. Das ist der Fall, für den Branch (c) gedacht ist.
- **Kosten und Latenz:** 45 % teurer, p95 1,6 s langsamer. Der längste Sonnet-Lauf dauerte 22 s.

### Streuung

Haiku streut an mehreren Stellen. Im Pilot fragte es bei M05 nicht nach, im vollen Lauf dreimal. F05 ist einmal von drei
richtig. F03 ist einmal falsch (56 Kündigungen statt 55 Kunden). E06 ist einmal falsch, weil Haiku den Grund
`'Duplicate Charges'` geraten hat, ohne die Werte nachzusehen, und der Filter deshalb nichts ausschloss. F04 in
Wiederholung 3 war eine Rückfrage (UTC oder Ortszeit?). Das ist eine berechtigte Frage, zählt nach den Regeln bei einer
Fallen-Frage aber als falsch. Bei Sonnet ist nur M02 nicht in allen drei Läufen gleich bewertet (2/3). E05 und F02 sind immer falsch, aber mal als Rückfrage, mal mit einer Zahl.

### `NOW()`

Haiku hat im vollen Lauf kein `NOW()` geschrieben. Sonnet hat es dreimal in Probe-Abfragen verwendet (E04, E14, F05), nie
in der Antwort-SQL. Die Bewertung ist davon nicht betroffen.

### Ein Laufzeitfehler

Haiku E05, Wiederholung 1: Die Antwort-SQL scheiterte an einer mehrdeutigen Spalte (`amount_usd` in einem Join). Das
zählt als falsch.

## Rohausgabe `scripts/auswerten.py`

| Modell | Variante | richtig | pass^k | E | M | F | U | Kosten/1000 Req. | p50 | p95 | SQL/Frage | Fehler |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | schema | 47/81 (58 %) | 14/27 (k=3) | 32/42 | 9/18 | 3/15 | 3/6 | 6.54 USD | 4.7 s | 9.9 s | 1.1 | 1 |
| claude-sonnet-5-5 | schema | 74/81 (91 %) | 24/27 (k=3) | 39/42 | 17/18 | 12/15 | 6/6 | 9.51 USD | 5.3 s | 11.5 s | 0.9 | 0 |

### claude-haiku-4-5 · schema

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✓ | ✓ | ✓ |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| E05 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| E06 | ✓ | ✓ | ✗ ergebnis |
| E07 | ✓ | ✓ | ✓ |
| E08 | ✓ | ✓ | ✓ |
| E10 | ✓ | ✓ | ✓ |
| E11 | ✓ | ✓ | ✓ |
| E12 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| E13 | ✓ | ✓ | ✓ |
| E14 | ✓ | ✓ | ✓ |
| E15 | ✓ | ✓ | ✓ |
| F01 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| F02 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| F03 | ✓ | ✗ ergebnis | ✓ |
| F04 | ✗ ergebnis | ✗ ergebnis | ✗ rueckfrage |
| F05 | ✗ ergebnis | ✗ ergebnis | ✓ |
| M01 | ✓ | ✓ | ✓ |
| M02 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U01 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U02 | ✓ | ✓ | ✓ |

### claude-sonnet-5-5 · schema

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✓ | ✓ | ✓ |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✓ | ✓ | ✓ |
| E05 | ✗ rueckfrage | ✗ ergebnis | ✗ rueckfrage |
| E06 | ✓ | ✓ | ✓ |
| E07 | ✓ | ✓ | ✓ |
| E08 | ✓ | ✓ | ✓ |
| E10 | ✓ | ✓ | ✓ |
| E11 | ✓ | ✓ | ✓ |
| E12 | ✓ | ✓ | ✓ |
| E13 | ✓ | ✓ | ✓ |
| E14 | ✓ | ✓ | ✓ |
| E15 | ✓ | ✓ | ✓ |
| F01 | ✓ | ✓ | ✓ |
| F02 | ✗ ergebnis | ✗ ergebnis | ✗ rueckfrage |
| F03 | ✓ | ✓ | ✓ |
| F04 | ✓ | ✓ | ✓ |
| F05 | ✓ | ✓ | ✓ |
| M01 | ✓ | ✓ | ✓ |
| M02 | ✓ | ✗ ergebnis | ✓ |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✓ | ✓ | ✓ |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✓ | ✓ | ✓ |
| U01 | ✓ | ✓ | ✓ |
| U02 | ✓ | ✓ | ✓ |
