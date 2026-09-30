# Anatomie eines Laufs

Was passiert genau, wenn der Copilot eine Frage beantwortet? Dieses Dokument schaut einem Lauf über die Schulter.
Es beantwortet vier Fragen:

1. Was schickt der Copilot an das Modell, und was kommt zurück?
2. Warum wird jeder Aufruf größer als der vorige?
3. Was verrät das „Thinking“ (Nachdenken) des Modells?
4. Hilft ein einzelner Satz mehr im Prompt?

## Ein paar Begriffe vorab

- **Aufruf:** Der Copilot schickt eine Anfrage an das Modell (den **Request**) und bekommt eine Antwort (die
  **Response**). Für eine Frage braucht er meist 1 bis 3 Aufrufe.
- **Token:** Ein Textstück, etwa ein kurzes Wort oder ein Wortteil. Bezahlt wird je Token, getrennt nach dem, was
  hineingeht (**Input**) und was herauskommt (**Output**).
- **Werkzeug (Tool):** Eine Funktion, die das Modell benutzen darf. Hier gibt es zwei: `sql_ausfuehren` (eine Abfrage
  an die Datenbank schicken) und `antworten` (die Frage beenden).
- **Cache:** Ein Zwischenspeicher bei der API. Schickt man denselben Anfang noch einmal, kostet er nur ein Zehntel.

## Woher die Daten kommen

Die Messprotokolle speichern nur Tokens, SQL und Antwort. Den ganzen Request sieht man dort nicht. Deshalb gab es am
30.09.2026 ein paar neue Läufe, bei denen alles mitgeschnitten wurde (`scripts/anatomie.py`). In den Messläufen ist
dieser Mitschnitt immer ausgeschaltet.

| Datei in `evals/anatomie/` | Was drin ist | Kosten |
|---|---|---|
| `mitschnitt_U01_haiku.json` | Frage U01 mit Haiku, jeder Aufruf komplett | 0,0065 USD |
| `mitschnitt_U02_haiku.json` | Frage U02 mit Haiku, jeder Aufruf komplett | 0,0067 USD |
| `mitschnitt_U01_sonnet_1.json` | Frage U01 mit Sonnet, erster Versuch (Sonnet hat nicht nachgedacht) | 0,0098 USD |
| `mitschnitt_U01_sonnet_2.json` | Frage U01 mit Sonnet, zweiter Versuch mit Nachdenken (von Hand nachgestartet, gleiche Einstellungen) | 0,0046 USD |
| `zusatz_haiku.jsonl` | U01 und M02 je 5-mal mit Haiku, mit einem Satz mehr im Prompt | 0,0551 USD |
| | **zusammen (Budget 0,20 USD)** | **0,0827 USD** |

Das sind neue Läufe, keine Kopien der gemessenen. Sie verhalten sich aber wie in der Messung: Haiku lag bei U01 schon
viermal falsch und auch hier wieder. U02 und Sonnet lagen richtig.

In den JSON-Ausschnitten unten ist nur gekürzt, was sich wiederholt. Solche Stellen sind mit `[gekürzt]` oder „wie
oben“ markiert. Die `id` der Antworten ist weggelassen.

## 1. Was im Request steht

Das Modell merkt sich nichts zwischen zwei Aufrufen. Darum schickt der Copilot jedes Mal alles mit:

- `model`: welches Modell antworten soll
- `system`: die Anweisung an den Copiloten und das Datenbankschema
- `tools`: die beiden Werkzeuge
- `messages`: das bisherige Gespräch

So sah der erste Aufruf zu U01 mit Haiku aus. Nur das Schema ist gekürzt:

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

Wie viele Tokens entfallen auf welchen Teil? Gezählt mit `count_tokens`, das kostet nichts:

| Teil | Haiku 4.5 | Sonnet 5.5 |
|---|---|---|
| Anweisung (13 Zeilen) | 287 | 383 |
| Schema (`db/schema.sql`) | 622 | 1.156 |
| Werkzeuge (2 Beschreibungen) | 802 | 670 |
| Frage | 24 | 30 |
| Rahmen | 8 | 9 |
| **Input beim ersten Aufruf** | **1.743** | **2.248** |

