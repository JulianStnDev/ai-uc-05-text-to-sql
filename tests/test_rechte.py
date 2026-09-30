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
    """Ohne Grant-Option vergibt Postgres nichts: bei vollem Tabellenrecht nur eine Warnung ("no privileges were
    granted"), seit den Spaltenrechten auf customers (Branch e) sogar ein Fehler. Beides ist wirkungslos."""
    ro.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
    for t in ("customers", "refunds"):
        try:
            ro.execute(f"GRANT SELECT ON {t} TO PUBLIC")
        except errors.InsufficientPrivilege:
            pass
        assert ro.execute(f"SELECT has_table_privilege('public', '{t}', 'SELECT')").fetchone()[0] is False


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


# ---------- Branch (e): Guardrails der Datenbank, ohne Modell geprüft ----------

def test_email_ist_fuer_analyst_ro_gesperrt(ro):
    with pytest.raises(errors.InsufficientPrivilege):
        ro.execute("SELECT email FROM customers LIMIT 1")
    with pytest.raises(errors.InsufficientPrivilege):   # SELECT * schließt die gesperrte Spalte ein
        ro.execute("SELECT * FROM customers LIMIT 1")
    assert ro.execute("SELECT count(*), count(DISTINCT country) FROM customers").fetchone()[0] == 600
    assert ro.execute("SELECT has_column_privilege('customers', 'email', 'SELECT')").fetchone()[0] is False
    assert ro.execute("SELECT has_column_privilege('customers', 'country', 'SELECT')").fetchone()[0] is True


@pytest.mark.parametrize("versuch", [
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_ls_dir('.')",
    "COPY (SELECT 1) TO PROGRAM 'id'",
    "SELECT lo_import('/etc/passwd')",
    "SELECT rolpassword FROM pg_authid",
])
def test_dateien_programme_und_passwoerter_sind_verboten(ro, versuch):
    with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
        ro.execute(versuch)


def test_katalog_zeigt_rollen_aber_keine_passwoerter(ro):
    """pg_roles ist für alle lesbar (Rollennamen, Rechte-Flags), das Passwort steht dort nur als ********."""
    zeilen = ro.execute("SELECT rolname, rolpassword FROM pg_roles WHERE rolname = 'analyst_ro'").fetchall()
    assert zeilen == [("analyst_ro", "********")]


def test_zeitlimit_und_keine_erweiterungen(ro):
    assert ro.execute("SHOW statement_timeout").fetchone()[0] == "15s"
    erweiterungen = {r[0] for r in ro.execute("SELECT extname FROM pg_extension")}
    assert not erweiterungen & {"dblink", "postgres_fdw", "file_fdw", "plpython3u"}


def test_alle_referenz_sql_laufen_mit_den_spaltenrechten(ro):
    import json
    from pathlib import Path
    fragen = json.loads((Path(__file__).resolve().parents[1] / "evals" / "goldset.json").read_text())["fragen"]
    for f in fragen:
        for s in [f.get("sql")] + [d["sql"] for d in f.get("deutungen", [])] + [(f.get("mit_glossar") or {}).get("sql")]:
            if s:
                ro.execute(s).fetchall()
