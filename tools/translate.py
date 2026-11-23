"""Machine drafts for a language, from the English catalog (prompt 04, docs/LOCALISATION.md).

    python tools/translate.py --locale es --from drafts/es.tsv     # import drafts (key<TAB>text)
    python tools/translate.py --locale zh-Hant --engine opencc --source zh-Hans
    python tools/translate.py --locale fr --engine copy            # English placeholders, to fill
    python tools/translate.py --locale es --review "story.intro.*" # a reviewer signs entries off
    python tools/translate.py --locale es --check                  # placeholders and markup intact?

Writes data/i18n/<locale>.json: every entry it writes is marked "draft" in the file's _status;
an entry marked "reviewed" is never overwritten. A locale appears in the game's language menu
once its reviewed share reaches review_threshold in data/i18n/locales.json (or while it is listed
in "preview").

Engines: "tsv" (the default with --from: drafts made elsewhere, by a translation service or a
person), "opencc" (Simplified to Traditional Chinese with Taiwan vocabulary, from an existing
zh-Hans catalog; needs `pip install opencc-python-reimplemented`), "copy" (the English text,
for a translator to replace). A draft is refused if it loses a {placeholder} or an inline
command ({wave}, {rune WHERE}...) of the English, so the game never shows a broken line.

STATUS: tsv import, opencc, copy, review marks, placeholder check, never overwrites reviewed.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from i18n.catalog import CATALOG, CATALOG_DIR, SOURCE  # noqa: E402

# Terms where Taiwan's database vocabulary differs from a character-by-character conversion.
OPENCC_TERMS = {"事務": "交易", "檢視": "檢視表"}
HELP = ("Machine draft by tools/translate.py. Entries marked draft in _status wait for a native "
        "reviewer; see docs/LOCALISATION.md. Keys are the English catalog's; SQL, table and "
        "column names, spell and item names stay in English.")


def tokens_of(text: str) -> list[str]:
    """The placeholders and inline commands a translation must keep: {foe}, {wave}, {rune X},
    the argument names of ICU plural/select ({count, plural, ...} -> {count})."""
    out = []
    depth, start = 0, 0
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                body = text[start + 1:i]
                head = body.split(",")[0].strip()
                if "," in body and body.split(",")[1].strip() in ("plural", "select", "number"):
                    out.append("{" + head + "}")
                elif head.startswith("rune"):
                    out.append("{rune}")                      # the rune word may be the same
                else:
                    out.append("{" + head + "}")
    return sorted(out)


def problem(english: str, draft: str) -> str | None:
    """Why a draft would break the game, or None."""
    # The player's gender select is each language's own business: added where a language
    # inflects (Spanish bruja/brujo), dropped where it does not (Chinese).
    want = [t for t in tokens_of(english) if t != "{player.gender}"]
    got = [t for t in tokens_of(draft) if t != "{player.gender}"]
    if want != got:
        return f"placeholders differ: English {want}, draft {got}"
    if draft.count("{") != draft.count("}"):
        return "unbalanced { }"
    return None


def load(locale: str) -> dict:
    path = CATALOG_DIR / f"{locale}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(locale: str, data: dict) -> Path:
    source = CATALOG.messages(SOURCE)
    status = data.get("_status", {})
    ordered = {"_help": data.get("_help", HELP),
               "_status": {k: status[k] for k in source if k in status}}
    for key in source:                                  # the English order, for reviewers
        if key in data:
            ordered[key] = data[key]
    path = CATALOG_DIR / f"{locale}.json"
    path.write_text(json.dumps(ordered, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    CATALOG.reload()
    return path


def write_drafts(locale: str, drafts: dict[str, str]) -> tuple[int, list[str]]:
    data = load(locale)
    status = data.setdefault("_status", {})
    source = CATALOG.messages(SOURCE)
    written, refused = 0, []
    for key, text in drafts.items():
        if key not in source:
            refused.append(f"{key}: not an English key")
            continue
        if status.get(key) == "reviewed":
            continue                                    # a reviewer's word is final
        why = problem(source[key], text)
        if why:
            refused.append(f"{key}: {why}")
            continue
        data[key] = text
        status[key] = "draft"
        written += 1
    save(locale, data)
    return written, refused


def read_tsv(path: Path) -> dict[str, str]:
    out = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        key, _, text = line.partition("\t")
        out[key.strip()] = text
    return out


def opencc_drafts(source_locale: str) -> dict[str, str]:
    from opencc import OpenCC                            # optional: only this engine needs it
    convert = OpenCC("s2twp").convert
    out = {}
    for key, text in CATALOG.messages(source_locale).items():
        if key not in CATALOG.messages(SOURCE):
            continue
        # Convert only the words: SQL, names and {placeholders} keep their exact letters.
        parts = re.split(r"(\{[^{}]*\}|'[^']*'|[A-Za-z_][A-Za-z0-9_.* ()=<>',]*)", text)
        done = "".join(p if (p.startswith("{") or re.match(r"[A-Za-z_']", p or " ")) else
                       convert(p) for p in parts)
        for old, new in OPENCC_TERMS.items():
            done = done.replace(old, new)
        out[key] = done
    return out


def review(locale: str, patterns: list[str]) -> int:
    data = load(locale)
    status = data.setdefault("_status", {})
    marked = 0
    for key in list(status):
        if any(fnmatch.fnmatch(key, p) for p in patterns):
            status[key] = "reviewed"
            marked += 1
    save(locale, data)
    return marked


def check(locale: str) -> list[str]:
    source = CATALOG.messages(SOURCE)
    data = load(locale)
    return [f"{k}: {why}" for k, v in data.items() if not k.startswith("_") and k in source
            and (why := problem(source[k], v))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--locale", required=True)
    parser.add_argument("--from", dest="tsv", type=Path, help="drafts as key<TAB>text lines")
    parser.add_argument("--engine", choices=["tsv", "opencc", "copy"], default=None)
    parser.add_argument("--source", default="zh-Hans", help="opencc: the catalog to convert")
    parser.add_argument("--review", nargs="*", help="mark matching keys reviewed (globs)")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.locale == SOURCE:
        print("English is the source: edit data/i18n/en.json and the scripts instead.")
        return 2
    if args.check:
        problems = check(args.locale)
        print("\n".join(problems) or f"{args.locale}: every entry keeps its placeholders")
        return 1 if problems else 0
    if args.review is not None:
        print(f"{review(args.locale, args.review)} entries marked reviewed")
        return 0
    engine = args.engine or ("tsv" if args.tsv else "copy")
    if engine == "tsv":
        drafts = read_tsv(args.tsv)
    elif engine == "opencc":
        drafts = opencc_drafts(args.source)
    else:
        drafts = dict(CATALOG.messages(SOURCE))
    written, refused = write_drafts(args.locale, drafts)
    print(f"{args.locale}: {written} drafts written")
    for line in refused:
        print("  refused", line)
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
