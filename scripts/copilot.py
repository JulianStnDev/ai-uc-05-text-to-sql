"""Der Analytics-Copilot: beantwortet eine Frage mit SQL gegen die Analyse-Datenbank (als analyst_ro).

Zwei Werkzeuge:
- sql_ausfuehren: führt eine Abfrage aus (höchstens MAX_SQL je Frage) und gibt höchstens ZEILEN_LIMIT Zeilen zurück.
- antworten:      beendet die Frage mit art "ergebnis" (+ SQL), "rueckfrage" oder "keine_daten".
Bei art "ergebnis" führt der Harness die angegebene SQL selbst noch einmal aus. Deren Ergebnis wird bewertet,
nicht der Antworttext (scripts/vergleich.py).

Variante "schema" (Branch b): Das Modell sieht nur db/schema.sql. Variante "glossar" (Branch c): zusätzlich
docs/GLOSSAR.md. DATA_NOTES.md und DATENRUNDGANG.md gelangen nie in einen Prompt (tests/test_copilot.py).
"""

import json
import time
from decimal import Decimal
from pathlib import Path

import psycopg

WURZEL = Path(__file__).resolve().parents[1]

# Preise in USD je Million Tokens (Stand 2026-09-25). Cache: Schreiben 1,25 ×, Lesen 0,1 × Input.
MODELLE = {
    "haiku": {"id": "claude-haiku-4-5", "input": 1.00, "output": 5.00},
    "sonnet": {"id": "claude-sonnet-5-5", "input": 2.00, "output": 10.00, "effort": "medium"},
}
MAX_SQL = 5           # SQL-Ausführungen je Frage
MAX_AUFRUFE = 8       # Modellaufrufe je Frage (inkl. einer Erinnerung, falls kein Werkzeug benutzt wird)
ZEILEN_LIMIT = 50     # so viele Zeilen sieht das Modell je Abfrage
MAX_TOKENS = 8000

ANWEISUNG = """Du bist ein Analytics-Copilot für FocusFlow, eine Habit-Tracker-App mit Pro-Abos. Du beantwortest Business-Fragen,
indem du SQL gegen eine PostgreSQL-Datenbank schreibst und ausführst. Du hast nur Lesezugriff.

Heute ist der 30.09.2026. Die Datenbanksitzung läuft in UTC.

Vorgehen:
- Prüfe deine Abfragen mit dem Werkzeug sql_ausfuehren (höchstens 5 Ausführungen je Frage).
- Beende jede Frage mit dem Werkzeug antworten:
  - art "ergebnis": Die Frage ist beantwortbar. Gib die SQL an, deren Ergebnis die Antwort ist, und einen kurzen Antworttext.
  - art "rueckfrage": Die Frage ist mehrdeutig. Stelle eine kurze Rückfrage.
  - art "keine_daten": Die Datenbank enthält die nötigen Informationen nicht. Erkläre kurz, was fehlt."""

TOOLS = [
    {"name": "sql_ausfuehren",
     "description": "Führt eine SQL-Abfrage (PostgreSQL, nur lesend) aus und gibt Spalten und bis zu 50 Zeilen als JSON zurück.",
     "strict": True,
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string", "description": "Eine SELECT-Abfrage"}},
                      "required": ["sql"], "additionalProperties": False}},
    {"name": "antworten",
     "description": "Beendet die Frage. art: ergebnis (mit SQL), rueckfrage oder keine_daten.",
     "strict": True,
     "input_schema": {"type": "object",
                      "properties": {"art": {"type": "string", "enum": ["ergebnis", "rueckfrage", "keine_daten"]},
                                     "text": {"type": "string", "description": "Antwort, Rückfrage oder Erklärung für den Nutzer"},
                                     "sql": {"type": "string", "description": "Bei ergebnis: die SQL der Antwort, sonst leer"}},
                      "required": ["art", "text", "sql"], "additionalProperties": False}},
]


def system_prompt(variante: str) -> str:
    teile = [ANWEISUNG, "Schema der Datenbank:\n```sql\n" + (WURZEL / "db" / "schema.sql").read_text(encoding="utf-8").strip() + "\n```"]
    if variante == "glossar":
        teile.append("Geschäftsdefinitionen:\n" + (WURZEL / "docs" / "GLOSSAR.md").read_text(encoding="utf-8").strip())
    elif variante != "schema":
        raise ValueError(f"Unbekannte Variante: {variante!r}")
    return "\n\n".join(teile)


def verbinden(url: str) -> psycopg.Connection:
    c = psycopg.connect(url, autocommit=True)
    c.execute("SET TIME ZONE 'UTC'")
    return c


def wert(v):
    return str(v) if isinstance(v, Decimal) else (v.isoformat() if hasattr(v, "isoformat") else v)


def sql_ausfuehren(conn, sql: str) -> dict:
    """{"ok": True, "spalten", "zeilen", "anzahl"} oder {"ok": False, "fehler"}. Schreibversuche weist die DB ab."""
    try:
        cur = conn.execute(sql)
        if cur.description is None:
            return {"ok": False, "fehler": "Die Anweisung liefert keine Zeilen."}
        zeilen = [[wert(v) for v in z] for z in cur.fetchall()]
        return {"ok": True, "spalten": [d.name for d in cur.description], "zeilen": zeilen, "anzahl": len(zeilen)}
    except psycopg.Error as e:
        return {"ok": False, "fehler": f"{type(e).__name__}: {str(e).strip()[:500]}"}


