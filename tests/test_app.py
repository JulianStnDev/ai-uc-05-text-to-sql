"""Web-App ohne API: Ein Fake-Copilot liefert Läufe im Format „karte“. Geprüft werden Antwortkarte, Rückfrage,
Vergleich, Galerie, Kostendeckel (Sitzung und Monat), Cookie-Signatur und dass Fehler keine Verbindungsdaten zeigen."""

import pytest
from fastapi.testclient import TestClient

from app.deckel import Kostenbuch
from app.einstellungen import Einstellungen
from app.main import COOKIE, create_app


def lauf(art="ergebnis", text="Der Umsatz im Mai 2026 betrug 1.224,34 USD.", zeilen=(("1224.34",),), kosten=0.01, **karte):
    k = {"begriffe": ["Umsatz"], "annahmen": ["Web je Rechnung einmal"], "andere_deutung": None,
         "andere_deutung_sql": None, "andere_deutung_zeilen": None, **karte}
    return {"antwort": {"art": art, "text": text, "sql": "SELECT 1" if art == "ergebnis" else None,
                        "zeilen": [list(z) for z in zeilen] if art == "ergebnis" else None, "karte": k},
            "sql_ausfuehrungen": [], "aufrufe": [{"input": 3000, "output": 400, "cache_lesen": 0, "cache_schreiben": 0}],
            "fehler": None, "kosten_usd": kosten, "dauer_s": 4.2}


class Fake:
    def __init__(self, *laeufe):
        self.laeufe, self.aufrufe = list(laeufe), []

    def __call__(self, frage, modell, variante):
        self.aufrufe.append((frage, modell, variante))
        return self.laeufe.pop(0) if len(self.laeufe) > 1 else self.laeufe[0]


def cfg(tmp_path, **kw):
    return Einstellungen(analytics_ro_url="postgresql://nicht-benutzt", session_secret="s" * 32, daten_dir=tmp_path, **kw)


@pytest.fixture
def client(tmp_path):
    def machen(*laeufe, **kw):
        fake = Fake(*(laeufe or (lauf(),)))
        c = TestClient(create_app(cfg(tmp_path, **kw), antwort_fn=fake))
        return c, fake
    return machen


def test_seiten_und_health(client):
    c, _ = client()
    for pfad in ("/", "/compare", "/gallery"):
        r = c.get(pfad)
        assert r.status_code == 200 and "FocusFlow" in r.text and "$0.25 of $0.25 left" in r.text
    assert c.get("/health").json() == {"ok": True}
    assert "Disallow: /" in c.get("/robots.txt").text


def test_antwortkarte(client):
    andere = lauf(andere_deutung="Brutto vor Erstattungen", andere_deutung_sql="SELECT 2", andere_deutung_zeilen=[["1344.34"]])
    c, fake = client(andere)
    r = c.post("/antwort", data={"frage": "Wie hoch war der Umsatz im Mai 2026?", "modell": "haiku", "variante": "glossar"})
    t = r.text
    assert "1.224,34" in t and "Definitions used" in t and "Umsatz" in t and "Assumptions" in t
    assert "Other reading" in t and "1.344,34" in t and "SELECT 1" in t
    assert 'hx-swap-oob="true"' in t and "$0.24 of $0.25 left" in t   # Budget nach der Frage aktualisiert
    assert fake.aufrufe == [("Wie hoch war der Umsatz im Mai 2026?", "haiku", "glossar")]


def test_rueckfrage_mit_zahl_im_text_bekommt_hinweis(client):
    c, _ = client(lauf("rueckfrage", "Meinen Sie 600 Konten oder 201 Pro-Kunden?"))
    t = c.post("/antwort", data={"frage": "Wie viele Kunden haben wir?"}).text
    assert "Clarifying question" in t and "not from executed SQL" in t


def test_keine_daten(client):
    c, _ = client(lauf("keine_daten", "Die Datenbank erfasst keinen Marketingkanal."))
    t = c.post("/antwort", data={"frage": "Marketingkanal?"}).text
    assert "No data for this" in t and "keine_daten" not in t.split("<article")[0]


