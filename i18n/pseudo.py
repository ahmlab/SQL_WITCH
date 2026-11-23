"""The pseudo-locale qps: English made strange on purpose, to test localisation without a
translator. Every letter gets an accent ("Ŝéléçţ" style), the text grows by about 35% (the
expansion every UI box must survive) and it is wrapped in [brackets], so text that still comes
from code (not the catalog) stands out on screen, and so does text cut at a box's edge.

Kept as they are: {placeholders}, ICU plural/select syntax (their branches are pseudo'd),
the script markup ({wave}...), words in capitals (SQL keywords: SELECT, WHERE), words with an
underscore or digits (table and column names: foe_spells), a table name after FROM, JOIN,
INTO, UPDATE or TABLE, and anything in 'quotes' (SQL strings, spell names typed in queries).

Never imports pygame.

STATUS: accents, +35% expansion, brackets, placeholders and SQL kept.
"""

from __future__ import annotations

import re

ACCENTS = str.maketrans(
    "abcdeghiklmnoprstuwyzACDEGHIKLNORSTUWYZ",
    "åƀçđéĝĥîķļɱñöþŕšţûŵýžÅÇĐÉĜĤÎĶĻÑÖŘŠŢÛŴÝŽ")
EXPANSION = 0.35
_KEEP = re.compile(r"('[^']*'|\b[A-Z][A-Z0-9_]+\b|\b\w*[_\d]\w*\b"
                   r"|(?<=FROM )\w+|(?<=JOIN )\w+|(?<=INTO )\w+|(?<=UPDATE )\w+|(?<=TABLE )\w+)")


def _letters(text: str) -> str:
    """Accent the plain words of a piece of text, keeping SQL-looking words."""
    out, last = [], 0
    for match in _KEEP.finditer(text):
        out.append(text[last:match.start()].translate(ACCENTS))
        out.append(match.group(0))
        last = match.end()
    out.append(text[last:].translate(ACCENTS))
    return "".join(out)


def _walk(text: str) -> str:
    """Accent the text outside braces; inside an ICU plural/select, accent its branches."""
    out, i = [], 0
    while i < len(text):
        if text[i] != "{":
            j = text.find("{", i)
            j = len(text) if j < 0 else j
            out.append(_letters(text[i:j]))
            i = j
            continue
        depth, j = 0, i
        while j < len(text):
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            if depth == 0:
                break
            j += 1
        body = text[i + 1:j]
        head = body.split(",", 2)
        if len(head) == 3 and head[1].strip() in ("plural", "select"):
            branches = re.sub(r"\{([^{}]*)\}", lambda m: "{" + _walk(m.group(1)) + "}", head[2])
            out.append("{" + head[0] + "," + head[1] + "," + branches + "}")
        else:
            out.append(text[i:j + 1])                 # a placeholder or markup: as it is
        i = j + 1
    return "".join(out)


def pseudo(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return text
    visible = len(re.sub(r"\{[^{}]*\}", "", text))
    pad = max(1, round(visible * EXPANSION) - 2)      # the two brackets count too
    return "[" + _walk(text) + " " + "~" * (pad - 1) + "]" if pad > 1 else "[" + _walk(text) + "]"
