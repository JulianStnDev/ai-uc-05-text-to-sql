# Guardrails: welche Schicht stoppt was?

Der Copilot schreibt SQL, das niemand vorher liest. Drei Schichten stehen zwischen einer Frage und der Datenbank:

1. **Modell:** Lehnt es ab, fragt es nach, schreibt es nur SELECT?
2. **Harness und App** (`scripts/copilot.py`, `app/`): eine Anweisung je Ausführung, höchstens 5 SQL-Ausführungen und
   8 Modellaufrufe je Frage, höchstens 50 Zeilen an das Modell, 0,05 USD je Frage, Deckel pro Sitzung und Monat,
   Rollenprüfung, Fehlermeldungen ohne Verbindungsdaten.
3. **Datenbank** (Rolle `analyst_ro`): nur SELECT auf die sieben Analyse-Tabellen, bei `customers` ohne `email`;
   standardmäßig read-only; 15 s Timeout; keine Grant-Option; kein Zugriff auf andere Datenbanken des Projekts.

Diese Übersicht stützt sich nur auf **deterministische Tests** (ohne Modell, ohne API-Kosten), Stand 30.09.2026. Jede
Zelle nennt den Test, der es belegt. **Die Spalte „Modell“ ist nicht gemessen.** Die Angriffsdemo mit dem Modell ist
nach UC6 verschoben (docs/decisions.md, 30.09.2026).

## Zusammenfassung

- **Nachweislich stoppt die Datenbank** Schreiben, Rechte-Weitergabe, Personendaten (`email`), Datei- und
  Programmzugriff, Passwörter, andere Datenbanken und lange Abfragen.
- **Nachweislich stoppt der Harness bzw. die App** Anweisungsketten, zu viele Ausführungen, zu große Ergebnisse für das
  Modell, Kosten über 0,05 USD je Frage, 0,25 USD je Sitzung und 3,00 USD im Monat, den Betrieb mit einer falschen Rolle
  und Verbindungsdaten in Fehlermeldungen.
- **Zwei Schichten** gibt es nur beim Schreiben (Rechte *und* read-only, dazu die Sperre gegen Ketten).
- **Nur eine Schicht** steht bei allem anderen zwischen Angriff und Erfolg, siehe unten. Die wichtigste: **`email` ist
  allein durch die Spaltenrechte geschützt.** Das Modell sieht die Spalte im Schema, der Harness filtert nichts.
- **Keine Schicht:** Metadaten im Katalog (Tabellen- und Rollennamen) sind lesbar. Das ist in Postgres üblich und hier
  unkritisch, aber kein Schutz.

## Matrix: Schicht × Angriffsart

| Angriffsart | Modell | Harness / App | Datenbank | Schichten |
|---|---|---|---|---|
| Schreiben (INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE, ALTER) | nicht gemessen (UC6) | – (Schreibversuche gehen als Fehler an das Modell zurück: `test_sql_fehler_und_schreibversuch_gehen_als_fehler_zurueck`) | **stoppt** zweifach: fehlende Rechte, auch bei umgestellter Sitzung (`test_schreiben_wird_von_der_datenbank_abgewiesen`), und read-only als Voreinstellung (`test_rolle_ist_standardmaessig_read_only`) | 2 |
| Anweisungsketten (`…; …`) | nicht gemessen (UC6) | **stoppt**: nur eine Anweisung je Ausführung, sonst wird nichts ausgeführt (`test_nur_eine_anweisung_je_ausfuehrung`) | stoppt den gefährlichen Teil wie beim Schreiben | 2 |
| Rechte weitergeben (GRANT) | nicht gemessen (UC6) | – | **stoppt**: keine Grant-Option, `PUBLIC` bekommt nichts (`test_weitergeben_von_rechten_bleibt_wirkungslos`) | 1 |
| Personendaten (`customers.email`) | nicht gemessen (UC6) | – | **stoppt**: Spaltenrechte; auch `SELECT *` auf `customers` scheitert (`test_email_ist_fuer_analyst_ro_gesperrt`) | **1** |
| Dateien, Programme, Large Objects, Passwörter | nicht gemessen (UC6) | – | **stoppt**: keine Superuser-Rechte (`test_dateien_programme_und_passwoerter_sind_verboten`) | 1 |
| Katalog ausspähen (Tabellen, Rollen) | nicht gemessen (UC6) | – | **stoppt nicht**: Namen und Rechte-Flags sind lesbar, Passwörter nur als `********` (`test_katalog_zeigt_rollen_aber_keine_passwoerter`) | 0 |
| Andere Datenbanken im Neon-Projekt | nicht gemessen (UC6) | – | **stoppt**: keine Rechte in `neondb` (`test_kein_zugriff_auf_andere_datenbanken_des_projekts`) | 1 |
| Erweiterungen für Fremdzugriffe (dblink, fdw) | nicht gemessen (UC6) | – | **stoppt**: nicht installiert (`test_zeitlimit_und_keine_erweiterungen`) | 1 |
| Lange Abfrage | nicht gemessen (UC6) | begrenzt die Zahl: höchstens 5 Ausführungen je Frage (`test_hoechstens_fuenf_sql_ausfuehrungen`) | **stoppt** jede einzelne nach 15 s (`test_zeitlimit_und_keine_erweiterungen`) | 1 je Abfrage |
| Große Ergebnismengen an das Modell | nicht gemessen (UC6) | **begrenzt** auf 50 Zeilen je Ausführung (`test_ergebnis_wird_auf_50_zeilen_gekuerzt_bewertung_nutzt_alle`) | – | 1 |
| Kosten je Frage | nicht gemessen (UC6) | **stoppt** vor dem Aufruf, der 0,05 USD überschreiten würde (`test_harte_kostengrenze_je_frage`, `test_kostengrenze_meldung`) | – | 1 |
| Kosten je Sitzung und Monat | nicht gemessen (UC6) | **stoppt**: 0,25 USD je Sitzung, 3,00 USD je Monat, Reserve vorab, auch bei parallelen Aufrufen (`test_sitzungsdeckel`, `test_monatsdeckel_fuer_alle_sitzungen`, `test_parallele_reservierung_ueberschreitet_den_deckel_nicht`) | – | 1 |
| Überlange Eingabe | nicht gemessen (UC6) | **kürzt** auf 300 Zeichen (`test_frage_wird_gekuerzt`) | – | 1 |
| App mit falscher Rolle betrieben (etwa Admin-URL) | – | **stoppt**: `current_user` muss `analyst_ro` sein (`test_app_verweigert_jede_rolle_ausser_analyst_ro`) | – | 1 |
| Verbindungsdaten in Fehlermeldungen | – | **stoppt**: nur der Fehlertyp wird gezeigt (`test_fehler_zeigt_keine_verbindungsdaten`) | – | 1 |

