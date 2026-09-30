"""Goldset: 25 Business-Fragen auf Deutsch mit Referenz-SQL (Quelle zum Bearbeiten).

Die Ergebnisse berechnet scripts/goldset_berechnen.py als analyst_ro aus der Datenbank und schreibt sie nach
evals/goldset.json (+ evals/goldset.md zur Durchsicht). Hier stehen nur Fragen und SQL.

Typen: eindeutig (15) | mehrdeutig (5, richtige Antwort ist eine Rückfrage, dazu die Deutungen) | falle (5).
Fallen: doppelabbuchung, store, kuendigung, erstattung, zeitzone, irrefuehrende_spalte (docs/DATA_NOTES.md).
Bei Fallen-Fragen ist `naiv_sql` die Referenz-SQL mit genau dem einen Fehler der Falle.
Geschäftsdefinitionen: docs/GLOSSAR.md. Alle Grenzen in UTC (die Skripte setzen die Sitzung auf UTC).
"""

# Umsatz laut Glossar: Web je Rechnung einmal, Store-Auszahlung, minus Erstattungen ohne duplicate_charge.
WEB = """web AS (  -- je Rechnung nur die erste erfolgreiche Zahlung; weitere sind Doppelabbuchungen
    SELECT DISTINCT ON (invoice_id) paid_at AS zeit, amount_usd AS betrag
    FROM payments WHERE status = 'succeeded' ORDER BY invoice_id, paid_at)"""
ERSTATTET = """erstattet AS (
    SELECT refunded_at AS zeit, -amount_usd AS betrag FROM refunds WHERE reason <> 'duplicate_charge')"""
STORE = """store AS (SELECT purchased_at AS zeit, proceeds_usd AS betrag FROM store_transactions)"""
UMSATZ = f"""WITH {WEB},
{ERSTATTET},
{STORE},
umsatz AS (SELECT * FROM web UNION ALL SELECT * FROM erstattet UNION ALL SELECT * FROM store)"""

LAUFEND_AM_STICHTAG = "started_at < '2026-10-01' AND (ends_at IS NULL OR ends_at >= '2026-10-01')"

