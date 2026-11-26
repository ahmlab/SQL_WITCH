# Telemetry (opt-in)

Off by default. The first launch asks, in plain words, and Settings can change it at any time.
Nothing is recorded, queued or sent without a yes. A second toggle, "share my queries", is needed
before the text of a query ever leaves the computer.

## What is sent

Only these events, and only these fields (`save/telemetry.py`, `EVENTS`):

| Event | Fields |
|---|---|
| `battle_start` | guardian, seed, retry |
| `battle_end` | guardian, result, rounds, retries, seconds, rewinds |
| `cast` | guardian, turn, techniques (e.g. `["LIMIT", "WHERE"]`), kind, outcome, rows, read, overflow, mp_spent, and `sql` only with "share my queries" |
| `hint` | guardian, topic, node |
| `rewind` | guardian, turn |
| `lesson` | lesson, seconds |
| `language` | locale |

Every event also carries `event`, `t` (a Unix time in seconds) and `install` (a random id made
on first use; it identifies an installation, never a person). No names, no free text.

## The endpoint

`data/telemetry.json` holds `endpoint` (null: nothing is ever sent; events stay in the local
queue) and `batch` (events per request). When an endpoint is set, the game posts batches when it
quits:

```
POST <endpoint>            Content-Type: application/json
{"schema": 1, "events": [ {...}, {...} ]}
```

Any 2xx answer removes the batch from the queue; anything else (or no network) keeps it for
the next time. The queue keeps at most 5000 events. The server must accept HTTPS only, store
nothing it was not sent, and never try to join `install` with anything else.

## Learning metrics, locally

The school report's metric (uses of a technique before its guardian against uses after it) is
computed on the player's own computer from their own log (`save/stats.py`), and shown on the
Statistics screen ("you used WHERE 0 times before meeting the Knight, and 41 times since"). It
needs no telemetry at all.
