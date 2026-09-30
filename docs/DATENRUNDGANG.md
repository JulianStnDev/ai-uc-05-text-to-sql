# Datenrundgang: echte Zeilen aus der Analyse-Datenbank

Nur für Menschen, **nie ans Modell** (erklärt die Fallen, wie `DATA_NOTES.md`). Erzeugt von `scripts/datenrundgang.py`, nur lesend als `analyst_ro`. Alle Zeiten in UTC, sofern nicht „Ortszeit“ dasteht.

## 1. Die sieben Tabellen

### customers

Ein Konto pro Zeile: Land, Zeitzone, Anmeldung und `is_premium` (heißt in Wahrheit „hatte je Pro“).

| customer_id | email | country | timezone | signup_at | is_premium |
|---|---|---|---|---|---|
| C0001 | user0001@example.com | GB | Europe/London | 2026-06-10 09:12:26 | True |
| C0002 | user0002@example.com | US | America/Los_Angeles | 2026-09-30 22:37:29 | False |
| C0003 | user0003@example.com | JP | Asia/Tokyo | 2026-05-26 10:56:29 | True |

### subscriptions

Ein Pro-Abo pro Zeile: Tarif, Kanal (web/apple/google), Beginn und Ende des Zugangs (`ends_at` leer = läuft).

| subscription_id | customer_id | plan | channel | started_at | ends_at |
|---|---|---|---|---|---|
| S00001 | C0001 | pro_annual | apple | 2026-06-15 03:29:57 | – |
| S00002 | C0003 | pro_monthly | web | 2026-05-26 14:02:07 | 2026-08-26 14:02:07 |
| S00003 | C0004 | pro_monthly | web | 2026-08-17 20:50:45 | – |

### cancellations

Eine Kündigungserklärung pro Abo: wann der Kunde gekündigt hat und warum. Das Abo endet oft später.

| cancellation_id | subscription_id | cancelled_at | reason |
|---|---|---|---|
| K00001 | S00002 | 2026-08-17 03:16:15 | price_increase |
| K00002 | S00005 | 2026-08-18 08:57:30 | price_increase |
| K00003 | S00010 | 2026-08-29 04:01:20 | price_increase |

### payments

Jeder Einzugsversuch für Web-Abos, auch fehlgeschlagene. Mehrere Zeilen können zur selben Rechnung gehören.

| payment_id | invoice_id | subscription_id | customer_id | paid_at | amount_usd | status |
|---|---|---|---|---|---|---|
| P000001 | INV-000001 | S00002 | C0003 | 2026-05-26 14:02:17 | 6.99 | succeeded |
| P000002 | INV-000002 | S00002 | C0003 | 2026-06-26 14:02:16 | 6.99 | succeeded |
| P000003 | INV-000003 | S00002 | C0003 | 2026-07-26 14:02:13 | 6.99 | succeeded |

### refunds

Erstattungen auf Web-Zahlungen, mit Grund (Widerruf, Kulanz, Doppelabbuchung).

| refund_id | payment_id | refunded_at | amount_usd | reason |
|---|---|---|---|---|
| R0001 | P000057 | 2026-05-21 22:28:22 | 59.00 | withdrawal_14d |
| R0002 | P000073 | 2026-06-08 07:24:50 | 59.00 | withdrawal_14d |
| R0003 | P000074 | 2026-06-24 02:27:59 | 59.00 | withdrawal_14d |

### store_transactions

Käufe und Verlängerungen über Apple und Google. Diese Abos haben keine Zeilen in `payments`.

| transaction_id | subscription_id | customer_id | store | purchased_at | customer_price_usd | proceeds_usd |
|---|---|---|---|---|---|---|
| T000001 | S00001 | C0001 | apple | 2026-06-15 03:30:51 | 59.00 | 50.15 |
| T000002 | S00004 | C0006 | google | 2026-05-10 01:34:00 | 6.99 | 5.94 |
| T000003 | S00004 | C0006 | google | 2026-06-10 01:33:00 | 6.99 | 5.94 |

