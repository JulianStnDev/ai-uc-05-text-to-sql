"""Vergleichsregeln (scripts/vergleich.py), festgelegt vor der ersten Messung. Plus Selbsttest am Goldset:
Referenz richtig, naive Antwort falsch, Rückfrage je nach Typ."""

import json
from pathlib import Path

import pytest

from vergleich import bewerten, zahl, zeilen_gleich

GOLDSET = json.loads((Path(__file__).resolve().parents[1] / "evals" / "goldset.json").read_text(encoding="utf-8"))
FRAGEN = {f["id"]: f for f in GOLDSET["fragen"]}


def ergebnis(zeilen):
    return {"art": "ergebnis", "zeilen": zeilen}


@pytest.mark.parametrize("text, wert", [
    ("1.224,34 USD", "1224.34"), ("1,224.34", "1224.34"), ("1224.34", "1224.34"), ("35,5 %", "35.5"),
    ("$ 613.46", "613.46"), ("1.234.567", "1234567"), ("6696", "6696"), (7.4, "7.4"), (201, "201"),
])
def test_zahlenformat(text, wert):
    assert zahl(text) == zahl(wert)


def test_text_ist_keine_zahl():
    assert zahl("iOS") is None and zahl("price_increase") is None and zahl(None) is None and zahl(True) is None


def test_rundungstoleranz_eine_stelle():
    soll = {"spalten": ["umsatz_usd"], "zeilen": [["1224.34"]]}
    assert zeilen_gleich(soll, [[1224.344]]) and zeilen_gleich(soll, [["1.224,35 USD"]])
    assert not zeilen_gleich(soll, [[1224.36]]) and not zeilen_gleich(soll, [[1224]])
    median = {"spalten": ["median_tage"], "zeilen": [["7.4"]]}
    assert zeilen_gleich(median, [[7.36]]) and zeilen_gleich(median, [[7.5]]) and not zeilen_gleich(median, [[7.52]])


def test_ganzzahlen_exakt():
    soll = {"spalten": ["kunden"], "zeilen": [[201]]}
    assert zeilen_gleich(soll, [[201]]) and zeilen_gleich(soll, [["201"]]) and zeilen_gleich(soll, [[201.0]])
    assert not zeilen_gleich(soll, [[202]]) and not zeilen_gleich(soll, [[200.6]])


def test_prozent_auch_als_anteil():
    soll = {"spalten": ["prozent"], "zeilen": [["35.5"]]}
    assert zeilen_gleich(soll, [[0.355]]) and zeilen_gleich(soll, [["35,5 %"]])
    ohne = {"spalten": ["kunden"], "zeilen": [["35.5"]]}
    assert not zeilen_gleich(ohne, [[0.355]])


def test_spalten_egal_extras_erlaubt_zeilenzahl_nicht():
    soll = {"spalten": ["channel", "neue_abos"], "zeilen": [["apple", 15], ["google", 9], ["web", 34]]}
    assert zeilen_gleich(soll, [[34, "Web"], [15, "Apple"], [9, "Google"]])          # Reihenfolge egal
    assert zeilen_gleich(soll, [["web", 34, "58.6 %"], ["apple", 15, "25.9 %"], ["google", 9, "15.5 %"]])  # Extra-Spalte
    assert not zeilen_gleich(soll, [["web", 34], ["apple", 15]])                         # Zeile fehlt
    assert not zeilen_gleich(soll, [["web", 34], ["apple", 15], ["google", 9], ["summe", 58]])  # Zeile zu viel
    assert not zeilen_gleich(soll, [["web", 15], ["apple", 34], ["google", 9]])          # Werte vertauscht


def test_top1_nur_erste_zeile():
    for fid in ("E07", "E10"):
        top = FRAGEN[fid]
        assert top["top1"] is True
        (spitze,) = top["ergebnis"]["zeilen"]
        assert bewerten(top, ergebnis([spitze, ["zweiter", 1], ["dritter", 0]]))["richtig"]  # Rangliste erlaubt
        assert not bewerten(top, ergebnis([["zweiter", 1], spitze]))["richtig"]              # Spitze nicht vorn
        assert not bewerten(top, ergebnis([]))["richtig"]
    assert not any(f.get("top1") for f in FRAGEN.values() if f["id"] not in ("E07", "E10"))


def test_reihenfolge_nur_wenn_gefordert():
    top = FRAGEN["E02"]
    assert top["reihenfolge"] is True
    richtig = top["ergebnis"]["zeilen"]
    assert bewerten(top, ergebnis(richtig))["richtig"]
    assert not bewerten(top, ergebnis(list(reversed(richtig))))["richtig"]


def test_goldset_selbsttest_referenz_richtig_naiv_falsch():
    for f in GOLDSET["fragen"]:
        if f["typ"] in ("eindeutig", "falle"):
            assert bewerten(f, ergebnis(f["ergebnis"]["zeilen"]))["richtig"], f["id"]
            for art in ("rueckfrage", "keine_daten"):
                assert not bewerten(f, {"art": art, "zeilen": []})["richtig"], f["id"]
        if f.get("naiv_ergebnis"):  # die Toleranz darf keine Falle verschlucken
            assert not bewerten(f, ergebnis(f["naiv_ergebnis"]["zeilen"]))["richtig"], f["id"]


def test_mehrdeutig_nur_rueckfrage_richtig():
    for f in (f for f in GOLDSET["fragen"] if f["typ"] == "mehrdeutig"):
        assert bewerten(f, {"art": "rueckfrage", "zeilen": []})["richtig"]
        assert not bewerten(f, {"art": "keine_daten", "zeilen": []})["richtig"]
        for d in f["deutungen"]:  # eine Zahl ist falsch, auch wenn sie zu einer Deutung passt
            assert not bewerten(f, ergebnis(d["ergebnis"]["zeilen"]))["richtig"], f["id"]


def test_unbeantwortbar_keine_daten_oder_rueckfrage():
    for f in (f for f in GOLDSET["fragen"] if f["typ"] == "unbeantwortbar"):
        assert bewerten(f, {"art": "keine_daten", "zeilen": []})["richtig"]
        assert bewerten(f, {"art": "rueckfrage", "zeilen": []})["richtig"]
        assert not bewerten(f, ergebnis([["web", 34]]))["richtig"]  # Ersatz-Abfrage


def test_m06_mit_glossar_eindeutig():
    m06 = FRAGEN["M06"]
    zahl_374 = m06["mit_glossar"]["ergebnis"]["zeilen"]
    assert zahl_374 == [[374]]
    assert bewerten(m06, {"art": "rueckfrage", "zeilen": []}, "schema")["richtig"]
    assert not bewerten(m06, ergebnis(zahl_374), "schema")["richtig"]
    assert bewerten(m06, ergebnis(zahl_374), "glossar")["richtig"]
    assert not bewerten(m06, {"art": "rueckfrage", "zeilen": []}, "glossar")["richtig"]
    assert not bewerten(m06, ergebnis([[201]]), "glossar")["richtig"]


def test_unbekannte_antwortart():
    with pytest.raises(ValueError):
        bewerten(FRAGEN["E01"], {"art": "vielleicht"})
