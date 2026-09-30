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
| Kosten je 1.000 richtige Antworten | 11,27 USD | 10,41 USD |
| p50 / p95 | 4,7 s / 9,9 s | 5,3 s / 11,5 s |

Kosten zusammen 1,30 USD (Budgets 1,00 und 3,50 USD, Schätzung 1,80–3,00 USD). Sonnet ist je Frage nur rund 45 % teurer
als Haiku, trotz doppeltem Tokenpreis: Das Prompt-Caching greift (290.000 gelesene Cache-Tokens), und Sonnet braucht
weniger Aufrufe (1,9 statt 2,1 je Frage). Bei Haiku greift der Cache nicht (Prompt unter 4.096 Tokens).

Je richtige Antwort ist Sonnet günstiger: 0,770701 USD / 74 = 10,41 USD je 1.000 richtige Antworten, Haiku
0,529623 USD / 47 = 11,27 USD.

### Bekannte Grenze des Goldsets

Ohne Glossar sind E05 und F02 faktisch mehrdeutig: „Umsatz“ kann brutto oder nach Store-Gebühr gemeint sein, mit oder
ohne Erstattungen. Sonnets Rückfragen dort (3 von 6 Läufen) sind vertretbar. Die Regeln bleiben eingefroren und die
Bewertung bleibt wie gemessen: E05 und F02 zählen als falsch. In Branch (c) definiert das Glossar „Umsatz“.

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

## Branch (c): Schema + Glossar, voller Lauf am 30.09.2026

Glossar: der Entwurf aus Branch (a), unverändert eingefroren (SHA-256 in docs/decisions.md, Test
`test_glossar_eingefroren`). Je Modell 27 Fragen × 3. Protokolle:
[`laeufe/20260930-164926_haiku_glossar.jsonl`](laeufe/20260930-164926_haiku_glossar.jsonl),
[`laeufe/20260930-164928_sonnet_glossar.jsonl`](laeufe/20260930-164928_sonnet_glossar.jsonl).
Mit Glossar ist M06 eindeutig (erwartet 374, vorab im Goldset festgelegt). In der Spalte „mehrdeutig“ zählt M06 dort also
als richtig, wenn die Zahl stimmt.

| | Haiku (b) | **Haiku (c)** | Sonnet (b) | **Sonnet (c)** |
|---|---|---|---|---|
| richtig (81 Läufe) | 47/81 (58 %) | **70/81 (86 %)** | 74/81 (91 %) | **78/81 (96 %)** |
| pass^3 | 14/27 | **22/27** | 24/27 | **26/27** |
| eindeutig | 32/42 | 39/42 | 39/42 | 39/42 |
| mehrdeutig | 9/18 | 14/18 | 17/18 | 18/18 |
| Fallen | 3/15 | **14/15** | 12/15 | **15/15** |
| unbeantwortbar | 3/6 | 3/6 | 6/6 | 6/6 |
| Kosten je 1.000 Fragen | 6,54 USD | 8,51 USD | 9,51 USD | 10,14 USD |
| Kosten je 1.000 richtige Antworten | 11,27 USD | **9,85 USD** | 10,41 USD | 10,53 USD |
| p95 | 9,9 s | 9,4 s | 11,5 s | 8,1 s |

Kosten Branch (c): Haiku 0,69 USD, Sonnet 0,82 USD (Budgets 1,50 und 3,00 USD).

**Das Glossar hebt Haiku fast auf Sonnet-Niveau ohne Glossar** (86 % gegenüber 91 %). Je richtige Antwort ist Haiku mit
Glossar jetzt die günstigste Kombination: 9,85 USD je 1.000 richtige Antworten. Der längere Prompt kostet je Frage mehr,
dafür stimmen viel mehr Antworten.

### Wo das Glossar hilft

