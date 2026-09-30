🇬🇧 [English version](README.md)

# UC5 — Text-to-SQL: Ein Analytics-Copilot auf Daten mit Fallen

> Stand: in Arbeit. Branch (a) ist fertig: Datenbank, Daten und Goldset. Branch (b) und (c) sind gemessen: Mit Glossar steigt Haiku 4.5 von 58 % auf 86 % richtige Antworten, Sonnet 5.5 von 91 % auf 96 %.

## Problem
Produkt- und Support-Teams der fiktiven Habit-Tracker-App FocusFlow stellen Business-Fragen („Wie viel Umsatz hatten wir im Q2?“, „Wie viele Kunden haben im August gekündigt?“) und warten Tage auf einen Analysten. Ein Copilot, der SQL schreibt und ausführt, könnte in Sekunden antworten, aber nur, wenn die Zahl stimmt. Text-to-SQL scheitert selten an der Syntax. Es scheitert an Geschäftsregeln, die das Schema nicht zeigt: Doppelabbuchungen, Store-Käufe in einer eigenen Tabelle, Kündigung vs. Abo-Ende, Erstattungen, Zeitzonen, eine irreführend benannte Spalte. Und er soll bei mehrdeutigen Fragen zurückfragen statt zu raten.

## PM-Entscheidung
Plan in drei Branches, jeweils ein Pull Request:
- **(a) Daten und Goldset (fertig):** eigene Neon-Postgres-Datenbank mit realistischen, aber erfundenen Daten und sechs in die Daten eingebauten Fallen; 25 Business-Fragen auf Deutsch mit Referenz-SQL und aus der Datenbank berechneten Ergebnissen.
- **(b) Nur Schema:** Das Modell sieht die Tabellendefinitionen und sonst nichts.
- **(c) Schema + Glossar:** Das Modell bekommt zusätzlich die Geschäftsdefinitionen ([docs/GLOSSAR.md](docs/GLOSSAR.md)).

Die Frage ist, wie viel ein Glossar gegenüber dem Schema allein bringt. Vor jedem kostenpflichtigen Schritt gibt es eine Kostenschätzung.

Warum eine echte Datenbank mit Rollen statt einer Regel im Prompt: Der Copilot führt SQL als `analyst_ro` aus, der nur SELECT auf die sieben Analyse-Tabellen darf. Postgres weist INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE und ALTER ab, auch wenn die Sitzung auf Lesen und Schreiben umgestellt wird (per Test belegt). Entscheidungen: [docs/decisions.md](docs/decisions.md).

## Architekturskizze
```
evals/goldset_fragen.py ──▶ scripts/goldset_berechnen.py ──(analyst_ro, UTC)──▶ Neon Postgres "analytics" (Frankfurt)
                                        │                                           ▲
                                        ▼                                           │ analytics_admin
                        evals/goldset.json, evals/goldset.md        scripts/daten_erzeugen.py → scripts/laden.py (Seed 20260930)
```
- `db/schema.sql`: sieben Tabellen, ohne erklärende Kommentare (in Branch b das Einzige, was das Modell sieht).
- `docs/DATA_NOTES.md`: die Fallen, nur für Menschen, nie Teil eines Prompts.
- `docs/GLOSSAR.md`: Geschäftsdefinitionen (Entwurf), bekommt das Modell erst in Branch (c).
- `scripts/copilot.py`: der Copilot. Zwei strikte Werkzeuge, `sql_ausfuehren` (führt SQL als `analyst_ro` aus, höchstens 5 je Frage) und `antworten` (Ergebnis mit SQL, Rückfrage oder „keine Daten“). Der Harness führt die Antwort-SQL erneut aus; bewertet wird dieses Ergebnis, nicht der Text.
- `app/`: die Web-App (FastAPI + Jinja2 + htmx), siehe unten.
- `scripts/baseline.py`: Messlauf mit hartem Budget, zeigt ohne `--ja` nur die Schätzung. `scripts/auswerten.py`: Trefferquote je Fragetyp, Kosten je 1000 Requests, p50/p95-Latenz.

## Daten
600 Kunden, 265 Abos, 94 Kündigungen, 400 Web-Zahlungen, 366 Store-Käufe, 33 Erstattungen, 26.798 Logins zwischen 01.10.2025 und 30.09.2026, deterministisch (fester Seed). Jede Falle ändert das Ergebnis einer naiven Abfrage messbar:

