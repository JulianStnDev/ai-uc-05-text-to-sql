"""Code-Prüfung der Annahmen (app/annahmen.py) an echten Karten aus dem Regressionstest (d1) und an kleinen Beispielen.
Die vier Fehlkarten aus docs/ANTWORTEN.md müssen ⚠ zeigen, E05 W1 (richtige Zahl durch Glück) ebenso."""

import json
from pathlib import Path

import pytest

from app.annahmen import pruefen

LAUF = Path(__file__).resolve().parents[1] / "evals" / "laeufe" / "20260930-180934_haiku_glossar_karte.jsonl"
KARTEN = {(z["frage_id"], z["wiederholung"]): z["antwort"] for z in map(json.loads, LAUF.read_text(encoding="utf-8").splitlines())}


def badges(frage, wdh):
    a = KARTEN[(frage, wdh)]
    return {x: pruefen(x, a["sql"])[0] for x in a["karte"]["annahmen"]}


@pytest.mark.parametrize("frage, wdh, stichwort", [
    ("F01", 1, "invoice_id"),        # NOT IN schließt nie etwas aus
    ("F01", 3, "Rechnung"),          # schließt auch nach fehlgeschlagenen Versuchen aus
    ("F02", 2, "Invoice"),           # entfernt Rechnungen mit Doppelabbuchung ganz
    ("M06", 1, "01. September"),     # SQL beginnt am 31.08.
    ("E05", 1, "je Rechnung"),       # summiert alle Zahlungen je Rechnung, Zahl nur durch Glück richtig
])
def test_fehlkarten_zeigen_warnung(frage, wdh, stichwort):
    b = badges(frage, wdh)
    treffer = [s for x, s in b.items() if stichwort in x]
    assert treffer == ["warn"], b


def test_richtige_karten_zeigen_haken():
    assert set(badges("E05", 3).values()) == {"ok"}                       # Umsatz: alle vier Regeln umgesetzt
    assert "warn" not in badges("F04", 1).values() and "ok" in badges("F04", 1).values()   # Zeitzone
    b = badges("F03", 3)
    assert b["Kündigungszeitpunkt ist cancellations.cancelled_at"] == "ok"
    assert b["Kündigung und Abo-Ende sind verschiedene Ereignisse"] == "ok"
    assert badges("F01", 2)["Von jeder Rechnung wird nur die erste erfolgreiche Zahlung gezählt (Doppelabbuchungen ausgeschlossen)"] == "ok"


def test_ohne_bekannte_regel_kein_badge():
    assert pruefen("Kunden werden nicht doppelt gezählt", "SELECT count(DISTINCT customer_id) FROM customers") == (None, "")
    assert pruefen("Umsatz = Web + Store − Erstattungen", None) == (None, "")


def test_minus_in_datum_ist_kein_abzug():
    sql = "SELECT sum(amount_usd) FROM payments p JOIN refunds r USING (payment_id) WHERE paid_at >= '2026-05-01'"
    assert pruefen("Umsatz = Web − Erstattungen", sql)[0] == "warn"
    assert pruefen("Umsatz = Web − Erstattungen", sql.replace("SELECT sum(amount_usd)", "SELECT sum(p.amount_usd) - sum(r.amount_usd)"))[0] == "ok"


def test_alias_mit_refunds_ist_keine_tabelle():
    sql = "SELECT sum(amount_usd) AS umsatz_before_refunds FROM payments"
    assert pruefen("Erstattungen werden nicht abgezogen", sql)[0] == "ok"


def test_zeitraum_nur_wenn_sql_datumswerte_hat():
    assert pruefen("Zeitraum 01.10.2025 bis 30.09.2026", "SELECT count(*) FROM logins") == (None, "")
    sql = "SELECT count(*) FROM logins WHERE logged_in_at >= '2026-08-01' AND logged_in_at < '2026-09-01'"
    assert pruefen("Zeitraum 01.08.2026 bis 31.08.2026", sql)[0] == "ok"
    assert pruefen("Zeitraum 01.08.2026 bis 30.08.2026", sql)[0] == "warn"   # Karte nennt ein anderes Ende


def test_zeitzone_und_store():
    assert pruefen("Morgens in der Ortszeit des Kunden", "SELECT … WHERE extract(hour FROM l.logged_in_at AT TIME ZONE c.timezone) >= 6")[0] == "ok"
    assert pruefen("Morgens in der Ortszeit des Kunden", "SELECT … WHERE extract(hour FROM logged_in_at AT TIME ZONE 'UTC') >= 6")[0] == "warn"
    assert pruefen("Store-Umsatz = Auszahlung (proceeds_usd)", "SELECT sum(customer_price_usd) FROM store_transactions")[0] == "warn"
