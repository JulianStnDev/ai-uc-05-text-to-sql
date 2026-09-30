# Goldset (berechnet, zur Durchsicht)

Erzeugt von `scripts/goldset_berechnen.py` aus `evals/goldset_fragen.py`. Nicht von Hand bearbeiten.

| ID | Typ | Frage | Falle | Erwartet | Naiv (Falle) |
|---|---|---|---|---|---|
| E01 | eindeutig | Wie viele Kunden haben sich im März 2026 registriert? | – | neukunden: 54 |  |
| E02 | eindeutig | In welchen fünf Ländern haben wir die meisten Kunden, und wie viele sind es jeweils? | – | DE 189 · US 121 · GB 52 · AU 45 · JP 38 |  |
| E03 | eindeutig | Wie viele Pro-Abos wurden im ersten Quartal 2026 abgeschlossen, aufgeteilt nach Kanal? | – | apple 15 · google 9 · web 34 |  |
| E04 | eindeutig | Wie viele Kunden hatten am 30. September 2026 ein laufendes Jahresabo? | irrefuehrende_spalte | kunden: 98 |  |
| E05 | eindeutig | Wie hoch war der Umsatz im Mai 2026? | doppelabbuchung, store, erstattung | umsatz_usd: 1224.34 |  |
| E06 | eindeutig | Wie viel Geld haben wir im Gesamtzeitraum an Kunden erstattet, ohne die Erstattungen von Doppelabbuchungen? | doppelabbuchung, erstattung | erstattungen: 25, summe_usd: 604.94 |  |
| E07 | eindeutig | Welcher Kündigungsgrund wurde am häufigsten angegeben, und wie oft? | – | reason: price_increase, anzahl: 49 |  |
| E08 | eindeutig | Wie viele Kunden haben sich im Juli 2026 mindestens einmal eingeloggt? | – | kunden: 316 |  |
| E10 | eindeutig | Über welche Plattform kamen im August 2026 die meisten Logins, und wie viele waren es? | – | platform: ios, logins: 2239 |  |
| E11 | eindeutig | Wie viele Web-Zahlungen sind im Gesamtzeitraum fehlgeschlagen? | – | fehlgeschlagen: 17 |  |
| E12 | eindeutig | Wie viele Tage vergehen im Median zwischen Registrierung und erstem Pro-Abo? | – | median_tage: 7.4 |  |
| E13 | eindeutig | Wie viele Kunden haben mehr als ein Abo abgeschlossen? | – | kunden: 10 |  |
| E14 | eindeutig | Wie viele Abos endeten im September 2026? | kuendigung | beendete_abos: 22 |  |
| E15 | eindeutig | Wie hoch war der Umsatz aus Käufen im Apple App Store im zweiten Quartal 2026? | store | umsatz_usd: 1020.23 |  |
| M01 | mehrdeutig | Wie viele Kunden haben wir im Sommer verloren? | kuendigung | **Rückfrage:** Was heißt „verloren“: gekündigt, Abo beendet oder nicht mehr genutzt? Und ist mit Sommer Juni bis August gemeint?<br>(1) Kunden mit Kündigung (cancelled_at) von Juni bis August 2026: kunden: 65<br>(2) Kunden, deren Abo von Juni bis August 2026 endete und die am 31.08. kein laufendes Abo hatten: kunden: 23<br>(3) Kunden mit Login im Mai 2026, aber keinem Login von Juni bis August: kunden: 30 |  |
| M02 | mehrdeutig | Wie viele Kunden haben wir? | irrefuehrende_spalte | **Rückfrage:** Welche Kunden meinst du: alle registrierten Konten, zahlende Pro-Kunden oder aktive Kunden? Und zu welchem Stichtag?<br>(1) Alle registrierten Konten: kunden: 600<br>(2) Pro-Kunden mit laufendem Abo am 30.09.2026: kunden: 201<br>(3) Aktive Kunden (Login in den 30 Tagen bis 30.09.2026): kunden: 374 |  |
| M03 | mehrdeutig | Welcher Kanal ist am besten? | store | **Rückfrage:** Woran gemessen: am Umsatz, an der Zahl neuer Abos oder daran, wie selten gekündigt wird?<br>(1) Umsatz je Kanal im Gesamtzeitraum: web 5018.91 · apple 3008.59 · google 1331.74<br>(2) Neue Abos je Kanal im Gesamtzeitraum: web 140 · apple 87 · google 38<br>(3) Anteil gekündigter Abos je Kanal (niedrig ist gut): apple 28.7 · web 38.6 · google 39.5 |  |
| M04 | mehrdeutig | Wie hoch ist unsere Kündigungsquote? | kuendigung | **Rückfrage:** Für welchen Zeitraum und auf welcher Basis: Anteil aller Abos, monatlich (z. B. August 2026) oder je Kunde?<br>(1) Anteil gekündigter Abos an allen Abos im Gesamtzeitraum: prozent: 35.5<br>(2) Monatlich, August 2026: Kündigungen im August / am 01.08. laufende Abos: prozent: 31.5<br>(3) Je Kunde: Kunden mit mindestens einer Kündigung / Kunden mit mindestens einem Abo: prozent: 35.4 |  |
| M05 | mehrdeutig | Wie viele Kunden nutzen FocusFlow regelmäßig? | – | **Rückfrage:** Was heißt regelmäßig und in welchem Zeitraum: an mindestens 10 Tagen im Monat, jede Woche, oder aktiv laut Definition (Login in den letzten 30 Tagen)?<br>(1) Login an mindestens 10 verschiedenen Tagen im September 2026: kunden: 217<br>(2) Login in jeder der vier Wochen 01.–28.09.2026: kunden: 241<br>(3) Aktive Kunden laut Glossar (Login in den 30 Tagen bis 30.09.2026): kunden: 374 |  |
| M06 | mehrdeutig | Wie viele aktive Kunden hatten wir am 30. September 2026? | – | **Rückfrage:** Was heißt aktiv: eingeloggt in den letzten 30 Tagen, in der letzten Woche, oder mit laufendem Pro-Abo?<br>(1) Login in den 30 Tagen bis 30.09.2026 (Definition laut Glossar): aktive_kunden: 374<br>(2) Login in den 7 Tagen bis 30.09.2026: aktive_kunden: 306<br>(3) Laufendes Pro-Abo am 30.09.2026: aktive_kunden: 201<br>**Mit Glossar (Branch c) eindeutig:** aktive_kunden: 374 |  |
| F01 | falle | Wie hoch war der Web-Umsatz im September 2026 vor Erstattungen? | doppelabbuchung | umsatz_usd: 613.46 | umsatz_usd: 686.44 (zählt Doppelabbuchungen (zweite Zahlung zur selben Rechnung) als Umsatz) |
| F02 | falle | Wie hoch war der Umsatz im zweiten Quartal 2026 insgesamt? | store | umsatz_usd: 3109.63 | umsatz_usd: 1592.48 (rechnet nur payments; Apple- und Google-Käufe stehen in store_transactions) |
| F03 | falle | Wie viele Kunden haben im August 2026 gekündigt? | kuendigung | kunden: 55 | kunden: 18 (nimmt das Abo-Ende statt der Kündigungserklärung; Kündigungen im August enden meist im September) |
| F04 | falle | Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt? | zeitzone | logins: 6696 | logins: 3695 (nimmt die UTC-Stunde statt der Ortszeit des Kunden) |
| F05 | falle | Wie viele Kunden hatten am 30. September 2026 ein laufendes Pro-Abo? | irrefuehrende_spalte | kunden: 201 | kunden: 254 (is_premium heißt „hatte je Pro“ und wird nach Kündigung nicht zurückgesetzt) |
| U01 | unbeantwortbar | Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden? | – | **Keine Daten:** Die Herkunft der Kunden (Kampagne, Anzeige, Empfehlung) wird nicht erfasst.<br>Falsch wäre: subscriptions.channel (Kaufkanal web/apple/google) oder logins.platform |  |
| U02 | unbeantwortbar | Wie hoch war der NPS im dritten Quartal 2026? | – | **Keine Daten:** Es gibt keine Umfrage- oder Bewertungsdaten.<br>Falsch wäre: Kündigungsquote oder Kündigungsgründe (cancellations.reason) als Zufriedenheitsersatz |  |

## Beleg je Falle

| Falle | Frage | richtig | naiv |
|---|---|---|---|
| doppelabbuchung | F01 | umsatz_usd: 613.46 | umsatz_usd: 686.44 |
| store | F02 | umsatz_usd: 3109.63 | umsatz_usd: 1592.48 |
| kuendigung | F03 | kunden: 55 | kunden: 18 |
| erstattung | E05 | umsatz_usd: 1224.34 | umsatz_usd: 1344.34 |
| zeitzone | F04 | logins: 6696 | logins: 3695 |
| irrefuehrende_spalte | F05 | kunden: 201 | kunden: 254 |
