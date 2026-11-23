"""Localisation: the catalog, ICU messages (plural, gender) and locales (plan D3-D4, prompt 04).

Every player-visible string comes from here by key: t("ui.title.press_enter"). The catalogs
are data/i18n/<locale>.json; English is the source. See i18n/catalog.py and i18n/icu.py.

Must not: import pygame. Fonts on screen live in engine/.

STATUS: catalog with English fallback and ICU messages; locales and tools in prompt 04.
"""

from i18n.catalog import CATALOG, locale, set_locale, t

__all__ = ["CATALOG", "locale", "set_locale", "t"]
