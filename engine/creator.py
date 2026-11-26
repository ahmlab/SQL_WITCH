"""The character creator (prompt 06): name, gender and look, with a live preview.

Rows: name (typed, any script; a Chinese IME composes inline), gender (feminine or masculine,
decision D3: it drives the ICU select of every inflecting language and nothing else), outfit,
hair style, hair colour, skin tone, outfit colours (primary, secondary), hat, accessory, then
Randomise and Done. UP/DOWN choose a row, LEFT/RIGHT change it. Every colour comes from the
game's palette (data/characters/witch.json), so nothing clashes.

The preview plays the idle animation and shows the dialogue portrait, both built from the same
layer choices. A refused name (magic/names.py) is answered in character, with a suggestion
(TAB takes it).

The mirror (opened later from the Hearth) is the same scene with the name locked: the name is
in the Scrolls and the log already.

Must not: change the world; the name reaches the database only through a new battle's witch row.

STATUS: name rules, gender, every look option, randomise, preview (sprite and portrait), mirror.
"""

from __future__ import annotations

import pygame

from engine import render
from engine.animation import Character, default_look, spec
from i18n import CATALOG, t
from i18n.width import text_cells
from magic.names import MAX_LENGTH, check_name

LOOK_ROWS = [("outfit", "outfit"), ("hair", "hair"), ("hair_colour", "hair"), ("skin", "skin"),
             ("primary", "primary"), ("secondary", "secondary"), ("hat", "hat"),
             ("accessory", "accessory")]
GENDERS = ("feminine", "masculine")


def choices(row: str) -> list[str]:
    s = spec()
    if row in ("outfit", "hair", "hat", "accessory"):
        return list(s["options"][row])
    return list(s["colours"]["hair" if row == "hair_colour" else row])


class CreatorScene:
    PLACE = "menu"

    def __init__(self, game, mirror: bool = False, back=None):
        self.game, self.mirror, self.back, self.time = game, mirror, back, 0
        player = game.state.player
        self.name = player.name or CATALOG.player["name"]
        self.gender = player.gender or "feminine"
        self.look = {**default_look(), **player.look}
        self.rows = (["name"] if not mirror else []) + ["gender"] + \
            [row for row, _ in LOOK_ROWS] + ["randomise", "done"]
        self.row = 0
        self.composing = ""
        self.refusal: tuple[str, str] | None = None     # (i18n key, suggestion)
        self.preview = Character(self.look)

    def enter(self):
        pygame.key.start_text_input()

    def exit(self):
        pygame.key.stop_text_input()

    def update(self, dt):
        self.time += dt
        self.preview.animator.update(dt)

    # ------------------------------------------------------------ changes

    def _rebuild(self) -> None:
        self.preview = Character(self.look)

    def change(self, row: str, step: int) -> None:
        if row == "gender":
            self.gender = GENDERS[(GENDERS.index(self.gender) + step) % len(GENDERS)]
        elif row in self.look:
            options = choices(row)
            current = self.look[row] if self.look[row] in options else options[0]
            self.look[row] = options[(options.index(current) + step) % len(options)]
            self._rebuild()
        self.game.audio.play("typing", self.row)

    def randomise(self) -> None:
        rng = self.game.vfx                    # visual randomness only, never a battle's rng
        for row, _ in LOOK_ROWS:
            self.look[row] = rng.choice(choices(row))
        self._rebuild()
        self.game.audio.play("rune")

    def finish(self) -> None:
        if not self.mirror:
            key, value = check_name(self.name)
            if key:
                self.refusal = (key, value)
                self.game.audio.play("miscast")
                return
            self.name = value
        player = self.game.state.player
        if not self.mirror:
            player.name = self.name
        player.gender, player.look = self.gender, dict(self.look)
        CATALOG.set_player(player.name, player.gender)
        self.game.audio.play("confirm")
        if self.mirror:
            self.game.switch(self.back)
        else:
            self.game.start_profile()

    # ------------------------------------------------------------ input

    def handle(self, event):
        row = self.rows[self.row]
        if row == "name" and event.type == pygame.TEXTEDITING:
            self.composing = event.text
            return
        if row == "name" and event.type == pygame.TEXTINPUT:
            self.composing = ""
            if len(self.name) < MAX_LENGTH:
                self.name += event.text[: MAX_LENGTH - len(self.name)]
                self.refusal = None
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE and self.back is not None:
            self.game.switch(self.back)
        elif event.key == pygame.K_UP:
            self.row = (self.row - 1) % len(self.rows)
        elif event.key == pygame.K_DOWN:
            self.row = (self.row + 1) % len(self.rows)
        elif row == "name" and event.key == pygame.K_BACKSPACE:
            self.name, self.refusal = self.name[:-1], None
        elif event.key == pygame.K_TAB and self.refusal:
            self.name, self.refusal = self.refusal[1], None      # take the suggestion
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and row not in ("name", "randomise",
                                                                             "done"):
            self.change(row, -1 if event.key == pygame.K_LEFT else 1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if row == "randomise":
                self.randomise()
            elif row == "done" or row == "name":
                self.finish()
            else:
                self.change(row, 1)

    # ------------------------------------------------------------ drawing

    def value(self, row: str) -> str:
        if row == "name":
            return self.name + self.composing + ("_" if (self.time // 400) % 2 == 0 else " ")
        if row == "gender":
            return t(f"creator.gender.{self.gender}")
        if row in ("randomise", "done"):
            return ""
        return t(f"creator.value.{self.look[row]}")

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        title = t("creator.mirror_title" if self.mirror else "creator.title")
        f.draw(canvas, title, (12, 8), render.BUTTER)
        y = 24
        for i, row in enumerate(self.rows):
            chosen = i == self.row
            if chosen:
                pygame.draw.rect(canvas, render.DUSK, (8, y - 2, 196, 9))
            f.draw(canvas, t(f"creator.row.{row}"), (12, y), render.WHITE if chosen else render.LILAC)
            value = self.value(row)
            f.draw(canvas, value, (200 - text_cells(value) * render.ADVANCE, y), render.GOLD)
            y += 10
        # The preview: the sprite (idle, twice the size) and the portrait, same choices.
        sprite = pygame.transform.scale_by(self.preview.frame(), 2)
        canvas.blit(sprite, (262, 88))
        portrait = pygame.transform.scale_by(self.preview.portrait(), 2)
        render.panel(canvas, pygame.Rect(250, 14, 68, 68))
        canvas.blit(portrait, (252, 16))
        if self.refusal:
            key, suggestion = self.refusal
            from engine.grimoire import wrap
            for i, line in enumerate(wrap(t(key, suggestion=suggestion), 76)[:2]):
                f.draw(canvas, line, (12, 150 + i * 8), render.RED)
        f.draw(canvas, t("creator.keys"), (12, 170), render.GREY)
