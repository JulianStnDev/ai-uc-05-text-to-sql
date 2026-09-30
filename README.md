🇩🇪 [Deutsche Version](README_DE.md)

# UC5 — Text-to-SQL: An Analytics Copilot on Trap-Laden Data

> Status: in progress. Branch (a) is done: database, data and goldset. No model has been measured yet.

## Problem
Product and support teams at the fictional habit-tracker app FocusFlow ask business questions ("How much revenue did we make in Q2?", "How many customers cancelled in August?") and wait days for an analyst. A copilot that writes and runs SQL could answer in seconds, but only if the number is right. Text-to-SQL rarely fails on syntax. It fails on business rules the schema does not show: duplicate charges, store purchases in a separate table, cancellation vs. end of subscription, refunds, time zones, a misleadingly named column. And it should ask back when a question is ambiguous instead of guessing.

## PM Decision
Plan in three branches, each a pull request:
- **(a) Data and goldset (done):** a separate Neon Postgres database with realistic but made-up data and six traps built into the data; 25 German business questions with reference SQL and results computed from the database.
- **(b) Schema only:** the model sees the table definitions and nothing else.
- **(c) Schema + glossary:** the model also gets the business definitions ([docs/GLOSSAR.md](docs/GLOSSAR.md)).

The question is how much a glossary is worth compared to the schema alone. Before every paid step there is a cost estimate.

Why a real database with roles instead of a prompt rule: the copilot runs SQL as `analyst_ro`, which may only SELECT on the seven analysis tables. Postgres rejects INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE and ALTER even if the session is switched to read-write (proven by tests). Decisions: [docs/decisions.md](docs/decisions.md).

## Architecture Sketch
```
evals/goldset_fragen.py ──▶ scripts/goldset_berechnen.py ──(analyst_ro, UTC)──▶ Neon Postgres "analytics" (Frankfurt)
                                        │                                           ▲
                                        ▼                                           │ analytics_admin
                        evals/goldset.json, evals/goldset.md        scripts/daten_erzeugen.py → scripts/laden.py (seed 20260930)
```
- `db/schema.sql`: seven tables, no explanatory comments (it is all the model sees in branch b).
- `docs/DATA_NOTES.md`: the traps, for humans only, never part of a prompt.
- `docs/GLOSSAR.md`: business definitions (draft), only given to the model in branch (c).

## Data
600 customers, 265 subscriptions, 94 cancellations, 400 web payments, 366 store transactions, 33 refunds, 26,798 logins between 01.10.2025 and 30.09.2026, deterministic (fixed seed). Each trap changes the result of a naive query measurably:

| Trap | Question | correct | naive |
|---|---|---|---|
| Duplicate charges | Web revenue Sep. before refunds | 613.46 USD | 686.44 USD |
| Store vs. web | Revenue Q2 2026 | 3,109.63 USD | 1,592.48 USD |
| Cancellation ≠ end | Customers who cancelled in August | 55 | 18 |
| Refunds | Revenue May 2026 | 1,224.34 USD | 1,344.34 USD |
| Time zone | Logins between 6 and 9 a.m. | 6,696 | 3,695 |
| Misleading column | Running Pro subscriptions on 30.09. | 201 | 254 |

## Evaluation Results
Goldset: 25 questions in German, 15 unambiguous, 5 ambiguous (correct answer: a clarifying question, plus every interpretation with SQL and result), 5 aimed at the traps. Table: [evals/goldset.md](evals/goldset.md). Measurements follow in branches (b) and (c).

## Cost & Latency
- Cost per 1000 requests: pending (branch b)
- p95 latency: pending (branch b)
- Quality metric: pending (branch b)
- Branch (a) made no API calls. Neon runs in the free tier.

## Running Locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
NEON_OWNER_URL=... .venv/bin/python scripts/setup_db.py   # once: database, roles, writes .env
.venv/bin/python scripts/laden.py                          # create and fill tables (deterministic)
.venv/bin/python scripts/goldset_berechnen.py              # expected results as analyst_ro
.venv/bin/python -m pytest                                 # data, permissions, goldset (no API)
```

## Learnings
- **Every trap needs a counter-query.** Only when the naive query with exactly one mistake returns a different number is the trap real. The script aborts otherwise.
- **Check realism against the numbers.** The first version of the login data had 586 of 600 customers active in September because free users never went dormant. The measure would have been meaningless.
- **Fix the session time zone.** Date boundaries like `'2026-05-01'` depend on the session time zone; all scripts set UTC.

## What I Would Do Differently
Pending until the end of the use case.