- **Fallen, Haiku 3/15 → 14/15.** Doppelabbuchungen (F01), Umsatz mit Store und Erstattungen (F02), Zeitzone (F04) und
  `is_premium` (F05) stehen im Glossar, und Haiku setzt sie um. Sonnet schafft jetzt alle 15.
- **Umsatz (E05, F02), beide Modelle 0/6 → 6/6.** Ohne Glossar war „Umsatz“ mehrdeutig (brutto oder netto, mit oder
  ohne Erstattungen). Das Glossar legt es fest, und beide Modelle rechnen es richtig.
- **Kündigung ≠ Abo-Ende (E04), Haiku 0/3 → 3/3.**
- **Rückfragen, Haiku M02 und M04 0/3 → 3/3.** Das Glossar sagt ausdrücklich, dass „Kunde“ allein mehrdeutig ist. Das
  bringt Haiku dazu nachzufragen. Bei M04 (Kündigungsquote) fragt Haiku jetzt nach Zeitraum und Bezug, obwohl das
  Glossar die Quote gar nicht definiert. Die Definitionen machen es insgesamt vorsichtiger.

### Wo das Glossar nicht hilft

- **U01 (Marketingkanal), Haiku 0/3.** Das Glossar sagt nichts über `channel`. Haiku deutet den Abrechnungsweg weiter
  als Marketingkanal.
- **E12 (Median in Tagen), Haiku 0/3.** `EXTRACT(DAY FROM interval)` schneidet auf ganze Tage ab: 7,0 statt 7,4. Das ist
  ein SQL-Fehler, keine Definitionsfrage.
- **M06 (aktive Kunden), Haiku 0/3.** Die Definition „Login in den 30 Tagen bis einschließlich Stichtag“ kennt Haiku, zählt
  aber ab dem 31.08., also 31 Tage: 377 statt 374. Sonnet rechnet 3/3 richtig.

### Rückschritt: Sonnet E02, 3/3 → 0/3 (bekannte Grenze des Goldsets)

*„In welchen fünf Ländern haben wir die meisten Kunden, und wie viele sind es jeweils?“* Das Glossar sagt: „**Kunde**
allein ist im Haus mehrdeutig … Immer präzisieren.“ Sonnet hält sich daran und fragt dreimal nach, ob Konten, Pro-Kunden
oder aktive Kunden gemeint sind. Das Goldset wertet E02 aber als eindeutig (Konten). Hier widersprechen sich Glossar und
Goldset, beide von uns geschrieben. Sonnets Rückfrage ist nach dem Glossar richtig. Die Regeln bleiben eingefroren und die
Bewertung bleibt wie gemessen: E02 zählt als falsch. Ohne diesen Widerspruch stünde Sonnet (c) bei 81/81.

### Fehler-Rundgang Branch (c)

| Frage | Modell | falsch | Ursache |
|---|---|---|---|
| E02 | Sonnet | 3/3 | Rückfrage nach „Kunde“, wie das Glossar verlangt (Konflikt Glossar ↔ Goldset, siehe oben) |
| E12 | Haiku | 3/3 | `EXTRACT(DAY …)` statt exakter Zeitdifferenz: 7,0 statt 7,4 |
| M06 | Haiku | 3/3 | 30-Tage-Fenster um einen Tag zu lang (ab 31.08.): 377 statt 374 |
| U01 | Haiku | 3/3 | Abrechnungsweg als Marketingkanal, das Glossar sagt dazu nichts |
| M01 | Haiku | 1/3 | Deutung statt Rückfrage: „Sommer“ als Juni bis August angenommen (67) |
| F03 | Haiku | 1/3 | Kündigungen gezählt statt Kunden: 56 statt 55 |

## Zusatzvariante: Glossar + Spaltenverzeichnis (nur Haiku)