FRAGEN = [
    # ---------- eindeutig ----------
    {"id": "E01", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Kunden haben sich im März 2026 registriert?",
     "sql": "SELECT count(*) AS neukunden FROM customers WHERE signup_at >= '2026-03-01' AND signup_at < '2026-04-01'"},
    {"id": "E02", "typ": "eindeutig", "fallen": [],
     "frage": "In welchen fünf Ländern haben wir die meisten Kunden, und wie viele sind es jeweils?",
     "sql": "SELECT country, count(*) AS kunden FROM customers GROUP BY country ORDER BY kunden DESC, country LIMIT 5"},
    {"id": "E03", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Pro-Abos wurden im ersten Quartal 2026 abgeschlossen, aufgeteilt nach Kanal?",
     "sql": "SELECT channel, count(*) AS neue_abos FROM subscriptions "
            "WHERE started_at >= '2026-01-01' AND started_at < '2026-04-01' GROUP BY channel ORDER BY channel"},
    {"id": "E04", "typ": "eindeutig", "fallen": ["irrefuehrende_spalte"],
     "frage": "Wie viele Kunden hatten am 30. September 2026 ein laufendes Jahresabo?",
     "sql": f"SELECT count(DISTINCT customer_id) AS kunden FROM subscriptions WHERE plan = 'pro_annual' AND {LAUFEND_AM_STICHTAG}"},
    {"id": "E05", "typ": "eindeutig", "fallen": ["doppelabbuchung", "store", "erstattung"],
     "frage": "Wie hoch war der Umsatz im Mai 2026?",
     "sql": f"{UMSATZ}\nSELECT sum(betrag) AS umsatz_usd FROM umsatz WHERE zeit >= '2026-05-01' AND zeit < '2026-06-01'"},
    {"id": "E06", "typ": "eindeutig", "fallen": ["doppelabbuchung", "erstattung"],
     "frage": "Wie viel Geld haben wir im Gesamtzeitraum an Kunden erstattet, ohne die Erstattungen von Doppelabbuchungen?",
     "sql": "SELECT count(*) AS erstattungen, sum(amount_usd) AS summe_usd FROM refunds WHERE reason <> 'duplicate_charge'"},
    {"id": "E07", "typ": "eindeutig", "fallen": [],
     "frage": "Welcher Kündigungsgrund wurde am häufigsten angegeben, und wie oft?",
     "sql": "SELECT reason, count(*) AS anzahl FROM cancellations GROUP BY reason ORDER BY anzahl DESC, reason LIMIT 1"},
    {"id": "E08", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Kunden haben sich im Juli 2026 mindestens einmal eingeloggt?",
     "sql": "SELECT count(DISTINCT customer_id) AS kunden FROM logins "
            "WHERE logged_in_at >= '2026-07-01' AND logged_in_at < '2026-08-01'"},
    {"id": "E09", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele aktive Kunden hatten wir am 30. September 2026?",
     "sql": "SELECT count(DISTINCT customer_id) AS aktive_kunden FROM logins "
            "WHERE logged_in_at >= '2026-09-01' AND logged_in_at < '2026-10-01'"},
    {"id": "E10", "typ": "eindeutig", "fallen": [],
     "frage": "Über welche Plattform kamen im August 2026 die meisten Logins, und wie viele waren es?",
     "sql": "SELECT platform, count(*) AS logins FROM logins WHERE logged_in_at >= '2026-08-01' AND logged_in_at < '2026-09-01' "
            "GROUP BY platform ORDER BY logins DESC LIMIT 1"},
    {"id": "E11", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Web-Zahlungen sind im Gesamtzeitraum fehlgeschlagen?",
     "sql": "SELECT count(*) AS fehlgeschlagen FROM payments WHERE status = 'failed'"},
    {"id": "E12", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Tage vergehen im Median zwischen Registrierung und erstem Pro-Abo?",
     "sql": "WITH erstes AS (SELECT customer_id, min(started_at) AS beginn FROM subscriptions GROUP BY customer_id)\n"
            "SELECT round((percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM e.beginn - c.signup_at) / 86400))::numeric, 1) "
            "AS median_tage FROM erstes e JOIN customers c USING (customer_id)"},
    {"id": "E13", "typ": "eindeutig", "fallen": [],
     "frage": "Wie viele Kunden haben mehr als ein Abo abgeschlossen?",
     "sql": "SELECT count(*) AS kunden FROM (SELECT customer_id FROM subscriptions GROUP BY customer_id HAVING count(*) > 1) x"},
    {"id": "E14", "typ": "eindeutig", "fallen": ["kuendigung"],
     "frage": "Wie viele Abos endeten im September 2026?",
     "sql": "SELECT count(*) AS beendete_abos FROM subscriptions WHERE ends_at >= '2026-09-01' AND ends_at < '2026-10-01'"},
    {"id": "E15", "typ": "eindeutig", "fallen": ["store"],
     "frage": "Wie hoch war der Umsatz aus Käufen im Apple App Store im zweiten Quartal 2026?",
     "sql": "SELECT sum(proceeds_usd) AS umsatz_usd FROM store_transactions "
            "WHERE store = 'apple' AND purchased_at >= '2026-04-01' AND purchased_at < '2026-07-01'"},

    # ---------- mehrdeutig: richtige Antwort ist eine Rückfrage ----------
    {"id": "M01", "typ": "mehrdeutig", "fallen": ["kuendigung"],
     "frage": "Wie viele Kunden haben wir im Sommer verloren?",
     "rueckfrage": "Was heißt „verloren“: gekündigt, Abo beendet oder nicht mehr genutzt? Und ist mit Sommer Juni bis August gemeint?",
     "deutungen": [
         {"deutung": "Kunden mit Kündigung (cancelled_at) von Juni bis August 2026",
          "sql": "SELECT count(DISTINCT s.customer_id) AS kunden FROM cancellations k JOIN subscriptions s USING (subscription_id) "
                 "WHERE k.cancelled_at >= '2026-06-01' AND k.cancelled_at < '2026-09-01'"},
         {"deutung": "Kunden, deren Abo von Juni bis August 2026 endete und die am 31.08. kein laufendes Abo hatten",
          "sql": "SELECT count(DISTINCT customer_id) AS kunden FROM subscriptions s WHERE ends_at >= '2026-06-01' AND ends_at < '2026-09-01' "
                 "AND NOT EXISTS (SELECT 1 FROM subscriptions t WHERE t.customer_id = s.customer_id "
                 "AND t.started_at < '2026-09-01' AND (t.ends_at IS NULL OR t.ends_at >= '2026-09-01'))"},
         {"deutung": "Kunden mit Login im Mai 2026, aber keinem Login von Juni bis August",
          "sql": "SELECT count(DISTINCT customer_id) AS kunden FROM logins l WHERE logged_in_at >= '2026-05-01' AND logged_in_at < '2026-06-01' "
                 "AND NOT EXISTS (SELECT 1 FROM logins m WHERE m.customer_id = l.customer_id "
                 "AND m.logged_in_at >= '2026-06-01' AND m.logged_in_at < '2026-09-01')"},
     ]},
    {"id": "M02", "typ": "mehrdeutig", "fallen": ["doppelabbuchung", "store", "erstattung"],
     "frage": "Wie hat sich der Umsatz im letzten Quartal entwickelt?",
     "rueckfrage": "Welches Quartal ist gemeint (Q3 2026, das am 30.09. endet, oder das letzte vor heute voll abgeschlossene Q2), "
                   "und im Vergleich wozu: zum Vorquartal absolut oder in Prozent?",
     "deutungen": [
         {"deutung": "Q3 2026 gegenüber Q2 2026",
          "sql": f"{UMSATZ},\nq AS (SELECT sum(betrag) FILTER (WHERE zeit >= '2026-04-01' AND zeit < '2026-07-01') AS q2,\n"
                 "              sum(betrag) FILTER (WHERE zeit >= '2026-07-01' AND zeit < '2026-10-01') AS q3 FROM umsatz)\n"
                 "SELECT q2, q3, q3 - q2 AS differenz, round(100 * (q3 - q2) / q2, 1) AS prozent FROM q"},
         {"deutung": "Q2 2026 gegenüber Q1 2026",
          "sql": f"{UMSATZ},\nq AS (SELECT sum(betrag) FILTER (WHERE zeit >= '2026-01-01' AND zeit < '2026-04-01') AS q1,\n"
                 "              sum(betrag) FILTER (WHERE zeit >= '2026-04-01' AND zeit < '2026-07-01') AS q2 FROM umsatz)\n"
                 "SELECT q1, q2, q2 - q1 AS differenz, round(100 * (q2 - q1) / q1, 1) AS prozent FROM q"},
     ]},
    {"id": "M03", "typ": "mehrdeutig", "fallen": ["store"],
     "frage": "Welcher Kanal ist am besten?",
     "rueckfrage": "Woran gemessen: am Umsatz, an der Zahl neuer Abos oder daran, wie selten gekündigt wird?",
     "deutungen": [
         {"deutung": "Umsatz je Kanal im Gesamtzeitraum",
          "sql": f"WITH {WEB},\n{ERSTATTET}\n"
                 "SELECT 'web' AS kanal, (SELECT sum(betrag) FROM web) + (SELECT sum(betrag) FROM erstattet) AS umsatz_usd\n"
                 "UNION ALL SELECT store, sum(proceeds_usd) FROM store_transactions GROUP BY store ORDER BY umsatz_usd DESC"},
         {"deutung": "Neue Abos je Kanal im Gesamtzeitraum",
          "sql": "SELECT channel AS kanal, count(*) AS abos FROM subscriptions GROUP BY channel ORDER BY abos DESC"},
         {"deutung": "Anteil gekündigter Abos je Kanal (niedrig ist gut)",
          "sql": "SELECT s.channel AS kanal, round(100.0 * count(k.cancellation_id) / count(*), 1) AS kuendigungsanteil_prozent "
                 "FROM subscriptions s LEFT JOIN cancellations k USING (subscription_id) GROUP BY s.channel ORDER BY 2"},
     ]},
    {"id": "M04", "typ": "mehrdeutig", "fallen": ["kuendigung"],
     "frage": "Wie hoch ist unsere Kündigungsquote?",
     "rueckfrage": "Für welchen Zeitraum und auf welcher Basis: Anteil aller Abos, monatlich (z. B. August 2026) oder je Kunde?",
     "deutungen": [
         {"deutung": "Anteil gekündigter Abos an allen Abos im Gesamtzeitraum",
          "sql": "SELECT round(100.0 * (SELECT count(*) FROM cancellations) / (SELECT count(*) FROM subscriptions), 1) AS prozent"},
         {"deutung": "Monatlich, August 2026: Kündigungen im August / am 01.08. laufende Abos",
          "sql": "SELECT round(100.0 * (SELECT count(*) FROM cancellations WHERE cancelled_at >= '2026-08-01' AND cancelled_at < '2026-09-01')\n"
                 "  / (SELECT count(*) FROM subscriptions WHERE started_at < '2026-08-01' AND (ends_at IS NULL OR ends_at >= '2026-08-01')), 1) AS prozent"},
         {"deutung": "Je Kunde: Kunden mit mindestens einer Kündigung / Kunden mit mindestens einem Abo",
          "sql": "SELECT round(100.0 * count(DISTINCT s.customer_id) FILTER (WHERE k.cancellation_id IS NOT NULL) "
                 "/ count(DISTINCT s.customer_id), 1) AS prozent FROM subscriptions s LEFT JOIN cancellations k USING (subscription_id)"},
     ]},
    {"id": "M05", "typ": "mehrdeutig", "fallen": [],
     "frage": "Wie viele Kunden nutzen FocusFlow regelmäßig?",
     "rueckfrage": "Was heißt regelmäßig und in welchem Zeitraum: an mindestens 10 Tagen im Monat, jede Woche, oder aktiv laut Definition "
                   "(Login in den letzten 30 Tagen)?",
     "deutungen": [
         {"deutung": "Login an mindestens 10 verschiedenen Tagen im September 2026",
          "sql": "SELECT count(*) AS kunden FROM (SELECT customer_id FROM logins WHERE logged_in_at >= '2026-09-01' AND logged_in_at < '2026-10-01' "
                 "GROUP BY customer_id HAVING count(DISTINCT logged_in_at::date) >= 10) x"},
         {"deutung": "Login in jeder der vier Wochen 01.–28.09.2026",
          "sql": "SELECT count(*) AS kunden FROM (SELECT customer_id FROM logins WHERE logged_in_at >= '2026-09-01' AND logged_in_at < '2026-09-29' "
                 "GROUP BY customer_id HAVING count(DISTINCT (extract(day FROM logged_in_at)::int - 1) / 7) = 4) x"},
         {"deutung": "Aktive Kunden laut Glossar (Login in den 30 Tagen bis 30.09.2026)",
          "sql": "SELECT count(DISTINCT customer_id) AS kunden FROM logins WHERE logged_in_at >= '2026-09-01' AND logged_in_at < '2026-10-01'"},
     ]},

    # ---------- Fallen: naive_sql = Referenz mit genau dem einen Fehler ----------
    {"id": "F01", "typ": "falle", "fallen": ["doppelabbuchung"],
     "frage": "Wie hoch war der Web-Umsatz im September 2026 vor Erstattungen?",
     "sql": f"WITH {WEB}\nSELECT sum(betrag) AS umsatz_usd FROM web WHERE zeit >= '2026-09-01' AND zeit < '2026-10-01'",
     "naiv_sql": "SELECT sum(amount_usd) AS umsatz_usd FROM payments WHERE status = 'succeeded' "
                 "AND paid_at >= '2026-09-01' AND paid_at < '2026-10-01'",
     "naiv_fehler": "zählt Doppelabbuchungen (zweite Zahlung zur selben Rechnung) als Umsatz"},
    {"id": "F02", "typ": "falle", "fallen": ["store"],
     "frage": "Wie hoch war der Umsatz im zweiten Quartal 2026 insgesamt?",
     "sql": f"{UMSATZ}\nSELECT sum(betrag) AS umsatz_usd FROM umsatz WHERE zeit >= '2026-04-01' AND zeit < '2026-07-01'",
     "naiv_sql": f"WITH {WEB},\n{ERSTATTET},\numsatz AS (SELECT * FROM web UNION ALL SELECT * FROM erstattet)\n"
                 "SELECT sum(betrag) AS umsatz_usd FROM umsatz WHERE zeit >= '2026-04-01' AND zeit < '2026-07-01'",
     "naiv_fehler": "rechnet nur payments; Apple- und Google-Käufe stehen in store_transactions"},
    {"id": "F03", "typ": "falle", "fallen": ["kuendigung"],
     "frage": "Wie viele Kunden haben im August 2026 gekündigt?",
     "sql": "SELECT count(DISTINCT s.customer_id) AS kunden FROM cancellations k JOIN subscriptions s USING (subscription_id) "
            "WHERE k.cancelled_at >= '2026-08-01' AND k.cancelled_at < '2026-09-01'",
     "naiv_sql": "SELECT count(DISTINCT customer_id) AS kunden FROM subscriptions WHERE ends_at >= '2026-08-01' AND ends_at < '2026-09-01'",
     "naiv_fehler": "nimmt das Abo-Ende statt der Kündigungserklärung; Kündigungen im August enden meist im September"},
    {"id": "F04", "typ": "falle", "fallen": ["zeitzone"],
     "frage": "Wie viele Logins fanden im Gesamtzeitraum morgens zwischen 6 und 9 Uhr statt?",
     "sql": "SELECT count(*) AS logins FROM logins l JOIN customers c USING (customer_id) "
            "WHERE extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) BETWEEN 6 AND 8",
     "naiv_sql": "SELECT count(*) AS logins FROM logins WHERE extract(hour FROM logged_in_at AT TIME ZONE 'UTC') BETWEEN 6 AND 8",
     "naiv_fehler": "nimmt die UTC-Stunde statt der Ortszeit des Kunden"},
    {"id": "F05", "typ": "falle", "fallen": ["irrefuehrende_spalte"],
     "frage": "Wie viele Kunden hatten am 30. September 2026 ein laufendes Pro-Abo?",
     "sql": f"SELECT count(DISTINCT customer_id) AS kunden FROM subscriptions WHERE {LAUFEND_AM_STICHTAG}",
     "naiv_sql": "SELECT count(*) AS kunden FROM customers WHERE is_premium",
     "naiv_fehler": "is_premium heißt „hatte je Pro“ und wird nach Kündigung nicht zurückgesetzt"},
]

