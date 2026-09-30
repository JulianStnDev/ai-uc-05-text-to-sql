"""Harness ohne API: Ein Fake-Client spielt Modellantworten ab, SQL läuft echt als analyst_ro.
Geprüft werden Prompt-Inhalt, Tool-Loop, Obergrenzen, Kosten, Budget-Abbruch und Auswertung."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import auswerten
import baseline
from copilot import MAX_SQL, TOOLS, beantworten, kosten_usd, system_prompt

WURZEL = Path(__file__).resolve().parents[1]
FRAGEN = {f["id"]: f for f in json.loads((WURZEL / "evals" / "goldset.json").read_text(encoding="utf-8"))["fragen"]}


def usage(ein=1500, aus=200, schreiben=0, lesen=0):
    return NS(input_tokens=ein, output_tokens=aus, cache_creation_input_tokens=schreiben, cache_read_input_tokens=lesen)


def werkzeug(name, **eingabe):
    werkzeug.n = getattr(werkzeug, "n", 0) + 1
    return NS(type="tool_use", name=name, input=eingabe, id=f"toolu_{werkzeug.n}")


def antwort(*bloecke, stop="tool_use", u=None):
    return NS(content=list(bloecke), stop_reason=stop, usage=u or usage())


class FakeClient:
    """Gibt die vorgegebenen Antworten der Reihe nach zurück und merkt sich jede Anfrage."""

    def __init__(self, antworten):
        self.antworten, self.anfragen = list(antworten), []
        self.messages = self

    def create(self, **params):
        self.anfragen.append({**params, "messages": list(params["messages"])})
        return self.antworten.pop(0)


def richtig_fuer(frage_id):
    return FRAGEN[frage_id]["sql"]


# ---------- Prompt ----------

def test_prompt_schema_enthaelt_nur_schema():
    p = system_prompt("schema")
    assert (WURZEL / "db" / "schema.sql").read_text(encoding="utf-8").strip() in p
    assert "Heute ist der 30.09.2026" in p
    verboten = ["Doppelabbuchung", "hatte irgendwann", "is_premium bedeutet", "Falle", "proceeds_usd`, nach",
                "Kündigung und Abo-Ende", "Ortszeit des Kunden", "Geschäftsdefinitionen"]
    assert not [w for w in verboten if w in p]


def test_prompt_nie_mit_data_notes_oder_datenrundgang():
    for variante in ("schema", "glossar", "glossar_spalten"):
        p = system_prompt(variante)
        for datei in ("DATA_NOTES.md", "DATENRUNDGANG.md"):
            zeilen = [z.strip() for z in (WURZEL / "docs" / datei).read_text(encoding="utf-8").splitlines() if len(z.strip()) > 40]
            assert not [z for z in zeilen if z in p], (variante, datei)


def test_prompt_glossar_nur_in_variante_glossar():
    glossar = (WURZEL / "docs" / "GLOSSAR.md").read_text(encoding="utf-8").strip()
    assert glossar in system_prompt("glossar") and glossar not in system_prompt("schema")
    with pytest.raises(ValueError):
        system_prompt("alles")


def test_spaltenverzeichnis_nur_in_der_zusatzvariante():
    spalten = (WURZEL / "docs" / "SPALTEN.md").read_text(encoding="utf-8").strip()
    glossar = (WURZEL / "docs" / "GLOSSAR.md").read_text(encoding="utf-8").strip()
    p = system_prompt("glossar_spalten")
    assert glossar in p and spalten in p and p.index(glossar) < p.index(spalten)
    assert spalten not in system_prompt("glossar") and spalten not in system_prompt("schema")
    # Keine Liste fehlender Daten (docs/decisions.md, 30.09.2026): das wäre die Antwort auf U01/U02.
    assert not [w for w in ("Marketing", "NPS", "nicht erfasst", "Umfrage") if w in spalten]


def test_glossar_eingefroren():
    """Branch (c) misst den Entwurf aus Branch (a) unverändert (docs/decisions.md, 30.09.2026)."""
    import hashlib
    inhalt = (WURZEL / "docs" / "GLOSSAR.md").read_bytes()
    assert hashlib.sha256(inhalt).hexdigest() == "e3d770e9c4edfdd5a0f9e978a920baaf1cf29f69d73d99dcb559c8b62aa38393"


def test_tools_strikt_und_ohne_erzwungene_auswahl(ro):
    assert all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in TOOLS)
    c = FakeClient([antwort(werkzeug("antworten", art="rueckfrage", text="Welche Kunden?", sql=""))])
    beantworten(c, ro, "Wie viele Kunden haben wir?", "sonnet")
    anfrage = c.anfragen[0]
    assert "tool_choice" not in anfrage  # erzwungene Werkzeugwahl lehnt Sonnet 5.5 ab
    assert anfrage["model"] == "claude-sonnet-5-5" and anfrage["output_config"] == {"effort": "medium"}
    assert "thinking" not in anfrage  # Sonnet 5.5: adaptiv (Standard)


# ---------- Loop ----------

def test_richtige_antwort_wird_richtig_bewertet(ro):
    c = FakeClient([
        antwort(werkzeug("sql_ausfuehren", sql=richtig_fuer("F05"))),
        antwort(NS(type="text", text="Das sind 201."), werkzeug("antworten", art="ergebnis", text="201 Kunden", sql=richtig_fuer("F05"))),
    ])
    lauf = beantworten(c, ro, FRAGEN["F05"]["frage"], "haiku")
    assert lauf["antwort"]["zeilen"] == [[201]] and lauf["fehler"] is None
    assert baseline.bewertung(FRAGEN["F05"], lauf, "schema")["richtig"]
    # zweiter Aufruf bekam das SQL-Ergebnis als tool_result zurück
    rueck = c.anfragen[1]["messages"][-1]["content"][0]
    assert rueck["type"] == "tool_result" and json.loads(rueck["content"])["zeilen"] == [[201]] and not rueck["is_error"]
    assert "output_config" not in c.anfragen[0]  # Haiku: kein effort


def test_naive_antwort_wird_falsch_bewertet(ro):
    c = FakeClient([antwort(werkzeug("antworten", art="ergebnis", text="254", sql=FRAGEN["F05"]["naiv_sql"]))])
    lauf = beantworten(c, ro, FRAGEN["F05"]["frage"], "haiku")
    assert lauf["antwort"]["zeilen"] == [[254]]
    assert not baseline.bewertung(FRAGEN["F05"], lauf, "schema")["richtig"]


def test_rueckfrage_und_keine_daten(ro):
    c = FakeClient([antwort(werkzeug("antworten", art="keine_daten", text="Herkunft wird nicht erfasst.", sql=""))])
    lauf = beantworten(c, ro, FRAGEN["U01"]["frage"], "haiku")
    assert lauf["antwort"]["art"] == "keine_daten" and lauf["antwort"]["zeilen"] is None
    assert baseline.bewertung(FRAGEN["U01"], lauf, "schema")["richtig"]
    assert not baseline.bewertung(FRAGEN["E01"], lauf, "schema")["richtig"]


def test_ohne_werkzeug_eine_erinnerung_dann_fehler(ro):
    c = FakeClient([antwort(NS(type="text", text="54"), stop="end_turn"), antwort(NS(type="text", text="54"), stop="end_turn")])
    lauf = beantworten(c, ro, FRAGEN["E01"]["frage"], "haiku")
    assert lauf["fehler"] == "kein Werkzeug benutzt" and lauf["antwort"]["art"] is None and len(c.anfragen) == 2
    assert c.anfragen[1]["messages"][-1] == {"role": "user", "content": "Bitte beende die Frage mit dem Werkzeug antworten."}
    assert not baseline.bewertung(FRAGEN["E01"], lauf, "schema")["richtig"]


def test_sql_fehler_und_schreibversuch_gehen_als_fehler_zurueck(ro):
    c = FakeClient([
        antwort(werkzeug("sql_ausfuehren", sql="SELEC 1"), werkzeug("sql_ausfuehren", sql="DELETE FROM refunds")),
        antwort(werkzeug("antworten", art="keine_daten", text="-", sql="")),
    ])
    lauf = beantworten(c, ro, "x?", "haiku")
    rueck = c.anfragen[1]["messages"][-1]["content"]
    assert [r["is_error"] for r in rueck] == [True, True]
    assert "SyntaxError" in rueck[0]["content"] and "ReadOnlySqlTransaction" in rueck[1]["content"]
    assert [s["ok"] for s in lauf["sql_ausfuehrungen"]] == [False, False]
    assert ro.execute("SELECT count(*) FROM refunds").fetchone()[0] == 33


def test_hoechstens_fuenf_sql_ausfuehrungen(ro):
    viele = antwort(*[werkzeug("sql_ausfuehren", sql="SELECT 1") for _ in range(MAX_SQL + 2)])
    c = FakeClient([viele, antwort(werkzeug("antworten", art="ergebnis", text="1", sql="SELECT 1"))])
    lauf = beantworten(c, ro, "x?", "haiku")
    rueck = c.anfragen[1]["messages"][-1]["content"]
    assert len(lauf["sql_ausfuehrungen"]) == MAX_SQL
    assert [r["is_error"] for r in rueck] == [False] * MAX_SQL + [True, True] and "Limit" in rueck[-1]["content"]


def test_ergebnis_wird_auf_50_zeilen_gekuerzt_bewertung_nutzt_alle(ro):
    c = FakeClient([antwort(werkzeug("sql_ausfuehren", sql="SELECT customer_id FROM customers ORDER BY 1")),
                    antwort(werkzeug("antworten", art="ergebnis", text="-", sql="SELECT customer_id FROM customers ORDER BY 1"))])
    lauf = beantworten(c, ro, "x?", "haiku")
    inhalt = json.loads(c.anfragen[1]["messages"][-1]["content"][0]["content"])
    assert len(inhalt["zeilen"]) == 50 and inhalt["anzahl_zeilen"] == 600 and len(lauf["antwort"]["zeilen"]) == 600


def test_fehlerhafte_antwort_sql(ro):
    c = FakeClient([antwort(werkzeug("antworten", art="ergebnis", text="-", sql="SELECT nichts FROM nirgends"))])
    lauf = beantworten(c, ro, FRAGEN["E01"]["frage"], "haiku")
    assert lauf["antwort"]["zeilen"] is None and lauf["fehler"].startswith("Antwort-SQL fehlerhaft")
    assert not baseline.bewertung(FRAGEN["E01"], lauf, "schema")["richtig"]


def test_refusal_bricht_ab(ro):
    c = FakeClient([antwort(stop="refusal")])
    lauf = beantworten(c, ro, "x?", "sonnet")
    assert lauf["fehler"] == "refusal" and lauf["antwort"]["art"] is None


def test_thinking_bloecke_gehen_unveraendert_zurueck(ro):
    denken = NS(type="thinking", thinking="", signature="sig")
    c = FakeClient([antwort(denken, werkzeug("sql_ausfuehren", sql="SELECT 1")),
                    antwort(werkzeug("antworten", art="rueckfrage", text="?", sql=""))])
    beantworten(c, ro, "x?", "sonnet")
    assert c.anfragen[1]["messages"][1]["content"][0] is denken


# ---------- Kosten und Budget ----------

def test_kosten_mit_cache():
    assert kosten_usd("haiku", usage(1_000_000, 0)) == pytest.approx(1.00)
    assert kosten_usd("sonnet", usage(0, 1_000_000)) == pytest.approx(10.00)
    assert kosten_usd("sonnet", usage(0, 0, schreiben=1_000_000, lesen=1_000_000)) == pytest.approx(2.00 * 1.25 + 2.00 * 0.1)


def test_budget_bricht_vor_der_naechsten_frage_ab(ro, tmp_path):
    teuer = usage(ein=30_000, aus=1_000)  # 0,035 USD je Aufruf mit Haiku
    c = FakeClient([antwort(werkzeug("antworten", art="rueckfrage", text="?", sql=""), u=teuer) for _ in range(10)])
    fragen = [FRAGEN[i] for i in ("M01", "M02", "M03", "M04", "M05")]
    ziel = tmp_path / "lauf.jsonl"
    z = baseline.ausfuehren(c, ro, fragen, "haiku", "schema", 1, budget=0.12, ziel=ziel, ausgabe=lambda *_: None)
    assert z["abgebrochen"] and z["laeufe"] == 2 and z["kosten_usd"] <= 0.12
    assert len(ziel.read_text().splitlines()) == 2


# ---------- Auswertung ----------

def test_auswertung_ueber_jsonl(ro, tmp_path):
    ziel = tmp_path / "lauf.jsonl"
    skript = {
        "F05": [antwort(werkzeug("antworten", art="ergebnis", text="201", sql=FRAGEN["F05"]["sql"]))],
        "F03": [antwort(werkzeug("antworten", art="ergebnis", text="18", sql=FRAGEN["F03"]["naiv_sql"]))],
        "M02": [antwort(werkzeug("antworten", art="rueckfrage", text="Welche?", sql=""))],
        "U02": [antwort(werkzeug("antworten", art="ergebnis", text="-", sql="SELECT count(*) FROM cancellations"))],
    }
    for fid, antworten in skript.items():
        baseline.ausfuehren(FakeClient(antworten), ro, [FRAGEN[fid]], "haiku", "schema", 1, 1.0, ziel, lambda *_: None)
    laeufe = auswerten.laden([ziel])
    k = auswerten.kennzahlen(laeufe, FRAGEN)
    assert (k["richtig"], k["n"]) == (2, 4) and k["abweichend"] == 0
    assert k["je_typ"] == {"eindeutig": (0, 0), "mehrdeutig": (1, 1), "falle": (1, 2), "unbeantwortbar": (0, 1)}
    assert k["fallen"] == {"F03": (0, 1), "F05": (1, 1)}
    assert k["kosten_je_1000"] == pytest.approx(1000 * kosten_usd("haiku", usage()))
    text = auswerten.bericht(laeufe, FRAGEN)
    assert "| claude-haiku-4-5 | schema | 2/4 (50 %)" in text and "| F03 | ✗ ergebnis |" in text


def test_perzentil_naechster_rang():
    assert auswerten.perzentil([1, 2, 3, 4, 100], 0.95) == 100 and auswerten.perzentil([], 0.5) is None


# ---------- Experimente (docs/ANATOMIE.md) ----------

class Roh(NS):
    """Antwort mit model_dump wie beim SDK, damit der Mitschnitt geprüft werden kann."""

    def model_dump(self, **_):
        return {"stop_reason": self.stop_reason, "content": [vars(b) for b in self.content],
                "usage": vars(self.usage)}


def test_experimente_aendern_den_messlauf_nicht(ro):
    c = FakeClient([antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))])
    beantworten(c, ro, FRAGEN["U01"]["frage"], "sonnet")
    assert c.anfragen[0]["system"] == system_prompt("schema") and "thinking" not in c.anfragen[0]


def test_zusatz_thinking_und_mitschnitt(ro):
    erster = Roh(**vars(antwort(werkzeug("sql_ausfuehren", sql="SELECT 1 AS x"))))
    zweiter = Roh(**vars(antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))))
    c, mitschnitt = FakeClient([erster, zweiter]), []
    beantworten(c, ro, FRAGEN["U01"]["frage"], "sonnet", zusatz="Frag nach.", thinking_anzeigen=True,
                mitschnitt=mitschnitt)
    assert c.anfragen[0]["system"].endswith("\n\nFrag nach.")
    assert c.anfragen[0]["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert len(mitschnitt) == 2 and json.dumps(mitschnitt)
    assert len(mitschnitt[0]["request"]["messages"]) == 1 and len(mitschnitt[1]["request"]["messages"]) == 3
    assert mitschnitt[1]["response"]["content"][0]["name"] == "antworten"
    c = FakeClient([antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))])
    beantworten(c, ro, FRAGEN["U01"]["frage"], "haiku", thinking_anzeigen=True)
    assert "thinking" not in c.anfragen[0]  # Haiku läuft ohne Thinking


# ---------- Antwortformat „karte“ (Branch d) ----------

def test_format_kurz_bleibt_wie_in_b_und_c(ro):
    c = FakeClient([antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))])
    beantworten(c, ro, FRAGEN["U01"]["frage"], "haiku", "glossar")
    assert c.anfragen[0]["tools"] == TOOLS and c.anfragen[0]["system"] == system_prompt("glossar")


def test_format_karte_felder_und_zahl_der_anderen_deutung(ro):
    karte = dict(art="ergebnis", ergebnis="600 Konten.", begriffe=["Konto"], annahmen=["Kunde = Konto"],
                 andere_deutung="Pro-Kunden zum Stichtag", andere_deutung_sql="SELECT 201 AS kunden",
                 sql="SELECT count(*) FROM customers")
    c = FakeClient([antwort(werkzeug("antworten", **karte))])
    lauf = beantworten(c, ro, FRAGEN["M02"]["frage"], "haiku", "glossar", format="karte")
    assert c.anfragen[0]["tools"][1]["input_schema"]["required"][-1] == "sql"
    assert "Antwortformat" in c.anfragen[0]["system"]
    a = lauf["antwort"]
    assert a["text"] == "600 Konten." and a["zeilen"] == [[600]]
    assert a["karte"]["andere_deutung_zeilen"] == [[201]]      # vom Harness ausgeführt, nicht vom Modell behauptet
    assert a["karte"]["begriffe"] == ["Konto"] and a["karte"]["annahmen"] == ["Kunde = Konto"]
    assert not baseline.bewertung(FRAGEN["M02"], lauf, "glossar")["richtig"]  # Zahl statt Rückfrage bleibt falsch


def test_format_karte_ohne_andere_deutung_und_rueckfrage(ro):
    karte = dict(art="rueckfrage", ergebnis="Welche Kunden?", begriffe=[], annahmen=[], andere_deutung="",
                 andere_deutung_sql="", sql="")
    c = FakeClient([antwort(werkzeug("antworten", **karte))])
    lauf = beantworten(c, ro, FRAGEN["M02"]["frage"], "haiku", "glossar", format="karte")
    assert lauf["antwort"]["karte"]["andere_deutung"] is None and lauf["antwort"]["karte"]["andere_deutung_zeilen"] is None
    assert baseline.bewertung(FRAGEN["M02"], lauf, "glossar")["richtig"]
    with pytest.raises(ValueError):
        beantworten(FakeClient([]), ro, "x", "haiku", format="lang")


def test_harte_kostengrenze_je_frage(ro):
    teuer = usage(ein=20000, aus=2000)   # 0,03 USD je Aufruf mit Haiku
    c = FakeClient([antwort(werkzeug("sql_ausfuehren", sql="SELECT 1"), u=teuer)] * 3
                   + [antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))])
    lauf = beantworten(c, ro, "x", "haiku", max_kosten_usd=0.05)
    assert len(lauf["aufrufe"]) == 1 and lauf["fehler"].startswith("Kostengrenze") and lauf["kosten_usd"] <= 0.05
    c = FakeClient([antwort(werkzeug("sql_ausfuehren", sql="SELECT 1"), u=teuer),
                    antwort(werkzeug("antworten", art="keine_daten", text="-", sql=""))])
    assert beantworten(c, ro, "x", "haiku")["fehler"] is None   # ohne Grenze (Messläufe) unverändert
