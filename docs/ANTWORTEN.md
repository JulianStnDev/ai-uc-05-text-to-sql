# Stimmen die Annahmen zum SQL?

Im Antwortformat „karte“ (Branch d) nennt der Copilot zu jeder Zahl die verwendeten Glossar-Begriffe, seine Annahmen
und eine andere naheliegende Deutung. Das soll Vertrauen schaffen. Die Gefahr: **eine ehrliche Karte über einer falschen
Zahl.** Die Karte behauptet etwa „Doppelabbuchungen herausgerechnet“, das SQL tut es aber nicht. Wer der Karte glaubt,
prüft die Zahl nicht mehr.

Geprüft von Hand am Regressionstest vom 30.09.2026 (Haiku 4.5 + Glossar, Format „karte“, 27 × 3,
[`evals/laeufe/20260930-180934_haiku_glossar_karte.jsonl`](../evals/laeufe/20260930-180934_haiku_glossar_karte.jsonl)):
die fünf vereinbarten Fragen in allen drei Wiederholungen, dazu vier auffällige Fälle aus dem übrigen Lauf. Wo eine
Behauptung nachgerechnet werden musste, ist das mit einer Abfrage als `analyst_ro` belegt.

## Das Ergebnis in einem Satz

In 11 der 15 geprüften Karten der fünf Fragen stimmt jede Annahme zum SQL. In 4 Karten gibt es eine Abweichung. Nur eine
davon (F03 W1: „bis 30.08.“) fällt schon beim Lesen auf, für die anderen muss man das SQL lesen.

## Vier Arten von Abweichung

| Art | Beispiel | Zahl | Gefahr |
|---|---|---|---|
| **A. Behauptet, nicht umgesetzt, Zahl zufällig richtig** | E05 W1 | richtig | hoch: Die Karte bestätigt eine Regel, die das SQL nicht einhält. Im nächsten Monat wäre die Zahl falsch. |
| **B. Behauptet, nicht umgesetzt, Zahl falsch** | U01 W3, dazu F01 W1, F01 W3, F02 W2, M06 W1 | falsch | am höchsten: ehrliche Karte über falscher Zahl |
| **C. Annahme falsch formuliert, SQL richtig** | F03 W1 | richtig | gering, aber verwirrend |
| **D. Zahl im Text, nicht aus SQL** | M02 W1 | Text | mittel: Die Zahl in einer Rückfrage prüft niemand |

## Die fünf Fragen

### E05 „Wie hoch war der Umsatz im Mai 2026?“: 3/3 richtig, aber einmal nur durch Glück

| Wdh. | Annahme | im SQL? |
|---|---|---|
| 1 | „Web-Umsatz = erfolgreiche Zahlungen, **je Rechnung nur einmal**“ | **nein.** Das SQL gruppiert nach `invoice_id` und bildet `SUM(amount_usd)`, zählt Doppelabbuchungen also mit. |
| 1 | „Store-Umsatz = proceeds_usd“, „Erstattungen außer duplicate_charge“ | ja |
| 2 | „je Invoice nur die erste erfolgreiche Zahlung“ | ja (`MIN(payment_id)` je Rechnung) |
| 3 | „je invoice_id die erste erfolgreiche Zahlung“ | ja (`ROW_NUMBER() … ORDER BY paid_at`, `rn = 1`) |

**Art A.** Im Mai 2026 gibt es keine einzige Doppelabbuchung (Abfrage: April 1, Juni 3, Juli 3, September 3, Mai 0).
Darum stimmt die Zahl in Wiederholung 1 trotzdem. Die Karte sagt „je Rechnung nur einmal“, und ein Leser würde glauben, die
Regel sei umgesetzt. Mit derselben SQL wäre der Juni falsch.

### F03 „Wie viele Kunden haben im August 2026 gekündigt?“: 3/3 richtig

| Wdh. | Annahme | im SQL? |
|---|---|---|
| 1 | „Zeitraum = August 2026 (01.08.2026 bis **30.08.2026** in UTC)“ | **nein, aber zugunsten der Zahl.** Das SQL filtert bis `< '2026-09-01'`, schließt den 31.08. also ein. |
| 1–3 | „Kündigung = cancelled_at“, „gezählt werden Kunden (distinct customer_id)“ | ja |
| 3 | andere Deutung: „Das Abo endete im August 2026 (ends_at)“ → **18** | ja, und genau die naive Zahl der Kündigungs-Falle |

