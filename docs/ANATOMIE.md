# Anatomie eines Laufs

Lern-Zwischenstufe zwischen Branch (b) und (c): Was geht bei einer Frage tatsächlich über die Leitung, warum wachsen die
Tokens, was verrät das Thinking, und was bewirkt ein zusätzlicher Satz im Prompt?

**Datenbasis.** Die Messprotokolle (`evals/laeufe/`) enthalten Tokens, SQL und Antwort, aber keine rohen Requests,
keine Textblöcke und kein Thinking. Deshalb gab es am 30.09.2026 einige neue Läufe mit Mitschnitt
(`scripts/anatomie.py`, Harness-Schalter `mitschnitt`, `zusatz` und `thinking_anzeigen`, in Messläufen alle aus):

| Datei in `evals/anatomie/` | Inhalt | Kosten |
|---|---|---|
| `mitschnitt_U01_haiku.json` | U01 mit Haiku, jeder Aufruf roh | 0,0065 USD |
| `mitschnitt_U02_haiku.json` | U02 mit Haiku, jeder Aufruf roh | 0,0067 USD |
| `mitschnitt_U01_sonnet_1.json` | U01 mit Sonnet, Thinking sichtbar geschaltet, hat aber nicht gedacht | 0,0098 USD |
| `mitschnitt_U01_sonnet_2.json` | U01 mit Sonnet, zweiter Versuch, diesmal mit Thinking (von Hand nachgestartet, gleiche Einstellungen) | 0,0046 USD |
| `zusatz_haiku.jsonl` | U01 und M02 je 5 × Haiku mit einem Satz mehr im Prompt | 0,0551 USD |
| | **zusammen (Budget 0,20 USD)** | **0,0827 USD** |

Die Mitschnitte sind neue Läufe, keine Wiederholungen der gemessenen. Sie zeigen typisches Verhalten, das zu den
Messungen passt: Haiku lag bei U01 in allen 4 gemessenen Läufen falsch und auch hier, U02 und Sonnet lagen richtig.
Unten gekürzt ist nur, was sich wiederholt, markiert mit `[gekürzt]` oder „wie oben“. `id`-Felder der Antworten sind
weggelassen.

## 1. Was ein Request enthält

