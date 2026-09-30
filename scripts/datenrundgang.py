"""Erzeugt docs/DATENRUNDGANG.md aus der Datenbank: Tabellen mit Beispielzeilen, zwei Kunden-Lebensläufe und
vier Goldset-Fragen im Detail. Nur lesend als analyst_ro, keine API-Aufrufe.

    .venv/bin/python scripts/datenrundgang.py

Wie DATA_NOTES.md nur für Menschen: erklärt die Fallen und darf nie in einen Prompt.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

WURZEL = Path(__file__).resolve().parents[1]
NORMAL, FALLEN = "C0345", "C0250"

TABELLEN = [
    ("customers", "Ein Konto pro Zeile: Land, Zeitzone, Anmeldung und `is_premium` (heißt in Wahrheit „hatte je Pro“).",
     "SELECT * FROM customers ORDER BY customer_id LIMIT 3"),
    ("subscriptions", "Ein Pro-Abo pro Zeile: Tarif, Kanal (web/apple/google), Beginn und Ende des Zugangs (`ends_at` leer = läuft).",
     "SELECT * FROM subscriptions ORDER BY subscription_id LIMIT 3"),
    ("cancellations", "Eine Kündigungserklärung pro Abo: wann der Kunde gekündigt hat und warum. Das Abo endet oft später.",
     "SELECT * FROM cancellations ORDER BY cancellation_id LIMIT 3"),
    ("payments", "Jeder Einzugsversuch für Web-Abos, auch fehlgeschlagene. Mehrere Zeilen können zur selben Rechnung gehören.",
     "SELECT * FROM payments ORDER BY payment_id LIMIT 3"),
    ("refunds", "Erstattungen auf Web-Zahlungen, mit Grund (Widerruf, Kulanz, Doppelabbuchung).",
     "SELECT * FROM refunds ORDER BY refund_id LIMIT 3"),
    ("store_transactions", "Käufe und Verlängerungen über Apple und Google. Diese Abos haben keine Zeilen in `payments`.",
     "SELECT * FROM store_transactions ORDER BY transaction_id LIMIT 3"),
    ("logins", "Jeder Login mit Zeitpunkt in UTC und Plattform. Die Ortszeit ergibt sich erst mit `customers.timezone`.",
     "SELECT * FROM logins ORDER BY login_id LIMIT 3"),
]


def zelle(v) -> str:
    if v is None:
        return "–"
    if hasattr(v, "isoformat"):
        return v.strftime("%Y-%m-%d %H:%M:%S") if hasattr(v, "hour") else v.isoformat()
    return str(v).replace("|", "\\|")


def tabelle(cur) -> str:
    spalten = [d.name for d in cur.description]
    zeilen = cur.fetchall()
    return "\n".join(["| " + " | ".join(spalten) + " |", "|" + "---|" * len(spalten)]
                     + ["| " + " | ".join(zelle(v) for v in z) + " |" for z in zeilen])


def sql_block(sql: str) -> str:
    return f"```sql\n{sql.strip()}\n```"


def lebenslauf(c, kunden_id: str) -> str:
    """Alle Ereignisse eines Kunden chronologisch; Logins je Monat zusammengefasst."""
    zone = c.execute("SELECT timezone FROM customers WHERE customer_id=%s", (kunden_id,)).fetchone()[0]
    tz = ZoneInfo(zone)
    ereignisse = c.execute("""
        SELECT signup_at, 'customers', 'Anmeldung (' || country || ', ' || timezone || ')' FROM customers WHERE customer_id = %(k)s
        UNION ALL SELECT started_at, 'subscriptions', 'Abo ' || subscription_id || ' beginnt: ' || plan || ' über ' || channel
          FROM subscriptions WHERE customer_id = %(k)s
        UNION ALL SELECT p.paid_at, 'payments', p.payment_id || ' · Rechnung ' || p.invoice_id || ' · ' || p.amount_usd || ' USD · ' || p.status
          FROM payments p WHERE p.customer_id = %(k)s
        UNION ALL SELECT r.refunded_at, 'refunds', r.refund_id || ' erstattet ' || r.amount_usd || ' USD auf ' || r.payment_id || ' (' || r.reason || ')'
          FROM refunds r JOIN payments p USING (payment_id) WHERE p.customer_id = %(k)s
        UNION ALL SELECT k.cancelled_at, 'cancellations', 'Kündigung von ' || k.subscription_id || ' (' || k.reason || ')'
          FROM cancellations k JOIN subscriptions s USING (subscription_id) WHERE s.customer_id = %(k)s
        UNION ALL SELECT ends_at, 'subscriptions', 'Abo ' || subscription_id || ' endet (ends_at)'
          FROM subscriptions WHERE customer_id = %(k)s AND ends_at IS NOT NULL
        UNION ALL SELECT purchased_at, 'store_transactions', transaction_id || ' · ' || store || ' · Kunde zahlt ' || customer_price_usd
          || ' USD, FocusFlow erhält ' || proceeds_usd || ' USD' FROM store_transactions WHERE customer_id = %(k)s
        UNION ALL SELECT min(logged_in_at), 'logins', count(*) || ' Logins im ' || to_char(logged_in_at, 'MM/YYYY')
          FROM logins WHERE customer_id = %(k)s GROUP BY to_char(logged_in_at, 'MM/YYYY')
        ORDER BY 1""", {"k": kunden_id}).fetchall()
    zeilen = ["| Zeit (UTC) | Ortszeit | Tabelle | Ereignis |", "|---|---|---|---|"]
    for zeit, t, text in ereignisse:
        zeilen.append(f"| {zeit:%Y-%m-%d %H:%M} | {zeit.astimezone(tz):%d.%m. %H:%M} | {t} | {text} |")
    return "\n".join(zeilen)


def main() -> None:
    load_dotenv(WURZEL / ".env")
    teile = ["# Datenrundgang: echte Zeilen aus der Analyse-Datenbank",
             "",
             "Nur für Menschen, **nie ans Modell** (erklärt die Fallen, wie `DATA_NOTES.md`). Erzeugt von "
             "`scripts/datenrundgang.py`, nur lesend als `analyst_ro`. Alle Zeiten in UTC, sofern nicht „Ortszeit“ dasteht.",
             ""]
    with psycopg.connect(os.environ["ANALYTICS_RO_URL"], autocommit=True) as c:
        c.execute("SET TIME ZONE 'UTC'")
        q = lambda sql, p=None: tabelle(c.execute(sql, p))  # noqa: E731

        teile += ["## 1. Die sieben Tabellen", ""]
        for name, satz, sql in TABELLEN:
            teile += [f"### {name}", "", satz, "", q(sql), ""]

        teile += ["## 2. Zwei Kunden-Lebensläufe", "",
                  f"### Ein ganz normaler Kunde: {NORMAL}", "",
                  "Meldet sich in Berlin an, schließt zehn Tage später ein Web-Monatsabo ab und zahlt jeden Monat pünktlich. "
                  "Keine Kündigung, keine Erstattung. Logins je Monat zusammengefasst.", "",
                  lebenslauf(c, NORMAL), "",
                  f"### Ein Kunde mit vielen Fallen: {FALLEN}", "",
                  "Lebt in Kolkata (UTC+5:30): Schon die Anmeldung ist in UTC der 18.01., beim Kunden aber der 19.01. "
                  "Der erste Einzug scheitert und klappt am nächsten Tag (gleiche Rechnung). Im Juni wird doppelt abgebucht "
                  "und die zweite Zahlung erstattet, dazu kommen zwei Kulanz-Erstattungen. Er kündigt am 29.09. (UTC; in "
                  "Kolkata schon der 30.09.), sein Abo läuft aber bis 20.10. weiter. Am Stichtag 30.09. ist er also noch "
                  "Pro-Kunde, obwohl er gekündigt hat.", "",
                  lebenslauf(c, FALLEN), ""]

        teile += ["## 3. Vier Goldset-Fragen im Detail", ""]

        # F01
        doppelt = [r[0] for r in c.execute("""
            SELECT p.amount_usd FROM payments p
            WHERE p.status = 'succeeded' AND p.paid_at >= '2026-09-01' AND p.paid_at < '2026-10-01'
              AND p.paid_at > (SELECT min(q.paid_at) FROM payments q WHERE q.invoice_id = p.invoice_id AND q.status = 'succeeded')
            ORDER BY p.amount_usd DESC""")]
        teile += ["### F01 · Doppelabbuchung: „Wie hoch war der Web-Umsatz im September 2026 vor Erstattungen?“", "",
                  "**Entscheidende Zeilen:** drei Rechnungen im September haben je zwei erfolgreiche Zahlungen. Die zweite "
                  "kam Sekunden bis Minuten später und ist ein Fehler des Zahlungsanbieters, kein Umsatz.", "",
                  q("""SELECT p.invoice_id, p.payment_id, p.paid_at, p.amount_usd,
       coalesce(r.reason, '–') AS erstattet_als
