"""The system screens: the first-launch flow, language, telemetry consent, Load, Pause, Credits.

First launch (no settings.json yet): language -> consent -> character creator (prompt 06,
skipped with --skip-creator) -> story. Later new games go straight to the creator. Each step is
a small menu scene; `first_launch_steps` strings them together.

Load lists the profiles, then a profile's slots (1-3 and the autosave) with where the story
stands and the playtime; a damaged slot offers its last good backup (B). Pause (P, outside
battles) saves to a slot, opens Settings or Statistics, or goes back to the title. Credits
scrolls CREDITS.md.

Must not: write files itself (save/ does), or change the world.

STATUS: menu scene, first-launch flow, language, consent, load (with backups), pause, credits.
"""

from __future__ import annotations

import re
from pathlib import Path

import pygame

from engine import render
from engine import settings as settings_screen
from i18n import CATALOG, t

ROOT = Path(__file__).resolve().parent.parent


class Menu:
    """A list of (label, action) chosen with UP/DOWN and ENTER; ESC calls back()."""
    PLACE = "menu"
    TITLE = ""

    def __init__(self, game):
        self.game, self.time, self.choice = game, 0, 0

    def items(self) -> list[tuple[str, object]]:
        return []

    def back(self) -> None:
        pass

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt):
        self.time += dt

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return
        items = self.items()
        if event.key == pygame.K_ESCAPE:
            self.back()
        elif event.key == pygame.K_UP and items:
            self.choice = (self.choice - 1) % len(items)
        elif event.key == pygame.K_DOWN and items:
            self.choice = (self.choice + 1) % len(items)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and items:
            self.game.audio.play("confirm")
            items[min(self.choice, len(items) - 1)][1]()

    def draw_items(self, canvas, top: int = 40, centred: bool = True) -> None:
        f = render.font()
        for i, (label, _) in enumerate(self.items()):
            colour = render.WHITE if i == self.choice else render.LILAC
            x = (320 - f.width(label)) // 2 if centred else 24
            if i == self.choice:
                f.draw(canvas, ">", (x - 8, top + i * 10), render.GOLD)
            f.draw(canvas, label, (x, top + i * 10), colour, shadow=render.INK)

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        title = t(self.TITLE) if self.TITLE else ""
        f.draw(canvas, title, ((320 - f.width(title)) // 2, 12), render.BUTTER)
        self.draw_items(canvas)


# ------------------------------------------------------------------ the first launch

def first_launch_steps(game) -> None:
    """Language and consent once per machine, then the creator (each new profile)."""
    if game.saves is not None and game.first_launch and not game.settings.language:
        game.switch(LanguageScene(game))
    elif game.saves is not None and not game.settings.consent_asked:
        game.switch(ConsentScene(game))
    elif not game.skip_creator:
        from engine.creator import CreatorScene
        game.switch(CreatorScene(game))
    else:
        game.start_profile()


class LanguageScene(Menu):
    TITLE = "menu.language"

    def items(self):
        return [(CATALOG.name_of(code), lambda code=code: self.pick(code))
                for code in CATALOG.menu_locales()]

    def pick(self, code: str) -> None:
        self.game.settings.language = code
        settings_screen.apply(self.game)
        self.game.save_settings()
        self.game.track("language", locale=code)
        first_launch_steps(self.game)

    def handle(self, event):
        super().handle(event)
        codes = CATALOG.menu_locales()              # each language shows itself as you go
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN) and codes:
            from i18n import set_locale
            set_locale(codes[self.choice % len(codes)])


class ConsentScene(Menu):
    TITLE = "consent.title"

    def items(self):
        return [(t("consent.no"), lambda: self.pick(False)),
                (t("consent.yes"), lambda: self.pick(True))]

    def pick(self, yes: bool) -> None:
        s = self.game.settings
        s.telemetry, s.consent_asked = yes, True
        self.game.save_settings()
        first_launch_steps(self.game)

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        f.draw(canvas, t(self.TITLE), (16, 12), render.BUTTER)
        y = 28
        from engine.grimoire import wrap
        for line in wrap(t("consent.text"), 72):
            f.draw(canvas, line, (16, y), render.LILAC)
            y += 8
        self.draw_items(canvas, top=y + 10)


# ------------------------------------------------------------------ load

class LoadScene(Menu):
    TITLE = "menu.load"

    def __init__(self, game, back):
        super().__init__(game)
        self.back_to, self.profile = back, None

    def back(self):
        if self.profile is not None:
            self.profile, self.choice = None, 0
        else:
            self.game.switch(self.back_to)

    def items(self):
        saves = self.game.saves
        if self.profile is None:
            return [(p["name"], lambda p=p: self.open(p["id"])) for p in saves.profiles()]
        out = []
        for info in saves.slots(self.profile):
            name = t("menu.autosave") if info.slot == "auto" else t("menu.slot", n=info.slot)
            if info.status == "empty":
                out.append((f"{name}  {t('menu.empty')}", lambda: None))
            elif info.status == "damaged":
                label = t("menu.damaged_backup") if info.has_backup else t("menu.damaged")
                out.append((f"{name}  {label}", lambda info=info: self.pick(info, True)))
            else:
                where = t(f"menu.at.{info.at}") if CATALOG.has(f"menu.at.{info.at}") else info.at
                minutes = int(info.playtime_s // 60)
                out.append((f"{name}  {where}  {t('menu.minutes', count=minutes)}",
                            lambda info=info: self.pick(info, False)))
        return out

    def open(self, pid):
        self.profile, self.choice = pid, 0

    def pick(self, info, backup: bool):
        if backup and not info.has_backup:
            return
        self.game.load(self.profile, info.slot, backup=backup)


# ------------------------------------------------------------------ pause (outside battles)

class PauseScene(Menu):
    TITLE = "menu.pause"

    def __init__(self, game, back):
        super().__init__(game)
        self.back_to, self.note = back, ""

    def back(self):
        self.game.switch(self.back_to)

    def items(self):
        from engine.stats import StatsScene
        out = [(t("menu.resume"), self.back)]
        if self.game.saves is not None and self.game.profile_id is not None:
            out += [(t("menu.save_to", n=n), lambda n=n: self.save(n)) for n in ("1", "2", "3")]
        from engine.creator import CreatorScene         # the mirror: the look, not the name
        out.append((t("menu.mirror"),
                    lambda: self.game.switch(CreatorScene(self.game, mirror=True, back=self))))
        out += [(t("menu.settings"),
                 lambda: self.game.switch(settings_screen.SettingsScene(self.game, self))),
                (t("menu.statistics"), lambda: self.game.switch(StatsScene(self.game, self))),
                (t("menu.to_title"), self.to_title)]
        return out

    def save(self, slot):
        self.note = t("menu.saved", n=slot) if self.game.save_slot(slot) else ""

    def to_title(self):
        from engine.scenes import TitleScene
        self.game.switch(TitleScene(self.game))

    def draw(self, canvas):
        super().draw(canvas)
        if self.note:
            f = render.font()
            f.draw(canvas, self.note, ((320 - f.width(self.note)) // 2, 150), render.GOLD)


# ------------------------------------------------------------------ credits

def credit_lines() -> list[str]:
    """CREDITS.md as plain lines: headings, names, licences (markdown marks removed)."""
    text = (ROOT / "CREDITS.md").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)     # [name](url) -> name
        line = line.replace("**", "").replace("`", "").lstrip("# ").strip()
        if set(line) <= set("|-: "):
            continue
        out.append(" ".join(cell.strip() for cell in line.strip("|").split("|")))
    return out


class CreditsScene(Menu):
    SPEED = 14                                          # pixels per second

    def __init__(self, game, back):
        super().__init__(game)
        self.back_to = back
        from engine.grimoire import wrap
        self.lines = [part for line in credit_lines() for part in (wrap(line, 74) or [""])]

    def back(self):
        self.game.switch(self.back_to)

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN,
                                                          pygame.K_KP_ENTER):
            self.back()

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        y = 180 - int(self.time / 1000 * self.SPEED)
        for line in self.lines:
            if -8 < y < 180:
                f.draw(canvas, line, ((320 - f.width(line)) // 2, y), render.LILAC)
            y += 9
        if y < 0:                                       # once it has all gone by, again
            self.time = 0