### logins

Jeder Login mit Zeitpunkt in UTC und Plattform. Die Ortszeit ergibt sich erst mit `customers.timezone`.

| login_id | customer_id | logged_in_at | platform |
|---|---|---|---|
| 1 | C0001 | 2026-06-13 11:05:36 | ios |
| 2 | C0001 | 2026-06-16 17:40:40 | ios |
| 3 | C0001 | 2026-06-17 07:35:00 | ios |

## 2. Zwei Kunden-Lebensläufe

### Ein ganz normaler Kunde: C0345

Meldet sich in Berlin an, schließt zehn Tage später ein Web-Monatsabo ab und zahlt jeden Monat pünktlich. Keine Kündigung, keine Erstattung. Logins je Monat zusammengefasst.

| Zeit (UTC) | Ortszeit | Tabelle | Ereignis |
|---|---|---|---|
| 2026-03-19 05:14 | 19.03. 06:14 | customers | Anmeldung (DE, Europe/Berlin) |
| 2026-03-21 18:06 | 21.03. 19:06 | logins | 4 Logins im 03/2026 |
| 2026-03-29 02:31 | 29.03. 04:31 | subscriptions | Abo S00153 beginnt: pro_monthly über web |
| 2026-03-29 02:31 | 29.03. 04:31 | payments | P000243 · Rechnung INV-000235 · 6.99 USD · succeeded |
| 2026-04-01 20:46 | 01.04. 22:46 | logins | 14 Logins im 04/2026 |
| 2026-04-29 02:31 | 29.04. 04:31 | payments | P000244 · Rechnung INV-000236 · 6.99 USD · succeeded |
| 2026-05-01 05:53 | 01.05. 07:53 | logins | 18 Logins im 05/2026 |
| 2026-05-29 02:32 | 29.05. 04:32 | payments | P000245 · Rechnung INV-000237 · 6.99 USD · succeeded |
| 2026-06-01 00:15 | 01.06. 02:15 | logins | 15 Logins im 06/2026 |
| 2026-06-29 02:31 | 29.06. 04:31 | payments | P000246 · Rechnung INV-000238 · 6.99 USD · succeeded |
| 2026-07-02 05:58 | 02.07. 07:58 | logins | 15 Logins im 07/2026 |
| 2026-07-29 02:32 | 29.07. 04:32 | payments | P000247 · Rechnung INV-000239 · 6.99 USD · succeeded |
| 2026-08-01 18:16 | 01.08. 20:16 | logins | 22 Logins im 08/2026 |
| 2026-08-29 02:32 | 29.08. 04:32 | payments | P000248 · Rechnung INV-000240 · 6.99 USD · succeeded |
| 2026-09-02 19:37 | 02.09. 21:37 | logins | 22 Logins im 09/2026 |
| 2026-09-29 02:31 | 29.09. 04:31 | payments | P000249 · Rechnung INV-000241 · 6.99 USD · succeeded |

### Ein Kunde mit vielen Fallen: C0250

Lebt in Kolkata (UTC+5:30): Schon die Anmeldung ist in UTC der 18.01., beim Kunden aber der 19.01. Der erste Einzug scheitert und klappt am nächsten Tag (gleiche Rechnung). Im Juni wird doppelt abgebucht und die zweite Zahlung erstattet, dazu kommen zwei Kulanz-Erstattungen. Er kündigt am 29.09. (UTC; in Kolkata schon der 30.09.), sein Abo läuft aber bis 20.10. weiter. Am Stichtag 30.09. ist er also noch Pro-Kunde, obwohl er gekündigt hat.

