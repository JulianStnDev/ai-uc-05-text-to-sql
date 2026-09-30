# Daten-Notizen (nur für Menschen, NIE ans Modell)

Diese Datei beschreibt die FocusFlow-Analysedaten und ihre absichtlich eingebauten Fallen. Sie ist die Grundlage für
das Goldset und darf **nie** in einen Prompt gelangen, weder in Branch (b) (nur Schema) noch in Branch (c) (Schema +
Glossar). Wie `CORPUS_NOTES.md` in UC3.

Stand: 30.09.2026 · Neon-Datenbank `analytics` (Frankfurt) · erzeugt von `scripts/daten_erzeugen.py`, Seed `20260930`

## Überblick

| Tabelle | Zeilen | Inhalt |
|---|---|---|
| customers | 600 | Konten, Land, Zeitzone, Anmeldung, `is_premium` |
| subscriptions | 265 | Pro-Abos: Tarif, Kanal (web/apple/google), Beginn, Ende |
| cancellations | 94 | Kündigungserklärungen mit Zeitpunkt und Grund |
| payments | 400 | nur Web-Zahlungen (Stripe), inkl. fehlgeschlagener Versuche |
| refunds | 33 | Erstattungen auf Web-Zahlungen |
| store_transactions | 366 | Käufe und Verlängerungen über Apple und Google |
| logins | 26.798 | Logins mit Zeitstempel in UTC und Plattform |

Zeitraum 01.10.2025 bis 30.09.2026, alle Zeitstempel in UTC. Alle Kunden haben sich in diesem Zeitraum angemeldet
(etwas mehr gegen Ende, Wachstum). Preise: 6,99 USD/Monat, 59,00 USD/Jahr. 254 Kunden (42 %) schließen ein Abo ab,
im Median 7,4 Tage nach der Anmeldung. Abos nach Kanal: 140 Web, 87 Apple, 38 Google.

**Deterministisch:** `scripts/laden.py` legt alle Tabellen neu an und erzeugt jedes Mal dieselben Zeilen.
`tests/test_daten.py` prüft das per Fingerabdruck.

## Die sechs Fallen

Jede Falle ist in den Daten gebaut, nicht nur in den Fragen. Die naive Abfrage ist jeweils die Referenzabfrage mit
genau dem einen Fehler, sodass der Unterschied genau diese Falle belegt (Werte aus `evals/goldset.json`):

| Falle | Frage | richtig | naiv | naiver Fehler |
|---|---|---|---|---|
| Doppelabbuchung | F01 Web-Umsatz Sep. vor Erstattungen | 613,46 USD | 686,44 USD | zweite Zahlung derselben Rechnung mitgezählt |
| Store vs. Web | F02 Umsatz Q2 2026 | 3.109,63 USD | 1.592,48 USD | nur `payments`, Store-Käufe fehlen |
| Kündigung ≠ Abo-Ende | F03 Kündigungen August | 55 Kunden | 18 Kunden | `ends_at` statt `cancelled_at` |
| Erstattungen | E05 Umsatz Mai | 1.224,34 USD | 1.344,34 USD | Erstattungen nicht abgezogen |
| Zeitzone | F04 Logins morgens 6–9 Uhr | 6.696 | 3.695 | UTC-Stunde statt Ortszeit |
| Irreführende Spalte | F05 laufende Pro-Abos 30.09. | 201 Kunden | 254 Kunden | `is_premium` statt laufender Abos |

### 1. Doppelabbuchungen
- **Gebaut:** 10 Web-Zahlungen wurden ein zweites Mal eingezogen: gleiche `invoice_id`, gleicher Betrag, 20–240 Sekunden
  später, beide `status = 'succeeded'`. Verteilt auf April, Juni, Juli und September 2026. 8 sind erstattet
  (`refunds.reason = 'duplicate_charge'`, 2–5 Tage später). **2 im September sind noch offen.**
