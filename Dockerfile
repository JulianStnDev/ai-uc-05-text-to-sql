# FocusFlow Analytics Copilot (Branch d2). Für Cloud Run gebaut (Branch f): Port aus $PORT, Nutzer ohne Root,
# Zustand nur in Datenbanken (Kostenbuch per KOSTEN_DB_URL), Secrets per Umgebung (Secret Manager), nie im Image.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 DATEN_DIR=/tmp/daten
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Nur was die App braucht: Code, Harness, Schema, Glossar, Goldset und die gemessenen Läufe (Galerie).
COPY app/ app/
COPY scripts/copilot.py scripts/vergleich.py scripts/
COPY db/schema.sql db/
COPY docs/GLOSSAR.md docs/
COPY evals/goldset.json evals/
COPY evals/laeufe/ evals/laeufe/

RUN useradd --uid 1000 --create-home copilot
USER copilot

CMD ["sh", "-c", "exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
