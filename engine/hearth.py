"""The Hearth on screen (prompt 08 §2): the camp between regions, and its small query desks.

How it works: HearthScene draws the camp (engine/hd_art.py: the lean-to, the fire, the letter
box) with the protagonist and the companions by the fire, and a menu of what can be done:
sleep, cook, talk, read the letters, the stall, the mirror, the Scroll shelf, a world backup,
and leave. The rules live in magic/hearth.py and magic/shop.py (no pygame); this file only
shows them. Cooking and buying happen at a QueryDesk: a small Grimoire with an editor on the
left, the result on the right and a line from whoever is at the desk; every query goes through
the guard. Talks and letters are script nodes (data/story/hearth.script, letters.script) played
by the DialogueScene, which comes back here when they end.

Must not: no rules here (they are in magic/); no literal player-visible text (i18n keys); the
world changes only through queries.

STATUS: HearthScene, QueryDesk (cook, stall), letters, shelf, backups, mirror, leave, woke.
"""

from __future__ import annotations

from typing import Callable

import pygame

from engine import gfx, hd_art, render
from engine.dialogue import DialogueBox
from engine.grimoire import wrap
from engine.textinput import QueryEditor, schema_tables, schema_words
from i18n import CATALOG, t
from magic.cast import cell_text
from magic.guard import Miscast
from magic.hearth import DATA, Hearth
from magic.shop import Shop

MARTA_LOOK = {"outfit": "coat", "hair": "braid", "hat": "wide", "accessory": "scarf",
              "skin": "clay", "hair_colour": "black", "primary": "forest", "secondary": "gold"}


def _hd(canvas) -> bool:
    return getattr(canvas, "scale", 1) >= render.WORLD_SCALE


