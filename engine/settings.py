"""Settings on screen: apply every value live, read key bindings, the settings scene (prompt 05).

apply(game) puts a save.settings_file.Settings into effect at once, without a restart: the
language, the display (windowed at a whole-number scale, or fullscreen letterboxed or filled),
the four volume sliders, the text speed, auto-advance, reduced motion (screen shake and
flashes), the colour-blind palette, the Grimoire font, the key bindings. The settings scene
changes one value at a time and calls apply() and save() after each change.

Accessibility notes (docs/ACCESSIBILITY.md): no dyslexia-friendly font exists at a 5x7 pixel
size (OpenDyslexic and Lexend are outline fonts that turn to noise at this size), so there is
no such option; the large Grimoire font draws heavier letters on the same grid.

Must not: store files itself (save/ does), or change the world (settings never touch a query).

STATUS: live apply for every setting, bindings, the settings scene with rebinding.
"""

from __future__ import annotations

import json

import pygame

from engine import render
from i18n import CATALOG, set_locale, t
from magic.db import DATA_DIR
from save.settings_file import DISPLAYS, PALETTES, TEXT_SPEEDS, Settings
from story import pacing

ACCESSIBILITY = json.loads((DATA_DIR / "accessibility.json").read_text(encoding="utf-8"))


def apply(game, settings: Settings | None = None) -> None:
    """Every setting takes effect now."""
    s = settings or game.settings
    if s.language and s.language != CATALOG.locale and s.language in CATALOG.settings()["locales"]:
        set_locale(s.language)
    if game.screen is not None and (game.screen.mode, game.screen.fill, game.screen.scale) != \
            (s.display, s.fill, s.scale if s.display == "windowed" else game.screen.scale):
        game.screen.set_display(s.display, s.scale, s.fill)
    if hasattr(game.audio, "set_levels"):
        game.audio.set_levels(**s.volume)
    pacing.set_text_speed(ACCESSIBILITY["text_speeds"].get(s.text_speed, 1.0))
    game.auto_advance = s.auto_advance
    render.set_palette(s.palette, ACCESSIBILITY["palettes"])
    render.HEAVY_TEXT[0] = s.grimoire_font == "large"


# ------------------------------------------------------------------ key bindings

KEY_NAMES = {"return": pygame.K_RETURN, "space": pygame.K_SPACE, "tab": pygame.K_TAB,
             "escape": pygame.K_ESCAPE}


def parse_binding(text: str) -> tuple[int, bool]:
    """'ctrl+return' -> (K_RETURN, ctrl held)."""
    parts = text.lower().split("+")
    ctrl = "ctrl" in parts[:-1]
    name = parts[-1]
    key = KEY_NAMES.get(name) or pygame.key.key_code(name)
    return key, ctrl


def binding_text(event) -> str | None:
    """A key press as a binding: 'f6', 'ctrl+return'."""
    if event.type != pygame.KEYDOWN or event.key in (pygame.K_LCTRL, pygame.K_RCTRL,
                                                     pygame.K_LSHIFT, pygame.K_RSHIFT):
        return None
    name = pygame.key.name(event.key)
    return ("ctrl+" if event.mod & pygame.KMOD_CTRL else "") + name


def pressed(event, action: str, settings: Settings) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    key, ctrl = parse_binding(settings.bindings.get(action, ""))
    if event.key != key and not (key == pygame.K_RETURN and event.key == pygame.K_KP_ENTER):
        return False
    return not ctrl or bool(event.mod & pygame.KMOD_CTRL)


# ------------------------------------------------------------------ the settings scene

def _cycle(options, value, step):
    options = list(options)
    i = options.index(value) if value in options else 0
    return options[(i + step) % len(options)]


ROWS = ["language", "display", "scale", "fill", "volume.master", "volume.music",
        "volume.effects", "volume.ui", "text_speed", "auto_advance", "screen_shake", "flashes",
        "palette", "grimoire_font", "telemetry", "share_queries",
        "bind.cast", "bind.help", "bind.tables", "bind.rewind", "bind.scroll", "bind.codex"]