Die API ist zustandslos. Jeder Aufruf schickt alles, was das Modell wissen soll: Modell, `system` (Anweisung und
Schema), `tools` (zwei Werkzeuge) und `messages` (bisheriger Dialog). Der erste Aufruf zu U01 mit Haiku, vollständig
bis auf das Schema:

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 8000,
  "system": "Du bist ein Analytics-Copilot für FocusFlow, eine Habit-Tracker-App mit Pro-Abos. Du beantwortest Business-Fragen,\nindem du SQL gegen eine PostgreSQL-Datenbank schreibst und ausführst. Du hast nur Lesezugriff.\n\nHeute ist der 30.09.2026. Die Datenbanksitzung läuft in UTC.\n\nVorgehen:\n- Prüfe deine Abfragen mit dem Werkzeug sql_ausfuehren (höchstens 5 Ausführungen je Frage).\n- Beende jede Frage mit dem Werkzeug antworten:\n  - art \"ergebnis\": Die Frage ist beantwortbar. Gib die SQL an, deren Ergebnis die Antwort ist, und einen kurzen Antworttext.\n  - art \"rueckfrage\": Die Frage ist mehrdeutig. Stelle eine kurze Rückfrage.\n  - art \"keine_daten\": Die Datenbank enthält die nötigen Informationen nicht. Erkläre kurz, was fehlt.\n\nSchema der Datenbank:\n```sql\n… 2.237 Zeichen db/schema.sql, wörtlich … [gekürzt]\n```",
  "tools": [
    {
      "name": "sql_ausfuehren",
      "description": "Führt eine SQL-Abfrage (PostgreSQL, nur lesend) aus und gibt Spalten und bis zu 50 Zeilen als JSON zurück.",
      "strict": true,
      "input_schema": {
        "type": "object",
        "properties": {
          "sql": {
            "type": "string",
            "description": "Eine SELECT-Abfrage"
          }
        },
        "required": [
          "sql"
        ],
        "additionalProperties": false
      }
    },
    {
      "name": "antworten",
      "description": "Beendet die Frage. art: ergebnis (mit SQL), rueckfrage oder keine_daten.",
      "strict": true,
      "input_schema": {
        "type": "object",
        "properties": {
          "art": {
            "type": "string",
            "enum": [
              "ergebnis",
              "rueckfrage",
              "keine_daten"
            ]
          },
          "text": {
            "type": "string",
            "description": "Antwort, Rückfrage oder Erklärung für den Nutzer"
          },
          "sql": {
            "type": "string",
            "description": "Bei ergebnis: die SQL der Antwort, sonst leer"
          }
        },
        "required": [
          "art",
          "text",
          "sql"
        ],
        "additionalProperties": false
      }
    }
  ],
  "cache_control": {
    "type": "ephemeral"
  },
  "messages": [
    {
      "role": "user",
      "content": "Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?"
    }
  ]
}
```

Wie viele Tokens davon auf welchen Teil entfallen, mit `count_tokens` gemessen (kostenlos):

| Teil | Haiku 4.5 | Sonnet 5.5 |
|---|---|---|
| Anweisung (13 Zeilen) | 287 | 383 |
| Schema (`db/schema.sql`, 2.237 Zeichen) | 622 | 1.156 |
| Werkzeuge (2 Definitionen) | 802 | 670 |
| Frage | 24 | 30 |
| Rahmen | 8 | 9 |
| **Input des ersten Aufrufs** | **1.743** | **2.248** |

Drei Beobachtungen:
- **Die Werkzeuge sind bei Haiku der größte Block.** Die zwei kurzen JSON-Definitionen kosten 802 Tokens, weil die API
  daraus zusätzlich eine eigene Anleitung zur Werkzeugnutzung erzeugt, die im Request nicht zu sehen ist.
- **Derselbe Text zählt bei Sonnet anders.** Sonnet 5.5 hat einen anderen Tokenizer: Das Schema braucht dort 86 % mehr
  Tokens, die Werkzeuge weniger. Tokenzahlen lassen sich zwischen Modellen nicht vergleichen, nur Kosten.
- **Der Modellname wird aufgelöst.** Angefragt wird `claude-haiku-4-5`, die Antwort meldet
  `claude-haiku-4-5-20251001`.

## 2. U02 mit Haiku: richtig, aber mit Umweg (2 Aufrufe)

*„Wie hoch war der NPS im dritten Quartal 2026?“* Die Datenbank hat keine Umfragedaten, richtig ist „keine Daten“.

**Aufruf 1, Response.** Haiku erkennt das Problem sofort, antwortet aber als freier Text statt mit dem Werkzeug
`antworten`. `stop_reason` ist `end_turn`, nicht `tool_use`:

```json
{
  "content": [
    {
      "text": "Ich muss eine Rückfrage stellen, denn die Datenbank enthält keine direkten Informationen für die NPS-Berechnung (Net Promoter Score).\n\nDie verfügbaren Tabellen enthalten:\n- Kundendaten (Signup, Land, Zeitzone, Premium-Status)\n- Abonnement- und Zahlungsinformationen\n- Login-Verlauf\n- Stornierungen und Rückerstattungen\n\n**Für die NPS-Berechnung benötigen Sie typischerweise:**\n- Umfragedaten mit Bewertungen (z.B. \"Wie wahrscheinlich empfehlen Sie FocusFlow weiter?\" auf einer 0-10 Skala)\n- oder eine abgeleitete Metrik (z.B. basierend auf Retention, Churn oder Login-Verhalten)\n\n**Mögliche Alternativen:**\n- Können Sie eine Retention-Rate oder Churn-Rate für Q3 2026 berechnen?\n- Gibt es eine separate Umfrage-Tabelle in der Datenbank, auf die ich zugreifen kann?\n- Sollen wir den NPS aus Kundenbehavior (z.B. Login-Frequenz, Retention) approximieren?\n\nBitte klären Sie, wie der NPS definiert sein soll oder welche alternative Metrik ich berechnen kann.",
      "type": "text"
    }
  ],
  "model": "claude-haiku-4-5-20251001",
  "role": "assistant",
  "stop_reason": "end_turn",
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "not_available",
    "input_tokens": 1736,
    "output_tokens": 352,
    "service_tier": "standard"
  }
}
```

Der Text nennt sich selbst „Rückfrage“, schlägt Ersatzmetriken vor und fragt nach einer Tabelle, die es nicht gibt. Für
den Harness ist das keine Antwort, weil kein Werkzeug benutzt wurde. Er hängt deshalb genau einmal eine Erinnerung an
(sonst zählt die Frage als falsch).

**Aufruf 2, Request** (System und Werkzeuge wie oben): Die Frage, Haikus Text als `assistant` und die Erinnerung als
`user`:

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 8000,
  "system": "Du bist ein Analytics-Copilot für FocusFlow, eine Habit-Tracker-App mit Pro-Abos. Du beantwortest Business-Fragen,\nindem du SQL gegen eine PostgreSQL-Datenbank schreibst und ausführst. Du hast nur Lesezugriff.\n\nHeute ist der 30.09.2026. Die Datenbanksitzung läuft in UTC.\n\nVorgehen:\n- Prüfe deine Abfragen mit dem Werkzeug sql_ausfuehren (höchstens 5 Ausführungen je Frage).\n- Beende jede Frage mit dem Werkzeug antworten:\n  - art \"ergebnis\": Die Frage ist beantwortbar. Gib die SQL an, deren Ergebnis die Antwort ist, und einen kurzen Antworttext.\n  - art \"rueckfrage\": Die Frage ist mehrdeutig. Stelle eine kurze Rückfrage.\n  - art \"keine_daten\": Die Datenbank enthält die nötigen Informationen nicht. Erkläre kurz, was fehlt.\n\nSchema der Datenbank:\n```sql\n… 2.237 Zeichen db/schema.sql, wörtlich … [gekürzt]\n```",
  "tools": "[… 2 Werkzeuge wie oben, unverändert …]",
  "cache_control": {
    "type": "ephemeral"
  },
  "messages": [
    {
      "role": "user",
      "content": "Wie hoch war der NPS im dritten Quartal 2026?"
    },
    {
      "role": "assistant",
      "content": [
        {
          "text": "Ich muss eine Rückfrage stellen, denn die Datenbank enthält keine direkten Informationen für die NPS-Berechnung (Net Promoter Score).\n\nDie verfügbaren Tabellen enthalten:\n- Kundendaten (Signup, Land, Zeitzone, Premium-Status)\n- Abonnement- und Zahlungsinformationen\n- Login-Verlauf\n- Stornierungen und Rückerstattungen\n\n**Für die NPS-Berechnung benötigen Sie typischerweise:**\n- Umfragedaten mit Bewertungen (z.B. \"Wie wahrscheinlich empfehlen Sie FocusFlow weiter?\" auf einer 0-10 Skala)\n- oder eine abgeleitete Metrik (z.B. basierend auf Retention, Churn oder Login-Verhalten)\n\n**Mögliche Alternativen:**\n- Können Sie eine Retention-Rate oder Churn-Rate für Q3 2026 berechnen?\n- Gibt es eine separate Umfrage-Tabelle in der Datenbank, auf die ich zugreifen kann?\n- Sollen wir den NPS aus Kundenbehavior (z.B. Login-Frequenz, Retention) approximieren?\n\nBitte klären Sie, wie der NPS definiert sein soll oder welche alternative Metrik ich berechnen kann.",
          "type": "text"
        }
      ]
    },
    {
      "role": "user",
      "content": "Bitte beende die Frage mit dem Werkzeug antworten."
    }
  ]
}
```

