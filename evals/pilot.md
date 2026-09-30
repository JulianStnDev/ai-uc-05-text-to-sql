# Pilot: Haiku 4.5, Branch (b), 27 × 1

Lauf am 30.09.2026, Protokoll: [`laeufe/20260930-132455_haiku_schema.jsonl`](laeufe/20260930-132455_haiku_schema.jsonl).
Zweck: echte Tokens und Kosten messen und das Messinstrument prüfen. Danach wurden drei Messfehler der Vergleichsregeln
behoben (docs/decisions.md, 30.09.2026). Seitdem sind Goldset und Regeln eingefroren.

| | alte Regeln | neue Regeln (gültig) |
|---|---|---|
| richtig | 13/27 | **16/27 (59 %)** |
| eindeutig | 8/14 | 11/14 |
| mehrdeutig (Rückfrage) | 2/6 | 2/6 |
| Fallen | 2/5 | 2/5 |
| unbeantwortbar | 1/2 | 1/2 |

Neu richtig: E06 (nur die Summe ist gefragt), E07 und E10 (Spitzenwert richtig, dazu die übrige Rangliste).

## Tokens und Kosten

| | Aufrufe | Input-Tokens | Output-Tokens | Kosten | Dauer |
|---|---|---|---|---|---|
| Summe | 60 | 116.895 | 12.311 | 0,178 USD | |
| je Frage | 2,2 | 4.329 | 456 | 0,0066 USD | p50 5,0 s, p95 9,1 s |

- Kosten je 1.000 Fragen: 6,61 USD (Haiku, Variante schema). Die Schätzung vor dem Pilot lag bei 0,010 USD je Frage.
- Prompt-Caching greift nicht: Prompt und Schema haben ca. 1.700 Tokens, Haiku 4.5 cacht erst ab 4.096 Tokens.
- Ausreißer E01 (21 s): erste Frage, Kaltstart.

Schätzung für den vollen Lauf (je 27 × 3): Haiku ca. 0,54 USD (gemessen × 81). Sonnet 5.5 ca. 1,20–2,40 USD
(doppelter Preis, ca. 30 % mehr Tokens durch den Tokenizer, zusätzliche Thinking-Tokens, dafür Caching ab 512 Tokens).
Budgets 1,00 und 3,50 USD.

<details><summary>Je Frage</summary>

