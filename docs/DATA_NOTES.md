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
- **Naiv:** Abos mit `ends_at` im August, das sind überwiegend Kündigungen aus dem Juli.

### 4. Erstattungen mindern den Umsatz
- **Gebaut:** 33 Erstattungen: 9 Widerrufe von Web-Jahresabos innerhalb von 14 Tagen (`withdrawal_14d`, voller Betrag,
  Abo endet sofort), 16 Kulanz-Erstattungen auf Monatszahlungen (`goodwill`, teils anteilig 2,00 oder 3,50 USD), 8
  Erstattungen von Doppelabbuchungen.
- **Richtig:** Erstattungen außer `duplicate_charge` im Monat von `refunded_at` abziehen.
- **Naiv:** Summe der Zahlungen ohne Abzug.
- Im Goldset gibt es dafür keine eigene Fallen-Frage (fünf Fallen-Fragen für sechs Fallen). Die Falle steckt in E05,
  E06 und M02 und ist oben mit E05 belegt.

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
was „verloren“, „regelmäßig“, „am besten“, „letztes Quartal“ oder eine „Kündigungsquote“ ohne Zeitraum bedeuten. Die fünf
mehrdeutigen Fragen sollen auch mit Glossar eine Rückfrage auslösen. Die Deutungen im Goldset liefern deutlich
verschiedene Zahlen (z. B. M01: 65, 23 oder 30 Kunden).
