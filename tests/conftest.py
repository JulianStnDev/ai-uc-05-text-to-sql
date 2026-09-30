import os
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

WURZEL = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(WURZEL / "scripts"), str(WURZEL / "evals")]
load_dotenv(WURZEL / ".env")


def url(name: str) -> str:
    if not os.environ.get(name):
        pytest.skip(f"{name} fehlt (.env)")
    return os.environ[name]


@pytest.fixture
def ro():
    """Verbindung als analyst_ro (nur lesend), Sitzung in UTC."""
    with psycopg.connect(url("ANALYTICS_RO_URL"), autocommit=True) as c:
        c.execute("SET TIME ZONE 'UTC'")
        yield c
