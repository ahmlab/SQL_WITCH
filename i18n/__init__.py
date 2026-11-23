"""Localisation: the catalog, ICU messages (plural, gender) and locales (plan D3-D4, prompt 04).

Every player-visible string comes from here by key: t("ui.title.press_enter"). The catalogs
are data/i18n/<locale>.json; English is the source. See i18n/catalog.py and i18n/icu.py.

Must not: import pygame. Fonts on screen live in engine/.

Modules: catalog (lookup, fallback, review status, menu), icu (plural, select, numbers),
width (cells, wrapping), pseudo (the qps locale), sources (text that lives in data files),
check (overflow, untranslated, gender). Tools: tools/translate.py, tools/i18n_report.py.

STATUS: 27 locales listed; EN source, ES / ZH-Hans / ZH-Hant drafts; qps; checks and tools.
"""

from i18n.catalog import CATALOG, locale, set_locale, set_player, t

__all__ = ["CATALOG", "locale", "set_locale", "set_player", "t"]
