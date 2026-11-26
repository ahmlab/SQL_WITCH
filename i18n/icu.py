"""A small ICU MessageFormat: arguments, plurals (CLDR rules) and select (gender).

    format_message("{count, plural, one {# row} other {# rows}}", {"count": 3}, "en") -> "3 rows"
    format_message("{gender, select, feminine {tired} masculine {tired} other {tired}}", ...)
    format_message("Hello {name}", {"name": "Ada"}, "en")                          -> "Hello Ada"

Only the subset the game needs: {arg}, {arg, number}, {arg, plural, ...} with =N and the CLDR
categories (zero one two few many other), # inside a plural branch, and {arg, select, ...}.
Apostrophes are literal text (the game writes "Ada's"), which differs from strict ICU quoting:
writers never need to escape anything. Plural categories come from Babel's CLDR data, so every
locale (Polish "few", Irish "two", Arabic "zero"...) follows its real rules.

Never imports pygame.

STATUS: arguments, number, plural (CLDR via Babel), select, nesting.
"""

from __future__ import annotations

from functools import lru_cache


def format_message(pattern: str, args: dict, locale: str = "en") -> str:
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "{":
            end = _matching(pattern, i)
            out.append(_argument(pattern[i + 1:end], args, locale))
            i = end + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _matching(text: str, start: int) -> int:
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"unbalanced braces in message: {text!r}")


def _split_top(text: str, sep: str = ",", limit: int = 2) -> list[str]:
    parts, depth, last = [], 0, 0
    for j, c in enumerate(text):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == sep and depth == 0 and len(parts) < limit:
            parts.append(text[last:j])
            last = j + 1
    parts.append(text[last:])
    return [p.strip() for p in parts]


def _branches(text: str) -> dict[str, str]:
    """'one {# row} other {# rows}' -> {'one': '# row', 'other': '# rows'}"""
    out, i = {}, 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        j = text.index("{", i)
        selector = text[i:j].strip()
        end = _matching(text, j)
        out[selector] = text[j + 1:end]
        i = end + 1
    return out


def _argument(body: str, args: dict, locale: str) -> str:
    parts = _split_top(body)
    name = parts[0]
    value = _lookup(args, name)
    if len(parts) == 1:
        return str(value)
    kind = parts[1]
    if kind == "number":
        return format_number(value, locale)
    branches = _branches(parts[2]) if len(parts) > 2 else {}
    if kind == "plural":
        exact = f"={value}"
        chosen = branches.get(exact) or branches.get(plural_category(value, locale)) \
            or branches.get("other", "")
        text = format_message(chosen, args, locale)
        return text.replace("#", format_number(value, locale))
    if kind == "select":
        chosen = branches.get(str(value), branches.get("other", ""))
        return format_message(chosen, args, locale)
    return str(value)


def _lookup(args: dict, name: str):
    """An argument by name; dotted names reach inside: player.gender."""
    if name in args:
        return args[name]
    value = args
    for part in name.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return "{" + name + "}"                 # unknown: shown as written
    return value


def _english_rule(number) -> str:
    return "one" if number == 1 else "other"


@lru_cache(maxsize=None)
def _plural_rule(locale: str):
    try:
        from babel import Locale
    except ImportError:
        # Babel is in requirements.txt; without it the game still runs (English plural rules
        # for every language) instead of crashing in the middle of a battle.
        print("[i18n] Babel is not installed: plurals follow English rules. "
              "Run: pip install -r requirements.txt")
        return _english_rule
    try:
        return Locale.parse(locale.replace("-", "_")).plural_form
    except Exception:                                   # an unknown locale: English rules
        return Locale.parse("en").plural_form


def plural_category(value, locale: str) -> str:
    """The CLDR plural category of a number in a locale: zero, one, two, few, many or other."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "other"
    if number.is_integer():
        number = int(number)
    return _plural_rule(locale)(number)


def format_number(value, locale: str) -> str:
    """A number with the locale's digits and separators (1,000.5 or 1.000,5 or 1 000,5)."""
    try:
        from babel.numbers import format_decimal
        return format_decimal(value, locale=locale.replace("-", "_"))
    except Exception:
        return str(value)