# Beleg für jede der sechs Fallen (auch erstattung, die im Goldset nur in E05/E06/M02 vorkommt): richtig vs. naiv.
FALLEN_BELEGE = [
    {"falle": "doppelabbuchung", "frage": "F01", "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "F01"),
     "naiv_sql": next(f["naiv_sql"] for f in FRAGEN if f["id"] == "F01")},
    {"falle": "store", "frage": "F02", "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "F02"),
     "naiv_sql": next(f["naiv_sql"] for f in FRAGEN if f["id"] == "F02")},
    {"falle": "kuendigung", "frage": "F03", "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "F03"),
     "naiv_sql": next(f["naiv_sql"] for f in FRAGEN if f["id"] == "F03")},
    {"falle": "erstattung", "frage": "E05",
     "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "E05"),
     "naiv_sql": f"WITH {WEB},\n{STORE},\numsatz AS (SELECT * FROM web UNION ALL SELECT * FROM store)\n"
                 "SELECT sum(betrag) AS umsatz_usd FROM umsatz WHERE zeit >= '2026-05-01' AND zeit < '2026-06-01'"},
    {"falle": "zeitzone", "frage": "F04", "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "F04"),
     "naiv_sql": next(f["naiv_sql"] for f in FRAGEN if f["id"] == "F04")},
    {"falle": "irrefuehrende_spalte", "frage": "F05", "richtig_sql": next(f["sql"] for f in FRAGEN if f["id"] == "F05"),
     "naiv_sql": next(f["naiv_sql"] for f in FRAGEN if f["id"] == "F05")},
]
