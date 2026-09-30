"""Datengenerator ohne Datenbank: deterministisch, Größenordnung, und jede Falle ist in den Daten vorhanden."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

import pytest

from daten_erzeugen import ENDE, START, erzeugen


@pytest.fixture(scope="module")
def d():
    return erzeugen()


def fingerabdruck(daten) -> str:
    return hashlib.sha256(json.dumps(daten, default=str, sort_keys=True).encode()).hexdigest()


def test_deterministisch(d):
    assert fingerabdruck(d) == fingerabdruck(erzeugen())


def test_groessenordnung_und_zeitraum(d):
    assert len(d["customers"]) == 600 and 200 <= len(d["subscriptions"]) <= 400
    for t, spalte in [("customers", 4), ("payments", 4), ("store_transactions", 4), ("logins", 2), ("cancellations", 2)]:
        assert all(START <= z[spalte] < ENDE for z in d[t]), t


def test_falle_doppelabbuchung(d):
    je_rechnung = Counter(z[1] for z in d["payments"] if z[6] == "succeeded")
    doppelt = [r for r, n in je_rechnung.items() if n > 1]
    assert len(doppelt) == 10
    erstattet = {e[1] for e in d["refunds"] if e[4] == "duplicate_charge"}
    zweite = [z for z in d["payments"] if z[1] in doppelt and z[6] == "succeeded" and z[0] not in
              {min((y for y in d["payments"] if y[1] == z[1] and y[6] == "succeeded"), key=lambda y: y[4])[0]}]
    assert len(zweite) == 10 and len([z for z in zweite if z[0] not in erstattet]) == 2  # zwei noch offen


def test_falle_store_nicht_in_payments(d):
    store_abos = {a[0] for a in d["subscriptions"] if a[3] != "web"}
    assert store_abos and not any(z[2] in store_abos for z in d["payments"])
    assert all(t[6] < t[5] for t in d["store_transactions"])  # Auszahlung < Kundenpreis


def test_falle_kuendigung_august_ende_september(d):
    ende = {a[0]: a[5] for a in d["subscriptions"]}
    august = [k for k in d["cancellations"] if k[2].month == 8 and k[2].year == 2026]
    assert len(august) >= 30 and sum(ende[k[1]] and ende[k[1]].month == 9 for k in august) >= 15


def test_falle_zeitzonen(d):
    zonen = Counter(k[3] for k in d["customers"])
    assert len(zonen) >= 10 and zonen["Europe/Berlin"] < 300


def test_falle_is_premium_bleibt_nach_abo_ende(d):
    stichtag = datetime(2026, 10, 1, tzinfo=timezone.utc)
    laufend = {a[1] for a in d["subscriptions"] if a[5] is None or a[5] >= stichtag}
    premium = {k[0] for k in d["customers"] if k[5]}
    assert laufend < premium and len(premium - laufend) >= 20


def test_erstattungen_nie_hoeher_als_zahlung(d):
    betrag = {z[0]: z[5] for z in d["payments"]}
    assert all(e[3] <= betrag[e[1]] for e in d["refunds"])