def draw_hearth(game, canvas, time: int, people: bool = True) -> None:
    """The camp at night, with the fire; the protagonist and companions when people is True."""
    if _hd(canvas):
        gfx.blit_hd(canvas, hd_art.hearth(), (0, 0))
        gfx.blit_hd(canvas, hd_art.campfire(time // 140 % 4), (146, 122))
    else:
        canvas.fill(render.NIGHT)
        gfx.rect(canvas, render.FOREST, (0, 128, 320, 52))
        gfx.circle(canvas, render.AMBER, (160, 140), 6)
    if not people:
        return
    from engine.scenes import draw_protagonist
    draw_protagonist(game, canvas, (196, 152))
    for i, cid in enumerate(Hearth(game.state, game.fatigue).companions()):
        companion_character(cid).draw(canvas, (120 - i * 26, 150), flip=True)


_CHARACTERS: dict = {}


def companion_character(cid: str):
    from engine.animation import Character
    if cid not in _CHARACTERS:
        _CHARACTERS[cid] = Character(MARTA_LOOK if cid == "marta" else {})
    return _CHARACTERS[cid]


def leave_hearth(game, after: str | None) -> None:
    """Out of the camp: the map when there is one, else the next guardian's arrival, else the
    title (the end of this build)."""
    try:
        from engine.worldmap import MapScene
    except ImportError:
        MapScene = None
    if MapScene is not None:
        game.switch(MapScene(game, after))
        return
    from engine.scenes import DialogueScene, TitleScene
    if after:
        game.switch(DialogueScene(game, f"{after}_intro", after))
    else:
        game.switch(TitleScene(game))


# ------------------------------------------------------------------ the camp

class HearthScene:
    PLACE = "hearth"
    MENU = pygame.Rect(206, 8, 108, 118)

    def __init__(self, game, after: str | None = None, woke: bool = False,
                 greeted: bool = False):
        self.game, self.after, self.time = game, after, 0
        self.hearth = Hearth(game.state, game.fatigue, game.scrolls)
        self.choice = 0
        self.message = ""
        self.woke = woke
        if not greeted:
            self.hearth.arrive()
            if woke:
                self.hearth.sleep()               # carried here and put to bed
            game.autosave()
        self.greeted = greeted

    # ------------------------------------------------------------ what can be done

    def items(self) -> list[tuple[str, Callable[[], None]]]:
        h = self.hearth
        out = [(t("hearth.sleep"), self.sleep),
               (t("hearth.cook"), self.cook)]
        for cid in h.companions():
            out.append((t("hearth.talk", name=h.companion(cid)["name"].split()[0]),
                        lambda cid=cid: self.talk(cid)))
        due = len(h.letters_due())
        out.append((t("hearth.letters", count=due), self.letters))
        out += [(t("hearth.stall"), self.stall), (t("hearth.mirror"), self.mirror),
                (t("hearth.shelf"), self.shelf), (t("hearth.backup"), self.backup),
                (t("hearth.leave"), self.leave)]
        return out

    def _here(self, message: str = "") -> "HearthScene":
        scene = HearthScene(self.game, self.after, greeted=True)
        scene.hearth = self.hearth
        scene.choice, scene.message = self.choice, message
        return scene

    def _back_here(self, message: str = "") -> None:
        self.game.switch(self._here(message))

    def _say(self, node: str, script: str = "hearth", then=None) -> bool:
        from engine.scenes import DialogueScene
        from story.scenes import scene_lines
        variables = self.hearth.variables()
        if not scene_lines(node, variables, script):
            return False
        self.game.switch(DialogueScene(self.game, node, self.after or "", script=script,
                                       then=then or (lambda: self._back_here()),
                                       variables=variables))
        return True

    def sleep(self) -> None:
        fell = self.hearth.sleep()
        self.game.keep_fatigue()
        self.game.autosave()
        self.message = t("hearth.slept", amount=round(fell * 100))
        self.game.audio.play("hp_up")

    def cook(self) -> None:
        h = self.hearth

        def run(sql):
            meal = h.cook(sql)
            self.game.keep_fatigue()
            if meal.name:
                return meal.columns, meal.rows, t("hearth.ate", meal=meal.name,
                                                  amount=round(meal.rest * 100)), True
            return meal.columns, meal.rows, t("hearth.just_looking"), False
        self.game.switch(QueryDesk(self.game, "hearth.cook_title", "hearth.cook_prompt",
                                   h.kitchen(), h.cook_draft(), run, self._back_here,
                                   speaker="Marta Quill" if h.companions() else "Grimoire"))

    def talk(self, cid: str) -> None:
        self._say(self.hearth.companion(cid)["talk"])

    def letters(self) -> None:
        due = self.hearth.letters_due()
        if not due:
            self.message = t("hearth.no_letters")
            return
        letter = due[0]

        def done():
            self.hearth.read_letter(letter)
            self.game.keep_fatigue()
            self._back_here(t("hearth.letter_read"))
        self.game.audio.play("rune")
        self._say(letter, "letters", then=done)

    def stall(self) -> None:
        state = self.game.state
        from magic.battle import EXPLORATION
        shop = Shop(state.inventory, EXPLORATION["coins"]["start"] if state.coins is None
                    else state.coins, CATALOG.player["name"])

        def run(sql):
            receipt = shop.query(sql)
            if receipt.kind == "write":
                state.inventory, state.coins = dict(shop.inventory), shop.coins
                self.game.autosave()
                items = ", ".join(f"{n} x{q}" for n, q in receipt.bought.items())
                return receipt.columns, receipt.rows, t("shop.bought", items=items,
                                                        price=receipt.paid), False
            return receipt.columns, receipt.rows, "", False
        self.game.switch(QueryDesk(self.game, "hearth.stall_title", "hearth.stall_prompt",
                                   shop._db(), Shop.draft(), run, self._back_here,
                                   speaker="Shopkeeper", purse=lambda: shop.coins))

    def mirror(self) -> None:
        from engine.creator import CreatorScene
        self.game.switch(CreatorScene(self.game, mirror=True, back=self._here()))

    def shelf(self) -> None:
        self.game.switch(ShelfScene(self.game, self._back_here))

    def backup(self) -> None:
        self.game.switch(NameScene(self.game, "hearth.backup_prompt",
                                   lambda name: self._backed_up(name), self._back_here))

    def _backed_up(self, name: str) -> None:
        try:
            saved = self.hearth.backup(name)
        except ValueError:
            self._back_here()
            return
        self.game.autosave()
        self._back_here(t("hearth.backed_up", name=saved))

    def leave(self) -> None:
        out = self.hearth.leave()
        self.game.keep_fatigue()
        self.game.autosave()
        go = lambda: leave_hearth(self.game, self.after)
        said = False
        if not out["slept"]:
            for cid in self.hearth.companions():
                node = self.hearth.companion(cid)["leave"]
                said = self._say(node, then=go)
                if said:
                    break
        if not said:
            go()

    # ------------------------------------------------------------ the scene

    def enter(self):
        if not self.greeted:
            self.greeted = True
            node = DATA["woke"] if self.woke else DATA["arrival"]
            self._say(node, then=lambda: self._back_here())

    def exit(self):
        pass

    def update(self, dt):
        self.time += dt

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return
        items = self.items()
        if event.key == pygame.K_UP:
            self.choice = (self.choice - 1) % len(items)
        elif event.key == pygame.K_DOWN:
            self.choice = (self.choice + 1) % len(items)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.game.audio.play("confirm")
            self.message = ""
            items[min(self.choice, len(items) - 1)][1]()
        elif event.key == pygame.K_p:
            from engine.menus import PauseScene
            self.game.switch(PauseScene(self.game, self))

    def draw(self, canvas):
        f = render.font()
        draw_hearth(self.game, canvas, self.time)
        render.panel(canvas, self.MENU)
        f.draw(canvas, t("hearth.title"), (self.MENU.x + 4, self.MENU.y + 3), render.VIOLET)
        for i, (label, _) in enumerate(self.items()):
            y = self.MENU.y + 14 + i * 10
            if i == self.choice:
                f.draw(canvas, ">", (self.MENU.x + 3, y), render.GOLD)
            f.draw(canvas, label, (self.MENU.x + 10, y), render.INK if i == self.choice
                   else render.SLATE)
        self._draw_status(canvas)
        if self.message:
            box = pygame.Rect(6, 156, 196, 20)
            render.panel(canvas, box)
            for i, line in enumerate(wrap(self.message, 46)[:2]):
                f.draw(canvas, line, (box.x + 4, box.y + 2 + i * 8), render.INK)

    def _draw_status(self, canvas):
        """Fatigue (a candle and its band), letters waiting, coins."""
        f = render.font()
        fatigue = self.game.fatigue
        box = pygame.Rect(6, 6, 150, 20)
        render.panel(canvas, box)
        band = fatigue.band
        f.draw(canvas, t(f"panel.fatigue.{band.id}", rows=fatigue.page_rows()),
               (box.x + 4, box.y + 3), render.INK)
        render.meter(canvas, pygame.Rect(box.x + 4, box.y + 12, 80, 4),
                     round(100 * (1 - fatigue.value)), 100, render.AMBER)
        coins = self.game.state.coins
        from magic.battle import EXPLORATION
        coins = EXPLORATION["coins"]["start"] if coins is None else coins
        label = t("hearth.coins", coins=coins)
        f.draw(canvas, label, (box.right - 4 - f.width(label), box.y + 10), render.GOLD)


# ------------------------------------------------------------------ a small Grimoire

class QueryDesk:
    """A query, a result and a voice: the stall, the cooking pot (and later the puzzles)."""
    PLACE = "hearth"
    EDITOR = pygame.Rect(8, 56, 146, 72)
    RESULT = pygame.Rect(166, 56, 146, 72)

    def __init__(self, game, title_key: str, prompt_key: str, conn, draft: str,
                 run: Callable, back: Callable, speaker: str = "Grimoire",
                 purse: Callable[[], int] | None = None, done_back: bool = True):
        self.game, self.time = game, 0
        self.title_key, self.prompt_key = title_key, prompt_key
        self.run, self.back = run, back
        self.speaker, self.purse = speaker, purse
        self.tables = [(name, [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')])
                       for name in schema_tables(conn)]
        self.editor = QueryEditor(names=schema_words(conn), tables=schema_tables(conn),
                                  unlocked={"WHERE", "LIMIT", "ORDER BY", "JOIN", "GROUP BY"},
                                  columns=36, visible_lines=7)
        self.editor.set_text(draft)
        self.columns: list[str] = []
        self.rows: list[tuple] = []
        self.line = t(prompt_key)
        self.error = False
        self.finished = False
        self.done_back = done_back

    def enter(self):
        pygame.key.start_text_input()

    def exit(self):
        pygame.key.stop_text_input()

    def update(self, dt):
        self.time += dt

    def submit(self, sql: str) -> None:
        try:
            self.columns, self.rows, line, done = self.run(sql)
            self.error = False
            self.line = line or t(self.prompt_key)
            self.game.audio.play("cast" if done else "scry")
            if done:
                self.finished = True
        except Miscast as miscast:
            self.columns, self.rows, self.line, self.error = [], [], str(miscast), True
            self.game.audio.play("miscast")

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.back(self.line if self.finished else "")
            return
        if self.finished and event.type == pygame.KEYDOWN and \
                event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.done_back:
            self.back(self.line)
            return
        sql = self.editor.handle_event(event)
        if sql:
            self.submit(sql)
            self.editor.set_text(sql)             # the query stays on the page, to edit

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)                 # a desk by the fire: the camp behind is dark
        top = pygame.Rect(4, 4, 312, 44)
        render.panel(canvas, top)
        f.draw(canvas, t(self.title_key), (top.x + 4, top.y + 3), render.VIOLET)
        if self.purse is not None:
            coins = t("hearth.coins", coins=self.purse())
            f.draw(canvas, coins, (top.right - 4 - f.width(coins), top.y + 3), render.GOLD)
        who = t(f"speaker.{self.speaker}") if self.speaker in ("Grimoire", "Shopkeeper") \
            else self.speaker
        for i, line in enumerate(wrap(f"{who}: {self.line}", 74)[:3]):
            f.draw(canvas, line, (top.x + 4, top.y + 13 + i * 9),
                   render.WINE if self.error else render.INK)
        for rect, label in ((self.EDITOR, t("grimoire.your_query")),
                            (self.RESULT, t("grimoire.result"))):
            render.panel(canvas, rect.inflate(6, 14).move(0, -4))
            f.draw(canvas, label, (rect.x, rect.y - 8), render.VIOLET)
        self.editor.draw(canvas, self.EDITOR.topleft, self.time, True)
        self._draw_result(canvas)
        tables = "  ".join(f"{name}({', '.join(cols)})" for name, cols in self.tables)
        for i, line in enumerate(wrap(tables, 76)[:3]):
            f.draw(canvas, line, (6, 140 + i * 8), render.LILAC, shadow=render.INK)
        keys = t("hearth.desk_keys_done") if self.finished else t("hearth.desk_keys")
        f.draw(canvas, keys, (6, 170), render.BUTTER, shadow=render.INK)

    def _draw_result(self, canvas):
        f = render.font()
        if not self.columns:
            return
        widths = [len(c) for c in self.columns]
        for row in self.rows:
            for i, v in enumerate(row):
                widths[i] = max(widths[i], len(cell_text(v)))
        canvas.set_clip(self.RESULT)
        x = self.RESULT.x
        xs = []
        for w in widths:
            xs.append(x)
            x += (w + 1) * render.ADVANCE
        for name, x in zip(self.columns, xs):
            f.draw(canvas, name, (x, self.RESULT.y), render.LEATHER)
        for r, row in enumerate(self.rows[:6]):
            for value, x in zip(row, xs):
                f.draw(canvas, cell_text(value), (x, self.RESULT.y + 10 + r * 10), render.INK)
        canvas.set_clip(None)


# ------------------------------------------------------------------ the Scroll shelf

class ShelfScene:
    """The Scrolls the protagonist has saved (views): read them, throw one away."""
    PLACE = "hearth"

    def __init__(self, game, back: Callable):
        self.game, self.back, self.time, self.choice = game, back, 0, 0

    def enter(self): pass
    def exit(self): pass

    def update(self, dt):
        self.time += dt

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return
        names = sorted(self.game.scrolls)
        if event.key == pygame.K_ESCAPE:
            self.back("")
        elif names and event.key == pygame.K_UP:
            self.choice = (self.choice - 1) % len(names)
        elif names and event.key == pygame.K_DOWN:
            self.choice = (self.choice + 1) % len(names)
        elif names and event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            del self.game.scrolls[names[min(self.choice, len(names) - 1)]]
            self.game.state.scrolls = dict(self.game.scrolls)
            self.choice = max(0, self.choice - 1)

    def draw(self, canvas):
        f = render.font()
        draw_hearth(self.game, canvas, self.time, people=False)
        box = pygame.Rect(20, 14, 280, 152)
        render.panel(canvas, box)
        f.draw(canvas, t("hearth.shelf_title"), (box.x + 6, box.y + 4), render.VIOLET)
        names = sorted(self.game.scrolls)
        if not names:
            for i, line in enumerate(wrap(t("hearth.shelf_empty"), 64)):
                f.draw(canvas, line, (box.x + 6, box.y + 18 + i * 9), render.SLATE)
        for i, name in enumerate(names[:7]):
            y = box.y + 18 + i * 18
            colour = render.INK if i == self.choice else render.SLATE
            f.draw(canvas, ("> " if i == self.choice else "  ") + f"scroll_{name}",
                   (box.x + 6, y), colour)
            f.draw(canvas, wrap(self.game.scrolls[name], 64)[0], (box.x + 18, y + 8),
                   render.LEATHER)
        f.draw(canvas, t("hearth.shelf_keys"), (box.x + 6, box.bottom - 10), render.SLATE)


# ------------------------------------------------------------------ naming a backup

class NameScene:
    PLACE = "hearth"

    def __init__(self, game, prompt_key: str, done: Callable[[str], None], back: Callable):
        self.game, self.prompt_key, self.done, self.back = game, prompt_key, done, back
        self.text, self.time = "", 0

    def enter(self):
        pygame.key.start_text_input()

    def exit(self):
        pygame.key.stop_text_input()

    def update(self, dt):
        self.time += dt

    def handle(self, event):
        if event.type == pygame.TEXTINPUT:
            self.text = (self.text + event.text)[:24]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.back("")
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.text.strip():
                self.done(self.text)

    def draw(self, canvas):
        f = render.font()
        draw_hearth(self.game, canvas, self.time, people=False)
        box = pygame.Rect(40, 60, 240, 50)
        render.panel(canvas, box)
        for i, line in enumerate(wrap(t(self.prompt_key), 56)[:2]):
            f.draw(canvas, line, (box.x + 6, box.y + 5 + i * 9), render.INK)
        cursor = "_" if (self.time // 400) % 2 == 0 else " "
        f.draw(canvas, self.text + cursor, (box.x + 6, box.y + 30), render.VIOLET)