Was daran auffällt:
- **Bei Haiku kosten die Werkzeuge am meisten.** Die zwei kurzen Beschreibungen zählen 802 Tokens, mehr als das ganze
  Schema. Der Grund: Die API baut aus den Werkzeugen selbst noch eine Anleitung. Die steht nicht im Request, wird aber
  mitgezählt.
- **Sonnet zählt anders.** Derselbe Text ergibt bei Sonnet andere Token-Zahlen, beim Schema 86 % mehr. Token-Zahlen
  kann man also nicht zwischen Modellen vergleichen. Vergleichen kann man die Kosten.
- **Der Modellname wird ergänzt.** Wir fragen `claude-haiku-4-5` an. In der Antwort steht
  `claude-haiku-4-5-20251001`.

## 2. U02 mit Haiku: richtig, aber mit einem Umweg

Frage U02: *„Wie hoch war der NPS im dritten Quartal 2026?“*

Der NPS ist eine Kennzahl aus Kundenumfragen. Umfragen gibt es in der Datenbank nicht. Die richtige Antwort ist also
„keine Daten“.

**Aufruf 1, Antwort des Modells.** Haiku merkt sofort, dass Umfragedaten fehlen. Aber es antwortet mit freiem Text,
nicht mit dem Werkzeug `antworten`. Man sieht das an `stop_reason: "end_turn"`. Bei einer Werkzeugnutzung stünde dort
`"tool_use"`.

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

Der Copilot braucht aber das Werkzeug `antworten`, sonst gibt es keine Antwort, die er bewerten kann. Also schickt er
einmal eine Erinnerung.

**Aufruf 2, Request.** System und Werkzeuge sind gleich wie oben. Im Gespräch stehen jetzt drei Nachrichten: die Frage,
Haikus Text und die Erinnerung.

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

**Aufruf 2, Antwort.** Jetzt benutzt Haiku das Werkzeug und antwortet richtig mit `keine_daten`:

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

Der Umweg kostet einen zweiten Aufruf mit 2.110 Input-Tokens. Er erklärt auch, warum Haiku für U02 mal einen und mal
zwei Aufrufe braucht.

## 3. U01: Haiku biegt falsch ab, Sonnet nicht

Frage U01: *„Über welchen Marketingkanal kamen im März 2026 die meisten Neukunden?“*

Die Datenbank speichert nicht, über welche Werbung ein Kunde kam. Es gibt zwar eine Spalte `channel` in der Tabelle
`subscriptions`. Sie sagt aber nur, wie ein Abo bezahlt wird: im Web, über Apple oder über Google. Die richtige
Antwort ist also „keine Daten“.

### Haiku, Aufruf 1: Hier passiert der Fehler

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

**➜ Der Fehler steckt im ersten Satz, noch vor der SQL.** Haiku schreibt: *„… nach ihrem **Registrierungskanal** zu
analysieren.“* Aus „Marketingkanal“ ist unbemerkt „Registrierungskanal“ geworden. Und dafür gibt es eine Spalte, die
passend klingt: `channel`. Ab jetzt fragt Haiku nicht mehr: „Gibt es diese Daten überhaupt?“ Es fragt nur noch: „Wie
frage ich diese Spalte ab?“

Dazu kommt ein zweiter, kleinerer Fehler: Die SQL zählt nur Neukunden, die schon im März ein Abo abgeschlossen haben.
Das sind 17 von 54 Neukunden. Gefragt war nach allen.

### Haiku, Aufruf 2: der Request wird größer

Zum Gespräch kommen Haikus eigene Antwort aus Aufruf 1 und das Ergebnis der Abfrage dazu:

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

### Haiku, Aufruf 2: die Antwort

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

Das Ergebnis (web 9, apple 6, google 2) sieht plausibel aus. Also macht Haiku es zur Antwort. Nichts im Ablauf bringt
Haiku dazu, seine Deutung noch einmal zu prüfen. In den gemessenen Läufen kamen mal 9/6/2 und mal 13/7/2 heraus, je
nach Filter. Die falsche Deutung war jedes Mal dieselbe.

### Sonnet bei derselben Frage: ein einziger Aufruf

Request (System und Werkzeuge wie oben, dazu die Einstellungen für das Nachdenken):

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

Antwort:

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