| Falle | Frage | richtig | naiv |
|---|---|---|---|
| Doppelabbuchungen | Web-Umsatz Sep. vor Erstattungen | 613,46 USD | 686,44 USD |
| Store vs. Web | Umsatz Q2 2026 | 3.109,63 USD | 1.592,48 USD |
| Kündigung ≠ Abo-Ende | Kunden mit Kündigung im August | 55 | 18 |
| Erstattungen | Umsatz Mai 2026 | 1.224,34 USD | 1.344,34 USD |
| Zeitzone | Logins zwischen 6 und 9 Uhr | 6.696 | 3.695 |
| Irreführende Spalte | Laufende Pro-Abos am 30.09. | 201 | 254 |

## Evaluationsergebnisse
Goldset: 27 Fragen auf Deutsch, vor jeder Messung durchgesehen: 14 eindeutig, 6 mehrdeutig (richtige Antwort: eine Rückfrage, dazu jede Deutung mit SQL und Ergebnis), 5 gezielt auf die Fallen, 2 unbeantwortbar (richtige Antwort: „keine Daten dazu“; eine Ersatz-Abfrage mit ähnlicher Spalte gilt als falsch). Tabelle: [evals/goldset.md](evals/goldset.md).

Die Vergleichsregeln stehen vor der ersten Messung als Code fest ([scripts/vergleich.py](scripts/vergleich.py)): verglichen wird das Ergebnis der ausgeführten SQL, nicht der Fließtext; Ganzzahlen exakt, Dezimalzahlen auf eine Einheit der letzten Stelle; deutsches und englisches Zahlenformat; Spaltennamen und zusätzliche Spalten egal, die Zeilenzahl nicht; Zeilenreihenfolge nur bei Top-N-Fragen; bei Top-1-Fragen zählt nur die erste Zeile; eine Rückfrage ist bei mehrdeutigen und unbeantwortbaren Fragen richtig, bei allen anderen falsch. Ein Selbsttest prüft, dass jede Referenz als richtig und jede naive Fallen-Antwort als falsch gilt.

**Pilot (Haiku 4.5, 27 × 1, nur Schema): 16/27 richtig.** Der Pilot hat das Messinstrument kalibriert: Drei richtige Antworten waren als falsch gewertet worden (eine Top-1-Antwort mit angehängter übriger Rangliste und eine Referenz, die mehr verlangte als die Frage). Diese Regeln wurden als datierte Entscheidung korrigiert und vor dem vollen Lauf eingefroren. Details, Kosten je Frage und Fehler-Rundgang: [evals/pilot.md](evals/pilot.md).

**Branch (b), nur Schema: voller Lauf am 30.09.2026, 27 Fragen × 3 Wiederholungen je Modell.**

| | Haiku 4.5 | Sonnet 5.5 (effort medium) |
|---|---|---|
| richtig (81 Läufe) | 47/81 (58 %) | **74/81 (91 %)** |
| pass^3 (in allen 3 Läufen richtig) | 14/27 | **24/27** |
| eindeutig | 32/42 | 39/42 |
| mehrdeutig: Rückfrage | 9/18 | 17/18 |
| Fallen | 3/15 | 12/15 |
| unbeantwortbar | 3/6 | 6/6 |

Mit dem Schema allein beantwortet Sonnet 5.5 91 % von 81 Läufen richtig (Haiku 4.5: 58 %). Sonnet erkennt fünf der sechs Fallen in jedem Lauf und fragt bei mehrdeutigen Fragen fast immer nach. Haiku fragt bei drei der sechs mehrdeutigen Fragen immer nach, bei den anderen drei nie. Beide Modelle scheitern am Umsatz (E05, F02): Sonnet findet alle Bausteine (Store-Tabelle, Doppelabbuchungen, Erstattungen, Brutto gegenüber Auszahlung), fragt dann aber nach, ob der Umsatz brutto oder netto gemeint ist, oder wählt eine andere Definition als die Referenz. Ohne Glossar ist „Umsatz“ tatsächlich mehrdeutig, genau dafür ist Branch (c) da. Details und Fehler-Rundgang: [evals/results.md](evals/results.md).