**Nach der Messung ergänzt, auf dieses Goldset hin optimiert.** `docs/SPALTEN.md` erklärt je missverständlicher Spalte
in einer Zeile, was sie bedeutet (etwa `subscriptions.channel` = Abrechnungsweg). Es ist entstanden, nachdem wir wussten,
woran Haiku in (b) scheitert. Protokoll:
[`laeufe/20260930-165159_haiku_glossar_spalten.jsonl`](laeufe/20260930-165159_haiku_glossar_spalten.jsonl), Kosten 0,80 USD.

| | Haiku (c) Glossar | Haiku Glossar + Spalten* |
|---|---|---|
| richtig | 70/81 (86 %) | 69/81 (85 %) |
| pass^3 | 22/27 | 20/27 |
| U01 | 0/3 | 1/3 |
| Kosten je 1.000 Fragen | 8,51 USD | 9,91 USD |

\* nach der Messung ergänzt, auf dieses Goldset hin optimiert

**Das Spaltenverzeichnis bringt nichts Messbares.** U01 gelingt einmal von drei Läufen. In einem anderen Lauf schreibt Haiku
sogar „Dies zeigt den Abrechnungskanal“ und gibt die Zahl trotzdem als Marketingkanal aus. Dafür streut es an anderen
Stellen: E05 einmal um ein Vielfaches zu hoch (55.692,70 USD) und einmal ohne Werkzeug beendet, F01 einmal ohne
Bereinigung der Doppelabbuchungen, M02 einmal mit Zahl statt Rückfrage. Unterm Strich 85 % gegenüber 86 %, also Rauschen.

**Warum diese Variante nur eingeschränkt aussagekräftig ist.** Das Spaltenverzeichnis wurde mit Wissen über die
Testfragen geschrieben. Selbst wenn es geholfen hätte, wüssten wir nicht, ob es bei neuen Fragen hilft oder nur bei
diesen 27. Das ist Overfitting aufs Testset: Man optimiert an genau den Daten, an denen man misst, und die Messung
überschätzt dann den Nutzen. Die saubere Alternative ist ein **Holdout**: neue Fragen, die beim Schreiben des Verzeichnisses
niemand kannte, mit Referenz-SQL vor der Messung festgelegt. Nur auf diesem Holdout wäre ein Gewinn belastbar. Hier gab es
nicht einmal einen Gewinn auf dem Testset selbst. Das stützt eher die Hauptmessung: Der große Sprung kommt aus den
Geschäftsdefinitionen, nicht aus Erklärungen zu einzelnen Spalten.

## Vorher/Nachher: dieselbe Frage ohne Glossar, mit Glossar, mit Spaltenverzeichnis (Haiku)

**E05 „Wie hoch war der Umsatz im Mai 2026?“** (erwartet 1.224,34 USD)
- Nur Schema: *„Der Gesamtumsatz im Mai 2026 betrug $1.344,34: Direktzahlungen $664,64, Store-Transaktionen $679,70.“*
  Die Erstattungen fehlen. ✗
- Glossar: *„1.224,34 USD (netto): 664,64 USD Web-Umsatz + 679,70 USD Store-Umsatz − 120,00 USD Erstattungen.“* ✓
- Spaltenverzeichnis: *„1.224,34 USD … Nettoumsatz nach Abzug von Erstattungen (ausgenommen Doppelabbuchungen).“* ✓
  (in 1 von 3 Läufen)

**F04 „Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt?“** (erwartet 6.696)
- Nur Schema: `EXTRACT(HOUR FROM logged_in_at AT TIME ZONE 'UTC')` → *„3.695 Logins“* ✗
- Glossar: `EXTRACT(HOUR FROM l.logged_in_at AT TIME ZONE c.timezone)` → *„6.696 Logins … (Ortszeit des jeweiligen
  Kunden)“* ✓
- Spaltenverzeichnis: 6.696 ✓. Der Satz im Glossar („Tageszeit … Ortszeit des Kunden“) reicht.