Sonnet fragt die Datenbank gar nicht erst ab. Das Schema reicht ihm, um zu sehen: Einen Marketingkanal gibt es nicht.
Genau die Spalte, an der Haiku falsch abbiegt, erklärt Sonnet ausdrücklich: Sie beschreibt den Bezahlweg, nicht den
Marketingkanal. Danach schlägt Sonnet andere Auswertungen vor, führt sie aber nicht ungefragt aus.

Das ist der eigentliche Unterschied: Einen Ersatz vorzuschlagen ist in Ordnung. Einen Ersatz als Antwort auszugeben,
ohne es zu sagen, ist es nicht.

| | Haiku | Sonnet |
|---|---|---|
| Aufrufe | 2 | 1 |
| Input-Tokens | 3.785 | 2.248 (davon 2.244 aus dem Cache) |
| Output-Tokens | 533 | 419 (davon 77 fürs Nachdenken) |
| Kosten | 0,0065 USD | 0,0046 USD |
| Ergebnis | Ersatz-Abfrage, falsch | keine Daten, richtig |

Hier ist Sonnet sogar billiger als Haiku. Es braucht nur einen Aufruf, und der Prompt kommt fast ganz aus dem Cache.

## 4. Warum jeder Aufruf größer wird

Das Modell merkt sich nichts. Darum schickt jeder Aufruf das ganze bisherige Gespräch noch einmal. Der nächste Aufruf ist
deshalb so groß wie:

> der vorige Input + die vorige Antwort des Modells + was der Copilot anhängt (Abfrage-Ergebnis oder Erinnerung)

Bei den beiden Mitschnitten geht die Rechnung genau auf:

| Lauf | Aufruf 1 | + Antwort | + angehängt | = Aufruf 2 |
|---|---|---|---|---|
| U01 Haiku | 1.743 | 243 | 56 (Abfrage-Ergebnis) | 2.042 |
| U02 Haiku | 1.736 | 352 | 22 (Erinnerung) | 2.110 |

Zwei Dinge machen einen Lauf teuer:
- **Große Abfrage-Ergebnisse.** Ein Ergebnis reist in jedem weiteren Aufruf mit. Bei Frage E06 im Pilot kamen nach
  der ersten Abfrage etwa 1.185 Tokens dazu (1.759 → 3.138). Deshalb gibt der Copilot dem Modell höchstens 50 Zeilen.
- **Jeder Aufruf wird voll bezahlt.** E06 hatte 4 Aufrufe mit zusammen 11.789 Input-Tokens. Das ist fast siebenmal so
  viel wie ein einzelner Prompt.

**Mit Cache (Sonnet) wird das Wachstum billig.** Der Cache speichert das ganze bisherige Gespräch. Beim nächsten Aufruf
kostet dieser Teil nur ein Zehntel. Voll bezahlt wird nur das, was neu dazukommt. Beispiel Frage F02, Sonnet:

| Aufruf | neu, ohne Cache | aus dem Cache gelesen | neu in den Cache geschrieben |
|---|---|---|---|
| 1 | 4 | 0 | 2.245 |
| 2 | 2 | 2.245 | 619 |
| 3 | 2 | 2.864 | 498 |
| 4 | 2 | 3.362 | 228 |
| 5 | 2 | 3.590 | 634 |

Bei Haiku klappt das nicht. Der Cache springt erst ab 4.096 Tokens an, und unser Prompt ist kürzer.

## 5. Was das Nachdenken (Thinking) verrät

Sonnet kann vor der Antwort „nachdenken“. Wie viel, entscheidet es selbst. Beim ersten Versuch zu U01 hat es gar nicht
nachgedacht (0 Tokens) und trotzdem richtig geantwortet. Die Frage war ihm offenbar leicht genug. Beim zweiten Versuch
kam dieser Block:

```json
{
  "signature": "CAQSowYKEAgSGAI4AUIIdGhpbmtpbmcSDObRjF9I… (1080 Zeichen) [gekürzt]",
  "thinking": "The schema doesn't track marketing or acquisition channels — the \"channel\" field in subscriptions just refers to billing platform (web/apple/google), not marketing source. So there's no data to answer this; no need to query further.\n\n",
  "type": "thinking"
}
```

Auf Deutsch: *„Das Schema erfasst keine Marketing- oder Akquisekanäle. Das Feld ‚channel‘ in subscriptions ist nur die
Bezahlplattform (web/apple/google), nicht die Marketingquelle. Es gibt also keine Daten dafür. Eine Abfrage ist nicht
nötig.“*

