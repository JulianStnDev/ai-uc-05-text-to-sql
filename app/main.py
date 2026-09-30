"""FocusFlow Analytics Copilot: kleine Web-App (FastAPI + Jinja2 + htmx). Oberfläche Englisch, Fragen und Antworten Deutsch.

    .venv/bin/uvicorn --factory app.main:create_app --reload

Seiten: Ask (eine Frage, Antwortkarte), Compare (dieselbe Frage zweimal nebeneinander), Gallery (gemessene Läufe, ohne
API-Kosten). Kostendeckel pro Sitzung und pro Monat (app/deckel.py). SQL läuft nur als analyst_ro (app/dienst.py).
Für Cloud Run: Port aus $PORT (Dockerfile), Zustand nur in Datenbanken, /health.
"""

import hashlib
import hmac
import re
import secrets
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import dienst, galerie
from .deckel import Kostenbuch
from .einstellungen import Einstellungen, aus_umgebung

HIER = Path(__file__).resolve().parent
COOKIE = "uc5_sitzung"
MAX_FRAGE = 300
BEISPIELE = ["E05", "F04", "E04", "F03", "M02", "M06", "U01", "U02"]
VERGLEICHE = {"glossar": [("haiku", "schema"), ("haiku", "glossar")],
              "modell": [("haiku", "glossar"), ("sonnet", "glossar")]}


def _signatur(sitzung: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"sitzung:{sitzung}".encode(), hashlib.sha256).hexdigest()[:32]


def zahl(wert) -> str:
    """Zahlen im deutschen Format (Antworten sind Deutsch): 1224.34 → 1.224,34, 6696 → 6.696. Text bleibt Text."""
    if isinstance(wert, bool) or wert is None:
        return "" if wert is None else str(wert)
    try:
        d = Decimal(str(wert))
    except InvalidOperation:
        return str(wert)
    if d == d.to_integral_value() and "." not in str(wert):
        return f"{int(d):,}".replace(",", ".")
    stellen = max(0, -d.as_tuple().exponent)
    return f"{d:,.{stellen}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def kurz(zeilen) -> str:
    """Ergebniszeilen in einer Zeile: [[201]] → 201, [["web", 13], ["apple", 7]] → web 13 · apple 7."""
    return " · ".join(" ".join(zahl(v) for v in z) for z in (zeilen or [])[:5]) + (" …" if len(zeilen or []) > 5 else "")