**Art C** in Wiederholung 1: Die Annahme beschreibt das SQL falsch, die Zahl stimmt. Wiederholung 3 zeigt, wofür die
andere Deutung gut ist: Sie nennt die Falle (Kündigung ≠ Abo-Ende) samt der Zahl, die man sonst bekäme.

### F04 „Wie viele Logins fanden morgens zwischen 6 und 9 Uhr statt?“: 3/3 richtig

| Wdh. | Annahme | im SQL? |
|---|---|---|
| 1–3 | „Morgens = 06:00–08:59 Ortszeit des Kunden“ | ja (`AT TIME ZONE c.timezone`, `>= 6 AND < 9`) |
| 1–3 | „Datenzeitraum 01.10.2025 bis 30.09.2026“ | ja (in 2 und 3 ausdrücklich gefiltert, in 1 durch die Daten gegeben) |
| 3 | „Alle **erfolgreichen** Logins werden gezählt“ | ohne Inhalt: `logins` kennt keinen Erfolgsstatus |

Alle Annahmen passen. Nur Wiederholung 3 erfindet eine Unterscheidung („erfolgreich“), die es in den Daten nicht gibt.
Harmlos, aber ein Hinweis: Annahmen klingen manchmal nur gründlich.

### M02 „Wie viele Kunden haben wir?“: 2/3 richtig (Rückfrage)

| Wdh. | Art | Beobachtung |
|---|---|---|
| 1 | Rückfrage | Die Rückfrage nennt Zahlen: „600 registrierte Konten, 201 Pro-Kunden oder **377** aktive Kunden?“ Die 377 ist falsch (richtig: 374, das Fenster beginnt einen Tag zu früh). **Art D:** Diese Zahlen stehen im Text, der Harness hat sie nie ausgeführt. |
| 2 | Rückfrage | ohne Zahlen, ohne Annahmen |
| 3 | **Zahl statt Rückfrage** | „FocusFlow hat 600 registrierte Kundenkonten.“ Annahme: „Mit ‚Kunden‘ sind alle registrierten Konten gemeint“ (im SQL: ja). Andere Deutung: Pro-Kunden → **201** (vom Harness ausgeführt, richtig). |

Wiederholung 3 ist das vorhergesagte Risiko des neuen Formats: Statt nachzufragen, wählt Haiku eine Deutung und legt
die andere daneben. Die Karte ist dabei vollkommen ehrlich, Annahme und Alternative stimmen. Nach den Regeln ist es
trotzdem falsch, denn bei einer mehrdeutigen Frage soll der Copilot nachfragen.

### U01 „Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“: 0/3

| Wdh. | Annahme | im SQL? |
|---|---|---|
| 1 | „Kanal = channel in subscriptions“, „Abos, die im März 2026 begonnen haben“ | ja, beides |
| 2 | „Kanal = subscription.channel des Kundenabos“ | ja |
| 3 | „Zuordnung nach dem **ersten/ältesten Abo** pro Neukunde“ | **nein.** Das SQL zählt jeden Kunden bei jedem Kanal, in dem er ein Abo hat. |

Die Antwort ist in allen drei Läufen falsch (keine Daten wäre richtig). Aber in Wiederholung 1 und 2 **legt die Karte den
Fehler offen**: „Kanal = channel in subscriptions“ ist genau der Ersatz, den ein Leser erkennen kann. Das ist die gute Seite
der Karte. Wiederholung 3 ist **Art B**: Die Annahme verspricht eine Zuordnung, die das SQL nicht macht.

## Vier weitere Fälle aus dem Lauf (Art B)

| Frage | Annahme | was das SQL tut | Zahl |
|---|---|---|---|
| F01 W1 | „Je invoice_id nur die erste erfolgreiche Zahlung“ | Der `NOT IN`-Filter sucht die Zahlung in einer Liste, die sie selbst ausschließt, und schließt deshalb nie etwas aus | 686,44 statt 613,46 |
| F01 W3 | „Pro Rechnung nur die erste erfolgreiche Zahlung“ | schließt jede Zahlung aus, vor der es irgendeinen Versuch gab, auch einen fehlgeschlagenen | 547,47 statt 613,46 |
| F02 W2 | „Web-Umsatz: je Invoice maximal einmal gezählt“ | wirft Rechnungen mit Doppelabbuchung ganz heraus (Web 1.872,01 statt 1.899,97) | 3.081,67 statt 3.109,63 |
| M06 W1 | „30 Tage (**01. September** bis 30. September 2026)“ | filtert ab `2026-08-31` | 377 statt 374 |

