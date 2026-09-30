# Deployment auf Cloud Run (Frankfurt)

Live: https://uc5-807149335205.europe-west3.run.app (Revision uc5-00001, deployt 2026-09-30).
Stand 2026-09-30. Gleiches Projekt wie UC7: `focusflow-demo-510014`, Region `europe-west3`, Dienst `uc5`.
Öffentlich ohne Code: Galerie (alle gemessenen Läufe, ohne API-Kosten), `/health`, `/login`. Live-Fragen (Ask,
Compare) nur mit Zugangscode. Deckel: 0,05 USD je Frage, 0,25 USD je Sitzung, 3,00 USD im Monat.

## Einmalige Einrichtung

APIs (`run`, `cloudbuild`, `artifactregistry`, `secretmanager`) und der Budgetalarm (5 EUR) des Projekts stammen aus
UC7 (siehe dort `docs/deploy.md`). Zusätzlich:

### Kostenbuch (Neon)

```bash
# NEON_OWNER_URL vorübergehend in .env, danach die Zeile wieder löschen
.venv/bin/python scripts/setup_kostenbuch.py
```
Legt die Datenbank `uc5_app` mit eigener Rolle `uc5_app` an und schreibt `KOSTEN_DB_URL` in die `.env`. Die App braucht
den Owner-Zugang nie; sie liest nur `ANALYTICS_RO_URL` (analyst_ro) und `KOSTEN_DB_URL`.

### Laufzeit-Konto und Secrets

```bash
gcloud iam service-accounts create uc5-run   # existiert seit 2026-09-30 --display-name="UC5 Cloud Run (liest nur UC5-Secrets)"

# Werte aus der lokalen .env, per stdin, ohne Anzeige
for NAME in ANTHROPIC_API_KEY ANALYTICS_RO_URL KOSTEN_DB_URL SESSION_SECRET ZUGANGSCODE; do
  SID="uc5-$(echo $NAME | tr 'A-Z_' 'a-z-')"
  .venv/bin/python -c "import sys;from dotenv import dotenv_values;sys.stdout.write(dotenv_values('.env')['$NAME'])" \
    | gcloud secrets create $SID --replication-policy=automatic --data-file=-
  gcloud secrets add-iam-policy-binding $SID \
    --member=serviceAccount:uc5-run@focusflow-demo-510014.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor
done
```
Das Laufzeit-Konto darf nur diese fünf Secrets lesen, sonst nichts. `ANTHROPIC_API_KEY` ist der eigene Key
„uc5-text-to-sql“ (Ausgabenlimit in der Anthropic Console, gesetzt von Julian). Neue Version eines Secrets:
`gcloud secrets versions add …`, dann im Deploy-Befehl die Versionsnummer erhöhen (Versionen sind fest, nicht `latest`).

## Deploy

```bash
gcloud run deploy uc5 --source . --region europe-west3 \
  --service-account uc5-run@focusflow-demo-510014.iam.gserviceaccount.com \
  --cpu 1 --memory 512Mi --min-instances 0 --max-instances 2 --concurrency 8 --timeout 120 \
  --allow-unauthenticated --set-env-vars COOKIE_SECURE=1 \
  --set-secrets ANTHROPIC_API_KEY=uc5-anthropic-api-key:1,ANALYTICS_RO_URL=uc5-analytics-ro-url:1,KOSTEN_DB_URL=uc5-kosten-db-url:1,SESSION_SECRET=uc5-session-secret:1,ZUGANGSCODE=uc5-zugangscode:1
```

- `--source .` baut mit dem `Dockerfile` per Cloud Build. `.gcloudignore` schließt `.env`, `.venv`, `daten/` und die
  Tests aus.
- `--allow-unauthenticated` heißt nur: kein Google-Konto nötig. Was Geld kostet, sperrt die App selbst per Zugangscode.
- `--max-instances 2`, `--min-instances 0`: keine Kosten ohne Besucher; der Monatsdeckel liegt im Kostenbuch
  (Postgres), gilt also über alle Instanzen.
- `--timeout 120`: Eine Frage dauert 5–20 s; die harte Grenze von 0,05 USD beendet sie vorher.

## Prüfen

```bash
URL=$(gcloud run services describe uc5 --region europe-west3 --format='value(status.url)')
curl $URL/health                        # {"ok":true}
curl -s -o /dev/null -w "%{http_code}\n" $URL/gallery     # 200 ohne Code
curl -s -o /dev/null -w "%{http_code}\n" $URL/            # 303 → /login
```
Eine echte Frage mit Zugangscode (im Browser) kostet etwa 0,01 USD und erscheint danach im Kostenbuch (`uc5_app.kosten`).
