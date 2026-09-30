"""Prüft die Annahmen einer Antwortkarte gegen das SQL, für die bekannten Glossar-Regeln (docs/ANTWORTEN.md).

Jede Regel hat zwei Teile: Woran erkennt man, dass eine Annahme die Regel behauptet (Stichworte im Text)? Und woran
erkennt man im SQL, dass sie umgesetzt ist (feste Muster)? Ergebnis je Annahme: "ok" (✓ verified in SQL), "warn"
(⚠ not found in SQL) oder None (keine bekannte Regel, kein Badge). Die Muster sind absichtlich eng: Lieber ein ⚠ zu viel
als ein ✓ über falschem SQL. Ein ✓ heißt nur, dass das Muster im SQL steht, nicht, dass die Zahl stimmt.
"""

import re
from datetime import date, timedelta

MONATE = {m: i for i, m in enumerate(["januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
                                       "september", "oktober", "november", "dezember"], 1)}
DATUM = re.compile(r"(\d{1,2})\.\s*(?:(\d{1,2})\.(\d{4})?|(" + "|".join(MONATE) + r")(?:\s+(\d{4}))?)", re.I)
BEREICH = re.compile(DATUM.pattern + r".{0,25}?(?:\sbis\s|\s?[–—]\s?|\s-\s)\s*" + DATUM.pattern, re.I)