| Frage | Typ | Aufrufe | SQL | Input-Tokens | Output-Tokens | Kosten USD | Dauer s | alt | neu |
|---|---|---|---|---|---|---|---|---|---|
| E01 | eindeutig | 2 | 1 | 3.653 | 313 | 0.0052 | 21.1 | ✓ | ✓ |
| E02 | eindeutig | 2 | 1 | 3.686 | 378 | 0.0056 | 6.6 | ✓ | ✓ |
| E03 | eindeutig | 2 | 1 | 3.766 | 590 | 0.0067 | 5.7 | ✓ | ✓ |
| E04 | eindeutig | 2 | 1 | 3.781 | 599 | 0.0068 | 5.5 | ✗ | ✗ |
| E05 | eindeutig | 2 | 1 | 3.656 | 363 | 0.0055 | 4.2 | ✗ | ✗ |
| E06 | eindeutig | 4 | 3 | 11.789 | 749 | 0.0155 | 9.1 | ✗ | ✓ |
| E07 | eindeutig | 2 | 1 | 3.663 | 388 | 0.0056 | 4.2 | ✗ | ✓ |
| E08 | eindeutig | 2 | 1 | 3.699 | 362 | 0.0055 | 6.4 | ✓ | ✓ |
| E10 | eindeutig | 2 | 1 | 3.723 | 418 | 0.0058 | 4.8 | ✗ | ✓ |
| E11 | eindeutig | 2 | 1 | 3.664 | 324 | 0.0053 | 3.9 | ✓ | ✓ |
| E12 | eindeutig | 3 | 2 | 6.183 | 833 | 0.0103 | 7.5 | ✗ | ✗ |
| E13 | eindeutig | 3 | 2 | 5.825 | 466 | 0.0082 | 5.5 | ✓ | ✓ |
| E14 | eindeutig | 2 | 1 | 3.643 | 309 | 0.0052 | 3.6 | ✓ | ✓ |
| E15 | eindeutig | 2 | 1 | 3.711 | 432 | 0.0059 | 7.4 | ✓ | ✓ |
| M01 | mehrdeutig | 1 | 0 | 1.735 | 306 | 0.0033 | 3.5 | ✓ | ✓ |
| M02 | mehrdeutig | 2 | 1 | 3.562 | 188 | 0.0045 | 2.9 | ✗ | ✗ |
| M03 | mehrdeutig | 2 | 0 | 3.651 | 395 | 0.0056 | 4.5 | ✓ | ✓ |
| M04 | mehrdeutig | 2 | 1 | 3.723 | 509 | 0.0063 | 5.5 | ✗ | ✗ |
| M05 | mehrdeutig | 3 | 2 | 5.894 | 702 | 0.0094 | 7.2 | ✗ | ✗ |
| M06 | mehrdeutig | 2 | 1 | 3.702 | 428 | 0.0058 | 4.9 | ✗ | ✗ |
| F01 | falle | 2 | 1 | 3.714 | 449 | 0.0060 | 4.8 | ✗ | ✗ |
| F02 | falle | 3 | 2 | 5.805 | 652 | 0.0091 | 7.8 | ✗ | ✗ |
| F03 | falle | 3 | 2 | 5.864 | 522 | 0.0085 | 6.1 | ✓ | ✓ |
| F04 | falle | 2 | 1 | 3.687 | 351 | 0.0054 | 4.0 | ✗ | ✗ |
| F05 | falle | 2 | 1 | 3.736 | 429 | 0.0059 | 4.5 | ✓ | ✓ |
| U01 | unbeantwortbar | 2 | 1 | 3.737 | 449 | 0.0060 | 4.4 | ✗ | ✗ |
| U02 | unbeantwortbar | 2 | 1 | 3.643 | 407 | 0.0057 | 5.0 | ✓ | ✓ |

</details>

## Fehler-Rundgang (neue Regeln, 11 falsch)

| ID | Typ | Modell | Erwartet | Ursache |
|---|---|---|---|---|
| E04 | eindeutig | 74 | 98 | Falle Kündigung ≠ Abo-Ende: gekündigte, noch laufende Abos ausgeschlossen |
| E05 | eindeutig | 664,64 | 1.224,34 | Umsatz nur aus `payments`: Store fehlt, Doppelabbuchungen und Erstattungen nicht berücksichtigt |
| E12 | eindeutig | 8,0 | 7,4 | Deutung: Kalendertage statt exakter Zeitdifferenz (nach Syntaxfehler selbst korrigiert) |
| M02 | mehrdeutig | 600 | Rückfrage | Ersatz-Abfrage: alle Konten |
| M04 | mehrdeutig | 35,47 % | Rückfrage | Ersatz-Abfrage: Gesamtzeitraum |
| M05 | mehrdeutig | 374 | Rückfrage | Ersatz-Abfrage: ein Login in 30 Tagen, mit `NOW()` |
| M06 | mehrdeutig | 200 | Rückfrage | Ersatz-Abfrage: laufendes Abo |
| F01 | Falle | 686,44 | 613,46 | Falle Doppelabbuchung nicht erkannt |
| F02 | Falle | 3.712,98 | 3.109,63 | `customer_price_usd` statt `proceeds_usd`, dazu Doppelabbuchungen und Erstattungen nicht berücksichtigt |
| F04 | Falle | 3.695 | 6.696 | Falle Zeitzone: Stunde in UTC statt Ortszeit des Kunden |
| U01 | unbeantwortbar | web 13 | keine Daten | Ersatz-Abfrage: Abo-Kanal als Marketingkanal |