def test_ungueltige_eingaben_kosten_nichts(client):
    c, fake = client()
    assert "Please enter a question" in c.post("/antwort", data={"frage": "   "}).text
    assert "Unknown model" in c.post("/antwort", data={"frage": "x", "modell": "opus"}).text
    assert "Unknown model" in c.post("/antwort", data={"frage": "x", "variante": "glossar_spalten"}).text
    assert fake.aufrufe == []


def test_frage_wird_gekuerzt(client):
    c, fake = client()
    c.post("/antwort", data={"frage": "x" * 1000})
    assert len(fake.aufrufe[0][0]) == 300


def test_vergleich_laedt_zwei_karten_parallel(client):
    c, fake = client()
    t = c.post("/compare", data={"frage": "Umsatz Mai?", "modus": "modell"}).text
    assert t.count('hx-post="/antwort"') == 2 and "Haiku 4.5" in t and "Sonnet 5.5" in t
    assert fake.aufrufe == []   # die Karten laden erst im Browser
    t = c.post("/compare", data={"frage": "Umsatz Mai?", "modus": "glossar"}).text
    assert "schema only" in t and "+ glossary" in t


def test_sitzungsdeckel(client):
    c, fake = client(lauf(kosten=0.08))
    for _ in range(3):
        assert "1.224,34" in c.post("/antwort", data={"frage": "a", "modell": "haiku"}).text
    # 0,24 verbraucht; die Reserve für Haiku (0,05) passt nicht mehr
    t = c.post("/antwort", data={"frage": "a", "modell": "haiku"}).text
    assert "Cost cap reached" in t and "session budget" in t and len(fake.aufrufe) == 3
    # eine neue Sitzung (neues Cookie) hat wieder Budget
    c.cookies.clear()
    assert "1.224,34" in c.post("/antwort", data={"frage": "a"}).text


def test_monatsdeckel_fuer_alle_sitzungen(client, tmp_path):
    c, fake = client(lauf(kosten=0.2), deckel_monat_usd=0.44)  # 0,40 verbraucht + 0,05 Reserve > 0,44
    for _ in range(2):
        c.cookies.clear()
        assert "1.224,34" in c.post("/antwort", data={"frage": "a"}).text
    c.cookies.clear()
    t = c.post("/antwort", data={"frage": "a"}).text
    assert "Cost cap reached" in t and "this month" in t and len(fake.aufrufe) == 2


def test_parallele_reservierung_ueberschreitet_den_deckel_nicht(tmp_path):
    buch = Kostenbuch(0.25, 3.0, pfad=tmp_path / "k.sqlite")
    assert buch.reservieren("s", "sonnet") and not buch.reservieren("s", "sonnet")  # 0,15 + 0,15 > 0,25
    assert buch.reservieren("s", "haiku")                                             # 0,15 + 0,05 ≤ 0,25


def test_fehler_zeigt_keine_verbindungsdaten(client, tmp_path):
    def kaputt(*_):
        raise RuntimeError("connection to postgresql://analyst_ro:geheim@host failed")
    c = TestClient(create_app(cfg(tmp_path), antwort_fn=kaputt))
    t = c.post("/antwort", data={"frage": "a"}).text
    assert "could not be answered (RuntimeError)" in t and "geheim" not in t and "postgresql" not in t
    assert "$0.25 of $0.25 left" in t   # gescheiterte Frage kostet nichts


def test_gefaelschtes_cookie_bekommt_neue_sitzung(client):
    c, _ = client(lauf(kosten=0.2))
    c.post("/antwort", data={"frage": "a"})
    sid = c.cookies[COOKIE].split(".")[0]
    c.cookies.set(COOKIE, f"{sid}.falsch")
    assert "$0.25 of $0.25 left" in c.get("/").text


def test_galerie_zeigt_gemessene_laeufe_ohne_api(client):
    c, fake = client()
    t = c.get("/gallery").text
    assert "Haiku · schema" in t and "Sonnet · glossary" in t and "answer card" in t and "column notes*" in t
    assert t.count('hx-get="/gallery/') == 6 * 27 * 3
    lauf_name = t.split('hx-get="/gallery/')[1].split("/")[0]
    k = c.get(f"/gallery/{lauf_name}/E05/1").text
    assert "Expected:" in k and "1224.34" in k and "no API cost" in k
    assert c.get("/gallery/gibtsnicht/E05/1").status_code == 404
    assert fake.aufrufe == []