**Bekannte Grenze des Goldsets:** Ohne Glossar sind E05 und F02 faktisch mehrdeutig („Umsatz“ brutto oder nach Store-Gebühr, mit oder ohne Erstattungen). Sonnets Rückfragen dort sind vertretbar. Die Regeln bleiben eingefroren, die Bewertung bleibt wie gemessen (E05 und F02 zählen als falsch); in Branch (c) definiert das Glossar „Umsatz“.

**Branch (c), Schema + Glossar: voller Lauf am 30.09.2026, 27 Fragen × 3 je Modell.** Das Glossar ist der Entwurf aus Branch (a), geschrieben vor jeder Messung und unverändert eingefroren (SHA-256 im Entscheidungslog, per Test abgesichert).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/ergebnis_de_dunkel.svg">
  <img src="docs/img/ergebnis_de_hell.svg" alt="Gruppiertes Balkendiagramm: Anteil richtiger Antworten je Fragetyp (eindeutig, mehrdeutig, Fallen, unbeantwortbar). Haiku 4.5 nur Schema: 76, 50, 20, 50 %; mit Glossar: 93, 78, 93, 50 %; mit Glossar im Format Antwortkarte: 93, 78, 80, 50 %; mit Glossar und Spaltenverzeichnis (nach der Messung ergänzt): 90, 78, 87, 67 %. Sonnet 5.5 nur Schema: 93, 94, 80, 100 %; mit Glossar: 93, 100, 100, 100 %.">
</picture>

*Richtige Antworten je Fragetyp, 3 Läufe je Frage; schraffiert = mit Glossar, gepunktet = mit Glossar im Format Antwortkarte (Branch d), kreuzschraffiert = nach der Messung ergänzte Zusatzvariante; die Grafik erzeugt `scripts/grafik.py` aus `evals/laeufe/`.*

| | Haiku (b) | **Haiku (c)** | Sonnet (b) | **Sonnet (c)** |
|---|---|---|---|---|
| richtig (81 Läufe) | 47/81 (58 %) | **70/81 (86 %)** | 74/81 (91 %) | **78/81 (96 %)** |
| pass^3 | 14/27 | **22/27** | 24/27 | **26/27** |
| eindeutig | 32/42 | 39/42 | 39/42 | 39/42 |
| mehrdeutig | 9/18 | 14/18 | 17/18 | 18/18 |
| Fallen | 3/15 | **14/15** | 12/15 | **15/15** |
| unbeantwortbar | 3/6 | 3/6 | 6/6 | 6/6 |

Mit Glossar steigt Haiku 4.5 von 58 % auf 86 % richtige Antworten, Sonnet 5.5 von 91 % auf 96 %. Das Glossar behebt die Fallen (Haiku 3 → 14 von 15) und den Umsatz (E05, F02: 0 → 6 von 6 bei beiden Modellen), und es bringt Haiku dazu, bei „Kunden“ nachzufragen. Es hilft nicht, wo es nichts sagt (U01: Haiku liest den Abrechnungsweg weiter als Marketingkanal), und nicht, wo die SQL falsch ist (E12, M06 um einen Tag daneben).

**Bekannte Grenze, E02:** Das Glossar sagt, „Kunde“ allein ist mehrdeutig und muss präzisiert werden. Sonnet hält sich daran und fragt bei „den fünf Ländern mit den meisten Kunden“ in allen drei Läufen nach; das Goldset erwartet die Zahl der Konten. Glossar und Goldset widersprechen sich hier, die Bewertung bleibt wie gemessen. Ohne diesen Widerspruch stünde Sonnet (c) bei 81/81.

**Zusatzvariante, nur Haiku: Glossar + Spaltenverzeichnis, nach der Messung ergänzt und auf dieses Goldset hin optimiert.** Je missverständlicher Spalte eine neutrale Zeile (etwa `subscriptions.channel` = Abrechnungsweg), keine Liste fehlender Daten. Ergebnis: 69/81 (85 %) gegenüber 70/81 mit Glossar allein, also Rauschen; U01 1 von 3. Weil das Verzeichnis mit Wissen über die Testfragen geschrieben wurde, sagte selbst ein Gewinn wenig über neue Fragen (Overfitting aufs Testset); sauber prüfen ließe es sich nur mit einem Holdout aus Fragen, die beim Schreiben niemand kannte. Vorher/Nachher-Beispiele und Fehler-Rundgang: [evals/results.md](evals/results.md).

