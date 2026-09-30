"""Verbindung zwischen App und Copilot (scripts/copilot.py): eine Frage beantworten, im Format „karte“.

Die App führt SQL ausschließlich als analyst_ro aus. Beim ersten Zugriff prüft sie das mit `SELECT current_user` und
verweigert jede andere Rolle. Fehlermeldungen enthalten nie Verbindungsdaten.
"""

import re
import sys
import threading
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))
from copilot import beantworten, verbinden  # noqa: E402

ROLLE = "analyst_ro"
MODELLE = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 5.5"}
MAX_KOSTEN_JE_FRAGE_USD = 0.05  # harte Obergrenze im Harness, gleich der Reserve im Kostenbuch (app/deckel.py)
VARIANTEN = {"schema": "schema only", "glossar": "+ glossary"}


class Copilot:
    """Beantwortet Fragen mit dem echten Modell. In Tests wird stattdessen eine Funktion mit derselben Signatur übergeben."""

    def __init__(self, analytics_ro_url: str):
        import anthropic
        self._url, self._client, self._geprueft, self._sperre = analytics_ro_url, anthropic.Anthropic(), False, threading.Lock()

    def _rolle_pruefen(self, conn) -> None:
        with self._sperre:
            if not self._geprueft:
                rolle = conn.execute("SELECT current_user").fetchone()[0]
                if rolle != ROLLE:
                    raise RuntimeError(f"Die App läuft nur mit der Rolle {ROLLE}, nicht mit {rolle}.")
                self._geprueft = True

    def __call__(self, frage: str, modell: str, variante: str) -> dict:
        with verbinden(self._url) as conn:
            self._rolle_pruefen(conn)
            return beantworten(self._client, conn, frage, modell, variante, format="karte",
                               max_kosten_usd=MAX_KOSTEN_JE_FRAGE_USD)


def glossar_begriffe() -> dict[str, str]:
    """Begriff → Definition aus docs/GLOSSAR.md (Zeilen der Form „- **Begriff:** Definition“), für die Tooltips."""
    begriffe = {}
    for zeile in (WURZEL / "docs" / "GLOSSAR.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?):?\*\*:?\s*(.*)", zeile.strip())
        if m:
            begriffe[m.group(1).strip()] = re.sub(r"\*\*|`", "", m.group(2)).strip()
    return begriffe


def definition(begriff: str, begriffe: dict[str, str]) -> str | None:
    """Definition zu einem vom Modell genannten Begriff, auch wenn er leicht anders geschrieben ist."""
    b = begriff.strip().lower()
    for name, text in begriffe.items():
        if name.lower() == b or name.lower().startswith(b) or b.startswith(name.lower()):
            return text
    return None