Dass die Spaltenrechte die Analyse nicht stören, belegt `test_alle_referenz_sql_laufen_mit_den_spaltenrechten`: Jede
Referenz-SQL des Goldsets läuft weiter.

## Wo nur eine Schicht steht

| Angriffsart | einzige Schicht | was passiert, wenn sie fehlt |
|---|---|---|
| Personendaten `email` | Spaltenrechte der Datenbank | Das Modell sieht `email` im Schema. Ohne die Spaltenrechte hätte nichts eine Abfrage darauf verhindert. |
| Rechte weitergeben | fehlende Grant-Option | Nur relevant, wenn die Rolle selbst mehr dürfte. |
| Dateien, Programme, Passwörter | keine Superuser-Rechte | Eine falsch angelegte Rolle (etwa mit `pg_read_server_files`) würde es erlauben. |
| Lange einzelne Abfrage | 15 s Timeout der Rolle | Eine Abfrage könnte die Datenbank lange belasten. Der Harness begrenzt nur die Anzahl, nicht die Dauer. |
| Kosten je Frage, Sitzung, Monat | Harness bzw. App | Ohne diese Grenzen gäbe es nur das Budget des API-Keys. |
| Betrieb mit falscher Rolle | Rollenprüfung der App | Mit der Admin-URL würden alle Datenbank-Schichten wegfallen. |

Die Datenbank-Schichten wirken unabhängig davon, was Modell und Harness tun. Deshalb stehen die wichtigsten Grenzen dort.
Die Rollenprüfung der App ist die Stelle, an der das ganze Konzept hängt: Sie stellt sicher, dass die Datenbank-Schichten
überhaupt greifen.

## Was diese Demo nicht abdeckt

- **Angriffe über das Modell selbst.** Ob das Modell schädliche Anweisungen ablehnt, sich per Prompt Injection umlenken
  lässt oder den System-Prompt preisgibt, ist hier nicht gemessen. Das gehört mit einer eigenen Angriffsliste nach UC6.
  Diese Übersicht zeigt nur, was passiert, *wenn* das Modell es versucht.
- **Indirekte Prompt Injection über Daten.** Texte in der Datenbank (etwa Kündigungsgründe), die das Modell als
  Anweisung liest. Unsere Daten sind synthetisch und enthalten keine solchen Texte (→ UC6).
- **Missbrauch legitimer Leserechte.** Wer die App benutzen darf, kann alles lesen, was `analyst_ro` lesen darf, und es
  sich zusammenfassen lassen, etwa Kundendaten in großen Mengen nach Land, Zeitzone und Anmeldedatum. Die Grenzen auf 50
  Zeilen (an das Modell) und 10 Zeilen (in der Antwortkarte) bremsen Listen, aber keine Aggregate über alle Kunden. Dagegen helfen nur engere Rechte
  (Aggregat-Views, Mindestgruppengrößen) oder Zugangskontrolle zur App, nicht die Schichten oben.
- **Kostenangriffe über viele Sitzungen.** Eine neue Sitzung ist ein neues Cookie und bekommt wieder 0,25 USD. Es bremst
  nur der Monatsdeckel von 3,00 USD für die ganze App; bis dahin kann ein einzelner Angreifer das Monatsbudget allein
  verbrauchen und die App für alle anderen sperren. Abhilfe beim Online-Gang (Branch f): Zugangscode oder persönliche
  Links wie in UC7, Rate-Limit je IP.
