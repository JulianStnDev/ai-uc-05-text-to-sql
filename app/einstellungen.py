"""Einstellungen der App, nur aus Umgebungsvariablen (lokal aus .env, auf Cloud Run aus Secret Manager).

Pflicht: ANALYTICS_RO_URL (nur die Rolle analyst_ro, die App prüft das beim ersten Zugriff) und ANTHROPIC_API_KEY.
Optional: SESSION_SECRET (sonst zufällig, Sitzungen überleben dann keinen Neustart), KOSTEN_DB_URL (Postgres für das
Kostenbuch; ohne sie SQLite in DATEN_DIR), DECKEL_SITZUNG_USD (0.25), DECKEL_MONAT_USD (3.00), COOKIE_SECURE.
"""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Einstellungen:
    analytics_ro_url: str
    session_secret: str
    kosten_db_url: str | None = None
    daten_dir: Path = Path("daten")
    deckel_sitzung_usd: float = 0.25
    deckel_monat_usd: float = 3.00
    cookie_secure: bool = False


def aus_umgebung() -> Einstellungen:
    url = os.environ.get("ANALYTICS_RO_URL")
    if not url:
        raise RuntimeError("ANALYTICS_RO_URL fehlt.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY fehlt.")
    return Einstellungen(
        analytics_ro_url=url,
        session_secret=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
        kosten_db_url=os.environ.get("KOSTEN_DB_URL") or None,
        daten_dir=Path(os.environ.get("DATEN_DIR", "daten")),
        deckel_sitzung_usd=float(os.environ.get("DECKEL_SITZUNG_USD", "0.25")),
        deckel_monat_usd=float(os.environ.get("DECKEL_MONAT_USD", "3.00")),
        cookie_secure=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
    )