FROM payments p LEFT JOIN refunds r USING (payment_id)
WHERE p.invoice_id IN (SELECT invoice_id FROM payments WHERE status = 'succeeded'
                       AND paid_at >= '2026-09-01' AND paid_at < '2026-10-01'
                       GROUP BY invoice_id HAVING count(*) > 1)
ORDER BY p.invoice_id, p.paid_at"""), "",
                  "**Naiv:**", "", sql_block("""
-- alle erfolgreichen Zahlungen im September zusammenzählen
SELECT sum(amount_usd) AS umsatz_usd
FROM payments
WHERE status = 'succeeded'
  AND paid_at >= '2026-09-01' AND paid_at < '2026-10-01'"""), "",
                  q("SELECT sum(amount_usd) AS umsatz_usd FROM payments WHERE status = 'succeeded' "
                    "AND paid_at >= '2026-09-01' AND paid_at < '2026-10-01'"), "",
                  "**Richtig:**", "", sql_block("""
-- je Rechnung nur die erste erfolgreiche Zahlung zählen
WITH web AS (
  SELECT DISTINCT ON (invoice_id) paid_at, amount_usd
  FROM payments
  WHERE status = 'succeeded'
  ORDER BY invoice_id, paid_at          -- die früheste Zahlung je Rechnung gewinnt
)
SELECT sum(amount_usd) AS umsatz_usd
FROM web
WHERE paid_at >= '2026-09-01' AND paid_at < '2026-10-01'"""), "",
                  q("WITH web AS (SELECT DISTINCT ON (invoice_id) paid_at, amount_usd FROM payments WHERE status = 'succeeded' "
                    "ORDER BY invoice_id, paid_at) SELECT sum(amount_usd) AS umsatz_usd FROM web "
                    "WHERE paid_at >= '2026-09-01' AND paid_at < '2026-10-01'"), "",
                  "**Warum verschieden:** Die naive Summe zählt die drei zweiten Abbuchungen als Umsatz ("
                  + " + ".join(f"{b:.2f}".replace(".", ",") for b in doppelt) + f" = {sum(doppelt):.2f}".replace(".", ",")
                  + " USD), obwohl sie nur versehentlich eingezogen wurden. Dass eine davon schon erstattet ist, spielt "
                  "hier keine Rolle: Gefragt ist der Umsatz vor Erstattungen.", ""]

        # F03
        aug_gesamt, aug_ende_aug, juli = c.execute("""
            SELECT count(DISTINCT s.customer_id) FILTER (WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'),
                   count(DISTINCT s.customer_id) FILTER (WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'
                                                         AND s.ends_at < '2026-09-01'),
                   count(DISTINCT s.customer_id) FILTER (WHERE k.cancelled_at < '2026-08-01' AND s.ends_at >= '2026-08-01'
                                                         AND s.ends_at < '2026-09-01')
            FROM cancellations k JOIN subscriptions s USING (subscription_id)""").fetchone()
        teile += ["### F03 · Kündigung: „Wie viele Kunden haben im August 2026 gekündigt?“", "",
                  "**Entscheidende Zeilen:** Kündigung (`cancellations.cancelled_at`) und Abo-Ende (`subscriptions.ends_at`) "
                  "sind verschiedene Tage. Wer im August kündigt, hat bis zum Ende der bezahlten Periode Zugang.", "",
                  "Wann enden die Abos, die im August gekündigt wurden?", "",
                  q("""SELECT to_char(s.ends_at, 'YYYY-MM') AS abo_endet_im, count(*) AS abos
FROM cancellations k JOIN subscriptions s USING (subscription_id)
WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'
GROUP BY 1 ORDER BY 1"""), "",
                  "Und umgekehrt: Wann wurden die Abos gekündigt, die im August enden?", "",
                  q("""SELECT to_char(k.cancelled_at, 'YYYY-MM') AS gekuendigt_im, count(*) AS abos
FROM subscriptions s JOIN cancellations k USING (subscription_id)
WHERE s.ends_at >= '2026-08-01' AND s.ends_at < '2026-09-01'
GROUP BY 1 ORDER BY 1"""), "",
                  "Drei Beispiele: gekündigt im August, Ende im September.", "",
                  q("""SELECT s.customer_id, k.cancelled_at, s.ends_at, s.plan, k.reason
FROM cancellations k JOIN subscriptions s USING (subscription_id)
WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'
  AND s.ends_at >= '2026-09-01' AND s.ends_at < '2026-10-01'
ORDER BY k.cancelled_at LIMIT 3"""), "",
                  "**Naiv:**", "", sql_block("""
-- Abos, die im August geendet haben
SELECT count(DISTINCT customer_id) AS kunden
FROM subscriptions
WHERE ends_at >= '2026-08-01' AND ends_at < '2026-09-01'"""), "",
                  q("SELECT count(DISTINCT customer_id) AS kunden FROM subscriptions WHERE ends_at >= '2026-08-01' AND ends_at < '2026-09-01'"), "",
                  "**Richtig:**", "", sql_block("""
-- Kündigungserklärungen im August, je Kunde einmal
SELECT count(DISTINCT s.customer_id) AS kunden
FROM cancellations k
JOIN subscriptions s USING (subscription_id)   -- Kunde steht am Abo
WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'"""), "",
                  q("SELECT count(DISTINCT s.customer_id) AS kunden FROM cancellations k JOIN subscriptions s USING (subscription_id) "
                    "WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'"), "",
                  f"**Warum verschieden:** Die naive Abfrage sieht nur Kunden, deren Abo im August schon ausgelaufen ist: "
                  f"{aug_ende_aug} Augustkündiger mit kurzer Restlaufzeit und {juli} Juli-Kündiger. Die übrigen "
                  f"{aug_gesamt - aug_ende_aug} Augustkündiger haben noch bis September oder länger Zugang (Monatsabo bis zum "
                  "nächsten Abrechnungstag, Jahresabo bis zum Jahrestag) und fehlen deshalb.", ""]

        # F04
        teile += ["### F04 · Zeitzone: „Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt?“", "",
                  "**Entscheidende Zeilen:** Derselbe Login hat in UTC eine andere Stunde als beim Kunden. Drei Morgen-Logins "
                  "(Ortszeit) aus verschiedenen Zeitzonen:", "",
                  q("""SELECT DISTINCT ON (c.timezone) l.login_id, c.timezone,
       l.logged_in_at AS utc,
       l.logged_in_at AT TIME ZONE c.timezone AS ortszeit
FROM logins l JOIN customers c USING (customer_id)
WHERE c.timezone IN ('Europe/Berlin', 'America/Los_Angeles', 'Asia/Tokyo')
  AND extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) = 7
ORDER BY c.timezone, l.login_id"""), "",
                  "**Naiv:**", "", sql_block("""
-- Stunde des gespeicherten Zeitstempels (UTC)
SELECT count(*) AS logins
FROM logins
WHERE extract(hour FROM logged_in_at AT TIME ZONE 'UTC') BETWEEN 6 AND 8   -- 06:00 bis 08:59"""), "",
                  q("SELECT count(*) AS logins FROM logins WHERE extract(hour FROM logged_in_at AT TIME ZONE 'UTC') BETWEEN 6 AND 8"), "",
                  "**Richtig:**", "", sql_block("""
-- Stunde in der Zeitzone des jeweiligen Kunden
SELECT count(*) AS logins
FROM logins l
JOIN customers c USING (customer_id)          -- Zeitzone steht am Kunden
WHERE extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) BETWEEN 6 AND 8"""), "",
                  q("SELECT count(*) AS logins FROM logins l JOIN customers c USING (customer_id) "
                    "WHERE extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) BETWEEN 6 AND 8"), "",
                  "**Warum verschieden:** Ein Berliner Frühaufsteher um 7 Uhr steht in UTC bei 5 oder 6 Uhr, ein Kunde in "
                  "Los Angeles um 7 Uhr bei 14 oder 15 Uhr UTC. Die UTC-Stunde trifft die Morgenspitze nur für einen Teil der Kunden.", ""]

        # U01
        teile += ["### U01 · Unbeantwortbar: „Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“", "",
                  "**Entscheidende Zeilen:** keine. Keine Tabelle speichert, woher ein Kunde kam (Anzeige, Kampagne, "
                  "Empfehlung). Alle Spalten mit „channel“ oder Ähnlichem:", "",
                  q("""SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (column_name ILIKE '%channel%' OR column_name ILIKE '%source%'
       OR column_name ILIKE '%campaign%' OR column_name ILIKE '%platform%' OR column_name ILIKE '%store%')
ORDER BY 1, 2"""), "",
                  "**Vermutliche Ersatz-Abfrage eines Modells** (falsch):", "", sql_block("""
-- nimmt den Kaufkanal des Abos als „Marketingkanal“
SELECT s.channel, count(DISTINCT c.customer_id) AS neukunden
FROM customers c
JOIN subscriptions s USING (customer_id)
WHERE c.signup_at >= '2026-03-01' AND c.signup_at < '2026-04-01'
GROUP BY s.channel
ORDER BY neukunden DESC"""), "",
                  q("""SELECT s.channel, count(DISTINCT c.customer_id) AS neukunden FROM customers c
JOIN subscriptions s USING (customer_id) WHERE c.signup_at >= '2026-03-01' AND c.signup_at < '2026-04-01'
GROUP BY s.channel ORDER BY neukunden DESC"""), "",
                  "Die Antwort wäre dann „web“. Sie klingt plausibel, sagt aber nur, wo bezahlt wurde. Außerdem fehlen alle "
                  "Neukunden ohne Abo:", "",
                  q("SELECT count(*) AS neukunden_maerz, count(*) FILTER (WHERE EXISTS (SELECT 1 FROM subscriptions s "
                    "WHERE s.customer_id = c.customer_id)) AS davon_mit_abo FROM customers c "
                    "WHERE signup_at >= '2026-03-01' AND signup_at < '2026-04-01'"), "",
                  "**Richtig:** keine Abfrage, sondern: „Dazu gibt es keine Daten. Die Herkunft der Kunden wird nicht erfasst.“ "
                  "Eine Rückfrage zählt ebenfalls als richtig.", "",
                  "**Warum:** `subscriptions.channel` ist der Kaufkanal (Web, Apple, Google), nicht der Marketingkanal. "
                  "Wer ihn als Ersatz nimmt, beantwortet eine andere Frage.", ""]

    ziel = WURZEL / "docs" / "DATENRUNDGANG.md"
    ziel.write_text("\n".join(teile), encoding="utf-8")
    print(ziel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