**M02 „Wie viele Kunden haben wir?“** (erwartet: Rückfrage)
- Nur Schema: *„FocusFlow hat insgesamt 600 Kunden.“* ✗
- Glossar: *„Bitte präzisieren Sie, welche Kundengruppe Sie interessiert: Konten insgesamt, zahlende Pro-Kunden zum
  30.09.2026, aktive Kunden …?“* ✓
- Spaltenverzeichnis: *„Welche Kunden meinst du? 1. Alle registrierten Konten 2. Pro-Kunden zum Stichtag 3. Aktive
  Kunden …“* ✓ (2 von 3)

**U01 „Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“** (erwartet: keine Daten)
- Nur Schema: *„… über den Web-Kanal (9 Kunden). Es folgen Apple mit 6 und Google mit 2.“* ✗
- Glossar: *„… über den Web-Kanal mit 13 Neukunden …“* ✗. Das Glossar sagt nichts über `channel`.
- Spaltenverzeichnis, Lauf 2: *„Die Datenbank enthält keine explizite Spalte für den Marketingkanal … Wenn Sie
  stattdessen nach dem Abrechnungskanal fragen …“* ✓. In Lauf 1 und 3 wieder die Ersatz-Abfrage. ✗

**Sonnet E02 „In welchen fünf Ländern haben wir die meisten Kunden?“** (Goldset: Konten, DE 189 …)
- Nur Schema: DE 189, US 121, GB 52, AU 45, JP 38 ✓
- Glossar: *„Was meinst du mit ‚Kunden‘? Im Haus gibt es dafür drei Definitionen …“* ✗ nach Goldset, richtig nach Glossar.

## Branch (d1): Antwortformat „karte“, Regressionstest am 30.09.2026

Haiku 4.5 + Glossar mit strukturierter Antwort (Ergebnis, Begriffe, Annahmen, andere Deutung mit Zahl aus ausgeführter
SQL, SQL), 27 × 3. Protokoll:
[`laeufe/20260930-180934_haiku_glossar_karte.jsonl`](laeufe/20260930-180934_haiku_glossar_karte.jsonl), Kosten 0,86 USD
(Budget 1,50, Schätzung 0,81).

| | Haiku (c), Format kurz | Haiku (d1), Format karte |
|---|---|---|
| richtig | 70/81 (86 %) | 68/81 (84 %) |
| pass^3 | 22/27 | 21/27 |
| eindeutig | 39/42 | 39/42 |
| mehrdeutig | 14/18 | 14/18 |
| Fallen | 14/15 | 12/15 |
| unbeantwortbar | 3/6 | 3/6 |
| Kosten je 1.000 Fragen | 8,51 USD | 10,67 USD |
| p95 | 9,4 s | 13,1 s |

**Keine messbare Regression bei der Qualität** (84 % gegenüber 86 %, im Rauschen). Das Format kostet aber: 25 % mehr je
Frage (mehr Output-Tokens für Annahmen und Deutung) und 3,7 s mehr beim p95.

**Das vorhergesagte Risiko bei den M-Fragen:** Die Quote bleibt bei 14/18, aber einmal tritt das Muster auf. **M02,
Wiederholung 3:** Statt nachzufragen antwortet Haiku *„FocusFlow hat 600 registrierte Kundenkonten“* und legt als andere
Deutung die Pro-Kunden daneben (201, vom Harness ausgeführt). Die Karte ist ehrlich, aber geraten ist geraten: Bei einer
mehrdeutigen Frage ist eine Rückfrage richtig. Im Lauf (c) ohne Kartenformat hat Haiku M02 in allen drei Läufen
nachgefragt. M01 wird dagegen besser (3/3 statt 2/3). Die andere Deutung füllt Haiku in 18 von 81 Karten, am häufigsten
bei E12, E03, M01 und U01.

**Fehler-Rundgang, Unterschiede zu (c):**

