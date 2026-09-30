"""Erzeugt die FocusFlow-Analysedaten deterministisch (fester Seed): Kunden, Abos, Kündigungen, Web-Zahlungen,
Erstattungen, Store-Käufe und Logins zwischen 01.10.2025 und 30.09.2026 (UTC).

Die Fallen sind absichtlich eingebaut und in docs/DATA_NOTES.md beschrieben (nur für Menschen, nie ans Modell).
Aufruf nur über scripts/laden.py; `erzeugen()` liefert je Tabelle eine Liste von Zeilen in Spaltenreihenfolge.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

SEED = 20260930
START = datetime(2025, 10, 1, tzinfo=timezone.utc)
ENDE = datetime(2026, 10, 1, tzinfo=timezone.utc)  # exklusiv: letzter Datentag ist der 30.09.2026
N_KUNDEN = 600

PREIS = {"pro_monthly": Decimal("6.99"), "pro_annual": Decimal("59.00")}
STORE_ANTEIL = Decimal("0.85")  # Auszahlung der Stores nach 15 % Provision
# Preiserhöhungs-Mail am 10.08.2026: Im August kündigen deutlich mehr Kunden (Abo-Ende meist im September).
PREISMAIL = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
AUGUST_ENDE = datetime(2026, 9, 1, tzinfo=timezone.utc)

LAENDER = [  # (Land, Zeitzone, Gewicht)
    ("DE", "Europe/Berlin", 30), ("AT", "Europe/Vienna", 5), ("CH", "Europe/Zurich", 5), ("NL", "Europe/Amsterdam", 4),
    ("GB", "Europe/London", 8), ("US", "America/New_York", 12), ("US", "America/Los_Angeles", 9),
    ("CA", "America/Toronto", 4), ("BR", "America/Sao_Paulo", 4), ("JP", "Asia/Tokyo", 7), ("IN", "Asia/Kolkata", 5),
    ("AU", "Australia/Sydney", 7),
]
KUENDIGUNGSGRUENDE = ["too_expensive", "not_using", "switched_app", "other"]
# Login-Uhrzeit in Ortszeit: Morgen- und Abendspitze
STUNDEN_GEWICHT = [1, 1, 1, 1, 1, 2, 8, 12, 10, 5, 4, 4, 5, 4, 3, 3, 3, 4, 5, 7, 10, 12, 9, 4]


def monat_plus(dt: datetime, n: int) -> datetime:
    m = dt.month - 1 + n
    jahr, monat = dt.year + m // 12, m % 12 + 1
    tage = [31, 29 if jahr % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1]
    return dt.replace(year=jahr, month=monat, day=min(dt.day, tage))


def zufallszeit(rng: random.Random, von: datetime, bis: datetime) -> datetime:
    return von + timedelta(seconds=rng.randrange(max(1, int((bis - von).total_seconds()))))


def erzeugen() -> dict[str, list[tuple]]:
    rng = random.Random(SEED)
    kunden, abos, kuendigungen, zahlungen, erstattungen, store, logins = [], [], [], [], [], [], []
    zaehler = {"abo": 0, "zahlung": 0, "rechnung": 0, "store": 0, "kuendigung": 0, "erstattung": 0}
    abo_zeitraeume: dict[str, list[tuple[datetime, datetime | None, str]]] = {}

    def neue_id(art: str, praefix: str, stellen: int) -> str:
        zaehler[art] += 1
        return f"{praefix}{zaehler[art]:0{stellen}d}"

    def web_zahlung(abo_id, kunden_id, faellig, betrag):
        rechnung = neue_id("rechnung", "INV-", 6)
        if rng.random() < 0.05:  # erster Einzug scheitert, Wiederholung 1–2 Tage später
            zahlungen.append((neue_id("zahlung", "P", 6), rechnung, abo_id, kunden_id, faellig, betrag, "failed"))
            faellig = faellig + timedelta(days=rng.randint(1, 2), seconds=rng.randint(0, 3600))
        if faellig < ENDE:
            zahlungen.append((neue_id("zahlung", "P", 6), rechnung, abo_id, kunden_id, faellig, betrag, "succeeded"))

    def abo_simulieren(kunden_id, beginn, plan, kanal) -> datetime | None:
        """Legt ein Abo mit allen Zahlungen an. Gibt das Abo-Ende zurück (None = läuft über den 30.09. hinaus)."""
        abo_id = neue_id("abo", "S", 5)
        periode, ende, kuendigung = beginn, None, None
        monate = 1 if plan == "pro_monthly" else 12
        while periode < ENDE and ende is None:
            naechste = monat_plus(periode, monate)
            if kanal == "web":
                web_zahlung(abo_id, kunden_id, periode + timedelta(seconds=rng.randint(1, 90)), PREIS[plan])
            else:
                preis = PREIS[plan]
                store.append((neue_id("store", "T", 6), abo_id, kunden_id, kanal, periode + timedelta(seconds=rng.randint(1, 90)),
                              preis, (preis * STORE_ANTEIL).quantize(Decimal("0.01"))))
            fenster_ende = min(naechste, ENDE)
            # Widerruf innerhalb von 14 Tagen (nur Web-Jahresabo, erste Periode): volle Erstattung, Abo endet sofort
            if periode == beginn and kanal == "web" and plan == "pro_annual" and rng.random() < 0.10:
                t = zufallszeit(rng, periode + timedelta(hours=2), min(periode + timedelta(days=14), ENDE))
                kuendigung, ende = (t, "withdrawal"), t
                zahlung = [z for z in zahlungen if z[2] == abo_id and z[6] == "succeeded"][-1]
                erstattungen.append((neue_id("erstattung", "R", 4), zahlung[0], t + timedelta(minutes=rng.randint(5, 600)),
                                     zahlung[5], "withdrawal_14d"))
                break
            p = 0.05 if plan == "pro_monthly" else 0.025
            august = periode < AUGUST_ENDE and fenster_ende > PREISMAIL
            if august and rng.random() < 0.20:
                t = zufallszeit(rng, max(periode, PREISMAIL), min(fenster_ende, AUGUST_ENDE))
                kuendigung = (t, "price_increase")
            elif rng.random() < p:
                kuendigung = (zufallszeit(rng, periode + timedelta(hours=1), fenster_ende), rng.choice(KUENDIGUNGSGRUENDE))
            if kuendigung:
                ende = naechste  # Kündigung wirkt zum Ende der bezahlten Periode
            periode = naechste
        if kuendigung:
            kuendigungen.append((neue_id("kuendigung", "K", 5), abo_id, kuendigung[0], kuendigung[1]))
        abos.append((abo_id, kunden_id, plan, kanal, beginn, ende))
        abo_zeitraeume.setdefault(kunden_id, []).append((beginn, ende, kanal))
        return ende

    for n in range(1, N_KUNDEN + 1):
        kunden_id = f"C{n:04d}"
        land, zone, _ = rng.choices(LAENDER, weights=[g for *_, g in LAENDER])[0]
        anmeldung = START + timedelta(seconds=int((ENDE - START).total_seconds() * rng.random() ** 0.8))
        abos_vorher = len(abos)
        if rng.random() < 0.45:
            beginn = anmeldung + timedelta(days=min(int(rng.expovariate(1 / 12)), 90), seconds=rng.randint(60, 86_000))
            kanal = rng.choices(["web", "apple", "google"], weights=[55, 30, 15])[0]
            plan = rng.choices(["pro_monthly", "pro_annual"], weights=[65, 35])[0]
            while beginn < ENDE:
                ende = abo_simulieren(kunden_id, beginn, plan, kanal)
                if ende is None or ende >= ENDE or rng.random() > 0.15:
                    break
                beginn = ende + timedelta(days=rng.randint(5, 60), seconds=rng.randint(0, 86_000))  # kommt zurück
                plan = rng.choice(["pro_monthly", "pro_annual"])
        # Irreführend: is_premium heißt "hatte je ein Pro-Abo" und wird nie zurückgesetzt.
        kunden.append((kunden_id, f"user{n:04d}@example.com", land, zone, anmeldung, len(abos) > abos_vorher))

    doppelabbuchungen_einbauen(rng, zahlungen, erstattungen, neue_id)
    kulanz_einbauen(rng, zahlungen, erstattungen, neue_id)
    logins = logins_erzeugen(rng, kunden, abo_zeitraeume)
    return {"customers": kunden, "subscriptions": abos, "cancellations": kuendigungen, "payments": zahlungen,
            "refunds": erstattungen, "store_transactions": store, "logins": logins}


def doppelabbuchungen_einbauen(rng, zahlungen, erstattungen, neue_id) -> None:
    """10 Web-Zahlungen werden ein zweites Mal eingezogen (gleiche Rechnung, gleicher Betrag, Sekunden bis Minuten
    später). 3 liegen im September 2026, davon 2 noch nicht erstattet; die übrigen 8 sind erstattet
    (reason duplicate_charge)."""
    erfolgreich = [z for z in zahlungen if z[6] == "succeeded"]
    september = [z for z in erfolgreich if z[4] >= datetime(2026, 9, 1, tzinfo=timezone.utc)
                 and z[4] < datetime(2026, 9, 27, tzinfo=timezone.utc)]
    frueher = [z for z in erfolgreich if datetime(2025, 11, 1, tzinfo=timezone.utc) <= z[4] < datetime(2026, 8, 1, tzinfo=timezone.utc)]
    for i, z in enumerate(rng.sample(september, 3) + rng.sample(frueher, 7)):
        doppelt = (neue_id("zahlung", "P", 6), z[1], z[2], z[3], z[4] + timedelta(seconds=rng.randint(20, 240)), z[5], "succeeded")
        zahlungen.append(doppelt)
        if i >= 2:  # die ersten beiden (September) sind noch nicht erstattet
            erstattungen.append((neue_id("erstattung", "R", 4), doppelt[0], doppelt[4] + timedelta(days=rng.randint(2, 5)),
                                 doppelt[5], "duplicate_charge"))


def kulanz_einbauen(rng, zahlungen, erstattungen, neue_id) -> None:
    """16 Kulanz-Erstattungen auf Monatszahlungen, teils anteilig. Nie auf eine Doppelabbuchung."""
    erste = {}
    for z in sorted((z for z in zahlungen if z[6] == "succeeded"), key=lambda z: z[4]):
        erste.setdefault(z[1], z[0])  # erste erfolgreiche Zahlung je Rechnung
    monatlich = [z for z in zahlungen if z[6] == "succeeded" and z[5] == PREIS["pro_monthly"] and erste[z[1]] == z[0]
                 and z[4] < datetime(2026, 9, 20, tzinfo=timezone.utc)]
    bereits = {e[1] for e in erstattungen}
    for z in rng.sample([z for z in monatlich if z[0] not in bereits], 16):
        betrag = rng.choice([Decimal("6.99"), Decimal("3.50"), Decimal("2.00")])
        erstattungen.append((neue_id("erstattung", "R", 4), z[0], z[4] + timedelta(days=rng.randint(1, 9), hours=rng.randint(0, 23)),
                             betrag, "goodwill"))


def logins_erzeugen(rng, kunden, abo_zeitraeume) -> list[tuple]:
    """Logins in UTC gespeichert, erzeugt aus Ortszeiten (Morgen- und Abendspitze in der Zeitzone des Kunden)."""
    zeilen, login_id = [], 0
    for kunden_id, _, _, zone, anmeldung, _ in kunden:
        tz = ZoneInfo(zone)
        zeitraeume = abo_zeitraeume.get(kunden_id, [])
        kanal = zeitraeume[0][2] if zeitraeume else None
        bevorzugt = {"apple": "ios", "google": "android"}.get(kanal) or rng.choices(["ios", "android", "web"], weights=[45, 30, 25])[0]
        # Gratis-Nutzung: die meisten probieren einige Wochen und werden dann selten, ein Teil bleibt lange dabei.
        frei_aktiv_bis = anmeldung + timedelta(days=rng.expovariate(1 / 35) if rng.random() < 0.7 else rng.expovariate(1 / 250))
        tag = anmeldung.astimezone(tz).date()
        while True:
            beginn_lokal = datetime(tag.year, tag.month, tag.day, tzinfo=tz)
            if beginn_lokal >= ENDE:
                break
            pro = any(b <= beginn_lokal and (e is None or beginn_lokal < e) for b, e, _ in zeitraeume)
            if pro:
                rate = 0.55
            elif zeitraeume and beginn_lokal >= zeitraeume[0][0]:
                rate = 0.012  # nach dem Abo-Ende nur noch vereinzelt
            else:
                rate = 0.25 if beginn_lokal < frei_aktiv_bis else 0.003
            for _ in range(2 if rng.random() < 0.15 else 1):
                if rng.random() >= rate:
                    continue
                stunde = rng.choices(range(24), weights=STUNDEN_GEWICHT)[0]
                lokal = beginn_lokal.replace(hour=stunde, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                utc = lokal.astimezone(timezone.utc)
                if anmeldung <= utc < ENDE:
                    login_id += 1
                    plattform = bevorzugt if rng.random() < 0.85 else rng.choice(["ios", "android", "web"])
                    zeilen.append((login_id, kunden_id, utc, plattform))
            tag = tag + timedelta(days=1)
    return zeilen


if __name__ == "__main__":
    for tabelle, zeilen in erzeugen().items():
        print(f"{tabelle:20} {len(zeilen):>7}")