def _sql_ohne_literale(sql: str) -> str:
    """SQL ohne Kommentare und String-Literale, damit etwa das „-“ in '2026-05-01' nicht als Minus zählt."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql).lower()


def _datum(tag, monat_zahl, jahr, monat_name, jahr2, jahr_ersatz) -> date | None:
    monat = int(monat_zahl) if monat_zahl else MONATE.get((monat_name or "").lower())
    j = jahr or jahr2 or jahr_ersatz
    try:
        return date(int(j), monat, int(tag)) if monat and j else None
    except ValueError:
        return None


# ---------- Regeln: (Name, behauptet?, geprüft im SQL?, Begründung bei ⚠) ----------

def _doppelabbuchung(text: str, sql: str, roh: str) -> tuple[bool, bool, str] | None:
    if not (re.search(r"rechnung|invoice", text) and re.search(r"einmal|erste|doppel|maximal", text)):
        return None
    muster = [r"distinct\s+on\s*\(\s*(\w+\.)?invoice_id",
              r"row_number\s*\(\s*\)\s*over\s*\(\s*partition\s+by\s+(\w+\.)?invoice_id\s+order\s+by\s+(\w+\.)?paid_at",
              r"min\s*\(\s*(\w+\.)?paid_at\s*\)[\s\S]*group\s+by\s+(\w+\.)?invoice_id"]
    ok = any(re.search(m, sql) for m in muster)
    if ok and "row_number" in sql and not re.search(r"=\s*1\b", sql):
        ok = False
    # NOT EXISTS (frühere erfolgreiche Zahlung zur selben Rechnung): alle drei Bedingungen müssen im Block stehen
    for block in re.findall(r"not\s+exists\s*\(([^()]*)\)", roh.lower()):
        if (re.search(r"invoice_id\s*=\s*\w+\.invoice_id", block) and re.search(r"paid_at\s*<\s*\w+\.paid_at", block)
                and "status = 'succeeded'" in re.sub(r"\s+", " ", block)):
            ok = True
    return ok, True, "one payment per invoice: no DISTINCT ON / ROW_NUMBER … = 1 / MIN(paid_at) per invoice_id in the SQL"


def _store(text: str, sql: str, roh: str):
    if not re.search(r"proceeds|auszahlung", text):
        return None
    return "proceeds_usd" in sql, True, "store revenue as payout: proceeds_usd not in the SQL"


def _erstattungen(text: str, sql: str, roh: str):
    if not re.search(r"erstatt|refund", text):
        return None
    tabelle = bool(re.search(r"\b(from|join)\s+refunds\b", sql))
    if re.search(r"nicht abgezogen|keine abzüge|ohne abzug|vor erstattung", text):
        return not tabelle, True, "refunds should not be deducted, but the SQL uses the refunds table"
    if re.search(r"außer|ausgenommen|ohne grund|!=|<>|not in", text) and "duplicate_charge" in text:
        ok = bool(re.search(r"(!=|<>|not\s+in\s*\()\s*'duplicate_charge'", roh.lower()))
        return ok, True, "refunds without duplicate_charge: no reason <> 'duplicate_charge' in the SQL"
    if re.search(r"−|-\s*erstatt|minus|abgezogen|abzüglich|mindern|abzug", text):
        ok = tabelle and bool(re.search(r"-\s*(\(|coalesce|sum|\w)", sql))
        return ok, True, "refunds deducted: no subtraction of refunds in the SQL"
    return None


def _zeitzone(text: str, sql: str, roh: str):
    if not re.search(r"ortszeit|kunden-?t?zeitzone|kundenzone|zeitzone des kunden|customers\.timezone", text):
        return None
    ok = bool(re.search(r"at\s+time\s+zone\s+(\w+\.)?timezone", sql))
    return ok, True, "customer's local time: no AT TIME ZONE <customer timezone> in the SQL"


def _kuendigung(text: str, sql: str, roh: str):
    if re.search(r"kündigung\w*\s*(=|ist)|kündigungserklärung|kündigungszeitpunkt|cancelled_at|kündigung und abo-ende", text):
        return "cancelled_at" in sql, True, "cancellation = cancelled_at: not in the SQL"
    if re.search(r"abo-ende|ends_at", text):
        return "ends_at" in sql, True, "end of subscription = ends_at: not in the SQL"
    return None


def _zeitraum(text: str, sql: str, roh: str):
    """„01.08.2026 bis 31.08.2026“: Anfang muss im SQL stehen, Ende als Tag selbst oder Folgetag (exklusive Grenze).
    Nur wenn das SQL überhaupt Datumswerte enthält; ohne Datumsfilter (ganzer Datenzeitraum) kein Badge."""
    m = BEREICH.search(text)
    literale = set(re.findall(r"'(\d{4}-\d{2}-\d{2})", roh))
    if not m or not literale:
        return None
    jahr = (re.findall(r"\d{4}", text) or [None])[0]
    g = m.groups()
    start, ende = _datum(*g[:5], jahr), _datum(*g[5:], jahr)
    if not start or not ende:
        return None
    ok = start.isoformat() in literale and (ende.isoformat() in literale or (ende + timedelta(days=1)).isoformat() in literale)
    # DATE_TRUNC('month', …) = 'JJJJ-MM-01' deckt genau einen ganzen Monat ab
    ganzer_monat = start.day == 1 and (ende + timedelta(days=1)).day == 1 and (ende - start).days < 31
    if not ok and ganzer_monat and start.isoformat() in literale and re.search(r"date_trunc\s*\(\s*''\s*,", sql):
        ok = "'month'" in roh.lower().replace('"', "'")
    return ok, True, f"period {start:%d.%m.%Y}–{ende:%d.%m.%Y}: these dates are not the bounds in the SQL"


REGELN = [_doppelabbuchung, _store, _erstattungen, _zeitzone, _kuendigung, _zeitraum]


def pruefen(annahme: str, sql: str | None) -> tuple[str | None, str]:
    """(status, begründung): status "ok", "warn" oder None."""
    if not sql:
        return None, ""
    text, bereinigt = annahme.lower(), _sql_ohne_literale(sql)
    ergebnisse = [r for regel in REGELN if (r := regel(text, bereinigt, sql)) is not None]
    if not ergebnisse:
        return None, ""
    fehlend = [grund for ok, _, grund in ergebnisse if not ok]
    return ("warn", "; ".join(fehlend)) if fehlend else ("ok", "")