| Zeit (UTC) | Ortszeit | Tabelle | Ereignis |
|---|---|---|---|
| 2026-01-18 21:48 | 19.01. 03:18 | customers | Anmeldung (IN, Asia/Kolkata) |
| 2026-01-20 01:03 | 20.01. 06:33 | logins | 7 Logins im 01/2026 |
| 2026-01-20 11:51 | 20.01. 17:21 | subscriptions | Abo S00103 beginnt: pro_monthly über web |
| 2026-01-20 11:52 | 20.01. 17:22 | payments | P000140 · Rechnung INV-000137 · 6.99 USD · failed |
| 2026-01-21 12:09 | 21.01. 17:39 | payments | P000141 · Rechnung INV-000137 · 6.99 USD · succeeded |
| 2026-02-04 10:58 | 04.02. 16:28 | logins | 19 Logins im 02/2026 |
| 2026-02-20 11:53 | 20.02. 17:23 | payments | P000142 · Rechnung INV-000138 · 6.99 USD · succeeded |
| 2026-03-01 15:37 | 01.03. 21:07 | logins | 18 Logins im 03/2026 |
| 2026-03-20 11:52 | 20.03. 17:22 | payments | P000143 · Rechnung INV-000139 · 6.99 USD · succeeded |
| 2026-04-01 07:19 | 01.04. 12:49 | logins | 20 Logins im 04/2026 |
| 2026-04-20 11:53 | 20.04. 17:23 | payments | P000144 · Rechnung INV-000140 · 6.99 USD · succeeded |
| 2026-05-03 06:27 | 03.05. 11:57 | logins | 17 Logins im 05/2026 |
| 2026-05-20 11:52 | 20.05. 17:22 | payments | P000145 · Rechnung INV-000141 · 6.99 USD · succeeded |
| 2026-06-04 17:32 | 04.06. 23:02 | logins | 19 Logins im 06/2026 |
| 2026-06-20 11:53 | 20.06. 17:23 | payments | P000146 · Rechnung INV-000142 · 6.99 USD · succeeded |
| 2026-06-20 11:56 | 20.06. 17:26 | payments | P000395 · Rechnung INV-000142 · 6.99 USD · succeeded |
| 2026-06-25 11:56 | 25.06. 17:26 | refunds | R0012 erstattet 6.99 USD auf P000395 (duplicate_charge) |
| 2026-06-27 17:53 | 27.06. 23:23 | refunds | R0025 erstattet 3.50 USD auf P000146 (goodwill) |
| 2026-07-01 03:27 | 01.07. 08:57 | logins | 25 Logins im 07/2026 |
| 2026-07-20 11:52 | 20.07. 17:22 | payments | P000147 · Rechnung INV-000143 · 6.99 USD · succeeded |
| 2026-07-21 14:52 | 21.07. 20:22 | refunds | R0026 erstattet 6.99 USD auf P000147 (goodwill) |
| 2026-08-02 00:50 | 02.08. 06:20 | logins | 20 Logins im 08/2026 |
| 2026-08-20 11:52 | 20.08. 17:22 | payments | P000148 · Rechnung INV-000144 · 6.99 USD · succeeded |
| 2026-09-04 08:08 | 04.09. 13:38 | logins | 11 Logins im 09/2026 |
| 2026-09-20 11:52 | 20.09. 17:22 | payments | P000149 · Rechnung INV-000145 · 6.99 USD · succeeded |
| 2026-09-29 19:54 | 30.09. 01:24 | cancellations | Kündigung von S00103 (other) |
| 2026-10-20 11:51 | 20.10. 17:21 | subscriptions | Abo S00103 endet (ends_at) |

## 3. Vier Goldset-Fragen im Detail

### F01 · Doppelabbuchung: „Wie hoch war der Web-Umsatz im September 2026 vor Erstattungen?“

**Entscheidende Zeilen:** drei Rechnungen im September haben je zwei erfolgreiche Zahlungen. Die zweite kam Sekunden bis Minuten später und ist ein Fehler des Zahlungsanbieters, kein Umsatz.