**Aufruf 2, Response.** Jetzt entscheidet Haiku sauber: `keine_daten`.

```json
{
  "content": [
    {
      "id": "toolu_01FH7nb711pRm9o2kc97xvoV",
      "caller": {
        "type": "direct"
      },
      "input": {
        "art": "keine_daten",
        "text": "Die Datenbank enthält keine NPS-Daten. Um den Net Promoter Score zu berechnen, benötigen wir Umfragedaten (z.B. Bewertungen auf einer 0-10 Skala zur Weiterempfehlungsbereitschaft). Die vorhandenen Tabellen enthalten keine solchen Umfrageinformationen. Es ist möglich, dass diese Daten in einer separaten Tabelle gespeichert sind, auf die ich keinen Zugriff habe, oder dass der NPS extern erfasst wird.",
        "sql": ""
      },
      "name": "antworten",
      "type": "tool_use"
    }
  ],
  "model": "claude-haiku-4-5-20251001",
  "role": "assistant",
  "stop_reason": "tool_use",
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "not_available",
    "input_tokens": 2110,
    "output_tokens": 222,
    "service_tier": "standard"
  }
}
```

Der Umweg kostet einen zweiten Aufruf mit 2.110 Input-Tokens. Er erklärt auch, warum U02 bei Haiku manchmal 1 und
manchmal 2 Aufrufe braucht.

