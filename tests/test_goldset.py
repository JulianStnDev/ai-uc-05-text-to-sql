"""Goldset: Aufbau (15/5/5), Pflichtfelder, keine relativen Zeitangaben im SQL, und goldset.json stimmt mit der
Datenbank überein (nur mit .env)."""

import json
import re
from pathlib import Path

from goldset_berechnen import berechnen
from goldset_fragen import FALLEN_BELEGE, FRAGEN

GOLDSET = Path(__file__).resolve().parents[1] / "evals" / "goldset.json"
FALLEN = {"doppelabbuchung", "store", "kuendigung", "erstattung", "zeitzone", "irrefuehrende_spalte"}


def alle_sql(f):
    return [f.get("sql"), f.get("naiv_sql")] + [d["sql"] for d in f.get("deutungen", [])]


def test_aufbau():
    typen = [f["typ"] for f in FRAGEN]
    assert len(FRAGEN) == 25 and (typen.count("eindeutig"), typen.count("mehrdeutig"), typen.count("falle")) == (15, 5, 5)
    assert len({f["id"] for f in FRAGEN}) == 25
    for f in FRAGEN:
        assert f["frage"].endswith("?") and set(f["fallen"]) <= FALLEN
        if f["typ"] == "mehrdeutig":
            assert f["rueckfrage"] and len(f["deutungen"]) >= 2 and "sql" not in f
        else:
            assert f["sql"]
        if f["typ"] == "falle":
            assert len(f["fallen"]) == 1 and f["naiv_sql"] and f["naiv_fehler"]


def test_jede_falle_ist_belegt():
    assert {b["falle"] for b in FALLEN_BELEGE} == FALLEN
    assert {f["fallen"][0] for f in FRAGEN if f["typ"] == "falle"} <= FALLEN


def test_keine_relativen_zeitangaben_im_sql():
    """now()/current_date würden die Ergebnisse jeden Tag ändern."""
    for f in FRAGEN:
        for s in filter(None, alle_sql(f)):
            assert not re.search(r"now\(\)|current_(date|timestamp)|localtimestamp", s, re.I), f["id"]


def test_gespeicherte_ergebnisse_stimmen_mit_der_datenbank(ro):
    gespeichert = json.loads(GOLDSET.read_text(encoding="utf-8"))
    ergebnisse, belege = berechnen(ro)
    assert ergebnisse == gespeichert["fragen"] and belege == gespeichert["fallen_belege"]


def test_naive_abfragen_liefern_andere_zahlen():
    gespeichert = json.loads(GOLDSET.read_text(encoding="utf-8"))
    for f in gespeichert["fragen"]:
        if f["typ"] == "falle":
            assert f["naiv_ergebnis"]["zeilen"] != f["ergebnis"]["zeilen"], f["id"]
    for b in gespeichert["fallen_belege"]:
        assert b["naiv"]["zeilen"] != b["richtig"]["zeilen"], b["falle"]
