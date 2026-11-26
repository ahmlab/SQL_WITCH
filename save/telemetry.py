"""Opt-in telemetry (prompt 05 §4, docs/TELEMETRY.md): off by default, nothing without consent.

record(event, **fields) keeps an event only when the player said yes, and only the fields
listed for that event in EVENTS: technique signatures, outcomes, counts, a lesson's timing,
the language. Never a name, never free text, never an identifier beyond a random install id.
The query text itself travels only if the player also turned on "share my queries".

Events wait in a local queue (telemetry/queue.jsonl) and leave in batches through a sender;
with no endpoint configured (data/telemetry.json) nothing ever leaves the machine.

Never imports pygame.

STATUS: consent gate, field whitelist, query-text gate, local queue, batches, HTTPS sender.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Callable

from save.files import read_json, write_json

EVENTS = {
    "battle_start": {"guardian", "seed", "retry"},
    "battle_end": {"guardian", "result", "rounds", "retries", "seconds", "rewinds"},
    "cast": {"guardian", "turn", "techniques", "kind", "outcome", "rows", "read", "overflow",
             "mp_spent", "sql"},
    "hint": {"guardian", "topic", "node"},
    "rewind": {"guardian", "turn"},
    "lesson": {"lesson", "seconds"},
    "language": {"locale"},
}
MAX_QUEUE = 5000


class Telemetry:
    def __init__(self, root: Path, consent: Callable[[], bool],
                 share_queries: Callable[[], bool] = lambda: False):
        self.root = Path(root)
        self.consent, self.share_queries = consent, share_queries
        self.queue_path = self.root / "telemetry" / "queue.jsonl"

    @property
    def install_id(self) -> str:
        """A random id for this installation (not the player): made on first use."""
        path = self.root / "install.json"
        data, _ = read_json(path) if path.exists() else (None, "missing")
        if not data or "install_id" not in data:
            data = {"install_id": uuid.uuid4().hex}
            write_json(path, data, keep_backup=False)
        return data["install_id"]

    def record(self, event: str, **fields) -> dict | None:
        if not self.consent() or event not in EVENTS:
            return None
        allowed = set(EVENTS[event])
        if not self.share_queries():
            allowed.discard("sql")
        entry = {k: v for k, v in fields.items() if k in allowed}
        entry.update(event=event, t=round(time.time()), install=self.install_id)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        lines = self.pending()[-(MAX_QUEUE - 1):] + [entry]
        self.queue_path.write_text("".join(json.dumps(e) + "\n" for e in lines),
                                   encoding="utf-8")
        return entry

    def pending(self) -> list[dict]:
        if not self.queue_path.exists():
            return []
        out = []
        for line in self.queue_path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def flush(self, sender: Callable[[list[dict]], bool] | None, batch: int = 200) -> int:
        """Send the queue in batches; what was accepted leaves the queue. Returns the count."""
        if sender is None or not self.consent():
            return 0
        queue, sent = self.pending(), 0
        while queue:
            chunk = queue[:batch]
            if not sender(chunk):
                break
            queue, sent = queue[batch:], sent + len(chunk)
        self.queue_path.write_text("".join(json.dumps(e) + "\n" for e in queue),
                                   encoding="utf-8")
        return sent


def https_sender(endpoint: str | None, timeout: float = 5.0):
    """A sender posting a JSON batch to the endpoint (docs/TELEMETRY.md), or None."""
    if not endpoint or not endpoint.startswith("https://"):
        return None

    def send(batch: list[dict]) -> bool:
        import urllib.request
        body = json.dumps({"schema": 1, "events": batch}).encode()
        request = urllib.request.Request(endpoint, body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return 200 <= response.status < 300
        except Exception:
            return False                          # offline: try again later
    return send