- **Richtig:** je `invoice_id` nur die erste erfolgreiche Zahlung. Erstattungen mit `duplicate_charge` mindern den Umsatz
  dann nicht noch einmal.
- **Naiv:** `SUM(amount_usd)` über alle erfolgreichen Zahlungen. Nach Abzug aller Erstattungen passt das zufällig für die
  erstatteten Fälle, nicht aber vor Erstattungen oder für die offenen im September.

### 2. Store-Käufe vs. Web-Käufe
- **Gebaut:** Apple- und Google-Abos haben **keine** Zeilen in `payments`. Ihre Käufe und Verlängerungen stehen nur in
  `store_transactions`, mit Kundenpreis (`customer_price_usd`) und Auszahlung nach 15 % Provision (`proceeds_usd`).
- **Richtig:** Umsatz = Web (`payments`) + Store (`proceeds_usd`).
- **Naiv:** nur `payments`, fast die Hälfte des Q2-Umsatzes fehlt. Zweite Variante (E15, Apple Q2): `customer_price_usd` statt
  `proceeds_usd` ergibt 1.200,38 statt 1.020,23 USD.

### 3. Kündigung im August, Abo-Ende im September
- **Gebaut:** Kündigung (`cancellations.cancelled_at`) und Abo-Ende (`subscriptions.ends_at`) sind getrennt. Eine Kündigung
  wirkt zum Ende der bezahlten Periode. Am 10.08.2026 ging eine Preiserhöhungs-Mail raus, danach kündigten deutlich mehr
  Kunden (Grund `price_increase`). Von den Kündigungen im August enden 16 Abos im August, 19 im September und der Rest
  (Jahresabos) erst 2026/2027.
- **Richtig:** Kündigungen nach `cancelled_at` zählen.
- **Naiv:** Abos mit `ends_at` im August: nur 16 Augustkündiger mit kurzer Restlaufzeit plus 2 aus dem Juli.
  Die übrigen 39 Augustkündiger haben noch Zugang und fehlen.

### 4. Erstattungen mindern den Umsatz
- **Gebaut:** 33 Erstattungen: 9 Widerrufe von Web-Jahresabos innerhalb von 14 Tagen (`withdrawal_14d`, voller Betrag,
  Abo endet sofort), 16 Kulanz-Erstattungen auf Monatszahlungen (`goodwill`, teils anteilig 2,00 oder 3,50 USD), 8
  Erstattungen von Doppelabbuchungen.
- **Richtig:** Erstattungen außer `duplicate_charge` im Monat von `refunded_at` abziehen.
- **Naiv:** Summe der Zahlungen ohne Abzug.
- Im Goldset gibt es dafür keine eigene Fallen-Frage (fünf Fallen-Fragen für sechs Fallen). Die Falle steckt in E05
  und E06 und ist oben mit E05 belegt.

### 5. Zeitstempel in UTC, Kunden in anderen Zeitzonen
- **Gebaut:** Logins werden in Ortszeit erzeugt (Spitzen 6–9 Uhr und 19–23 Uhr) und in UTC gespeichert.
  Zeitzonen: Europe/Berlin 189, New York 67, Los Angeles 54, London 52, Sydney 45, Tokyo 38, Wien 31, Kolkata 30,
  Toronto 28, Zürich 27, Amsterdam 24, São Paulo 15. Sommerzeit ist berücksichtigt (zoneinfo).
- **Richtig:** `logged_in_at AT TIME ZONE customers.timezone`.
- **Naiv:** UTC-Stunde, fast halb so viele Morgen-Logins.

### 6. Irreführender Spaltenname: `customers.is_premium`
- **Gebaut:** `is_premium` wird beim ersten Abo auf `true` gesetzt und **nie zurückgesetzt**. Die Spalte heißt eigentlich
  „hatte je Pro“. Die Tabelle hat keinen Hinweis darauf, auch keinen Kommentar im Schema.
- **Richtig:** laufendes Abo zum Stichtag (`started_at` davor, `ends_at` leer oder danach).
- **Naiv:** `COUNT(*) WHERE is_premium`, 53 Kunden zu viel.

