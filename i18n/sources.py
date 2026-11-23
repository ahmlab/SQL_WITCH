"""Where the English source text lives, besides data/i18n/en.json.

Writers keep text next to what it belongs to: dialogue in data/story/*.script, the spell
guide in data/guide.json, lesson titles in data/tutorial.json. This module reads those files
and gives every piece of text a stable key, so the catalog can serve them in English and every
translation can replace them:

    story.<file>.<node>.<n>        a line of a script (story/script.py makes the key)
    guide.<path>                   a string of data/guide.json: guide.basics.3, guide.examples.0.say
    tutorial.<lesson>.<field>      a lesson's title, keys or hint in data/tutorial.json

Only text fields are taken: SQL, table names and ids stay as they are, untranslated.
tools/i18n.py uses all_sources() to extract and report; the catalog merges them into English.

Never imports pygame.

STATUS: scripts, guide.json and tutorial.json as catalog sources; localise() for data files.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
# Which fields of each data file are words for the player (everything else is data).
TEXT_FIELDS = {
    "guide": {"basics", "tables_intro", "tables", "reading", "say", "does", "from"},
    "tutorial": {"title", "keys", "hint"},
}


def _walk(value, path: list[str], fields: set[str], inside: bool, out: dict) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.startswith("_"):
                continue
            _walk(item, path + [key], fields, inside or key in fields, out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _walk(item, path + [str(i)], fields, inside, out)
    elif isinstance(value, str) and inside and value.strip():
        out[".".join(path)] = value


def data_strings(name: str, data: dict) -> dict[str, str]:
    """key -> English text of a data file's words."""
    out: dict[str, str] = {}
    if name == "tutorial":                           # lessons are keyed by id, not by position
        for lesson in data.get("lessons", []) + [data.get("practice", {})]:
            for field in TEXT_FIELDS["tutorial"]:
                if isinstance(lesson.get(field), str):
                    out[f"tutorial.{lesson['id']}.{field}"] = lesson[field]
        return out
    _walk(data, [name], TEXT_FIELDS.get(name, set()), False, out)
    return out


@lru_cache(maxsize=None)
def _json(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def all_sources() -> dict[str, str]:
    """Every English string that lives outside en.json, by key."""
    from story.script import all_scripts                # story imports i18n: load it late
    out: dict[str, str] = {}
    for script in all_scripts().values():
        out.update(script.keys())
    for name in TEXT_FIELDS:
        out.update(data_strings(name, _json(name)))
    return out


def localise(name: str, data, catalog=None):
    """A copy of a data file with its words in the current language (English stays)."""
    from i18n.catalog import CATALOG
    catalog = catalog or CATALOG
    if name == "tutorial":
        data = json.loads(json.dumps(data))
        for lesson in data.get("lessons", []) + [data.get("practice", {})]:
            for field in TEXT_FIELDS["tutorial"]:
                if isinstance(lesson.get(field), str):
                    lesson[field] = catalog.raw(f"tutorial.{lesson['id']}.{field}") or lesson[field]
        return data
    fields = TEXT_FIELDS.get(name, set())

    def walk(value, path, inside):
        if isinstance(value, dict):
            return {k: (v if k.startswith("_") else walk(v, path + [k], inside or k in fields))
                    for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, path + [str(i)], inside) for i, v in enumerate(value)]
        if isinstance(value, str) and inside and value.strip():
            return catalog.raw(".".join(path)) or value
        return value
    return walk(data, [name], False)