def create_app(einstellungen: Einstellungen | None = None, antwort_fn: Callable | None = None) -> FastAPI:
    """antwort_fn(frage, modell, variante) -> Lauf wie scripts/copilot.beantworten. Standard: das echte Modell."""
    if einstellungen is None:
        load_dotenv(HIER.parent / ".env")
        einstellungen = aus_umgebung()
    cfg = einstellungen
    antwort_fn = antwort_fn or dienst.Copilot(cfg.analytics_ro_url)
    buch = Kostenbuch(cfg.deckel_sitzung_usd, cfg.deckel_monat_usd, url=cfg.kosten_db_url,
                      pfad=cfg.daten_dir / "kosten.sqlite")
    fragen, laeufe = galerie.laden()
    nach_id = {f["id"]: f for f in fragen}
    begriffe = dienst.glossar_begriffe()

    app = FastAPI(title="FocusFlow Analytics Copilot", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HIER / "static"), name="static")
    vorlagen = Jinja2Templates(directory=HIER / "templates")
    vorlagen.env.filters.update(zahl=zahl, kurz=kurz, hat_zahl=lambda t: bool(re.search(r"\d{2,}", t or "")))
    vorlagen.env.globals.update(MODELLE=dienst.MODELLE, VARIANTEN=dienst.VARIANTEN,
                                definition=lambda b: dienst.definition(b, begriffe))

    @app.middleware("http")
    async def sitzung(request: Request, call_next):
        wert = request.cookies.get(COOKIE, "")
        sid, _, sig = wert.partition(".")
        neu = not (sid and hmac.compare_digest(sig, _signatur(sid, cfg.session_secret)))
        request.state.sitzung = secrets.token_hex(16) if neu else sid
        antwort = await call_next(request)
        if neu:
            antwort.set_cookie(COOKIE, f"{request.state.sitzung}.{_signatur(request.state.sitzung, cfg.session_secret)}",
                               max_age=30 * 24 * 3600, httponly=True, samesite="lax", secure=cfg.cookie_secure)
        return antwort

    def seite(request: Request, name: str, **kontext) -> HTMLResponse:
        return vorlagen.TemplateResponse(request, name, {"stand": buch.stand(request.state.sitzung), **kontext})

    def beantworten(request: Request, frage: str, modell: str, variante: str) -> dict:
        """Eine Frage durch den Copiloten, mit Deckel. Gibt den Kontext für die Antwortkarte zurück."""
        frage = frage.strip()[:MAX_FRAGE]
        if not frage:
            return {"hinweis": "Please enter a question."}
        if modell not in dienst.MODELLE or variante not in dienst.VARIANTEN:
            return {"hinweis": "Unknown model or context."}
        buchung = buch.reservieren(request.state.sitzung, modell)
        if buchung is None:
            s = buch.stand(request.state.sitzung)
            welcher = "this month's budget for the whole app" if s.monat_usd + 0.05 > s.deckel_monat else "your session budget"
            return {"hinweis": f"Cost cap reached: {welcher} is used up. The gallery still works without API costs."}
        kosten = 0.0
        try:
            lauf = antwort_fn(frage, modell, variante)
            kosten = lauf["kosten_usd"]
        except Exception as e:  # noqa: BLE001 — nie Verbindungsdaten zeigen
            return {"hinweis": f"The question could not be answered ({type(e).__name__})."}
        finally:
            buch.abrechnen(buchung, kosten)
        return {"lauf": lauf, "frage": frage, "modell": modell, "variante": variante}

    @app.get("/", response_class=HTMLResponse)
    def ask(request: Request, q: str = "", m: str = "haiku", v: str = "glossar"):
        return seite(request, "ask.html", beispiele=[nach_id[i] for i in BEISPIELE], q=q[:MAX_FRAGE], m=m, v=v)

    @app.post("/antwort", response_class=HTMLResponse)
    def antwort(request: Request, frage: str = Form(""), modell: str = Form("haiku"), variante: str = Form("glossar"),
                titel: str = Form("")):
        ctx = beantworten(request, frage, modell, variante)
        return seite(request, "_karte.html", titel=titel, oob=True, **ctx)

    @app.get("/compare", response_class=HTMLResponse)
    def compare(request: Request, q: str = "", modus: str = "glossar"):
        return seite(request, "compare.html", beispiele=[nach_id[i] for i in BEISPIELE], q=q[:MAX_FRAGE],
                     modus=modus if modus in VERGLEICHE else "glossar")

    @app.post("/compare", response_class=HTMLResponse)
    def compare_start(request: Request, frage: str = Form(""), modus: str = Form("glossar")):
        paare = VERGLEICHE.get(modus, VERGLEICHE["glossar"])
        return seite(request, "_vergleich.html", frage=frage.strip()[:MAX_FRAGE], paare=paare)

    @app.get("/gallery", response_class=HTMLResponse)
    def gallery(request: Request):
        return seite(request, "gallery.html", fragen=fragen, laeufe=laeufe)

    @app.get("/gallery/{lauf}/{frage_id}/{wdh}", response_class=HTMLResponse)
    def gallery_karte(request: Request, lauf: str, frage_id: str, wdh: int):
        l = next((x for x in laeufe if x.schluessel == lauf), None)
        z = l.zeilen.get((frage_id, wdh)) if l else None
        if z is None:
            return HTMLResponse("Not found.", status_code=404)
        modell = "sonnet" if "sonnet" in z["modell"] else "haiku"
        return seite(request, "_karte.html", lauf=z, frage=nach_id[frage_id]["frage"], modell=modell,
                     variante=z["variante"], titel=f"{l.name} · run {wdh}", gespeichert=True,
                     erwartet=galerie.erwartet(nach_id[frage_id], z["variante"]), richtig=z["richtig"])

    @app.get("/health")
    def health():
        return JSONResponse({"ok": True})

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return "User-agent: *\nDisallow: /\n"

    return app