**Was man daraus lernt:**
- **Wie Sonnet entschieden hat, in Kurzform.** Es hat das Schema geprüft, die Falle erkannt und bewusst auf eine Abfrage
  verzichtet. Das passt zur Antwort.
- **Wie viel es nachgedacht hat.** 77 Tokens. Sie werden als Output bezahlt.
- **Dass das Nachdenken nicht immer passiert.** Bei derselben Frage mal 0, mal 77 Tokens.

**Was man daraus nicht lernt:**
- **Die echten Gedanken.** Die API gibt nur eine Zusammenfassung heraus, nie das eigentliche Nachdenken. In der Messung
  ist das Feld sogar ganz leer, weil wir die Zusammenfassung dort nicht anfordern.
- **Ob die Zusammenfassung stimmt.** Sie klingt plausibel und passt zur Antwort. Ein Beweis, dass Sonnet genau so
  entschieden hat, ist sie nicht.
- **Was in `signature` steht.** Das ist ein verschlüsselter Echtheitsstempel. Der Copilot muss den Block damit
  unverändert zurückschicken, damit die API ihn im nächsten Aufruf annimmt.

Ob man die Zusammenfassung anfordert, ändert nichts daran, wie Sonnet nachdenkt. Es ändert nur, ob man sie sieht.

## 6. Hilft ein Satz mehr im Prompt?

Am Ende der Anweisung stand zusätzlich dieser Satz:

> Wenn die Daten eine Frage nicht beantworten oder sie mehrdeutig ist, sag das oder frag nach, statt eine ähnliche
> Spalte oder eine eigene Deutung zu verwenden.

| Frage | Haiku ohne den Satz (Pilot + voller Lauf) | Haiku mit dem Satz | Was Haiku mit dem Satz geantwortet hat |
|---|---|---|---|
| U01 Marketingkanal | 0 von 4 richtig | **0 von 5** | 5-mal den Bezahlweg als Marketingkanal (web 9 bis 16) |
| M02 „Wie viele Kunden haben wir?“ | 0 von 4 richtig | **0 von 5** | 5-mal „FocusFlow hat 600 Kunden.“ |

**Der Satz hat nichts bewirkt.** Die Antworten sind fast Wort für Wort dieselben wie ohne ihn.

Warum? Der Satz sagt: „Wenn etwas nicht passt, sag es.“ Das hilft nur, wenn das Modell merkt, dass etwas nicht passt.
Haiku merkt es nicht. Für Haiku *ist* `channel` der Marketingkanal. Und „Kunden“ *sind* einfach alle Zeilen in der
Tabelle `customers`. Eine Regel für das Verhalten hilft nicht, wenn das Wissen fehlt, das die Regel auslösen würde.

**Was das für Branch (c) bedeutet:** Das Glossar sollte Fakten liefern, keine weiteren Regeln. Also zum Beispiel: Was
bedeutet `channel`? Welche Daten gibt es nicht, etwa den Marketingkanal? Welche Bedeutungen kann „Kunde“ haben?

Einschränkungen: nur 5 Läufe je Frage, nur ein Satz an einer Stelle, nur Haiku. Bei Sonnet ist es nicht gemessen. Sonnet
fragt dort aber ohnehin schon fast immer nach.

## Das Wichtigste in fünf Sätzen

1. Jeder Aufruf schickt alles mit: Anweisung, Schema, Werkzeuge und das ganze bisherige Gespräch. Bei Haiku kosten die
   Werkzeuge mehr als das Schema.
2. Jeder Aufruf wird größer, und jeder wird voll bezahlt. Große Abfrage-Ergebnisse machen das teuer, der Cache macht es
   bei Sonnet billig.
3. Falsche Antworten entstehen oft schon im ersten Satz, bevor überhaupt SQL geschrieben wird.
4. Das Nachdenken zeigt eine Zusammenfassung der Entscheidung, aber keinen Beweis.
5. Eine Regel wie „frag nach, wenn etwas unklar ist“ hilft nicht, wenn das Modell nicht merkt, dass etwas unklar ist.
   Dafür braucht es Fakten, und die soll das Glossar liefern.