def _block(b):
    """SDK-Objekte (Content Blocks) für den Mitschnitt in dicts verwandeln."""
    return b.model_dump(mode="json", exclude_none=True) if hasattr(b, "model_dump") else str(b)


def kosten_usd(modell: str, usage) -> float:
    p = MODELLE[modell]
    ein = (usage.input_tokens + 1.25 * (usage.cache_creation_input_tokens or 0) + 0.1 * (usage.cache_read_input_tokens or 0))
    return (ein * p["input"] + usage.output_tokens * p["output"]) / 1e6


def beantworten(client, conn, frage: str, modell: str, variante: str = "schema", *, zusatz: str | None = None,
                thinking_anzeigen: bool = False, mitschnitt: list | None = None) -> dict:
    """Ein Durchlauf für eine Frage. Gibt Antwort, Protokoll, Tokens, Kosten und Dauer zurück.

    Nur für Experimente (docs/ANATOMIE.md), in Messläufen nie gesetzt:
    zusatz: ein Satz, der an den System-Prompt angehängt wird.
    thinking_anzeigen: Sonnet liefert eine Zusammenfassung des Thinkings (display "summarized") statt eines leeren
        Blocks. Das Thinking selbst ändert sich dadurch nicht, nur seine Sichtbarkeit.
    mitschnitt: Liste, an die je Aufruf der rohe Request und die rohe Response als JSON-fähiges dict angehängt werden."""
    m = MODELLE[modell]
    system = system_prompt(variante) + (f"\n\n{zusatz}" if zusatz else "")
    params = {"model": m["id"], "max_tokens": MAX_TOKENS, "system": system, "tools": TOOLS,
              "cache_control": {"type": "ephemeral"}}
    if "effort" in m:
        params["output_config"] = {"effort": m["effort"]}
    if thinking_anzeigen and "effort" in m:
        params["thinking"] = {"type": "adaptive", "display": "summarized"}
    messages = [{"role": "user", "content": frage}]
    sql_protokoll, aufrufe, erinnert, antwort, fehler = [], [], False, None, None
    start = time.perf_counter()
    for _ in range(MAX_AUFRUFE):
        r = client.messages.create(**params, messages=messages)
        if mitschnitt is not None:
            mitschnitt.append({"request": json.loads(json.dumps({**params, "messages": messages}, default=_block)),
                               "response": r.model_dump(mode="json", exclude_none=True)})
        u = r.usage
        aufrufe.append({"input": u.input_tokens, "output": u.output_tokens,
                        "cache_schreiben": u.cache_creation_input_tokens or 0, "cache_lesen": u.cache_read_input_tokens or 0,
                        "kosten_usd": kosten_usd(modell, u), "stop": r.stop_reason})
        if r.stop_reason == "refusal":
            fehler = "refusal"
            break
        messages.append({"role": "assistant", "content": r.content})  # vollständig, inkl. Thinking-Blöcken
        werkzeuge = [b for b in r.content if b.type == "tool_use"]
        if not werkzeuge:
            if erinnert:
                fehler = "kein Werkzeug benutzt"
                break
            erinnert = True
            messages.append({"role": "user", "content": "Bitte beende die Frage mit dem Werkzeug antworten."})
            continue
        ergebnisse = []
        for b in werkzeuge:
            if b.name == "antworten":
                antwort = dict(b.input)
                ergebnisse.append({"type": "tool_result", "tool_use_id": b.id, "content": "ok"})
            elif len(sql_protokoll) >= MAX_SQL:
                ergebnisse.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                   "content": f"Limit von {MAX_SQL} Ausführungen erreicht. Bitte jetzt antworten."})
            else:
                e = sql_ausfuehren(conn, b.input["sql"])
                sql_protokoll.append({"sql": b.input["sql"], **{k: v for k, v in e.items() if k != "zeilen"}})
                inhalt = ({"spalten": e["spalten"], "zeilen": e["zeilen"][:ZEILEN_LIMIT], "anzahl_zeilen": e["anzahl"]}
                          if e["ok"] else e["fehler"])
                ergebnisse.append({"type": "tool_result", "tool_use_id": b.id, "is_error": not e["ok"],
                                   "content": json.dumps(inhalt, ensure_ascii=False, default=str)})
        if antwort:
            break
        messages.append({"role": "user", "content": ergebnisse})
    else:
        fehler = fehler or f"nach {MAX_AUFRUFE} Aufrufen keine Antwort"

    ergebnis = {"art": None, "text": None, "sql": None, "zeilen": None}
    if antwort:
        ergebnis.update(art=antwort["art"], text=antwort["text"], sql=antwort["sql"] or None)
        if antwort["art"] == "ergebnis":
            e = sql_ausfuehren(conn, antwort["sql"])  # bewertet wird das Ergebnis dieser SQL
            ergebnis["zeilen"] = e["zeilen"] if e["ok"] else None
            fehler = fehler or (None if e["ok"] else f"Antwort-SQL fehlerhaft: {e['fehler']}")
    return {"antwort": ergebnis, "sql_ausfuehrungen": sql_protokoll, "aufrufe": aufrufe, "fehler": fehler,
            "kosten_usd": sum(a["kosten_usd"] for a in aufrufe), "dauer_s": round(time.perf_counter() - start, 2)}