**Branch (d1), Antwortkarte: Regressionstest am 30.09.2026.** Das Werkzeug `antworten` liefert jetzt strukturierte Felder: Ergebnis, verwendete Glossar-Begriffe, Annahmen, eine andere naheliegende Deutung mit ihrer Zahl (vom Harness aus ausgeführter SQL berechnet, nie aus dem Text des Modells) und die SQL. Haiku + Glossar, 27 × 3: 68/81 (84 %) gegenüber 70/81 in (c), also keine messbare Regression, aber 25 % mehr Kosten je Frage und 3,7 s mehr beim p95. Das vorhergesagte Risiko trat einmal auf: Bei M02 antwortete Haiku „600 Konten“ und legte die Pro-Kunden (201) als andere Deutung daneben, statt nachzufragen. Die Handprüfung der Annahmen ([docs/ANTWORTEN.md](docs/ANTWORTEN.md)) zeigt: Sie beschreiben die Absicht, nicht das, was das SQL tut. Mehrere Karten nennen die richtige Regel (etwa „je Rechnung nur einmal“) über SQL, das sie falsch umsetzt.

## Kosten & Latenz
Gemessen an je 81 Läufen je Modell und Variante:

| | Haiku (b) | Haiku (c) | Sonnet (b) | Sonnet (c) |
|---|---|---|---|---|
| Kosten pro 1000 Requests | 6,54 USD | 8,51 USD | 9,51 USD | 10,14 USD |
| Kosten pro 1000 richtige Antworten | 11,27 USD | **9,85 USD** | 10,41 USD | 10,53 USD |
| p95-Latenz | 9,9 s | 9,4 s | 11,5 s | 8,1 s |
| Qualität: richtig / pass^3 | 58 % / 14 von 27 | 86 % / 22 von 27 | 91 % / 24 von 27 | 96 % / 26 von 27 |

- Sonnet kostet je Frage nur rund 45 % mehr, obwohl der Tokenpreis doppelt so hoch ist: Das Prompt-Caching greift (der Prompt liegt über Sonnets Minimum von 512 Tokens, aber unter Haikus 4.096), und Sonnet braucht weniger Aufrufe je Frage.
- Sonnet 5.5, nur Schema: 9,51 USD pro 1000 Requests bei 11,5 s p95-Latenz.
- Je richtige Antwort ist Sonnet günstiger als Haiku: 10,41 gegenüber 11,27 USD pro 1000 richtige Antworten, weil Haiku 42 % seiner Antworten falsch beantwortet.
- Haiku 4.5 mit Glossar: 9,85 USD pro 1000 richtige Antworten, die günstigste Kombination. Der längere Prompt kostet je Frage mehr, dafür stimmen viel mehr Antworten.
- Pilot und voller Lauf von Branch (b) kosteten zusammen 1,48 USD; Branch (c) mit Zusatzvariante 2,31 USD; die Anatomie eines Laufs 0,08 USD.
- Branch (a) machte keine API-Aufrufe. Neon läuft im Free-Tier.

## Die App (lokal)
Eine kleine Web-App über dem Copiloten, gleicher Stack wie UC7: FastAPI, Jinja2 und htmx (als Datei im Repo, kein CDN). Die Oberfläche ist Englisch, Fragen und Antworten sind Deutsch.