## 3. U01: Haiku biegt falsch ab, Sonnet nicht

*„Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“* Die Datenbank erfasst keinen Marketingkanal.
`subscriptions.channel` (web, apple, google) ist der Abrechnungsweg des Abos. Richtig ist „keine Daten“.

### Haiku, Aufruf 1: hier biegt es falsch ab

```json
{
  "content": [
    {
      "text": "Ich werde eine Abfrage ausführen, um die Neukunden im März 2026 nach ihrem Registrierungskanal zu analysieren.",
      "type": "text"
    },
    {
      "id": "toolu_01E5hbLmfrzfSkLruYP2mtop",
      "caller": {
        "type": "direct"
      },
      "input": {
        "sql": "\nSELECT \n    s.channel,\n    COUNT(DISTINCT c.customer_id) as new_customers\nFROM customers c\nINNER JOIN subscriptions s ON c.customer_id = s.customer_id\nWHERE c.signup_at >= '2026-03-01'::timestamptz \n  AND c.signup_at < '2026-04-01'::timestamptz\n  AND s.started_at >= '2026-03-01'::timestamptz\n  AND s.started_at < '2026-04-01'::timestamptz\nGROUP BY s.channel\nORDER BY new_customers DESC;\n"
      },
      "name": "sql_ausfuehren",
      "type": "tool_use"
    }
  ],
  "model": "claude-haiku-4-5-20251001",
  "role": "assistant",
  "stop_reason": "tool_use",
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "not_available",
    "input_tokens": 1743,
    "output_tokens": 243,
    "service_tier": "standard"
  }
}
```

**➜ Die Abzweigung** steht im ersten Satz, noch vor jeder SQL: *„… nach ihrem **Registrierungskanal** zu
analysieren.“* Aus „Marketingkanal“ wird stillschweigend „Registrierungskanal“, und dafür gibt es eine Spalte, die
passend klingt: `subscriptions.channel`. Ab hier stellt Haiku die Frage nicht mehr, ob die Daten die Frage beantworten,
sondern nur noch, wie man die Spalte abfragt. Nebenbei zählt die SQL nur Neukunden, die schon im März ein Abo
abgeschlossen haben (17 von 54 Neukunden). Die Frage fragt aber nach allen Neukunden.