| Frage | (c) | (d1) | Ursache in (d1) |
|---|---|---|---|
| M02 | 3/3 | 2/3 | W3: Zahl (600) mit anderer Deutung (201) statt Rückfrage |
| F01 | 3/3 | 1/3 | W1: `NOT IN`-Filter schließt nie etwas aus (686,44); W3: schließt zu viel aus (547,47). Die Annahme nennt beide Male die richtige Regel. |
| F02 | 3/3 | 2/3 | W2: Rechnungen mit Doppelabbuchung ganz entfernt statt einmal gezählt (3.081,67) |
| F03 | 2/3 | 3/3 | besser |
| M01 | 2/3 | 3/3 | besser |

Unverändert falsch wie in (c): E12 (Kalendertage), M06 (377 statt 374), U01 (Abrechnungsweg als Marketingkanal).

**Stimmen die Annahmen zum SQL?** Von Hand geprüft an E05, F03, F04, M02 und U01 in allen drei Wiederholungen, dazu vier
auffällige Fälle: [docs/ANTWORTEN.md](../docs/ANTWORTEN.md). Kurz: Annahmen sind Absichtserklärungen, keine Prüfung. Sie
legen Deutungsfehler offen (U01: „Kanal = channel in subscriptions“), aber nicht Umsetzungsfehler. Bei F01, F02 und M06
steht die richtige Regel in der Karte und eine falsche Umsetzung im SQL. E05 W1 behauptet „je Rechnung nur einmal“, setzt
es nicht um und liegt trotzdem richtig, weil es im Mai keine Doppelabbuchung gab.

## Rohausgabe `scripts/auswerten.py`

| Modell | Variante | richtig | pass^k | E | M | F | U | Kosten/1000 Req. | Kosten/1000 richtige | p50 | p95 | SQL/Frage | Fehler |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | glossar | 70/81 (86 %) | 22/27 (k=3) | 39/42 | 14/18 | 14/15 | 3/6 | 8.51 USD | 9.85 USD | 4.6 s | 9.4 s | 0.9 | 0 |
| claude-haiku-4-5 | glossar · karte | 68/81 (84 %) | 21/27 (k=3) | 39/42 | 14/18 | 12/15 | 3/6 | 10.67 USD | 12.70 USD | 5.9 s | 13.1 s | 1.0 | 0 |
| claude-haiku-4-5 | glossar_spalten | 69/81 (85 %) | 20/27 (k=3) | 38/42 | 14/18 | 13/15 | 4/6 | 9.91 USD | 11.64 USD | 4.8 s | 10.6 s | 0.9 | 1 |
| claude-haiku-4-5 | schema | 47/81 (58 %) | 14/27 (k=3) | 32/42 | 9/18 | 3/15 | 3/6 | 6.54 USD | 11.27 USD | 4.7 s | 9.9 s | 1.1 | 1 |
| claude-sonnet-5-5 | glossar | 78/81 (96 %) | 26/27 (k=3) | 39/42 | 18/18 | 15/15 | 6/6 | 10.14 USD | 10.53 USD | 5.0 s | 8.1 s | 0.8 | 0 |
| claude-sonnet-5-5 | schema | 74/81 (91 %) | 24/27 (k=3) | 39/42 | 17/18 | 12/15 | 6/6 | 9.51 USD | 10.41 USD | 5.3 s | 11.5 s | 0.9 | 0 |

### claude-haiku-4-5 · glossar

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✓ | ✓ | ✓ |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✓ | ✓ | ✓ |
| E05 | ✓ | ✓ | ✓ |
| E06 | ✓ | ✓ | ✓ |
| E07 | ✓ | ✓ | ✓ |
| E08 | ✓ | ✓ | ✓ |
| E10 | ✓ | ✓ | ✓ |
| E11 | ✓ | ✓ | ✓ |
| E12 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| E13 | ✓ | ✓ | ✓ |
| E14 | ✓ | ✓ | ✓ |
| E15 | ✓ | ✓ | ✓ |
| F01 | ✓ | ✓ | ✓ |
| F02 | ✓ | ✓ | ✓ |
| F03 | ✓ | ✓ | ✗ ergebnis |
| F04 | ✓ | ✓ | ✓ |
| F05 | ✓ | ✓ | ✓ |
| M01 | ✓ | ✓ | ✗ ergebnis |
| M02 | ✓ | ✓ | ✓ |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✓ | ✓ | ✓ |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U01 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U02 | ✓ | ✓ | ✓ |

