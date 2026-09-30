"""Kostendeckel: 0,25 USD pro Sitzung, 3,00 USD pro Kalendermonat für die ganze App (docs/decisions.md).

Jede Frage bucht vor dem Modellaufruf eine Reserve (die Obergrenze je Frage des Modells) und ersetzt sie danach durch die
echten Kosten. So können auch zwei parallele Aufrufe (Vergleichsmodus) den Deckel nicht überschreiten. Das Kostenbuch
liegt in einer Datenbank, nie im Speicher des Prozesses: SQLite lokal, Postgres auf Cloud Run (KOSTEN_DB_URL). Es ist
nicht die Analyse-Datenbank; dort hat die App nur Leserechte.
"""

import sqlite3
import threading
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Reserve je Frage: die harte Kostengrenze je Frage, die der Harness in der App durchsetzt (docs/decisions.md).
RESERVE_USD = {"haiku": 0.05, "sonnet": 0.05}  # = harte Obergrenze je Frage im Harness (app/dienst.py)

TABELLE = """CREATE TABLE IF NOT EXISTS kosten (
    buchung TEXT PRIMARY KEY, zeit TEXT NOT NULL, monat TEXT NOT NULL, sitzung TEXT NOT NULL,
    modell TEXT NOT NULL, usd DOUBLE PRECISION NOT NULL, offen INTEGER NOT NULL)"""


@dataclass
class Stand:
    sitzung_usd: float
    monat_usd: float
    deckel_sitzung: float
    deckel_monat: float

    @property
    def rest_sitzung(self) -> float:
        return max(0.0, self.deckel_sitzung - self.sitzung_usd)


class Kostenbuch:
    def __init__(self, deckel_sitzung: float, deckel_monat: float, url: str | None = None, pfad: Path | None = None):
        self.deckel_sitzung, self.deckel_monat = deckel_sitzung, deckel_monat
        self.url, self._sperre = url, threading.Lock()
        if url:
            import psycopg
            self._oeffnen = lambda: psycopg.connect(url, autocommit=True)
            self._p = "%s"
        else:
            pfad = pfad or Path("daten/kosten.sqlite")
            pfad.parent.mkdir(parents=True, exist_ok=True)
            self._oeffnen = lambda: sqlite3.connect(pfad, isolation_level=None, timeout=10)
            self._p = "?"
        with self._verbinden() as c:
            c.execute(TABELLE)

    @contextmanager
    def _verbinden(self):
        with closing(self._oeffnen()) as c:
            yield c

    def _summen(self, c, sitzung: str, monat: str) -> tuple[float, float]:
        s = c.execute(f"SELECT coalesce(sum(usd), 0) FROM kosten WHERE sitzung = {self._p}", (sitzung,)).fetchone()[0]
        m = c.execute(f"SELECT coalesce(sum(usd), 0) FROM kosten WHERE monat = {self._p}", (monat,)).fetchone()[0]
        return float(s), float(m)

    def stand(self, sitzung: str) -> Stand:
        with self._verbinden() as c:
            s, m = self._summen(c, sitzung, _monat())
        return Stand(s, m, self.deckel_sitzung, self.deckel_monat)

    def reservieren(self, sitzung: str, modell: str) -> str | None:
        """Bucht die Reserve, wenn beide Deckel sie noch zulassen. Gibt die Buchungs-ID zurück, sonst None."""
        reserve, monat = RESERVE_USD[modell], _monat()
        with self._sperre, self._verbinden() as c:  # Sperre im Prozess; auf Postgres zusätzlich über Instanzen hinweg
            if self.url:
                c.execute("SELECT pg_advisory_lock(55055)")
            try:
                s, m = self._summen(c, sitzung, monat)
                if s + reserve > self.deckel_sitzung + 1e-9 or m + reserve > self.deckel_monat + 1e-9:
                    return None
                buchung = uuid.uuid4().hex
                c.execute(f"INSERT INTO kosten VALUES ({', '.join([self._p] * 7)})",
                          (buchung, datetime.now(timezone.utc).isoformat(), monat, sitzung, modell, reserve, 1))
                return buchung
            finally:
                if self.url:
                    c.execute("SELECT pg_advisory_unlock(55055)")

    def abrechnen(self, buchung: str, usd: float) -> None:
        """Ersetzt die Reserve durch die echten Kosten (auch 0, wenn der Aufruf scheiterte)."""
        with self._verbinden() as c:
            c.execute(f"UPDATE kosten SET usd = {self._p}, offen = 0 WHERE buchung = {self._p}", (usd, buchung))


def _monat() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")