class SettingsScene:
    """UP/DOWN choose, LEFT/RIGHT change (applied at once), ENTER on a key binding waits for
    the new key, ESC goes back."""
    VISIBLE = 15

    def __init__(self, game, back):
        self.game, self.back = game, back
        self.time, self.row, self.rebinding = 0, 0, None

    # the scene protocol of engine/scenes.py
    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt):
        self.time += dt

    def value(self, row: str) -> str:
        s = self.game.settings
        if row.startswith("volume."):
            return f"{round(s.volume[row[7:]] * 100)}%"
        if row.startswith("bind."):
            return "..." if self.rebinding == row else s.bindings[row[5:]].upper()
        if row == "language":
            return CATALOG.name_of(s.language or CATALOG.locale)   # not chosen yet: current
        value = getattr(s, row)
        if isinstance(value, bool):
            return t("settings.on") if value else t("settings.off")
        if value is None:
            return t("settings.auto")
        return t(f"settings.value.{value}") if CATALOG.has(f"settings.value.{value}") \
            else str(value)

    def change(self, row: str, step: int) -> None:
        s = self.game.settings
        if row == "language":
            s.language = _cycle(CATALOG.menu_locales(), s.language, step)
        elif row == "display":
            s.display = _cycle(DISPLAYS, s.display, step)
        elif row == "scale":
            s.scale = max(1, min(8, (s.scale or 3) + step))
        elif row.startswith("volume."):
            key = row[7:]
            s.volume[key] = round(max(0.0, min(1.0, s.volume[key] + 0.1 * step)), 1)
        elif row == "text_speed":
            s.text_speed = _cycle(TEXT_SPEEDS, s.text_speed, step)
        elif row == "palette":
            s.palette = _cycle(PALETTES, s.palette, step)
        elif row == "grimoire_font":
            s.grimoire_font = _cycle(("normal", "large"), s.grimoire_font, step)
        elif not row.startswith("bind."):
            setattr(s, row, not getattr(s, row))
            if row == "telemetry":
                s.consent_asked = True
        self.commit()

    def commit(self) -> None:
        apply(self.game)
        self.game.save_settings()
        self.game.audio.play("confirm")

    def handle(self, event):
        if self.rebinding:
            text = binding_text(event)
            if text and text != "escape":
                self.game.settings.bindings[self.rebinding[5:]] = text
                self.rebinding = None
                self.commit()
            elif text == "escape":
                self.rebinding = None
            return
        if event.type != pygame.KEYDOWN:
            return
        row = ROWS[self.row]
        if event.key == pygame.K_ESCAPE:
            self.game.switch(self.back)
        elif event.key == pygame.K_UP:
            self.row = (self.row - 1) % len(ROWS)
        elif event.key == pygame.K_DOWN:
            self.row = (self.row + 1) % len(ROWS)
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            if not row.startswith("bind."):
                self.change(row, -1 if event.key == pygame.K_LEFT else 1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if row.startswith("bind."):
                self.rebinding = row
            else:
                self.change(row, 1)

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        f.draw(canvas, t("settings.title"), (12, 8), render.BUTTER)
        first = max(0, min(self.row - self.VISIBLE // 2, len(ROWS) - self.VISIBLE))
        y = 22
        for i in range(first, min(len(ROWS), first + self.VISIBLE)):
            row = ROWS[i]
            colour = render.WHITE if i == self.row else render.LILAC
            if i == self.row:
                pygame.draw.rect(canvas, render.DUSK, (8, y - 2, 304, 9))
            f.draw(canvas, t(f"settings.row.{row}"), (12, y), colour)
            value = self.value(row)
            f.draw(canvas, value, (308 - f.width(value), y), render.GOLD)
            y += 9
        f.draw(canvas, t("settings.keys"), (12, 168), render.GREY)