| invoice_id | payment_id | paid_at | amount_usd | erstattet_als |
|---|---|---|---|---|
| INV-000043 | P000043 | 2026-09-11 18:29:50 | 59.00 | – |
| INV-000043 | P000393 | 2026-09-11 18:32:57 | 59.00 | duplicate_charge |
| INV-000100 | P000101 | 2026-09-11 23:38:30 | 6.99 | – |
| INV-000100 | P000391 | 2026-09-11 23:42:16 | 6.99 | – |
| INV-000361 | P000377 | 2026-09-09 13:22:02 | 6.99 | – |
| INV-000361 | P000392 | 2026-09-09 13:25:59 | 6.99 | – |

**Naiv:**

```sql
-- alle erfolgreichen Zahlungen im September zusammenzählen
SELECT sum(amount_usd) AS umsatz_usd
FROM payments
WHERE status = 'succeeded'
  AND paid_at >= '2026-09-01' AND paid_at < '2026-10-01'
```

| umsatz_usd |
|---|
| 686.44 |

**Richtig:**

```sql
-- je Rechnung nur die erste erfolgreiche Zahlung zählen
WITH web AS (
  SELECT DISTINCT ON (invoice_id) paid_at, amount_usd
  FROM payments
  WHERE status = 'succeeded'
  ORDER BY invoice_id, paid_at          -- die früheste Zahlung je Rechnung gewinnt
)
SELECT sum(amount_usd) AS umsatz_usd
FROM web
WHERE paid_at >= '2026-09-01' AND paid_at < '2026-10-01'
```

| umsatz_usd |
|---|
| 613.46 |

**Warum verschieden:** Die naive Summe zählt die drei zweiten Abbuchungen als Umsatz (59,00 + 6,99 + 6,99 = 72,98 USD), obwohl sie nur versehentlich eingezogen wurden. Dass eine davon schon erstattet ist, spielt hier keine Rolle: Gefragt ist der Umsatz vor Erstattungen.

### F03 · Kündigung: „Wie viele Kunden haben im August 2026 gekündigt?“

**Entscheidende Zeilen:** Kündigung (`cancellations.cancelled_at`) und Abo-Ende (`subscriptions.ends_at`) sind verschiedene Tage. Wer im August kündigt, hat bis zum Ende der bezahlten Periode Zugang.

Wann enden die Abos, die im August gekündigt wurden?

| abo_endet_im | abos |
|---|---|
| 2026-08 | 16 |
| 2026-09 | 19 |
| 2026-10 | 1 |
| 2026-11 | 2 |
| 2026-12 | 1 |
| 2027-01 | 3 |
| 2027-02 | 2 |
| 2027-03 | 1 |
| 2027-05 | 1 |
| 2027-06 | 2 |
| 2027-07 | 3 |
| 2027-08 | 5 |

Und umgekehrt: Wann wurden die Abos gekündigt, die im August enden?

| gekuendigt_im | abos |
|---|---|
| 2026-07 | 2 |
| 2026-08 | 16 |

Drei Beispiele: gekündigt im August, Ende im September.

| customer_id | cancelled_at | ends_at | plan | reason |
|---|---|---|---|---|
| C0418 | 2026-08-10 19:34:52 | 2026-09-03 16:54:31 | pro_monthly | price_increase |
| C0486 | 2026-08-14 09:43:15 | 2026-09-13 07:28:17 | pro_monthly | other |
| C0514 | 2026-08-16 17:49:55 | 2026-09-02 13:42:35 | pro_monthly | price_increase |

**Naiv:**

```sql
-- Abos, die im August geendet haben
SELECT count(DISTINCT customer_id) AS kunden
FROM subscriptions
WHERE ends_at >= '2026-08-01' AND ends_at < '2026-09-01'
```

| kunden |
|---|
| 18 |

**Richtig:**