Bei allen vier ist die Annahme genau die richtige Geschäftsregel. Das Modell kennt sie aus dem Glossar und schreibt sie
korrekt auf, setzt sie im SQL aber falsch um. **Die Karte zeigt, was das Modell vorhatte, nicht, was das SQL tut.**

## Was daraus folgt

1. **Annahmen sind Absichtserklärungen, keine Prüfung.** Sie helfen bei Deutungsfehlern (U01: „Kanal = channel“), aber
   nicht bei Umsetzungsfehlern (F01, F02, M06). Genau dort wirken sie am überzeugendsten.
2. **Zahlen nur aus ausgeführter SQL, auch in Rückfragen.** Die andere Deutung rechnet der Harness selbst aus, das hat
   funktioniert (M02 W3: 201, F03 W3: 18). Zahlen im Text einer Rückfrage (M02 W1: 377) prüft niemand. Für die Oberfläche
   heißt das: Zahlen, die nicht aus ausgeführter SQL stammen, werden nicht hervorgehoben.
3. **Die Oberfläche zeigt SQL und Annahmen nebeneinander.** Der Leser soll beides vergleichen können. Eine automatische
   Prüfung (etwa: „Annahme nennt `invoice_id`, SQL hat kein `DISTINCT ON`/`ROW_NUMBER`“) wäre möglich, aber brüchig. Sie
   ist nicht Teil von Branch (d).
4. **Das Feld „andere Deutung“ kann Rückfragen verdrängen.** Das ist hier einmal passiert (M02 W3). Die M-Quote bleibt
   insgesamt bei 14/18, der Effekt ist im Rauschen, aber das Muster ist echt: Eine Zahl mit Alternative sieht hilfreich
   aus und ist doch geraten.

## Nachtrag: Code-Prüfung der Annahmen (Branch d2, 30.09.2026)

Aus Punkt 3 oben ist doch eine einfache Prüfung geworden (`app/annahmen.py`, Tests in `tests/test_annahmen.py`). Sie
kennt sechs Regeln: eine Zahlung je Rechnung, Store-Umsatz über `proceeds_usd`, Erstattungen abgezogen (oder bewusst
nicht) und ohne `duplicate_charge`, Zeitzone des Kunden, Kündigung = `cancelled_at` bzw. Abo-Ende = `ends_at`, genannter
Zeitraum. Behauptet eine Annahme eine dieser Regeln, sucht die Prüfung ein festes Muster im SQL (Kommentare und
String-Literale vorher entfernt) und zeigt **✓ verified in SQL** oder **⚠ not found in SQL**, sonst kein Badge. Den
Zeitraum prüft sie nur, wenn das SQL überhaupt Datumswerte enthält.

Über alle 81 Karten des Regressionstests: 71 ✓, 11 ⚠, 129 Annahmen ohne Badge.

| ⚠ auf | Anzahl | Karten |
|---|---|---|
| falscher Antwort (die vier Fehlkarten) | 4 | F01 W1, F01 W3, F02 W2, M06 W1 |
| richtiger Antwort, zu Recht | 5 | E05 W1 (Glück); E01 W2, E08 W1, E10 W1, F03 W1 (Karte nennt „bis 30.“, SQL rechnet bis Monatsende) |
| richtiger Antwort, aus Vorsicht | 2 | E05 W2 (`MIN(payment_id)` je Rechnung), F02 W1 (`MAX(amount_usd)` je Rechnung) |

Die zwei Fehlalarme sind gewollt: Beide Muster ergeben hier dieselbe Zahl, sind aber nicht „die erste erfolgreiche
Zahlung“. Ein ✓ ist dagegen nie über einer der vier Fehlkarten erschienen. Grenzen: Die Prüfung sieht nur Muster, keine
Semantik. Ein ✓ heißt, dass das SQL die Regel an irgendeiner Stelle umsetzt, nicht, dass die Zahl stimmt (M06 W2 und W3
bekommen ✓, weil Karte und SQL übereinstimmend beim 31.08. beginnen; beide sind trotzdem falsch).