- **Ask:** Frage eintippen oder ein Beispiel anklicken. Die Antwortkarte zeigt das Ergebnis groß, die verwendeten Glossar-Begriffe (Mouseover zeigt die Definition), die Annahmen, eine andere naheliegende Deutung mit ihrer Zahl, das SQL mit Ergebnis (einklappbar) und die Kosten der Frage.
- **Compare:** dieselbe Frage nebeneinander, wahlweise *nur Schema gegen + Glossar* oder *Haiku gegen Sonnet*. Beide Aufrufe laufen parallel.
- **Gallery:** alle gemessenen Läufe der vollen Messungen als anklickbare Beispiele, bewertet mit den eingefrorenen Regeln, ohne API-Kosten (Vorstufe für das Replay beim Online-Gang).
- **Kostendeckel:** 0,25 USD pro Sitzung (signiertes Cookie), 3,00 USD pro Monat für die ganze App und hart 0,05 USD je Frage. Jede Frage bucht zuerst eine Reserve von 0,05 USD und rechnet danach die echten Kosten ab, so können auch zwei parallele Aufrufe den Deckel nicht überschreiten. Das Kostenbuch liegt lokal in SQLite und auf Cloud Run in Postgres, nie im Speicher des Prozesses und nie in der Analyse-Datenbank, auf der die App nur Leserechte hat.
- **Nur lesend:** SQL läuft ausschließlich als `analyst_ro`; die App prüft `current_user` beim ersten Zugriff und verweigert jede andere Rolle. Fehlermeldungen zeigen nie Verbindungsdaten.
- **Bereit für Cloud Run:** `Dockerfile` (python:3.13-slim, Nutzer ohne Root, Port aus `$PORT`), `/health`, Secrets nur aus der Umgebung, `.gcloudignore` schließt `.env` aus.

Was die Antwortkarte sichtbar macht, nach [docs/ANTWORTEN.md](docs/ANTWORTEN.md): Zahlen kommen nur aus ausgeführter SQL; die Zahl der anderen Deutung rechnet der Harness; Zahlen im Text einer Rückfrage bekommen einen Hinweis, dass niemand sie ausgeführt hat. Die Annahmen heißen *as stated by the model*, und eine einfache Code-Prüfung markiert jede Annahme zu einer bekannten Glossar-Regel (eine Zahlung je Rechnung, Store-Auszahlung, Erstattungen abgezogen, Zeitzone des Kunden, Kündigung ≠ Abo-Ende, genannter Zeitraum) mit **✓ verified in SQL** oder **⚠ not found in SQL**; alle vier Fehlkarten aus ANTWORTEN.md bekommen ⚠. Ein ✓ heißt nur, dass das Muster im SQL steht, nicht, dass die Zahl stimmt. Jede Frage ist im Harness auf 0,05 USD begrenzt (Abbruch vor dem Aufruf, der die Grenze überschreiten würde).

![Galerie-Karte E05, Lauf 1: als richtig bewertet, aber die Annahme „je Rechnung nur einmal“ ist mit „not found in SQL“ markiert – die Zahl stimmt nur, weil es im Mai keine Doppelabbuchung gab](docs/img/app_badges_e05.png)

*E05, Lauf 1 aus dem Antwortkarten-Lauf: als richtig bewertet, trotzdem ⚠ bei „je Rechnung nur einmal“ – das SQL summiert alle Zahlungen je Rechnung und stimmt nur, weil es im Mai keine Doppelabbuchung gab. Die Screenshots darunter entstanden vor der Badge-Prüfung.*

| Antwortkarte (E05, Haiku + Glossar) | Rückfrage (M02) |
|---|---|
| ![Antwortkarte: Umsatz Mai 2026, 1.224,34, mit verwendeten Definitionen und Annahmen](docs/img/app_antwortkarte.png) | ![Rückfrage zu „Wie viele Kunden haben wir?“, mit Hinweis, dass die Zahlen im Text nicht ausgeführt wurden](docs/img/app_rueckfrage_m02.png) |
| **Vergleich nur Schema gegen + Glossar (E05)** | **Vergleich Haiku gegen Sonnet (U01)** |
| ![Nebeneinander: nur Schema ergibt 1.344,34 ohne Erstattungen, mit Glossar 1.224,34](docs/img/app_vergleich_glossar_e05.png) | ![Nebeneinander: Haiku nimmt den Abrechnungskanal als Ersatz für den Marketingkanal und sagt es; Sonnet antwortet „keine Daten“](docs/img/app_vergleich_modelle_u01.png) |