## Goldset

27 Fragen: 14 eindeutig (E), 6 mehrdeutig (M), 5 Fallen (F), 2 unbeantwortbar (U). Quelle `evals/goldset_fragen.py`,
Vergleichsregeln `scripts/vergleich.py`. Die Tabelle schreibt `scripts/goldset_berechnen.py`, nicht von Hand ändern.
Durchsicht und Korrekturen durch Julian am 30.09.2026: E09 wurde M06 (ohne Glossar ist „aktiv“ mehrdeutig, mit Glossar
erwartet: 374), M02 ersetzt durch „Wie viele Kunden haben wir?“, U01/U02 neu.

<!-- GOLDSET:START -->
| ID | Typ | Frage | Falle | Erwartet | Naiv (Falle) |
|---|---|---|---|---|---|
| E01 | eindeutig | Wie viele Kunden haben sich im März 2026 registriert? | – | neukunden: 54 |  |
| E02 | eindeutig | In welchen fünf Ländern haben wir die meisten Kunden, und wie viele sind es jeweils? | – | DE 189 · US 121 · GB 52 · AU 45 · JP 38 |  |
| E03 | eindeutig | Wie viele Pro-Abos wurden im ersten Quartal 2026 abgeschlossen, aufgeteilt nach Kanal? | – | apple 15 · google 9 · web 34 |  |
| E04 | eindeutig | Wie viele Kunden hatten am 30. September 2026 ein laufendes Jahresabo? | kuendigung | kunden: 98 |  |
| E05 | eindeutig | Wie hoch war der Umsatz im Mai 2026? | doppelabbuchung, store, erstattung | umsatz_usd: 1224.34 |  |
| E06 | eindeutig | Wie viel Geld haben wir im Gesamtzeitraum an Kunden erstattet, ohne die Erstattungen von Doppelabbuchungen? | doppelabbuchung, erstattung | summe_usd: 604.94 |  |
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
<!-- GOLDSET:END -->

## Weitere Eigenheiten (keine Fallen, aber wichtig für Referenz-SQL)
- **Fehlgeschlagene Zahlungen:** 5 % der ersten Einzüge scheitern (`status = 'failed'`), die Wiederholung 1–2 Tage später
  gelingt. Gleiche `invoice_id`. Nie Umsatz.
- **Store-Erstattungen** laufen über Apple/Google und sind nicht in den Daten.
- **Wiederkehrer:** 15 % der beendeten Abos werden später neu abgeschlossen (neues Abo, evtl. anderer Tarif).
  10 Kunden haben mehr als ein Abo.
- **Nutzung:** Pro-Kunden loggen sich an gut der Hälfte der Tage ein. Gratis-Nutzer sind meist einige Wochen aktiv und
  dann selten, ein Teil bleibt lange dabei. Nach dem Abo-Ende nur noch vereinzelt.
- **Session-Zeitzone:** Datumsgrenzen wie `'2026-05-01'` gelten in der Zeitzone der Sitzung. Alle Skripte setzen
  `SET TIME ZONE 'UTC'`. Der Neon-Pooler meldet `GMT`, gleicher Offset, keine Sommerzeit.

## Mehrdeutige Fragen: warum sie mehrdeutig bleiben
Das Glossar (Branch c) definiert Begriffe wie Umsatz, Kündigung, aktiver Kunde. Es legt aber bewusst **nicht** fest,
was „verloren“, „regelmäßig“ oder „am besten“ heißt oder welche Kündigungsquote gemeint ist. „Kunde“ allein erklärt es
ausdrücklich für mehrdeutig. M01–M05 sollen deshalb auch mit Glossar eine Rückfrage auslösen. Nur M06 („aktive Kunden“)
wird mit Glossar eindeutig (374). Die Deutungen liefern deutlich verschiedene Zahlen (z. B. M01: 65, 23 oder 30 Kunden).
