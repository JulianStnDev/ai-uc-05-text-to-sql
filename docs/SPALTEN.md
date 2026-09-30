# Spaltenverzeichnis FocusFlow

Bedeutung der Spalten, deren Name missverstanden werden kann. Eine Zeile je Spalte.

- `customers.signup_at`: Registrierung des Kontos, nicht Beginn eines Abos.
- `customers.timezone`: Zeitzone des Kunden (IANA-Name, etwa `Europe/Berlin`). Alle Zeitstempel sind in UTC gespeichert.
- `customers.is_premium`: wird beim ersten Pro-Abo gesetzt und nie zurückgesetzt; sagt nichts über ein laufendes Abo.
- `subscriptions.channel`: Abrechnungsweg des Abos: `web` = Zahlung über die Website (`payments`), `apple`/`google` = Kauf im App Store bzw. bei Google Play (`store_transactions`).
- `subscriptions.ends_at`: Ende des Zugangs; leer, solange das Abo läuft. Unabhängig vom Zeitpunkt einer Kündigung.
- `cancellations.cancelled_at`: Zeitpunkt der Kündigungserklärung, nicht das Abo-Ende.
- `cancellations.reason`: vom Kunden gewählter Grund (`price_increase`, `too_expensive`, `not_using`, `switched_app`, `withdrawal`, `other`).
- `payments.invoice_id`: Rechnung; eine Rechnung kann mehrere Zahlungsversuche und in Einzelfällen mehrere erfolgreiche Zahlungen haben.
- `refunds.reason`: Grund der Erstattung (`withdrawal_14d` = Widerruf, `goodwill` = Kulanz, `duplicate_charge` = Erstattung einer Doppelabbuchung).
- `store_transactions.customer_price_usd`: Preis, den der Kunde im Store bezahlt hat.
- `store_transactions.proceeds_usd`: Auszahlung des Stores an FocusFlow nach Provision.
- `logins.platform`: Gerät bzw. App, über die sich der Kunde eingeloggt hat; unabhängig vom Abrechnungsweg des Abos.
