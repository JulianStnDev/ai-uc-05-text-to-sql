# Glossar: Geschäftsdefinitionen FocusFlow (Entwurf für Branch c)

Dieses Glossar bekommt das Modell erst in Branch (c). In Branch (b) sieht es nur das Schema (`db/schema.sql`).
Stand: 30.09.2026, Entwurf.

## Zeit
- **Datenzeitraum:** 01.10.2025 bis 30.09.2026. Alle Zeitstempel sind in UTC gespeichert.
- **Monate, Quartale, Tage** für Geschäftszahlen (Umsatz, Kündigungen, Anmeldungen, Logins pro Monat) werden in **UTC** abgegrenzt.
- **Stichtag** „am 30.09.2026“ bedeutet: zum Ende dieses Tages (UTC), also Stand 01.10.2026 00:00 UTC.
- **Tageszeit** („morgens“, „abends“, „nachts“) bezieht sich auf die **Ortszeit des Kunden** (`customers.timezone`).
  Morgens = 06:00–08:59, abends = 18:00–22:59, nachts = 23:00–05:59 Ortszeit.

## Kunden
- **Kunde:** jedes registrierte Konto (`customers`), mit oder ohne Abo.
- **Neukunde:** Registrierung (`signup_at`) im betrachteten Zeitraum.
- **Pro-Kunde (zahlender Kunde) zum Stichtag:** hat ein laufendes Abo, also `started_at` vor dem Ende des Stichtags und
  `ends_at` leer oder nach dem Ende des Stichtags. **`customers.is_premium` bedeutet „hatte irgendwann ein Pro-Abo“**
  und wird nie zurückgesetzt. Die Spalte eignet sich nicht, um aktuelle Pro-Kunden zu zählen.
- **Aktiver Kunde zum Stichtag:** mindestens ein Login in den 30 Tagen bis einschließlich Stichtag.

## Abos und Kündigungen
- **Abo:** Zeile in `subscriptions`. Tarif `pro_monthly` (6,99 USD) oder `pro_annual` (59,00 USD), Kanal `web`, `apple` oder `google`.
- **Neues Abo:** `started_at` im Zeitraum.
- **Kündigung:** die Kündigungserklärung des Kunden, Zeitpunkt `cancellations.cancelled_at`. Eine Kündigung wirkt zum Ende
  der bezahlten Periode. **Kündigung und Abo-Ende sind verschiedene Ereignisse** (Kündigung im August, Ende im September).
- **Abo-Ende:** `subscriptions.ends_at`, das Ende des Zugangs. Leer, solange das Abo weiterläuft.

## Umsatz
- **Umsatz** (ohne Zusatz immer netto) = Web-Umsatz + Store-Umsatz − Erstattungen.
- **Web-Umsatz:** erfolgreiche Zahlungen (`payments.status = 'succeeded'`), **je Rechnung (`invoice_id`) nur einmal**.
  Fehlgeschlagene Zahlungen zählen nie.
- **Doppelabbuchung:** jede weitere erfolgreiche Zahlung zur selben `invoice_id`. Sie ist kein Umsatz. Ihre Erstattung
  (`refunds.reason = 'duplicate_charge'`) mindert den Umsatz deshalb auch nicht.
- **Store-Umsatz:** Käufe über Apple und Google stehen **nur in `store_transactions`**, nicht in `payments`. Umsatz ist die
  Auszahlung an FocusFlow (`proceeds_usd`, nach Store-Provision), nicht der Kundenpreis (`customer_price_usd`).
- **Erstattungen** (`refunds`, außer `duplicate_charge`) mindern den Umsatz im Monat der Erstattung (`refunded_at`).
- **Umsatz vor Erstattungen:** wie Umsatz, aber ohne Abzug der Erstattungen.
- Zuordnung zum Zeitraum: Web nach `paid_at`, Store nach `purchased_at`, Erstattungen nach `refunded_at`.
