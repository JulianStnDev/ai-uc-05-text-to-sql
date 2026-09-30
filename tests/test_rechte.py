"""analyst_ro darf nur lesen. Die Datenbank selbst weist jeden Schreibversuch ab, auch wenn die Sitzung
ausdrücklich auf Lesen und Schreiben umgestellt wird (die Rolle ist zusätzlich standardmäßig read-only)."""

from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import errors

from conftest import url
from laden import TABELLEN

VERSUCHE = {
    "INSERT": "INSERT INTO customers VALUES ('X0001', 'x@example.com', 'DE', 'Europe/Berlin', now(), false)",
    "UPDATE": "UPDATE customers SET country = 'XX' WHERE customer_id = 'C0001'",
    "DELETE": "DELETE FROM refunds",
    "DROP": "DROP TABLE logins",
    "TRUNCATE": "TRUNCATE payments",
    "CREATE": "CREATE TABLE schmuggel (x int)",
    "ALTER": "ALTER TABLE customers ADD COLUMN x int",
}


def test_lesen_erlaubt_auf_allen_analyse_tabellen(ro):
    for t in TABELLEN:
        assert ro.execute(f"SELECT count(*) FROM {t}").fetchone()[0] > 0


@pytest.mark.parametrize("art", VERSUCHE)
def test_schreiben_wird_von_der_datenbank_abgewiesen(ro, art):
    ro.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")  # Read-only-Voreinstellung aushebeln
    assert ro.execute("SHOW default_transaction_read_only").fetchone()[0] == "off"
    with pytest.raises(errors.InsufficientPrivilege):  # scheitert an den Rechten, nicht am Read-only-Modus
        ro.execute(VERSUCHE[art])


def test_weitergeben_von_rechten_bleibt_wirkungslos(ro):
    """Ohne Grant-Option gibt Postgres nur eine Warnung aus ("no privileges were granted"), vergeben wird nichts."""
    ro.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
    ro.execute("GRANT SELECT ON customers TO PUBLIC")
    assert ro.execute("SELECT has_table_privilege('public', 'customers', 'SELECT')").fetchone()[0] is False


def test_rolle_ist_standardmaessig_read_only(ro):
    assert ro.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
    with pytest.raises(errors.ReadOnlySqlTransaction):
        ro.execute("DELETE FROM refunds")


def test_kein_zugriff_auf_andere_datenbanken_des_projekts():
    """Im selben Neon-Projekt liegt die UC7-Datenbank neondb. analyst_ro darf dort nichts lesen."""
    teile = urlsplit(url("ANALYTICS_RO_URL"))
    fremd = urlunsplit(teile._replace(path="/neondb"))
    try:
        with psycopg.connect(fremd, autocommit=True) as c:
            tabellen = [r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")]
            for t in tabellen:
                with pytest.raises(errors.InsufficientPrivilege):
                    c.execute(f'SELECT 1 FROM "{t}" LIMIT 1')
    except psycopg.OperationalError:
        pass  # Verbindung schon abgewiesen: ebenfalls kein Zugriff