Die Ursachen sind mit Gegenabfragen als `analyst_ro` belegt. Bei E04 ergibt die SQL des Modells ohne den
Kündigungsfilter genau 98. Bei F01 ergibt die Summe ohne Bereinigung der Doppelabbuchungen genau 686,44. Bei F02 wären
es mit `proceeds_usd`, aber ohne die übrigen Bereinigungen, 3.445,08. Bei E12 liefert der Median über Kalendertage
genau 8,0.

### E04: Falle nicht erkannt

*Wie viele Kunden hatten am 30. September 2026 ein laufendes Jahresabo?*

```sql
SELECT COUNT(DISTINCT s.customer_id) FROM subscriptions s
WHERE s.plan = 'pro_annual' AND s.started_at <= '2026-09-30'
  AND (s.ends_at IS NULL OR s.ends_at > '2026-09-30')
  AND NOT EXISTS (SELECT 1 FROM cancellations c
                  WHERE c.subscription_id = s.subscription_id AND c.cancelled_at <= '2026-09-30')
```

Modell 74, erwartet 98. Das Modell wertet eine Kündigung als Abo-Ende. Ein gekündigtes Jahresabo läuft aber bis
`ends_at` weiter.

### F02: Schema missverstanden

*Wie hoch war der Umsatz im zweiten Quartal 2026 insgesamt?*

```sql
SELECT (SELECT SUM(amount_usd) FROM payments WHERE status = 'succeeded' AND paid_at >= '2026-04-01' AND paid_at < '2026-07-01')
     + (SELECT SUM(customer_price_usd) FROM store_transactions WHERE purchased_at >= '2026-04-01' AND purchased_at < '2026-07-01')
```

Modell 3.712,98, erwartet 3.109,63. Den Store-Kanal findet das Modell, summiert aber den Kundenpreis statt der
Auszahlung nach Provision. Doppelabbuchungen und Erstattungen fehlen.

### M05: Deutung statt Rückfrage

*Wie viele Kunden nutzen FocusFlow regelmäßig?*

```sql
SELECT COUNT(DISTINCT c.customer_id), COUNT(DISTINCT l.customer_id), ...
FROM customers c LEFT JOIN logins l ON c.customer_id = l.customer_id
  AND l.logged_in_at >= NOW() - INTERVAL '30 days'
```

Modell „374 (62,3 %)“, erwartet war eine Rückfrage (Deutungen: mindestens 10 Login-Tage im September = 217, jede Woche
und so weiter). Das Modell legt sich stillschweigend auf „mindestens ein Login“ fest. Wegen `NOW()` stimmt die Zahl
außerdem nur am Stichtag.

### F04: Falle nicht erkannt

*Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt?*

```sql
SELECT COUNT(*) FROM logins
WHERE EXTRACT(HOUR FROM logged_in_at) >= 6 AND EXTRACT(HOUR FROM logged_in_at) < 9
```

Modell 3.695, erwartet 6.696. Die Stunde ist in UTC gerechnet, obwohl `customers.timezone` existiert.

### E12: Syntax, danach Deutung

*Wie viele Tage vergehen im Median zwischen Registrierung und erstem Pro-Abo?*

Der erste Versuch mit `QUALIFY ROW_NUMBER() …` (Snowflake/BigQuery, nicht Postgres) scheitert am Syntaxfehler. Das
Modell ersetzt es selbst durch `ROW_NUMBER()` in einer Unterabfrage und rechnet dann
`started_at::DATE - signup_at::DATE`. Ergebnis 8,0, erwartet 7,4: ganze Kalendertage statt exakter Zeitdifferenz. Das
ist der einzige Syntaxfehler im Pilot.

## Rückfrage oder Ersatz-Abfrage?

- **Mehrdeutig:** 2/6 mit Rückfrage (M01, M03). Bei M02, M04, M05 und M06 hat das Modell still eine Deutung gewählt.
  Jedes Mal ist dabei eine der Goldset-Deutungen herausgekommen. Das Modell rät also nicht, es fragt nur nicht nach.
- **Unbeantwortbar:** U02 als „keine Daten“ erkannt. Bei U01 ersetzt das Modell den fehlenden Marketingkanal
  ungekennzeichnet durch den Abo-Kanal.