## Guardrails
Drei Schichten stehen zwischen einer Frage und den Daten: das Modell, Harness und App, und die Datenbank-Rolle `analyst_ro`. [docs/GUARDRAILS.md](docs/GUARDRAILS.md) ordnet jeder Angriffsart die Schicht zu, die sie stoppt, jeweils belegt durch einen deterministischen Test (ohne Modell, ohne API-Kosten). Die Datenbank stoppt Schreiben (zweifach: Rechte und read-only), Personendaten (`customers.email` ist per Spaltenrechten gesperrt; das Modell sieht die Spalte weiter im Schema, damit die Datenbank sichtbar greift), Datei- und Programmzugriffe, andere Datenbanken und lange Abfragen (15 s). Harness und App stoppen Anweisungsketten, Kosten über 0,05 USD je Frage, 0,25 USD je Sitzung und 3,00 USD im Monat und den Betrieb mit einer anderen Rolle als `analyst_ro`. Bei den meisten Angriffsarten steht nur eine Schicht; `email` schützen allein die Spaltenrechte. Die Spalte „Modell“ ist noch nicht gemessen: Die Angriffsdemo gegen das Modell ist nach UC6 verschoben.

## Lokal ausführen
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
NEON_OWNER_URL=... .venv/bin/python scripts/setup_db.py   # einmalig: Datenbank, Rollen, schreibt .env
.venv/bin/python scripts/laden.py                          # Tabellen anlegen und füllen (deterministisch)
.venv/bin/python scripts/goldset_berechnen.py              # erwartete Ergebnisse als analyst_ro
.venv/bin/python -m pytest                                 # Daten, Rechte, Goldset, Harness (ohne API)
.venv/bin/python scripts/baseline.py --modell haiku --budget 0.50        # nur Schätzung; --ja startet (kostet Geld)
.venv/bin/python scripts/auswerten.py evals/laeufe/*.jsonl                # Auswertung (ohne API)
.venv/bin/python scripts/grafik.py                                        # Grafik (ohne API)
.venv/bin/pip install -r requirements-dev.txt                             # httpx, nur für die App-Tests
.venv/bin/uvicorn --factory app.main:create_app --reload                  # die App auf http://localhost:8000 (kostet pro Frage, gedeckelt)
```

## Learnings
- **Jede Falle braucht eine Gegenabfrage.** Erst wenn die naive Abfrage mit genau einem Fehler eine andere Zahl liefert, ist die Falle echt. Das Skript bricht sonst ab.
- **Vergleichsregeln vor der Messung festlegen.** Sonst wird die Toleranz gewählt, nachdem man die Ergebnisse gesehen hat. Der Selbsttest zeigt außerdem, dass eine Toleranz von einer Einheit der letzten Stelle keine Falle verschluckt.
- **Realismus an den Zahlen prüfen.** Die erste Fassung der Login-Daten hatte 586 von 600 Kunden im September aktiv, weil Gratis-Nutzer nie einschliefen. Die Kennzahl wäre wertlos gewesen.
- **Sitzungs-Zeitzone festlegen.** Datumsgrenzen wie `'2026-05-01'` hängen von der Zeitzone der Sitzung ab; alle Skripte setzen UTC.
- **Das Modell schreibt manchmal `NOW()`**, obwohl der Prompt den 30.09.2026 als heute nennt. Solche Abfragen treffen die Referenz nur an diesem Tag, deshalb lief der volle Lauf am 30.09.2026. Beobachtet, nicht korrigiert.
- **Definitionen schlagen Modellgröße.** Mit Glossar kommt das kleine Modell (86 %) fast an das große ohne Glossar heran (91 %) und ist je richtige Antwort die günstigste Wahl.
- **Verhaltensregeln brauchen Fakten, die sie auslösen.** Ein zusätzlicher Satz im Prompt („frag nach, statt eine ähnliche Spalte zu nehmen“) änderte nichts (0/10), die Definitionen schon. Siehe [docs/ANATOMIE.md](docs/ANATOMIE.md).
- **Glossar und Goldset müssen zusammenpassen.** Unser eigenes Glossar nennt „Kunde“ mehrdeutig, unser eigenes Goldset wertet E02 als eindeutig. Das bessere Modell folgte dem Glossar und verlor drei Punkte.
- **Verbesserungen, die nach einem gescheiterten Test geschrieben werden, sind kein Beleg.** Das Spaltenverzeichnis ist auf dieses Goldset hin optimiert, so gekennzeichnet und bräuchte einen Holdout, um zu zählen.

## Was ich anders machen würde
Folgt zum Abschluss des Use Cases.