```sql
-- Kündigungserklärungen im August, je Kunde einmal
SELECT count(DISTINCT s.customer_id) AS kunden
FROM cancellations k
JOIN subscriptions s USING (subscription_id)   -- Kunde steht am Abo
WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'
```

| kunden |
|---|
| 55 |

**Warum verschieden:** Die naive Abfrage sieht nur Kunden, deren Abo im August schon ausgelaufen ist: 16 Augustkündiger mit kurzer Restlaufzeit und 2 Juli-Kündiger. Die übrigen 39 Augustkündiger haben noch bis September oder länger Zugang (Monatsabo bis zum nächsten Abrechnungstag, Jahresabo bis zum Jahrestag) und fehlen deshalb.

### F04 · Zeitzone: „Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt?“

**Entscheidende Zeilen:** Derselbe Login hat in UTC eine andere Stunde als beim Kunden. Drei Morgen-Logins (Ortszeit) aus verschiedenen Zeitzonen:

| login_id | timezone | utc | ortszeit |
|---|---|---|---|
| 165 | America/Los_Angeles | 2026-05-10 14:37:46 | 2026-05-10 07:37:46 |
| 66 | Asia/Tokyo | 2026-05-26 22:35:43 | 2026-05-27 07:35:43 |
| 270 | Europe/Berlin | 2026-08-13 05:15:18 | 2026-08-13 07:15:18 |

**Naiv:**

```sql
-- Stunde des gespeicherten Zeitstempels (UTC)
SELECT count(*) AS logins
FROM logins
WHERE extract(hour FROM logged_in_at AT TIME ZONE 'UTC') BETWEEN 6 AND 8   -- 06:00 bis 08:59
```

| logins |
|---|
| 3695 |

**Richtig:**

```sql
-- Stunde in der Zeitzone des jeweiligen Kunden
SELECT count(*) AS logins
FROM logins l
JOIN customers c USING (customer_id)          -- Zeitzone steht am Kunden
WHERE extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) BETWEEN 6 AND 8
```

| logins |
|---|
| 6696 |

**Warum verschieden:** Ein Berliner Frühaufsteher um 7 Uhr steht in UTC bei 5 oder 6 Uhr, ein Kunde in Los Angeles um 7 Uhr bei 14 oder 15 Uhr UTC. Die UTC-Stunde trifft die Morgenspitze nur für einen Teil der Kunden.

### U01 · Unbeantwortbar: „Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“

**Entscheidende Zeilen:** keine. Keine Tabelle speichert, woher ein Kunde kam (Anzeige, Kampagne, Empfehlung). Alle Spalten mit „channel“ oder Ähnlichem:

| table_name | column_name | data_type |
|---|---|---|
| logins | platform | text |
| store_transactions | store | text |
| subscriptions | channel | text |

**Vermutliche Ersatz-Abfrage eines Modells** (falsch):

```sql
-- nimmt den Kaufkanal des Abos als „Marketingkanal“
SELECT s.channel, count(DISTINCT c.customer_id) AS neukunden
FROM customers c
JOIN subscriptions s USING (customer_id)
WHERE c.signup_at >= '2026-03-01' AND c.signup_at < '2026-04-01'
GROUP BY s.channel
ORDER BY neukunden DESC
```

| channel | neukunden |
|---|---|
| web | 13 |
| apple | 7 |
| google | 2 |

Die Antwort wäre dann „web“. Sie klingt plausibel, sagt aber nur, wo bezahlt wurde. Außerdem fehlen alle Neukunden ohne Abo:

| neukunden_maerz | davon_mit_abo |
|---|---|
| 54 | 22 |

**Richtig:** keine Abfrage, sondern: „Dazu gibt es keine Daten. Die Herkunft der Kunden wird nicht erfasst.“ Eine Rückfrage zählt ebenfalls als richtig.

**Warum:** `subscriptions.channel` ist der Kaufkanal (Web, Apple, Google), nicht der Marketingkanal. Wer ihn als Ersatz nimmt, beantwortet eine andere Frage.
