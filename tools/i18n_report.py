"""Localisation reports for translators and reviewers (docs/LOCALISATION.md).

    python tools/i18n_report.py                      # every language: translated, reviewed...
    python tools/i18n_report.py missing es           # the keys es has not translated yet
    python tools/i18n_report.py overflow es          # strings that do not fit their box
    python tools/i18n_report.py overflow qps         # +35% test: which boxes are too small
    python tools/i18n_report.py lint                 # English lines that may need a gender form
    python tools/i18n_report.py export out.json      # every English string by key, one file

Extraction: the English catalog is data/i18n/en.json plus the text that lives next to its
content (data/story/*.script, data/guide.json, data/tutorial.json, see i18n/sources.py);
`export` writes all of it into one file for a translator or a translation service.

STATUS: report, missing, overflow, lint, export.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from i18n import check  # noqa: E402
from i18n.catalog import CATALOG, SOURCE  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args.pop(0) if args else "report"
    if command == "report":
        print(f"English source: {len(CATALOG.messages(SOURCE))} strings")
        print(check.report())
    elif command == "missing":
        print("\n".join(check.untranslated(args[0])) or "nothing missing")
    elif command == "overflow":
        problems = check.overflows(args[0])
        print("\n".join(problems) or f"{args[0]}: everything fits")
        return 1 if problems else 0
    elif command == "lint":
        warnings = check.pronoun_warnings()
        print("English lines with he/she/his/her and no {player.gender, select, ...}:")
        print("\n".join("  " + w for w in warnings) or "  none")
        print("(a line about someone else, like the Knight, needs no marker)")
    elif command == "export":
        out = Path(args[0])
        out.write_text(json.dumps(CATALOG.messages(SOURCE), indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"wrote {len(CATALOG.messages(SOURCE))} strings to {out}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