### claude-haiku-4-5 · glossar · karte

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✓ | ✓ | ✓ |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✓ | ✓ | ✓ |
| E05 | ✓ | ✓ | ✓ |
| E06 | ✓ | ✓ | ✓ |
| E07 | ✓ | ✓ | ✓ |
| E08 | ✓ | ✓ | ✓ |
| E10 | ✓ | ✓ | ✓ |
| E11 | ✓ | ✓ | ✓ |
| E12 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| E13 | ✓ | ✓ | ✓ |
| E14 | ✓ | ✓ | ✓ |
| E15 | ✓ | ✓ | ✓ |
| F01 | ✗ ergebnis | ✓ | ✗ ergebnis |
| F02 | ✓ | ✗ ergebnis | ✓ |
| F03 | ✓ | ✓ | ✓ |
| F04 | ✓ | ✓ | ✓ |
| F05 | ✓ | ✓ | ✓ |
| M01 | ✓ | ✓ | ✓ |
| M02 | ✓ | ✓ | ✗ ergebnis |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✓ | ✓ | ✓ |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U01 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U02 | ✓ | ✓ | ✓ |

### claude-haiku-4-5 · glossar_spalten

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✓ | ✓ | ✓ |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✓ | ✓ | ✓ |
| E05 | ✗ ergebnis | ✓ | ✗ keine |
| E06 | ✓ | ✓ | ✓ |
| E07 | ✓ | ✓ | ✓ |
| E08 | ✓ | ✓ | ✓ |
| E10 | ✓ | ✓ | ✓ |
| E11 | ✓ | ✓ | ✓ |
| E12 | ✗ ergebnis | ✓ | ✗ ergebnis |
| E13 | ✓ | ✓ | ✓ |
| E14 | ✓ | ✓ | ✓ |
| E15 | ✓ | ✓ | ✓ |
| F01 | ✓ | ✓ | ✗ ergebnis |
| F02 | ✓ | ✓ | ✓ |
| F03 | ✓ | ✗ ergebnis | ✓ |
| F04 | ✓ | ✓ | ✓ |
| F05 | ✓ | ✓ | ✓ |
| M01 | ✓ | ✓ | ✓ |
| M02 | ✓ | ✓ | ✗ ergebnis |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✓ | ✓ | ✓ |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✗ ergebnis | ✗ ergebnis | ✗ ergebnis |
| U01 | ✗ ergebnis | ✓ | ✗ ergebnis |
| U02 | ✓ | ✓ | ✓ |

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

### claude-sonnet-5-5 · glossar

| Frage | Wdh. 1 | Wdh. 2 | Wdh. 3 |
|---|---|---|---|
| E01 | ✓ | ✓ | ✓ |
| E02 | ✗ rueckfrage | ✗ rueckfrage | ✗ rueckfrage |
| E03 | ✓ | ✓ | ✓ |
| E04 | ✓ | ✓ | ✓ |
| E05 | ✓ | ✓ | ✓ |
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
| F02 | ✓ | ✓ | ✓ |
| F03 | ✓ | ✓ | ✓ |
| F04 | ✓ | ✓ | ✓ |
| F05 | ✓ | ✓ | ✓ |
| M01 | ✓ | ✓ | ✓ |
| M02 | ✓ | ✓ | ✓ |
| M03 | ✓ | ✓ | ✓ |
| M04 | ✓ | ✓ | ✓ |
| M05 | ✓ | ✓ | ✓ |
| M06 | ✓ | ✓ | ✓ |
| U01 | ✓ | ✓ | ✓ |
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