### Haiku, Aufruf 2: der Request wächst um die eigene Antwort und das Tool-Ergebnis

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 8000,
  "system": "Du bist ein Analytics-Copilot für FocusFlow, eine Habit-Tracker-App mit Pro-Abos. Du beantwortest Business-Fragen,\nindem du SQL gegen eine PostgreSQL-Datenbank schreibst und ausführst. Du hast nur Lesezugriff.\n\nHeute ist der 30.09.2026. Die Datenbanksitzung läuft in UTC.\n\nVorgehen:\n- Prüfe deine Abfragen mit dem Werkzeug sql_ausfuehren (höchstens 5 Ausführungen je Frage).\n- Beende jede Frage mit dem Werkzeug antworten:\n  - art \"ergebnis\": Die Frage ist beantwortbar. Gib die SQL an, deren Ergebnis die Antwort ist, und einen kurzen Antworttext.\n  - art \"rueckfrage\": Die Frage ist mehrdeutig. Stelle eine kurze Rückfrage.\n  - art \"keine_daten\": Die Datenbank enthält die nötigen Informationen nicht. Erkläre kurz, was fehlt.\n\nSchema der Datenbank:\n```sql\n… 2.237 Zeichen db/schema.sql, wörtlich … [gekürzt]\n```",
  "tools": "[… 2 Werkzeuge wie oben, unverändert …]",
  "cache_control": {
    "type": "ephemeral"
  },
  "messages": [
    "… Frage wie in Aufruf 1 …",
    {
      "role": "assistant",
      "content": [
        {
          "text": "Ich werde eine Abfrage ausführen, um die Neukunden im März 2026 nach ihrem Registrierungskanal zu analysieren.",
          "type": "text"
        },
        {
          "id": "toolu_01E5hbLmfrzfSkLruYP2mtop",
          "caller": {
            "type": "direct"
          },
          "input": {
            "sql": "\nSELECT \n    s.channel,\n    COUNT(DISTINCT c.customer_id) as new_customers\nFROM customers c\nINNER JOIN subscriptions s ON c.customer_id = s.customer_id\nWHERE c.signup_at >= '2026-03-01'::timestamptz \n  AND c.signup_at < '2026-04-01'::timestamptz\n  AND s.started_at >= '2026-03-01'::timestamptz\n  AND s.started_at < '2026-04-01'::timestamptz\nGROUP BY s.channel\nORDER BY new_customers DESC;\n"
          },
          "name": "sql_ausfuehren",
          "type": "tool_use"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_01E5hbLmfrzfSkLruYP2mtop",
          "is_error": false,
          "content": "{\"spalten\": [\"channel\", \"new_customers\"], \"zeilen\": [[\"web\", 9], [\"apple\", 6], [\"google\", 2]], \"anzahl_zeilen\": 3}"
        }
      ]
    }
  ]
}
```

### Haiku, Aufruf 2: Response

```json
{
  "content": [
    {
      "id": "toolu_01Rk4WtRV9k613poudsA41WB",
      "caller": {
        "type": "direct"
      },
      "input": {
        "art": "ergebnis",
        "text": "Im März 2026 kamen die meisten Neukunden über den **Web-Kanal** mit 9 neuen Kunden. Es folgen Apple mit 6 Neukunden und Google mit 2 Neukunden.",
        "sql": "\nSELECT \n    s.channel,\n    COUNT(DISTINCT c.customer_id) as new_customers\nFROM customers c\nINNER JOIN subscriptions s ON c.customer_id = s.customer_id\nWHERE c.signup_at >= '2026-03-01'::timestamptz \n  AND c.signup_at < '2026-04-01'::timestamptz\n  AND s.started_at >= '2026-03-01'::timestamptz\n  AND s.started_at < '2026-04-01'::timestamptz\nGROUP BY s.channel\nORDER BY new_customers DESC;\n"
      },
      "name": "antworten",
      "type": "tool_use"
    }
  ],
  "model": "claude-haiku-4-5-20251001",
  "role": "assistant",
  "stop_reason": "tool_use",
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "inference_geo": "not_available",
    "input_tokens": 2042,
    "output_tokens": 290,
    "service_tier": "standard"
  }
}
```

Das Ergebnis der Probe-Abfrage (web 9, apple 6, google 2) sieht plausibel aus, also wird es zur Antwort. Nichts im
Ablauf zwingt Haiku, die Deutung noch einmal zu prüfen. In den gemessenen Läufen kamen mal 9/6/2 heraus, mal 13/7/2,
je nachdem, ob die SQL zusätzlich auf den Abo-Start im März filtert. Die Deutung war jedes Mal dieselbe.

### Sonnet bei derselben Frage: ein Aufruf

Request (System und Werkzeuge wie oben, dazu Effort und das sichtbar geschaltete Thinking):

```json
{
  "model": "claude-sonnet-5-5",
  "max_tokens": 8000,
  "cache_control": {
    "type": "ephemeral"
  },
  "output_config": {
    "effort": "medium"
  },
  "thinking": {
    "type": "adaptive",
    "display": "summarized"
  },
  "messages": [
    {
      "role": "user",
      "content": "Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?"
    }
  ]
}
```

Response:

```json
{
  "content": [
    {
      "signature": "CAQSowYKEAgSGAI4AUIIdGhpbmtpbmcSDObRjF9I… (1080 Zeichen) [gekürzt]",
      "thinking": "The schema doesn't track marketing or acquisition channels — the \"channel\" field in subscriptions just refers to billing platform (web/apple/google), not marketing source. So there's no data to answer this; no need to query further.\n\n",
      "type": "thinking"
    },
    {
      "id": "toolu_012goEcKV2pGqtJs5davXfHU",
      "caller": {
        "type": "direct"
      },
      "input": {
        "art": "keine_daten",
        "text": "Das kann ich mit den vorhandenen Daten nicht beantworten, weil die Datenbank keine Marketingkanäle erfasst. Die Tabelle customers enthält keine Akquisequelle, Kampagne, UTM-Parameter oder Referrer. Die Spalte subscriptions.channel (web/apple/google) zeigt nur, über welchen Zahlungsweg oder Store abgerechnet wird. Das ist kein Marketingkanal. Ich kann stattdessen auswerten, wie viele Neukunden im März 2026 sich angemeldet haben, nach Land oder nach Abrechnungskanal ihres ersten Abos. Dafür bräuchte ich Ihre Bestätigung.",
        "sql": ""
      },
      "name": "antworten",
      "type": "tool_use"
    }
  ],
  "model": "claude-sonnet-5-5",
  "role": "assistant",
  "stop_reason": "tool_use",
  "type": "message",
  "usage": {
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 2244,
    "inference_geo": "global",
    "input_tokens": 4,
    "output_tokens": 419,
    "output_tokens_details": {
      "thinking_tokens": 77
    },
    "service_tier": "standard"
  }
}
```

Sonnet fragt die Datenbank gar nicht erst ab. Das Schema reicht, um zu sehen, dass es keinen Marketingkanal gibt.
Genau die Spalte, bei der Haiku abbiegt, benennt Sonnet ausdrücklich als Falle („Bezahlweg, nicht Marketingkanal“).
Danach bietet es sinnvolle Ersatzfragen an, führt sie aber nicht ungefragt aus. Das ist der Unterschied zu Haiku: Ein
Ersatz ist erlaubt, wenn er offen als Angebot kommt, nicht als Antwort getarnt.

| | Haiku | Sonnet |
|---|---|---|
| Aufrufe | 2 | 1 |
| Input-Tokens gesamt | 3.785 | 2.248 (davon 2.244 aus dem Cache gelesen) |
| Output-Tokens | 533 | 419 (davon 77 Thinking) |
| Kosten | 0,0065 USD | 0,0046 USD |
| Ergebnis | Ersatz-Abfrage, falsch | keine Daten, richtig |

Hier ist Sonnet sogar billiger: ein Aufruf statt zwei, und der Prompt kommt fast vollständig aus dem Cache.

## 4. Wie die Input-Tokens von Aufruf zu Aufruf wachsen

Weil die API keinen Zustand hält, schickt jeder Aufruf den ganzen bisherigen Dialog noch einmal. Der Input von Aufruf
n+1 ist deshalb ungefähr:

> Input(n) + Output(n) + das, was der Harness anhängt (Tool-Ergebnis oder Erinnerung)

| Lauf | Aufruf 1 | Aufruf 2 | Aufruf 3 | Aufruf 4 | angehängt |
|---|---|---|---|---|---|
| U01 Haiku (Mitschnitt) | 1.743 | 2.042 | | | 243 Output + 56 Tool-Ergebnis |
| U02 Haiku (Mitschnitt) | 1.736 | 2.110 | | | 352 Output + 22 Erinnerung |
| E06 Haiku (Pilot) | 1.759 | 3.138 | 3.351 | 3.541 | nach Aufruf 1: 194 Output + ca. 1.185 Tool-Ergebnis |

Bei U01 geht die Rechnung exakt auf: 1.743 + 243 + 56 = 2.042. Bei U02 genauso: 1.736 + 352 + 22 = 2.110. Zwei Dinge
treiben die Kosten:
- **Große Tool-Ergebnisse.** Bei E06 hat die erste Probe-Abfrage viele Zeilen geliefert. Das Ergebnis reist danach in
  jedem weiteren Aufruf mit. Deshalb begrenzt der Harness die Zeilen auf 50.
- **Die Summe, nicht der letzte Aufruf.** Bezahlt wird jeder Aufruf voll. E06 hatte 4 Aufrufe mit zusammen 11.789
  Input-Tokens, fast siebenmal so viel wie ein einzelner Prompt.

**Mit Cache (Sonnet)** sieht dasselbe Wachstum anders aus. Das automatische Caching setzt die Marke ans Ende des
Requests, der ganze bisherige Dialog wird also zum Präfix des nächsten Aufrufs. Beispiel F02, Sonnet, voller Lauf:

| Aufruf | ungecacht | aus dem Cache gelesen | in den Cache geschrieben |
|---|---|---|---|
| 1 | 4 | 0 | 2.245 |
| 2 | 2 | 2.245 | 619 |
| 3 | 2 | 2.864 | 498 |
| 4 | 2 | 3.362 | 228 |
| 5 | 2 | 3.590 | 634 |

Neu bezahlt wird je Aufruf nur, was dazukommt (Schreiben kostet 1,25 × Input). Der Rest kostet 0,1 ×. Bei Haiku
passiert das nicht, weil der Prompt unter Haikus Cache-Minimum von 4.096 Tokens liegt.

## 5. Thinking: was man ablesen kann und was nicht

Der Thinking-Block aus Sonnets Antwort zu U01 (oben vollständig):

```json
{
  "signature": "CAQSowYKEAgSGAI4AUIIdGhpbmtpbmcSDObRjF9I… (1080 Zeichen) [gekürzt]",
  "thinking": "The schema doesn't track marketing or acquisition channels — the \"channel\" field in subscriptions just refers to billing platform (web/apple/google), not marketing source. So there's no data to answer this; no need to query further.\n\n",
  "type": "thinking"
}
```

**Was man ablesen kann:**
- **Den Entscheidungsweg in Kurzform.** Sonnet prüft das Schema, erkennt `channel` als Abrechnungsweg und entscheidet
  ausdrücklich, keine Abfrage zu starten („no need to query further“). Die Antwort passt dazu.
- **Wie viel gedacht wurde.** `usage.output_tokens_details.thinking_tokens` = 77. Diese Tokens sind als Output bezahlt.
- **Dass adaptives Thinking wirklich adaptiv ist.** Im ersten Versuch hat Sonnet bei derselben Frage gar nicht gedacht
  (`thinking_tokens: 0`) und kam trotzdem zum richtigen Ergebnis. Auf Effort `medium` hält es U01 offenbar für leicht.

**Was man nicht ablesen kann:**
- **Den tatsächlichen Gedankengang.** Mit `display: "summarized"` kommt eine Zusammenfassung zurück, nicht das rohe
  Thinking. Das rohe Thinking gibt die API bei keinem Modell heraus. In der Messung (`display` nicht gesetzt, also
  `"omitted"`) ist das Feld leer.
- **Ob die Zusammenfassung vollständig oder getreu ist.** Sie klingt plausibel und passt zur Antwort, aber das ist
  keine Garantie dafür, dass genau diese Überlegung die Antwort erzeugt hat.
- **Die `signature`.** Sie ist verschlüsselt und nicht lesbar. Sie beweist der API, dass der Block echt ist, wenn der
  Harness ihn im nächsten Aufruf zurückschickt. Deshalb reicht der Harness Thinking-Blöcke unverändert zurück.

Die Anzeige ändert am Verhalten nichts: `display` steuert nur die Sichtbarkeit. Gedacht und bezahlt wird gleich.

## 6. Ein Satz Prompt

Am Ende des System-Prompts stand zusätzlich:

> Wenn die Daten eine Frage nicht beantworten oder sie mehrdeutig ist, sag das oder frag nach, statt eine ähnliche
> Spalte oder eine eigene Deutung zu verwenden.

| Frage | Haiku ohne Satz (Pilot + voller Lauf) | Haiku mit Satz | Antwort mit Satz |
|---|---|---|---|
| U01 Marketingkanal | 0/4 | **0/5** | 5 × Abo-Kanal als Marketingkanal (web 9–16) |
| M02 „Wie viele Kunden haben wir?“ | 0/4 | **0/5** | 5 × „FocusFlow hat 600 Kunden.“ |

**Kein Effekt.** Die Antworten mit dem Satz sind fast wortgleich mit denen ohne. Die Anweisung greift nur, wenn das
Modell die Situation als „passt nicht“ oder „mehrdeutig“ erkennt. Genau das tut Haiku hier nicht: Für Haiku *ist*
`channel` der Marketingkanal, und „Kunden“ *sind* die Zeilen in `customers`. Eine Regel über das Verhalten hilft nicht,
wenn das Wissen fehlt, das die Regel auslösen würde.

Das ist ein Hinweis für Branch (c): Nicht noch mehr Verhaltensregeln, sondern Fakten. Das Glossar sagt, was
`channel` bedeutet, dass es keinen Marketingkanal gibt und welche Definitionen von „Kunde“ es gibt.

Einschränkungen: 5 Läufe je Frage, ein Satz, eine Position (Ende des System-Prompts), nur Haiku. Ob der Satz bei
Sonnet etwas ändert, ist nicht gemessen. Sonnet fragt dort ohnehin schon fast immer nach.

## Kurz gesagt

1. Ein Request ist immer vollständig: System, Werkzeuge, ganzer Dialog. Bei Haiku kosten die Werkzeuge mehr Tokens
   als das Schema.
2. Input wächst je Aufruf um den eigenen Output und das Tool-Ergebnis. Bezahlt wird die Summe aller Aufrufe. Caching
   macht das bei Sonnet fast kostenlos, bei Haiku greift es nicht.
3. Falsche Antworten entstehen oft im ersten Satz, nicht in der SQL: Haiku deutet die Frage um, bevor es eine Zeile
   schreibt.
4. Thinking zeigt eine Zusammenfassung der Entscheidung, nicht den Beweis dafür.
5. Ein Satz Verhaltensregel ändert nichts, wenn das Modell die Lücke nicht sieht. Fakten sind die Aufgabe des Glossars.
