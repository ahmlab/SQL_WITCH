"""Scenes: Title -> Dialogue -> Battle -> Result -> next guardian, a small state machine.

Scenes only draw and react to input. Every rule lives in magic/ and ai/: the battle scene
calls Battle.ada_cast() and Battle.foe_act() and then plays back the events they report,
one narration beat at a time. Art is placeholder shapes for now (design doc 7.2: pixels last).

Two random generators exist on purpose: the battle's own (inside Battle, never touched here)
and game.vfx for screen shake and wandering, so visual effects can never change a battle.
The guardian walks around the battlefield by steering (ai/steering.py) towards whatever its
brain ordered: the brain decides, the scene only integrates the motion.

STATUS: title, story, tutorial hand-off, Slime and Knight battles with steering, narration,
sounds, F1; results.
"""

from __future__ import annotations

import json
import random
import re
import time
import uuid
from dataclasses import dataclass
from typing import Callable

import pygame

from engine import gfx

from engine import fx, hd_art, render, scenery
from engine.audio import Audio, Silent, pick_track
from engine.grimoire import LEFT_PAGE, Grimoire, draw_foe_book, wrap
from engine.guide import Guide
from engine.ada_anim import AdaAnimator
from engine.sprites import draw_ada
from engine.textinput import (KEYWORD_WORDS, QueryEditor, layout, locked_words,
                              schema_tables, schema_words)
from ai import steering
from ai.roster import GUARDIANS, ORDER, next_guardian
from magic.battle import Battle
from magic.cast import SCRY_PER_TURN, CastReport, effect_word
from magic.db import DATA_DIR
from magic.battle import _summary
from magic.guard import Miscast
from i18n import CATALOG, locale as i18n_locale, set_locale, t
from story.codex import Codex
from save.settings_file import Settings, SettingsFile
from save.state import GameState
from save.telemetry import Telemetry
from save.stats import cast_record, miscast_record
from magic.tutorial import tables_read
from engine import settings as settings_screen
from story.pacing import Typewriter, settings as settings_pacing, voice
from story.scenes import INTRO, legacy, mercy_line, overkill_lesson, record, text_of_key
from story.script import Choice, ScriptRunner, get as script_named, plain as plain_text
from story.script import tokens as script_tokens
from story.hints import HintDirector, context_of
from engine.dialogue import DialogueBox, draw_log, portraits as dialogue_portraits
from engine.animation import Character, is_default as is_default_look

LOG_KEEP = 60                      # lines the dialogue log remembers


def _last_word(text: str) -> str:
    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", text)
    return match.group(0) if match else ""


def load_dialogue() -> dict:
    """Text by name for the result screens and the battle tip, from data/story/intro.script."""
    return legacy()


def is_cast_key(event) -> bool:
    return (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            and bool(event.mod & pygame.KMOD_CTRL))


def is_confirm_key(event) -> bool:
    return event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE)


# ------------------------------------------------------------------ the scene machine

class Scene:
    def __init__(self, game: "Game"):
        self.game = game
        self.time = 0                     # ms since the scene started

    def enter(self) -> None: ...
    def exit(self) -> None: ...
    def handle(self, event: pygame.event.Event) -> None: ...

    def update(self, dt: int) -> None:
        self.time += dt

    def draw(self, canvas: pygame.Surface) -> None: ...


class Game:
    """Holds the current scene and what all scenes share. main.py runs the loop."""

    def __init__(self, canvas: pygame.Surface, seed: int, screen=None,
                 audio: Audio | None = None, start: str = "slime", saves=None,
                 settings=None, skip_creator: bool = True, locale: str | None = None):
        self.canvas = canvas
        # Where the story begins: "tutorial", "slime" or "knight". main.py starts at the
        # tutorial; the default here stays "slime" so a bare Game() is the classic slice.
        self.start = start
        self.story_start = start          # where every New Game begins (never a loaded save's)
        self.runes: set[str] = set()      # runes Ada keeps after each victory
        self.screen = screen              # optional: only used for screen shake
        self.audio = audio if audio is not None else Silent()
        self.seed = seed
        self.vfx = random.Random(seed)    # visual effects only, never the battle's rng
        self.dialogue = load_dialogue()
        self.dialogue_log: list[tuple[str, str]] = []   # what was said, for the log (L)
        self.auto_advance = False
        self.debug = False
        self.running = True
        self.held: set[int] = set()        # keys down right now (to spot held-key repeats)
        self.guide_seen = False           # the GUIDE button glows until it is opened once
        self.last_music: str | None = None   # so a retry does not replay the same track
        self.codex = Codex()                 # what the player has learned (plan §4.2)
        self.scrolls: dict[str, str] = {}    # saved queries: name -> SQL (plan §4.4)
        self.scene: Scene | None = None
        # Profiles, slots and settings (save/, prompt 05). Without a save folder (tests, the
        # smoke test) the game plays as before: nothing is written, nothing is asked.
        self.saves = saves
        self.settings_file = SettingsFile(saves.root) if saves else None
        self.first_launch = bool(self.settings_file and self.settings_file.first_launch)
        self.settings = settings or (self.settings_file.load() if self.settings_file
                                     else Settings())
        if locale:
            self.settings.language = locale            # --locale wins for this session
        self.skip_creator = skip_creator
        self.profile_id: str | None = None
        self.state = GameState(at=start)
        self.session = {"start": round(time.time()), "seconds": 0.0}
        self.state.sessions.append(self.session)
        self.telemetry = Telemetry(saves.root, lambda: self.settings.telemetry,
                                   lambda: self.settings.share_queries) if saves else None
        # A language switch re-renders what is open: most text is looked up every frame;
        # what a scene keeps (its dialogue lines) is refreshed by its relocalise().
        CATALOG.listen(self._relocalise)
        settings_screen.apply(self)
        self.switch(TitleScene(self))

    # ------------------------------------------------------------ saves and the log

    def character(self):
        """The layered protagonist for the current look (built once per look)."""
        look = dict(self.state.player.look)
        key = tuple(sorted(look.items()))
        if getattr(self, "_character", (None, None))[0] != key:
            self._character = (key, Character(look))
            dialogue_portraits["ada"] = self._character[1].portrait
        return self._character[1]

    def save_settings(self) -> None:
        if self.settings_file is not None:
            self.settings_file.save(self.settings)

    def snapshot(self) -> GameState:
        """The state to write: what the session holds now (never a battle in progress)."""
        state = self.state
        state.runes = sorted(self.runes)
        state.codex = self.codex.to_json()
        state.scrolls = dict(self.scrolls)
        state.player.name = CATALOG.player["name"]
        state.player.gender = CATALOG.player["gender"]
        state.settings = self.settings.to_dict()
        state.telemetry = {"consent": self.settings.telemetry,
                           "share_queries": self.settings.share_queries}
        return state

    def restore(self, state: GameState) -> None:
        self.state = state
        self.session = {"start": round(time.time()), "seconds": 0.0}
        state.sessions.append(self.session)
        self.runes = set(state.runes)
        self.codex = Codex.from_json(state.codex)
        self.scrolls = dict(state.scrolls)
        self.start = state.at if state.at != "end" else self.story_start
        CATALOG.set_player(state.player.name, state.player.gender)

    def autosave(self) -> bool:
        """After every guardian defeated (and at the Hearth, later). Never mid-battle."""
        if self.saves is None or self.profile_id is None:
            return False
        self.saves.save(self.profile_id, "auto", self.snapshot())
        return True

    def save_slot(self, slot: str) -> bool:
        if self.saves is None or self.profile_id is None:
            return False
        self.saves.save(self.profile_id, slot, self.snapshot())
        return True

    def record_cast(self, record: dict) -> None:
        record.update(run=self.state.run_id, battle=getattr(self.scene, "battle_id", ""))
        self.state.log.append(record)
        if not record.get("miscast"):
            outcome = "overflow" if record["overflow"] else "look" if record["scry"] else "cast"
            self.track("cast", guardian=record["guardian"], turn=record["turn"],
                       techniques=record["techniques"], kind=record["kind"], outcome=outcome,
                       rows=record["rows"], read=record["read"], overflow=record["overflow"],
                       mp_spent=record["mp_spent"], sql=record["sql"])

    def record_battle(self, record: dict) -> None:
        record.update(run=self.state.run_id, fatigue=self.state.fatigue)
        self.state.battles.append(record)
        self.track("battle_end", **record)

    def track(self, event: str, **fields) -> None:
        if self.telemetry is not None:
            self.telemetry.record(event, **fields)

    # ------------------------------------------------------------ starting and continuing

    def begin_story(self) -> None:
        """Into the story at the point the state holds (a new game: the intro)."""
        at = self.state.at
        if at == "end":
            # A finished run: play it again from the first guardian, keeping the profile,
            # its Codex, runes and Scrolls (there is no later content yet to continue to).
            at = self.state.at = ORDER[0]
        key = "intro" if at in ("tutorial", "slime") else f"{at}_intro"
        self.switch(DialogueScene(self, key, at))

    def new_game(self) -> None:
        """A new profile and run: the first-launch flow (language, consent, the creator)."""
        from engine.menus import first_launch_steps
        self.state = GameState(at=self.story_start)
        self.state.sessions.append(self.session)
        self.runes, self.codex, self.scrolls = set(), Codex(), {}
        first_launch_steps(self)

    def start_profile(self, profile_id: str | None = None) -> None:
        """The flow is done: the profile exists from now on (a new one, or the one given:
        a profile that has no save yet), the story begins."""
        if self.saves is not None:
            self.profile_id = profile_id or self.saves.create_profile(
                CATALOG.player["name"], self.state.player.look)
        self.begin_story()

    def play_profile(self, profile_id: str) -> None:
        """A profile with no save yet (it never beat a guardian): its story from the start,
        with its name and look."""
        profile = self.saves.profile(profile_id)
        self.state = GameState(at=self.story_start)
        self.state.sessions.append(self.session)
        self.state.player.name = profile.get("name", "Ada")
        self.state.player.look = dict(profile.get("look") or {})
        self.runes, self.codex, self.scrolls = set(), Codex(), {}
        CATALOG.set_player(self.state.player.name, self.state.player.gender)
        self.start_profile(profile_id)

    def continue_game(self) -> bool:
        found = self.saves.latest() if self.saves else None
        if found is None:
            return False
        self.load(*found)
        return True

    def load(self, profile: str, slot: str, backup: bool = False) -> None:
        state = self.saves.load_backup(profile, slot) if backup else \
            self.saves.load(profile, slot)
        self.profile_id = profile
        self.restore(state)
        self.begin_story()

    def _relocalise(self, locale: str) -> None:
        self.dialogue = load_dialogue()
        if hasattr(self.scene, "relocalise"):
            self.scene.relocalise()


    def switch(self, scene: Scene) -> None:
        if self.scene:
            self.scene.exit()
        self.scene = scene
        scene.enter()

    def handle(self, event: pygame.event.Event) -> None:
        repeat = False
        if event.type == pygame.KEYDOWN:
            repeat = event.key in self.held
            self.held.add(event.key)
        elif event.type == pygame.KEYUP:
            self.held.discard(event.key)
        if event.type == pygame.QUIT:
            self.running = False
        elif any(settings_screen.pressed(event, action, self.settings)
                 for action in ("debug", "mute", "help", "tables")):
            # The key bindings of the settings (F1 debug, F2 mute, F3 guide, F4 tables).
            if repeat:
                return                         # holding F1 must not make it flicker
            if settings_screen.pressed(event, "debug", self.settings):
                self.debug = not self.debug
            elif settings_screen.pressed(event, "mute", self.settings):
                self.audio.toggle_mute()
            elif settings_screen.pressed(event, "tables", self.settings):
                if hasattr(self.scene, "toggle_tables"):
                    self.scene.toggle_tables()
            elif hasattr(self.scene, "toggle_guide"):
                self.scene.toggle_guide()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = self.screen.to_logical(event.pos) if self.screen else event.pos
            if hasattr(self.scene, "click"):
                self.scene.click(x, y)
        else:
            self.scene.handle(event)

    def update(self, dt: int) -> None:
        self.scene.update(dt)
        self.audio.update(dt)                     # music fades move on with the game's clock
        seconds = dt / 1000
        self.state.playtime_s += seconds
        self.session["seconds"] = round(self.session["seconds"] + seconds, 3)
        place = getattr(self.scene, "PLACE", "menu")
        self.state.time_in[place] = round(self.state.time_in.get(place, 0.0) + seconds, 3)

    def draw(self) -> None:
        if isinstance(self.canvas, render.Canvas):
            self.canvas.begin_frame()             # text is recorded per frame
        self.scene.draw(self.canvas)

    def shake(self, frames: int = 6) -> None:
        if self.screen is not None and self.settings.screen_shake:   # reduced motion: still
            self.screen.shake = frames


# ------------------------------------------------------------------ the protagonist

def draw_protagonist(game, canvas, feet, flash: bool = False, anim=None) -> pygame.Rect:
    """The protagonist seen from behind: the artist's Ada for the default look, the layered
    character (engine/animation.py) for any other look, following the same events (cast, hit,
    faint) that AdaAnimator receives."""
    look = game.state.player.look
    if is_default_look(look):
        return draw_ada(canvas, feet, flash, anim=anim)
    character = game.character()
    if anim is not None:
        seen, animator = character.__dict__.setdefault("seen", {}), character.animator
        if not seen:
            seen.update(cast=anim.cast_at, hit=anim.hit_at, t=anim.t)
        if anim.fainting:
            animator.play("faint")
        elif animator.tag == "faint":                   # a new battle: back on her feet
            animator.__init__(animator.tags)
        elif anim.hit_at != seen["hit"]:
            animator.hit()
        elif anim.cast_at != seen["cast"]:
            animator.play("cast")
        animator.update(max(0, anim.t - seen["t"]))
        seen.update(cast=anim.cast_at, hit=anim.hit_at, t=anim.t)
    return character.draw(canvas, feet, flash=flash)


# ------------------------------------------------------------------ shared scenery

# The glade's colours. The ground is darker than the Slime (render.GRASS), so it stands out,
# and the trees are a night blue-green, so the tree line still reads against the grass.
TREES, GRASS_EDGE, GRASS_FIELD = render.TEAL, render.TEAL, render.FOREST
GROUND_SHADOW = render.TEAL       # shadows on the grass are darker than the grass


def hd(canvas) -> bool:
    """Is this the HD canvas? (Tests draw on plain 320x180 surfaces: the pixel art.)"""
    return getattr(canvas, "scale", 1) >= render.WORLD_SCALE


def draw_backdrop(canvas: pygame.Surface, ground_y: int = 60) -> None:
    """Night sky in bands, a few stars, the moon and the grass of the Tutorial Glade."""
    if hd(canvas):
        gfx.blit_hd(canvas, hd_art.glade(ground_y), (0, 0))
        return
    bands = [(0, render.INK), (12, render.NIGHT), (28, render.DUSK), (44, render.VIOLET)]
    for y, colour in bands:
        gfx.rect(canvas, colour, (0, y, render.LOGICAL_W, ground_y - y))
    for y, _ in bands[1:]:                             # one separator per colour change
        gfx.line(canvas, render.INK, (0, y - 1), (render.LOGICAL_W - 1, y - 1))    
    for i in range(24):                                    # stars on a fixed pattern
        canvas.set_at(((i * 53 + 17) % 320, (i * 29 + 5) % 40), render.LILAC)
    gfx.circle(canvas, render.BUTTER, (292, 14), 7)
    gfx.circle(canvas, render.NIGHT, (296, 12), 6)  # the moon's shadow side
    for x in range(0, render.LOGICAL_W, 8):                # a jagged tree line
        gfx.polygon(canvas, TREES,
                            [(x, ground_y), (x + 4, ground_y - 6 - (x // 8) % 3), (x + 8, ground_y)])
    gfx.rect(canvas, GRASS_EDGE, (0, ground_y, render.LOGICAL_W, 180 - ground_y))
    gfx.rect(canvas, GRASS_FIELD, (0, ground_y + 4, render.LOGICAL_W, 180 - ground_y))


def draw_slime(canvas: pygame.Surface, centre: tuple[int, int], t: int, flash: bool,
               exhausted: bool, fainted: bool) -> None:
    """Placeholder Asterisk Slime: a green dome with an asterisk heart (design doc fig. 11)."""
    cx, cy = centre
    if hd(canvas):
        image = hd_art.slime((t // 150) % 4, exhausted, fainted, flash)
        gfx.blit_hd(canvas, image, (cx - image.get_width() / render.WORLD_SCALE / 2,
                                    cy + 20 - image.get_height() / render.WORLD_SCALE))
        return
    body, edge = (render.WHITE, render.WHITE) if flash else (render.GRASS, render.FOREST)
    if fainted:
        gfx.ellipse(canvas, edge, (cx - 20, cy + 10, 40, 8))
        return
    bob = (0, 1, 1, 0)[(t // 150) % 4] + (2 if exhausted else 0)   # idle: 4 frames x 150 ms
    top = cy - 16 + bob
    gfx.ellipse(canvas, edge, (cx - 18, top, 36, 34))
    gfx.rect(canvas, edge, (cx - 18, top + 17, 36, 16 - bob))
    gfx.ellipse(canvas, body, (cx - 17, top + 1, 34, 32))
    gfx.rect(canvas, body, (cx - 17, top + 17, 34, 15 - bob))
    if not flash:
        gfx.rect(canvas, render.MINT, (cx - 10, top + 5, 3, 3))   # shine
        eye = 1 if exhausted else 3
        gfx.rect(canvas, render.INK, (cx - 7, top + 13, 2, eye))
        gfx.rect(canvas, render.INK, (cx + 5, top + 13, 2, eye))
        render.font().draw(canvas, "*", (cx - 3, top + 18), render.GOLD, scale=2)


# ------------------------------------------------------------------ title

TITLE_DOT = 3                     # big titles: each dot of a 5x7 letter is a 3x3 block

def next_scene(game: "Game", key: str) -> Scene:
    """The scene a story beat leads to: the tutorial, or a guardian's battle."""
    if key == "tutorial":
        # Imported here: the tutorial scene is built on BattleScene, defined in this module.
        from engine.tutorial_scene import TutorialScene
        return TutorialScene(game)
    return BattleScene(game, key)


class TitleScene(Scene):
    """The title: Continue (when a save exists: the most recent), New Game, Load, Settings,
    Statistics, Credits, Quit. UP/DOWN choose, ENTER opens, L changes the language."""

    def __init__(self, game):
        super().__init__(game)
        self.choice = 0

    def items(self) -> list[tuple[str, Callable[[], None]]]:
        from engine import menus
        from engine.stats import StatsScene
        game, saves = self.game, self.game.saves
        out = []
        latest = saves.latest() if saves else None
        if latest:
            out.append((t("menu.continue"), game.continue_game))
        out.append((t("menu.new_game"), game.new_game))
        if saves and saves.profiles():
            out.append((t("menu.load"), lambda: game.switch(menus.LoadScene(game, self))))
        out.append((t("menu.settings"),
                    lambda: game.switch(settings_screen.SettingsScene(game, self))))
        state = saves.load(*latest) if latest else None
        out.append((t("menu.statistics"), lambda: game.switch(StatsScene(game, self, state))))
        out.append((t("menu.credits"), lambda: game.switch(menus.CreditsScene(game, self))))
        out.append((t("menu.quit"), self.quit))
        return out

    def quit(self) -> None:
        self.game.running = False

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            self.next_language()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN):
            count = len(self.items())
            self.choice = (self.choice + (1 if event.key == pygame.K_DOWN else -1)) % count
        elif is_confirm_key(event):
            self.game.audio.play("confirm")
            items = self.items()
            items[min(self.choice, len(items) - 1)][1]()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.running = False

    def draw(self, canvas):
        f = render.font()
        draw_backdrop(canvas, ground_y=120)
        title = "SQL WITCH"
        if hd(canvas):
            image = hd_art.title(title)
            gfx.blit_hd(canvas, image, ((320 - image.get_width() / render.WORLD_SCALE) / 2, 30))
        else:
            f.draw_big(canvas, title, ((320 - f.big_width(title, TITLE_DOT)) // 2, 38),
                       render.BUTTER, TITLE_DOT, shadow=render.AMBER, outline=render.INK)
        sub = t("title.subtitle")
        f.draw(canvas, sub, ((320 - f.width(sub)) // 2, 74), render.LILAC)
        for i, (label, _) in enumerate(self.items()):
            y = 96 + i * 10
            chosen = i == self.choice
            if chosen and (self.time // 500) % 2 == 0:
                f.draw(canvas, ">", ((320 - f.width(label)) // 2 - 8, y), render.GOLD)
            f.draw(canvas, label, ((320 - f.width(label)) // 2, y),
                   render.WHITE if chosen else render.LILAC, shadow=render.INK)
        f.draw(canvas, t("title.seed", seed=self.game.seed), (4, 172), render.GRASS)
        here = i18n_locale()
        name = CATALOG.name_of(here)
        if CATALOG.is_draft(here):
            name = t("title.draft", name=name)
        language = t("title.language", name=name)
        f.draw(canvas, language, (316 - f.width(language), 172), render.LILAC)

    def next_language(self) -> None:
        """L on the title: the next language of the menu (data/i18n/locales.json)."""
        menu = CATALOG.menu_locales(include_pseudo=i18n_locale() == "qps")
        here = i18n_locale()
        nxt = menu[(menu.index(here) + 1) % len(menu)] if here in menu else menu[0]
        self.game.audio.play("confirm")
        set_locale(nxt)


# ------------------------------------------------------------------ dialogue

class DialogueScene(Scene):
    PLACE = "story"
    """A story scene played from a script node (data/story/intro.script): Ada falls asleep at
    her desk, dies, and wakes up in Codd, where a floating book speaks to her; or a guardian
    arrives. Each line's directions name its backdrop ([scene]), Ada's sleepiness ([sleep 0-3]),
    who is on stage ([book] [slime] [knight]), a sound ([sfx]), a portrait, [shake], [wait N].
    The typewriter is story.pacing (time-based, per speaker and language, pauses on
    punctuation). ENTER finishes the line, then moves on; holding it types faster; holding CTRL
    skips; A toggles auto-advance; L opens the log of what was said; ESC skips the scene."""
    FADE_MS = 450                     # half a dip to black between two backdrops
    BOOK_AT = (198, 72)
    BOX = pygame.Rect(8, 128, 304, 44)
    SKIP_HOLD_MS = 90                 # while CTRL is held, a finished line waits this long

    def __init__(self, game, key: str = "intro", guardian: str = "slime"):
        super().__init__(game)
        self.guardian = guardian             # what follows: "tutorial" or a guardian's battle
        self.key = key
        # The script's conditions read these: <<if next == "tutorial">>, codex.WHERE, ...
        self.variables = {"next": guardian,
                          "codex": {page.id: True for page in game.codex.unlocked()}}
        self.runner = ScriptRunner(script_named(INTRO), key, self.variables)
        self.lines: list[dict] = []
        self.choice = None                   # a Choice waiting for the player, when one is due
        self.choice_at = 0
        self._read_ahead()
        self.index = 0
        self.backdrop = self.lines[0].get("scene", "glade") if self.lines else "glade"
        self.fade_from, self.fade_at = "black", 0     # the story fades in from black
        self.drowsy = 0.0
        self.book_born: int | None = None
        self.void_since = 0
        self.held = self.skipping = False
        self.auto = game.auto_advance        # the A key's choice lasts the whole game
        self.show_log = False
        self.done_for = 0                    # ms the current line has been fully shown
        self.shake_until = 0
        self.box = DialogueBox(self.BOX, rows=4)
        self.ada = AdaAnimator()
        self.line_ms = -2.0 * self.FADE_MS   # the first line waits for the fade-in
        self._start_line()

    # ------------------------------------------------------------ the script

    def _read_ahead(self) -> None:
        """Take lines from the runner until a choice or the end."""
        while (item := self.runner.next()) is not None:
            if isinstance(item, Choice):
                self.choice, self.choice_at = item, 0
                return
            self.lines.append(record(item))

    @property
    def line(self) -> dict:
        return self.lines[min(self.index, len(self.lines) - 1)]

    def _shown_chars(self) -> int:
        return self.typer.visible(self.line_ms)

    def _line_done(self) -> bool:
        return self.typer.done(self.line_ms)

    def _start_line(self) -> None:
        line = self.line
        scene = line.get("scene", self.backdrop)
        if scene != self.backdrop:                    # dip to black, then the new place
            self.fade_from, self.fade_at, self.backdrop = self.backdrop, self.time, scene
            self.line_ms = -2.0 * self.FADE_MS
            if scene == "void":
                self.void_since = self.time + self.FADE_MS
        for name, args in line.get("directions", []):
            if name == "wait" and args:
                self.line_ms -= float(args[0])
            elif name == "shake":
                if self.game.settings.screen_shake:          # reduced motion: no tremble
                    self.shake_until = self.time + int(args[0]) if args else self.time + 400
            elif name == "music" and args:
                self.game.audio.play_music(args[0])
        if line.get("book") and self.book_born is None:
            self.book_born = self.time - int(min(0.0, self.line_ms))
        if line.get("sound"):
            self.game.audio.play(line["sound"])
        self.typer = Typewriter(line["markup"], line["speaker"], i18n_locale())
        self.blips = 0
        self.done_for = 0
        self.game.dialogue_log.append((line["speaker"], line["text"]))
        del self.game.dialogue_log[:-LOG_KEEP]

    def relocalise(self) -> None:
        """The language changed: every line again from the catalog, the current one restarted
        at the same moment."""
        for line in self.lines:
            line["markup"] = text_of_key(line["key"], line["markup"])
            line["text"] = plain_text(line["markup"])
        self.typer = Typewriter(self.line["markup"], self.line["speaker"], i18n_locale())

    def _advance(self) -> None:
        if self.index + 1 < len(self.lines):
            self.game.audio.play("next")
            self.index += 1
            self.line_ms = 0.0
            self._start_line()
        elif self.choice is None:
            self.game.audio.play("next")
            self.game.switch(next_scene(self.game, self.guardian))

    def _choose(self, option: int) -> None:
        self.game.audio.play("confirm")
        self.runner.choose(self.choice, option)
        self.choice = None
        before = len(self.lines)
        self._read_ahead()
        if len(self.lines) > before:
            self.index = before - 1
            self._advance()
        else:
            self.game.switch(next_scene(self.game, self.guardian))

    def _choosing(self) -> bool:
        return self.choice is not None and self.index == len(self.lines) - 1 and \
            self._line_done()

    # ------------------------------------------------------------ input and time

    def handle(self, event):
        ctrl = (pygame.K_LCTRL, pygame.K_RCTRL)
        if event.type == pygame.KEYUP:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.held = False
            elif event.key in ctrl:
                self.skipping = False
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.show_log:                             # the log closes with any key
            self.show_log = False
            return
        if event.key == pygame.K_ESCAPE:
            self.game.switch(next_scene(self.game, self.guardian))
        elif event.key == pygame.K_p:              # pause: save, settings, statistics
            from engine.menus import PauseScene
            self.game.switch(PauseScene(self.game, self))
        elif event.key in ctrl:
            self.skipping = True
        elif event.key == pygame.K_l:
            self.show_log = True
        elif event.key == pygame.K_a:
            self.auto = not self.auto
            self.game.auto_advance = self.auto
            self.game.audio.play("confirm")
        elif self._choosing() and event.key in (pygame.K_UP, pygame.K_DOWN):
            step = -1 if event.key == pygame.K_UP else 1
            self.choice_at = (self.choice_at + step) % len(self.choice.options)
        elif is_confirm_key(event):
            self.held = True
            if not self._line_done():
                self.line_ms = max(self.line_ms, self.typer.total_ms)   # finish it at once
            elif self._choosing():
                self._choose(self.choice_at)
            else:
                self._advance()

    def update(self, dt):
        super().update(dt)
        self.ada.update(dt)
        pace = settings_pacing()
        if self.show_log:
            return
        speed = pace["fast_forward"] if (self.held or self.skipping) else 1
        before = self._shown_chars()
        self.line_ms += dt * speed
        shown = self._shown_chars()
        self._blip(before, shown, pace["blip_every"])
        if self._line_done() and self.line_ms >= 0:
            self.done_for += dt
            wait = self.SKIP_HOLD_MS if self.skipping else pace["auto_advance_ms"]
            if (self.skipping or self.auto) and not self._choosing() and self.done_for >= wait:
                self._advance()
        target = float(self.line.get("sleep", self.drowsy))
        step = 0.6 * dt / 1000                        # Ada drifts off slowly, never at once
        self.drowsy = target if abs(target - self.drowsy) <= step else \
            self.drowsy + step * (1 if target > self.drowsy else -1)

    def _blip(self, before: int, shown: int, every: int) -> None:
        """The speaker's voice: one blip every few letters typed (not while skipping)."""
        if shown <= before or self.skipping or not self.line["speaker"]:
            return
        letters = sum(1 for c in self.typer.text[before:shown] if not c.isspace())
        self.blips += letters
        if self.blips >= every:
            self.blips %= every
            event, variant = voice(self.line["speaker"])
            self.game.audio.play(event, variant)

    # ------------------------------------------------------------ drawing

    def _draw_backdrop(self, canvas, name: str) -> None:
        if name == "office":
            progress = 0.95 + 0.04 * min(1.0, self.drowsy / 3)     # it stops at 99%
            scenery.draw_office(canvas, self.time, self.drowsy, progress)
        elif name == "void":
            scenery.draw_void(canvas, self.time - self.void_since)
        elif name in ("glade", "keep"):
            if name == "glade":
                draw_backdrop(canvas, ground_y=110)
            else:
                scenery.draw_keep(canvas, self.time, ground_y=110)
            draw_protagonist(self.game, canvas, ADA_STANDING, anim=self.ada)  # in front of the book
            if self.book_born is not None and self.line.get("book"):
                speaking = (self.line["speaker"] == "Grimoire" and not self._line_done())
                book_at = self.BOOK_AT if name == "glade" else (130, 64)
                scenery.draw_book(canvas, book_at, self.time,
                                  self.time - self.book_born, speaking,
                                  shadow=GROUND_SHADOW if name == "glade" else render.SLATE)
            if self.line.get("slime"):
                draw_slime(canvas, (262, 96), self.time, False, False, False)
            if self.line.get("knight"):
                scenery.draw_knight(canvas, (252, 92), self.time, False, False, True, False)
        else:
            canvas.fill(render.INK)

    def draw(self, canvas):
        f = render.font()
        elapsed = self.time - self.fade_at
        if elapsed < self.FADE_MS:                    # the old place goes dark...
            self._draw_backdrop(canvas, self.fade_from)
            scenery.dim(canvas, canvas.get_rect(), 255 * elapsed // self.FADE_MS)
        else:                                         # ...and the new one comes out of it
            self._draw_backdrop(canvas, self.backdrop)
            if elapsed < 2 * self.FADE_MS:
                scenery.dim(canvas, canvas.get_rect(),
                            255 - 255 * (elapsed - self.FADE_MS) // self.FADE_MS)
        if self.time < self.shake_until:              # [shake]: the whole picture trembles
            canvas.scroll(((self.time // 40) % 3) - 1, ((self.time // 55) % 3) - 1)
        line = self.line
        shown = max(0, self._shown_chars())
        self.box.draw(canvas, line["speaker"], self.typer.tokens, shown, self.time,
                      line.get("portrait"))
        box = self.BOX
        if self._choosing():
            self._draw_choice(canvas)
        elif self._line_done() and (self.time // 400) % 2 == 0:
            f.draw(canvas, "v", (box.right - 8, box.bottom - 9), render.VIOLET)
        if self.auto:
            f.draw(canvas, t("ui.dialogue.auto"), (box.right - 8, box.y + 3), render.GREY, small=True)
        if self.show_log:
            draw_log(canvas, self.game.dialogue_log, t("ui.dialogue.log_close"))

    def _draw_choice(self, canvas) -> None:
        f = render.font()
        options = [CATALOG.raw(key) or text for text, _, key in self.choice.options]
        width = max(f.width(o) for o in options) + 16
        panel = pygame.Rect(self.BOX.right - width, self.BOX.y - 6 - render.LINE_H * len(options),
                            width, render.LINE_H * len(options) + 4)
        render.panel(canvas, panel)
        for i, option in enumerate(options):
            y = panel.y + 3 + i * render.LINE_H
            if i == self.choice_at:
                f.draw(canvas, ">", (panel.x + 3, y), render.VIOLET)
            f.draw(canvas, option, (panel.x + 10, y),
                   render.INK if i == self.choice_at else render.SLATE)


# ------------------------------------------------------------------ battle

@dataclass
class Beat:
    """One line of narration and, optionally, what it does to the picture when it starts."""
    text: str
    ms: int = 700
    effect: Callable[[], None] | None = None
    sounds: tuple[str, ...] = ()          # event names in assets/audio/sounds.json
    speaker: str = ""                     # set: someone talks (a reaction), in a wider box
    markup: str = ""                      # a script line's inline effects ({wave}...), if any
    age: int = 0                          # ms since it started (the typewriter's clock)
    dismissed: bool = False               # the player pressed ENTER: it fades out now

    @property
    def speech(self) -> bool:
        return bool(self.speaker and self.text)


@dataclass
class Popup:
    text: str
    pos: tuple[int, int]
    colour: tuple
    age: int = 0


GUIDE_BUTTON = pygame.Rect(258, 2, 59, 11)        # the clickable "? GUIDE" tab, top right
TABLES_BUTTON = pygame.Rect(LEFT_PAGE.x + 46, LEFT_PAGE.y - 2, 29, 9)   # over the query
TABLES_PANEL = pygame.Rect(4, 4, 312, 94)
KEY_REPEAT_DELAY = 350       # ms a key must be held before it starts repeating
# The danger theme starts when Ada's HP bar drops below a quarter and stops once it is back
# above 35%: the gap keeps it from flapping on and off around a single threshold.
DANGER_OFF_ABOVE = render.HP_DANGER + 0.10
KEY_REPEAT_INTERVAL = 35     # ms between repeats (about 28 per second)
ADA_AT = (24, 58)                                   # where bolts and numbers start/land
ADA_FEET = (42, 100)                                # battle: on the grass, above the Grimoire
ADA_STANDING = (60, 114)                            # story scenes: standing on the grass
HOME = {"slime": (250, 50), "knight": (252, 46), "dummy": (266, 54)}   # each foe's post
FRONT = (182, 56)                                   # the striking spot, closer to Ada
ARENA = pygame.Rect(176, 36, 122, 30)               # where a guardian may walk (clear of panels)
ADA_BODY = (ADA_AT[0] + 18, ADA_AT[1] + 22)


class BattleScene(Scene):
    PLACE = "battle"                       # for the statistics: time spent in battle
    WAIT_MS = 350                          # a short breath between turns
    DANGER_MUSIC = True                    # the tutorial turns this off: nothing is at stake
    HINTS = True                           # the tutorial turns this off: its coach talks
    FOE_PANEL = pygame.Rect(4, 3, 120, 20)
    ADA_PANEL = pygame.Rect(196, 70, 120, 27)

    def __init__(self, game, guardian: str = "slime", battle: Battle | None = None):
        super().__init__(game)
        self.battle_id = uuid.uuid4().hex[:8]          # the log's link between casts
        self.codex_open = False
        self.rewinds = self.tricks_found = self.scrolls_made = 0
        if guardian in ORDER:                          # Continue resumes at this battle's start
            game.state.at = guardian
        game.track("battle_start", guardian=guardian, seed=game.seed,
                   retry=game.state.retries.get(guardian, 0))
        self.key = guardian
        runes = set(game.runes) | set(GUARDIANS[guardian].ada_runes)
        # A scene may be handed its battle (the tutorial runs its own); otherwise a new one.
        self.battle = battle or Battle(seed=game.seed, guardian=guardian, ada_runes=runes,
                                       codex=game.codex, scrolls=game.scrolls,
                                       ada_name=CATALOG.player["name"])
        # The guardian's body on screen, steered towards whatever its brain orders.
        home = steering.Vec(*HOME[guardian])
        self.body = steering.Kinematic(home, max_speed=75 if guardian == "knight" else 55)
        self.places = {"home": steering.Kinematic(home),
                       "front": steering.Kinematic(steering.Vec(*FRONT)),
                       "ada": steering.Kinematic(steering.Vec(*ADA_BODY))}
        self.wander = steering.WanderState()
        self.order = steering.Movement("wander", "home")
        conn = self.battle.conn
        self.editor = QueryEditor(names=schema_words(conn), tables=schema_tables(conn),
                                  unlocked=set(self.battle.state.ada.runes), visible_lines=6)
        self.editor.cast_key = lambda e: settings_screen.pressed(e, "cast", game.settings)
        self.grimoire = Grimoire(self.editor)
        self.beats: list[Beat] = []
        self.beat: Beat | None = None
        self.beat_left = 0
        self.popups: list[Popup] = []
        self.flash = {"ada": 0, "foe": 0}
        state = self.battle.state
        # What the bars show; narration effects move these, the true state catches up at rest.
        self.shown = {"ada": [state.ada.hp, state.ada.mp], "foe": [state.foe.hp, state.foe.mp]}
        self.bars = {side: [float(v) for v in values] for side, values in self.shown.items()}
        self.foe_sql: str | None = None
        self.foe_report: CastReport | None = None
        self.reasoning: dict = {}
        self.glow: tuple[str, int] | None = None
        self.shown_relevance = self.battle.state.foe.relevance
        self.idle = 0
        self.rounds_told = set()
        self.fx = fx.Effects(game.vfx)          # sparks and lightning: looks only
        self.streak = fx.Streak()
        self.word_glow: tuple[pygame.Rect, int] | None = None
        self.ada = AdaAnimator()
        self._elements: dict[str, str | None] = {}
        self._last_erase = -1000
        # The live rune set: the guide's examples unlock as Ada learns runes mid-battle.
        self.guide = Guide(self.battle.conn, self.battle.state.ada.runes)
        self.tables_open = False
        self.table_rows: list[tuple[pygame.Rect, str]] = []   # clickable table names
        self.schema = [(t, [r[1] for r in conn.execute(f"PRAGMA table_info({t})")])
                       for t in schema_tables(conn) if t != "relics"]
        self.say(game.dialogue["battle_tip"], 2500)
        self.phase = "input" if self.battle.whose_turn == "ada" else "wait"
        self.rewind_open = False                    # the Rewind page (F6)
        self.rewind_choice = 0
        self.last_cast: str | None = None           # the query F7 would save as a Scroll
        self._last_thud = -1000
        # Who speaks up when Ada is stuck (story/hints.py); the tutorial has its own coach.
        self.hints = HintDirector(guardian) if self.HINTS else None
        self.speech_box = DialogueBox(pygame.Rect(4, 70, 312, 28), rows=3, opaque=True)
        self.hint_context: dict = {}
        if self.phase == "input":
            self._hint_turn()

    def enter(self):
        pygame.key.start_text_input()
        # Held keys repeat: after a short pause, Backspace and the arrows keep going.
        pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)
        self._start_music()

    def _start_music(self) -> None:
        """Each guardian lists its themes in sounds.json ("battle" is the fallback). One is
        picked with the visual random generator, never the battle's: same seed, same fight."""
        audio = self.game.audio
        name = self.key if self.key in audio.config.get("music", {}) else "battle"
        choice = pick_track(audio.music_files(name), self.game.last_music, self.game.vfx)
        self.game.last_music = audio.play_music(name, choice) or self.game.last_music

    def _update_danger(self) -> None:
        """Only Ada's HP counts, as the bar shows it (after the narration has caught up)."""
        if not self.DANGER_MUSIC:
            return
        ada = self.battle.state.ada
        shown = self.bars["ada"][0] / ada.max_hp if ada.max_hp else 1.0
        if shown < render.HP_DANGER:
            self.game.audio.set_danger(True)
        elif shown > DANGER_OFF_ABOVE:
            self.game.audio.set_danger(False)

    def exit(self):
        pygame.key.stop_text_input()
        pygame.key.set_repeat(0)
        self.game.audio.stop_music()

    # ------------------------------------------------------------ narration

    def say(self, text: str, ms: int = 700, effect=None, *sounds: str, speaker: str = "",
            markup: str = "") -> None:
        look = settings_pacing()["battle_speech"]
        if speaker and text and not look["wait_for_enter"]:
            # Someone speaks and the line closes by itself: time to read it (data/pacing.json).
            ms += look["extra_ms"]
        self.beats.append(Beat(text, ms, effect, sounds, speaker, markup))

    def speak_hint(self, hint) -> None:
        """Someone speaks during Ada's turn (story/hints.py): typed out, long enough to read."""
        self.game.track("hint", guardian=self.key, topic=hint.topic, node=hint.node)
        ms = int(Typewriter(hint.markup, hint.speaker, i18n_locale()).total_ms) + 2600
        self.say(hint.text, ms, None, *voice(hint.speaker)[:1], speaker=hint.speaker,
                 markup=hint.markup)

    def _hint_turn(self) -> None:
        """Ada's turn starts: the Hint Director's idle clock restarts on fresh numbers."""
        if self.hints is not None:
            self.hints.start_turn(self.battle.state.turn)
            self.hint_context = context_of(self.battle)

    def side_of(self, name: str) -> str:
        return "ada" if name == self.battle.state.ada.name else "foe"

    def _element_of(self, spell: str) -> str | None:
        """A spell's element, read from the battle tables, to colour its bolt."""
        if spell not in self._elements:
            row = self.battle.conn.execute(
                "SELECT element FROM spells WHERE name = ? UNION ALL "
                "SELECT element FROM foe_spells WHERE name = ?", (spell, spell)).fetchone()
            self._elements[spell] = row[0] if row else None
        return self._elements[spell]

    def _hit(self, side: str, damage: int, crit: bool, spell: str = ""):
        def effect():
            ada_hand = (ADA_AT[0] + 22, ADA_AT[1] + 2)
            foe = self.foe_xy()
            start, end = (ada_hand, foe) if side == "foe" else (foe, ada_hand)
            self.fx.bolt(start, end, render.ELEMENT_COLOURS.get(self._element_of(spell),
                                                                 render.LILAC))
            self.shown[side][0] = max(0, self.shown[side][0] - damage)
            self.flash[side] = 160 if self.game.settings.flashes else 0   # reduced motion
            if side == "ada":
                self.ada.hit()
            x, y = (self.foe_xy()[0], self.foe_xy()[1] - 28) if side == "foe" \
                else (ADA_AT[0] + 18, ADA_AT[1] - 6)
            self.popups.append(Popup(str(damage), (x, y), render.GOLD if crit else render.WHITE))
            if crit:
                self.game.shake()
        return effect

    def foe_xy(self) -> tuple[int, int]:
        return render.snap(self.body.position.x), render.snap(self.body.position.y)

    def _show_relevance(self, up: bool):
        def effect():
            self.shown_relevance = up
            self.fx.burst(*self.foe_xy(), count=16 if not up else 8, speed=70,
                          colours=(render.AQUA, render.LILAC, render.WHITE))
            if not up:
                self.game.shake(4)
        return effect

    def _set_shown(self, side: str, slot: int, value: int):
        def effect():
            self.shown[side][slot] = value
        return effect

    def _add_shown(self, side: str, slot: int, amount: int):
        def effect():
            self.shown[side][slot] += amount
        return effect

    def narrate(self, report: CastReport) -> None:
        """Turn the cast's events into beats, in the order they happened (design doc 7.3)."""
        margin = overkill = 0
        for event in report.events:
            kind = event[0]
            if kind == "cast":
                _, _, _, spell, target, dmg, crit, mult = event
                words = effect_word(mult)
                text = t("battle.hit", spell=spell, damage=dmg) + \
                    (" " + t("battle.crit") if crit else "") + (f" {words}" if words else "")
                self.say(text, 650, self._hit(self.side_of(target), dmg, crit, spell),
                         "crit" if crit else "hit", *(("hp_down",) if dmg else ()))
            elif kind in ("heal", "item"):
                side = self.side_of(event[3])
                amount = event[4] if kind == "heal" else event[5]
                slot = 1 if kind == "item" and event[4] == "mp" else 0
                self.say(t("battle.gain", spell=event[2], amount=amount), 600, self._add_shown(side, slot, amount),
                         "mp_up" if slot == 1 else "hp_up")
            elif kind == "ward":
                self.say(t("battle.ward", spell=event[2], amount=event[4]), 600, None, "cast")
            elif kind == "fizzle":
                if event[3] == "overflow":
                    margin += 1
                elif event[3] == "duplicate":
                    self.say(t("battle.again", spell=event[2]), 600, None, "fizzle")
                elif event[3] == "no_mana":
                    self.say(t("battle.no_mp", spell=event[2]), 450, None, "fizzle")
                else:
                    self.say(t("battle.none_left", spell=event[2]), 450)
            elif kind == "mp":
                _, name, before, after = event
                if margin:
                    self.say(t("battle.margin", count=margin), 800, None, "fizzle")
                    margin = 0
                if before != after:
                    self.say(t("battle.mp", before=before, after=after), 600,
                             self._set_shown(self.side_of(name), 1, after),
                             "mp_down" if after < before else "mp_up")
            elif kind == "deflect":
                self.say(t("battle.deflect", spell=event[2]), 750, None, "deflect")
            elif kind == "shatter":
                self.say(t("battle.shatter"), 900, self._show_relevance(False),
                         "shatter")
            elif kind == "relevance":
                self.say(t("battle.relevance_up"), 1000,
                         self._show_relevance(True), "ward_up")
            elif kind == "dispel":
                self.say(t("battle.dispel", spell=event[2], amount=event[4]), 800,
                         None, "fizzle")
            elif kind == "exhausted":
                self.say(t("battle.exhausted", foe=event[1].split()[-1]), 800)
            elif kind == "faint":
                self.say(t("battle.faints", name=event[1]), 1000, None, "faint")
            elif kind == "overkill":
                # The foe is down and the next row of the page hits it anyway: it begs.
                overkill += 1
                foe = event[1]
                if foe == self.battle.state.foe.name:
                    self._speak_line(mercy_line(self.key, overkill, foe), "deflect")
            elif kind == "scry":
                self.say(t("battle.free_look") if not event[2] else t("battle.nothing_castable"), 600)
            elif kind == "write":
                key, args = _summary(report)
                self.say(t("ui.write.done", summary=t(key, **args)), 900, None, "cast")
            elif kind == "confused":
                self.say(t("world.forgets", foe=event[1]), 900, None, "fizzle")
            elif kind == "rewind":
                self.say(t("reaction.rewind_grimoire", turn=event[1]), 1100,
                         self._sync_shown, "invitation", speaker="Grimoire")

        if overkill:
            self._speak_line(overkill_lesson(), "next")

    def _speak_line(self, line: dict, sound: str) -> None:
        """A script line as a beat: in the speech box when someone speaks, typed out."""
        ms = int(Typewriter(line["markup"], line["speaker"], i18n_locale()).total_ms) + 1300
        if line["speaker"]:
            self.say(line["text"], ms, None, sound, speaker=line["speaker"], markup=line["markup"])
        else:
            self.say(line["text"], ms, None, sound)

    def _speaker(self, who: str) -> str:
        # "Ada" is the protagonist's speaker id: their tag shows the player's own name.
        return {"foe": self.battle.state.foe.name, "grimoire": "Grimoire",
                "ada": "Ada"}.get(who, who)

    def _tell_world(self, report: CastReport) -> None:
        """What the world said about the last query: reactions, tricks, new Codex pages."""
        for reaction in list(report.reactions) + list(report.tricks):
            if reaction.effect == "refuse":
                continue                              # a refusal is shown as a miscast
            args = dict(reaction.args, foe=self.battle.state.foe.name)
            sound = "deflect" if reaction.effect in ("foe_rages", "fight_ends_confused") \
                else "invitation" if reaction in report.tricks else "next"
            self.say(t(reaction.line_key, **args), 2200, None, sound,
                     speaker=self._speaker(reaction.speaker))
        for page in report.codex:
            self.say(t("codex.unlocked", technique=page), 900, None, "rune")

    def _tell_round_end(self) -> None:
        end = self.battle.last_round
        if end and end.turn not in self.rounds_told:
            self.rounds_told.add(end.turn)
            self.say(t("battle.round_end", turn=end.turn, mp=end.mp_gained["ada"]), 700, self._sync_shown,
                     *(("mp_up",) if end.mp_gained["ada"] else ()))

    def _sync_shown(self) -> None:
        state = self.battle.state
        self.shown = {"ada": [state.ada.hp, state.ada.mp], "foe": [state.foe.hp, state.foe.mp]}
        self.shown_relevance = state.foe.relevance

    # ------------------------------------------------------------ turns

    def cast(self, sql: str) -> None:
        turn = self.battle.state.turn
        started = time.perf_counter()
        try:
            report = self.battle.ada_cast(sql)
        except Miscast as miscast:
            self.grimoire.show_miscast(str(miscast), self.time)
            self.game.audio.play("miscast")
            if self.hints is not None:
                self.hints.miscast()
            self.game.record_cast(miscast_record(sql, self.key, turn, miscast.key))
            return
        ms = (time.perf_counter() - started) * 1000            # real, measured
        plan, scanned = self.battle.explain(sql) if report.kind == "read" else ([], 0)
        try:
            tables = tables_read(sql)
        except Exception:
            tables = set()
        self.game.record_cast(cast_record(report, sql, self.key, turn, ms, plan, scanned,
                                          tables))
        self.tricks_found += len(report.tricks)
        self.game.audio.play("scry" if report.scry else "cast")
        self._ada_casts(report)
        if self.hints is not None:
            self.hints.observe(report)
            self.hint_context = context_of(self.battle)
        self.last_cast = sql
        if "weakness" in report.columns and report.rows:
            weakness = report.rows[0][report.columns.index("weakness")]
            if weakness:                            # she has seen it: now it can be suggested
                self.editor.known_weakness = weakness
        looks = SCRY_PER_TURN - self.battle.state.scries_used
        self.grimoire.show_result(report, self.time, looks)
        self.narrate(report)
        self._tell_world(report)
        if self.battle.spellbook.can_save(sql):
            from magic.spellbook import SCROLL_THRESHOLD
            self.say(t("ui.scroll.can_save", count=SCROLL_THRESHOLD), 1400, None, "rune")
        self._tell_round_end()
        if report.ends_turn:
            self.phase, self.idle = "wait", 0

    def _ada_casts(self, report: CastReport) -> None:
        """Ada steps forward and her hands glow in the colour of her first spell."""
        if report.casts:
            self.ada.cast(render.ELEMENT_COLOURS.get(report.casts[0].element, render.LILAC))

    def _update_ada(self, dt: int) -> None:
        """Ada's body follows what the bars show: hurt when red, down when empty."""
        self.ada.update(dt)
        ada = self.battle.state.ada
        shown = self.bars["ada"][0]
        self.ada.set_low(0 < shown < ada.max_hp * render.HP_DANGER)
        if shown <= 0 and ada.hp <= 0:
            self.ada.faint()

    def foe_turn(self) -> None:
        turn = self.battle.foe_act()
        self.foe_sql, self.foe_report, self.reasoning = turn.sql, turn.report, turn.reasoning
        if turn.movement is not None:
            self.order = turn.movement                 # steer as the brain planned
        name = self.battle.state.foe.name.split()[-1]
        self.say(t("battle.foe_casts", foe=name), 650, None, "scry" if turn.report.scry else "cast")
        self.narrate(turn.report)
        self._tell_world(turn.report)
        if turn.acknowledged:                          # she already used it: no lesson needed
            self.say(t("codex.acknowledged", foe=name, technique=turn.acknowledged), 1400,
                     None, "rune", speaker=self.battle.state.foe.name)
        if turn.invitation:
            rune = turn.invitation

            def learn():
                self.editor.unlocked.add(rune)
                self.glow = (rune, self.time)
            self.say(t("battle.rune_glows", rune=rune, foe=name), 1200, learn, "invitation")
            self.say(t("battle.copies_rune", rune=rune), 1200)
        self._tell_round_end()

    # ------------------------------------------------------------ input and time

    def toggle_tables(self) -> None:
        self.tables_open = not self.tables_open
        self.game.audio.play("scry")

    def toggle_guide(self) -> None:
        self.tables_open = False
        self.guide.toggle()
        if self.guide.open:
            self.game.guide_seen = True
            self.game.audio.play("scry")

    # ------------------------------------------------------------ someone speaks

    def speech_waiting(self) -> bool:
        """A speech box is on screen, waiting for the player to read it and press ENTER."""
        beat = self.beat
        return beat is not None and beat.speech and not beat.dismissed and \
            settings_pacing()["battle_speech"]["wait_for_enter"]

    def _speech_typer(self, beat: Beat) -> Typewriter:
        return Typewriter(script_tokens(beat.markup or beat.text), beat.speaker, i18n_locale())

    def advance_speech(self) -> None:
        """ENTER (or a click) on a speech box: finish typing it, or close it."""
        beat = self.beat
        total = self._speech_typer(beat).total_ms if beat.markup else 0
        if beat.age < total:
            beat.age = int(total) + 1                 # show the rest of the line at once
            return
        beat.dismissed = True
        self.beat_left = settings_pacing()["battle_speech"]["fade_ms"]
        self.game.audio.play("next")

    def speech_key(self, event) -> bool:
        """While someone speaks, ENTER moves on and every other key is held back (so a key
        meant for the speech never lands in the query). True if the event was taken."""
        if not self.speech_waiting():
            return False
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.advance_speech()
        return event.type in (pygame.KEYDOWN, pygame.TEXTINPUT, pygame.TEXTEDITING)

    def click(self, x: int, y: int) -> None:
        if self.speech_waiting():
            self.advance_speech()
            return
        if GUIDE_BUTTON.collidepoint(x, y):
            self.toggle_guide()
        elif TABLES_BUTTON.collidepoint(x, y):
            self.toggle_tables()
        elif self.tables_open:
            for rect, table in self.table_rows:
                if rect.collidepoint(x, y):            # write the table's name in the query
                    self.editor.insert(table)
                    self.game.audio.play("rune")
            self.tables_open = False
        elif self.guide.open:
            self.guide.click(x, y)
        elif step := self.grimoire.scroll_button_at(x, y):
            self._scroll_result(step)

    def _scroll_result(self, step: int) -> None:
        if self.grimoire.scroll(step):
            self.game.audio.play("scry")

    def _is_scroll_key(self, event) -> int:
        """Shift + Left/Right slides the result page sideways: -1, +1, or 0 if not."""
        if event.type == pygame.KEYDOWN and event.mod & pygame.KMOD_SHIFT:
            return {pygame.K_LEFT: -1, pygame.K_RIGHT: 1}.get(event.key, 0)
        return 0

    # ------------------------------------------------------------ Rewind and Scrolls

    def toggle_rewind(self) -> None:
        if self.phase != "input" and not self.rewind_open:
            self._thud()
            return
        self.rewind_open = not self.rewind_open
        self.rewind_choice = max(0, len(self.battle.world.snapshots) - 1)
        self.game.audio.play("scry")

    def _rewind_key(self, event) -> None:
        count = len(self.battle.world.snapshots)
        if event.key in (pygame.K_ESCAPE, pygame.K_F6):
            self.rewind_open = False
        elif event.key == pygame.K_UP and count:
            self.rewind_choice = max(0, self.rewind_choice - 1)
        elif event.key == pygame.K_DOWN and count:
            self.rewind_choice = min(count - 1, self.rewind_choice + 1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and count:
            self.rewind_open = False
            report = self.battle.rewind(self.rewind_choice)
            self.rewinds += 1
            self.game.track("rewind", guardian=self.key, turn=self.battle.state.turn)
            self.grimoire.clear()
            self.narrate(report)
            self._tell_world(report)
            self._tell_round_end()
            self.phase, self.idle = "wait", 0

    def save_scroll(self) -> None:
        book = self.battle.spellbook
        if self.phase != "input" or not self.last_cast or not book.can_save(self.last_cast):
            self._thud()
            return
        view = book.save(self.last_cast)
        self.game.scrolls = dict(book.scrolls)
        self.scrolls_made += 1
        self.editor.names.append(view)                # TAB completes it from now on
        self.say(t("ui.scroll.saved", name=view), 1600, None, "invitation")

    def _thud(self) -> None:
        """The book is closed: a soft sound, at most a few times a second (keys can repeat)."""
        if self.time - self._last_thud > 250:
            self.game.audio.play("locked")
            self._last_thud = self.time

    def handle(self, event):
        if self.speech_key(event):
            return
        if self.codex_open:                         # the Codex page takes the keyboard
            if event.type == pygame.KEYDOWN:
                self.codex_open = False
            return
        if settings_screen.pressed(event, "codex", self.game.settings):
            self.codex_open = True
            return
        if settings_screen.pressed(event, "rewind", self.game.settings):
            self.toggle_rewind()
            return
        if settings_screen.pressed(event, "scroll", self.game.settings):
            self.save_scroll()
            return
        if self.rewind_open:                        # the Rewind page takes the keyboard
            if event.type == pygame.KEYDOWN:
                self._rewind_key(event)
            return
        if not self.guide.open:                     # reading the page works at any time
            if step := self._is_scroll_key(event):
                self._scroll_result(step)
                return
            if event.type == pygame.MOUSEWHEEL:
                self._scroll_result(1 if (event.x > 0 or event.y < 0) else -1)
                return
        if self.tables_open and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.tables_open = False
            return
        if self.guide.open:                         # the guide takes the keyboard
            sql = self.guide.handle(event)
            if sql:
                self.editor.set_text(layout(sql, self.editor.columns))   # ready to cast
                self.game.audio.play("rune")
            return
        if self.phase == "input":
            if self.hints is not None and event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
                self.hints.keystroke()
            before = self.editor.text
            sql = self.editor.handle_event(event)
            if sql:
                cx, cy = self.grimoire.cursor_xy()
                self.fx.burst(cx, cy, count=14, speed=80)
                self.cast(sql)
                return
            self._typing_feedback(event, before)
            return
        if settings_screen.pressed(event, "cast", self.game.settings):   # waiting: fast-forward
            self.beat_left = 0
        elif event.type == pygame.TEXTINPUT or (event.type == pygame.KEYDOWN and
                                                event.key not in (pygame.K_LCTRL, pygame.K_RCTRL,
                                                                  pygame.K_LSHIFT, pygame.K_RSHIFT)):
            # Turn lock (plan §4.3): the book is closed outside Ada's turn. Keys are dropped,
            # never buffered for later, with one soft sound.
            self._thud()

    # ------------------------------------------------------------ the magic of typing

    def _typing_feedback(self, event, before: str) -> None:
        """Every key is a little spell: a note and a spark. Letters of one word climb a
        pentatonic scale; finishing a keyword makes its rune glow and chime."""
        if self.editor.text == before:
            return                                   # arrows, Home, F-keys: nothing typed
        self.ada.typed()
        x, y = self.grimoire.cursor_xy()
        self.streak.hit(self.time)
        heat = self.streak.level(self.time)
        if event.type == pygame.TEXTINPUT:
            char = event.text[-1:]
            if char.isalnum() or char == "_":
                word = self.editor.word_before_cursor()
                self.game.audio.play("typing", len(word) - 1)
                self.fx.burst(x, y + 2, count=2 + round(heat * 4), speed=30 + heat * 30)
            else:
                line = self.editor.lines[self.editor.row][:self.editor.col - 1]
                self._finish_word(_last_word(line), x - render.ADVANCE, y)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                if self.time - self._last_erase >= 70:    # held: not 28 sounds a second
                    self.game.audio.play("erase")
                    self._last_erase = self.time
                self.fx.burst(x, y + 3, count=2, colours=(render.GREY, render.SLATE), life=200)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.game.audio.play("newline")
                above = self.editor.lines[self.editor.row - 1] if self.editor.row else ""
                end_x = self.grimoire.EDITOR_AT[0] + len(above) * render.ADVANCE
                self._finish_word(_last_word(above), end_x, y - render.LINE_H, quiet=True)
            else:                                    # TAB or -> accepted a completion
                word = self.editor.word_before_cursor()
                if not self._finish_word(word, x, y):
                    self.game.audio.play("typing", 7)
                    self.fx.burst(x, y, count=6)

    def _finish_word(self, word: str, end_x: int, y: int, quiet: bool = False) -> bool:
        """A word just ended at end_x. If it is a keyword, its rune glows (or refuses)."""
        upper = word.upper()
        if upper not in KEYWORD_WORDS:
            return False
        rect = pygame.Rect(end_x - len(word) * render.ADVANCE - 1, y - 1,
                           len(word) * render.ADVANCE + 1, render.GLYPH_H + 1)
        if upper in locked_words(self.editor.unlocked):
            self.game.audio.play("locked")
            self.fx.burst(rect.centerx, rect.centery, count=4,
                          colours=(render.GREY, render.SLATE), life=260)
            return True
        if not quiet:
            self.game.audio.play("rune")
        self.word_glow = (rect, self.time)
        self.fx.burst(rect.centerx, rect.y, count=10, speed=60)
        return True

    def update(self, dt):
        super().update(dt)
        self._update_beats(dt)
        self._update_visuals(dt)
        self._update_danger()
        self._update_ada(dt)
        self._update_body(dt)
        self.fx.update(dt)
        resting = self.beat is None and not self.beats
        if resting:
            self._sync_shown()
        if resting and self.phase == "input" and self.hints is not None and \
                not (self.guide.open or self.rewind_open):
            if hint := self.hints.tick(dt, self.hint_context):
                self.speak_hint(hint)
        if not resting or self.phase == "input":
            return
        self.idle += dt
        if self.idle < self.WAIT_MS:
            return
        self.idle = 0
        turn = self.battle.whose_turn
        if self.phase == "end":
            self.battle.stats = {"battle": self.battle_id, "guardian": self.key,
                                 "result": self.battle.winner, "rounds": self.battle.state.turn,
                                 "seconds": round(self.time / 1000, 1), "rewinds": self.rewinds,
                                 "tricks": self.tricks_found, "scrolls": self.scrolls_made,
                                 "retries": self.game.state.retries.get(self.key, 0)}
            self.game.switch(ResultScene(self.game, self.battle))
        elif turn == "foe":
            self.foe_turn()
        elif turn == "ada":
            self.phase = "input"
            self._hint_turn()
            idle = getattr(self.battle.brain, "idle_movement", None)
            self.order = idle() if idle else steering.Movement("wander", "home")
        else:
            self.phase = "end"
            self.say("", 900)

    def _update_beats(self, dt: int) -> None:
        if self.beat is not None:
            self.beat.age += dt
            if not self.speech_waiting():          # someone speaks: it waits for ENTER
                self.beat_left -= dt
                if self.beat_left <= 0:
                    self.beat = None
        if self.beat is None and self.beats:
            self.beat = self.beats.pop(0)
            self.beat_left = self.beat.ms
            if self.beat.effect:
                self.beat.effect()
            for sound in self.beat.sounds:
                self.game.audio.play(sound)

    def _update_body(self, dt: int) -> None:
        """Steering: the brain's Movement order becomes an acceleration every frame."""
        accel = steering.steer(self.order, self.body, self.places, self.wander, self.game.vfx)
        self.body.integrate(accel, dt / 1000)
        p = self.body.position
        x = min(max(p.x, ARENA.left), ARENA.right)
        y = min(max(p.y, ARENA.top), ARENA.bottom)
        if (x, y) != (p.x, p.y):                       # stopped by the arena's edge
            self.body.position = steering.Vec(x, y)
            self.body.velocity = steering.Vec()

    def _update_visuals(self, dt: int) -> None:
        for side in ("ada", "foe"):
            self.flash[side] = max(0, self.flash[side] - dt)
            for slot in (0, 1):                      # bars glide at 60 points per second
                target, current = self.shown[side][slot], self.bars[side][slot]
                step = 60 * dt / 1000
                self.bars[side][slot] = target if abs(target - current) <= step else \
                    current + step * (1 if target > current else -1)
        for popup in self.popups:
            popup.age += dt
        self.popups = [p for p in self.popups if p.age < 800]

    # ------------------------------------------------------------ drawing

    def draw(self, canvas):
        f = render.font()
        state = self.battle.state
        flash = self.flash["foe"] > 0 and (self.time // 40) % 2 == 0
        fainted = self.bars["foe"][0] <= 0
        if self.key == "knight":
            scenery.draw_keep(canvas, self.time)
            scenery.draw_knight(canvas, self.foe_xy(), self.time, flash, fainted,
                                self.shown_relevance, self.body.velocity.length() > 5)
        else:
            draw_backdrop(canvas)
            home = HOME[self.key]
            gfx.ellipse(canvas, GROUND_SHADOW, (home[0] - 28, home[1] + 12, 56, 10))
            draw_slime(canvas, self.foe_xy(), self.time, flash, state.foe.exhausted, fainted)
        # Seen from behind, standing at the bottom left of the battlefield.
        draw_protagonist(self.game, canvas, ADA_FEET,
                         self.flash["ada"] > 0 and (self.time // 40) % 2 == 0,
                 anim=self.ada)

        self._draw_foe_panel(canvas)
        glow_word = self.glow[0] if self.glow and self.time - self.glow[1] < 4000 else None
        draw_foe_book(canvas, state.foe.name, self.foe_sql, self.foe_report, glow_word, self.time)
        self._draw_ada_panel(canvas)

        self._draw_narration(canvas)

        self.grimoire.closed = None if self.phase == "input" else self._closed_reason()
        self.grimoire.draw(canvas, self.time, focused=self.phase == "input")
        self._draw_page_heat(canvas)
        self.fx.draw(canvas)
        self._draw_guide_button(canvas)
        self._draw_tables_button(canvas)
        self._draw_speech(canvas)                     # over the battle, under the overlays
        if self.tables_open:
            self._draw_tables(canvas)
        if self.rewind_open:
            self._draw_rewind(canvas)
        if self.codex_open:
            self._draw_codex(canvas)
        if self.game.debug:
            self._draw_debug(canvas)
        self.guide.draw(canvas, self.time)

    def _closed_reason(self) -> str:
        whose = self.battle.whose_turn
        if whose == "over":
            return t("ui.book_closed.over")
        if whose == "foe":
            return t("ui.book_closed.foe_turn", foe=self.battle.state.foe.name)
        return t("ui.book_closed.animating")

    def _draw_rewind(self, canvas):
        """F6: the snapshots of this fight, oldest first; ENTER turns the world back."""
        f = render.font()
        box = TABLES_PANEL
        render.cover(canvas, box, (*render.INK, 255))
        render.cover(canvas, box.inflate(-2, -2), (*render.CREAM, 255))
        x, y = box.x + 4, box.y + 4
        f.draw(canvas, t("ui.rewind.title"), (x, y), render.VIOLET)
        y += render.LINE_H + 3
        entries = self.battle.world.entries()
        if not entries:
            for line in wrap(t("ui.rewind.empty"), 74):
                f.draw(canvas, line, (x, y), render.SLATE)
                y += render.LINE_H
        first = max(0, self.rewind_choice - 7)
        for i, (turn, key, args) in enumerate(entries[first:first + 9], start=first):
            text = t("world.rewind_entry", turn=turn, summary=t(key, **args))
            if i == self.rewind_choice:
                render.cover(canvas, pygame.Rect(x - 2, y - 1, box.width - 6, render.LINE_H + 1),
                             (*render.BUTTER, 255))
            f.draw(canvas, text[:74], (x, y), render.INK)
            y += render.LINE_H + 1
        f.draw(canvas, t("ui.rewind.help"), (x, box.bottom - 9), render.WINE)

    def _draw_narration(self, canvas):
        """The current beat in its little box, and the floating damage numbers."""
        f = render.font()
        if self.beat is not None and self.beat.text and self.beat.speaker:
            pass                                      # drawn on top of everything: _draw_speech
        elif self.beat is not None and self.beat.text:
            box = pygame.Rect(64, 80, 128, 17)
            render.panel(canvas, box)
            for i, line in enumerate(wrap(self.beat.text, 30)[:2]):
                f.draw(canvas, line, (box.x + 4, box.y + 3 + i * render.LINE_H), render.INK)
        for p in self.popups:
            f.draw(canvas, p.text, (p.pos[0] - f.width(p.text) // 2, p.pos[1] - p.age // 60),
                   p.colour, shadow=render.INK)

    def _draw_codex(self, canvas):
        """The Codex (F8): every technique the player has used or seen, in their own words."""
        f = render.font()
        box = pygame.Rect(8, 6, 304, 168)
        render.cover(canvas, box, (*render.INK, 245))
        f.draw(canvas, t("codex.screen.title"), (box.x + 6, box.y + 5), render.BUTTER)
        y = box.y + 16
        pages = self.battle.codex.unlocked()
        if not pages:
            f.draw(canvas, t("codex.screen.empty"), (box.x + 6, y), render.GREY)
        for page in pages:
            if y > box.bottom - 24:
                break
            f.draw(canvas, page.title, (box.x + 6, y), render.GOLD)
            y += render.LINE_H
            for line in wrap(page.text, 72)[:2]:
                f.draw(canvas, line, (box.x + 10, y), render.LILAC)
                y += render.LINE_H
            y += 2
        f.draw(canvas, t("codex.screen.close"), (box.x + 6, box.bottom - 9), render.GREY)

    def _draw_speech(self, canvas):
        """Someone speaks (a reaction, a trick, a hint, a plea): the rest of the screen darkens
        and a wide box with their name on a tag sits on top, opaque over the panels behind
        (their text is on the text layer). A script line keeps its effects and types out."""
        beat = self.beat
        if beat is None or not beat.text or not beat.speaker:
            return
        look = settings_pacing()["battle_speech"]
        fade = max(1, look["fade_ms"])
        closing = beat.dismissed or not look["wait_for_enter"]
        ramp = min(1.0, beat.age / fade, self.beat_left / fade if closing else 1.0)
        if ramp > 0 and look["dim"] > 0:
            render.cover(canvas, canvas.get_rect(), (*render.INK, round(look["dim"] * ramp)))
        typer = self._speech_typer(beat)
        shown = typer.visible(beat.age) if beat.markup else 10 ** 6
        box = self.speech_box.draw(canvas, beat.speaker, typer.tokens, shown, self.time)
        if self.speech_waiting() and shown >= len(typer) and (self.time // 400) % 2 == 0:
            f = render.font()
            more = t("ui.speech.continue")             # the line waits: say how to go on
            f.draw(canvas, more, (box.right - 6 - f.width(more, small=True), box.bottom - 8),
                   render.VIOLET, small=True)

    def _draw_tables_button(self, canvas):
        f = render.font()
        fill = render.TEAL if self.tables_open else render.FOAM
        gfx.rect(canvas, render.INK, TABLES_BUTTON)
        gfx.rect(canvas, fill, TABLES_BUTTON.inflate(-2, -2))
        f.draw(canvas, t("panel.tables"), (TABLES_BUTTON.x + 3, TABLES_BUTTON.y + 2),
               render.WHITE if self.tables_open else render.TEAL)

    def _draw_tables(self, canvas):
        """Every table of this world and its columns, to know what to write after FROM."""
        f = render.font()
        render.cover(canvas, TABLES_PANEL, (*render.INK, 255))
        render.cover(canvas, TABLES_PANEL.inflate(-2, -2), (*render.CREAM, 255))
        x, y = TABLES_PANEL.x + 4, TABLES_PANEL.y + 4
        f.draw(canvas, t("panel.tables_title"), (x, y), render.VIOLET)
        close = t("panel.tables_close")
        f.draw(canvas, close, (TABLES_PANEL.right - 4 - f.width(close), y), render.SAND)
        y += render.LINE_H + 3
        self.table_rows = []
        for table, columns in self.schema:
            rect = pygame.Rect(x - 1, y - 1, f.width(table) + 2, render.GLYPH_H + 2)
            render.cover(canvas, rect, (*render.FOAM, 255))
            self.table_rows.append((rect, table))
            f.draw(canvas, table, (x, y), render.TEAL)
            room = (TABLES_PANEL.right - 6 - (x + 11 * render.ADVANCE)) // render.ADVANCE
            for part in wrap(", ".join(columns), room):     # a long list goes on the next line
                f.draw(canvas, part, (x + 11 * render.ADVANCE, y), render.INK)
                y += render.LINE_H + 1
        f.draw(canvas, t("panel.tables_rule"),
               (x, TABLES_PANEL.bottom - 9), render.WINE)

    def _draw_guide_button(self, canvas):
        f = render.font()
        glowing = not self.game.guide_seen and (self.time // 400) % 2 == 0
        render.panel(canvas, GUIDE_BUTTON, fill=render.BUTTER if glowing else render.CREAM)
        f.draw(canvas, t("panel.guide_button"), (GUIDE_BUTTON.x + 4, GUIDE_BUTTON.y + 3), render.VIOLET)

    def _draw_page_heat(self, canvas):
        """The left page lights up the faster you type; a finished keyword shines."""
        if self.word_glow:
            rect, born = self.word_glow
            age = self.time - born
            if age < 140:
                gfx.rect(canvas, render.BUTTER, rect)
            elif age < 420:
                gfx.rect(canvas, render.GOLD, rect, 1)
            else:
                self.word_glow = None
        heat = self.streak.level(self.time)
        if heat > 0.25:
            edge = LEFT_PAGE.inflate(5, 5)
            colour = render.LILAC if heat > 0.7 else render.LAVENDER
            gfx.rect(canvas, colour, edge, 1)
            if heat > 0.7 and (self.time // 120) % 2 == 0:
                for corner in (edge.topleft, edge.topright, edge.bottomleft, edge.bottomright):
                    gfx.rect(canvas, render.GOLD, (corner[0] - 1, corner[1] - 1, 3, 3))

    def _draw_foe_panel(self, canvas):
        f, foe = render.font(), self.battle.state.foe
        box = pygame.Rect(self.FOE_PANEL)
        render.panel(canvas, box)
        f.draw(canvas, foe.name.upper(), (box.x + 4, box.y + 3), render.INK)
        if self.key in ORDER:                      # the training dummy has no level
            f.draw(canvas, t("panel.level", level=ORDER.index(self.key) + 1), (box.right - 16, box.y + 3),
                   render.SLATE)
        f.draw(canvas, t("panel.hp"), (box.x + 4, box.y + 11), render.AMBER)
        hp = round(self.bars["foe"][0])           # the gliding bar: its colour changes as it drops
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 11, 100, 5), hp, foe.max_hp,
                     render.hp_colour(hp, foe.max_hp))
        if foe.exhausted:
            f.draw(canvas, t("panel.exhausted"), (box.right + 4, box.y + 3), render.RED, shadow=render.INK)
        if self.shown_relevance:
            f.draw(canvas, t("panel.relevance"), (box.right + 4, box.y + 11), render.AQUA,
                   shadow=render.INK)

    def _draw_ada_panel(self, canvas):
        f, ada = render.font(), self.battle.state.ada
        box = pygame.Rect(self.ADA_PANEL)
        render.panel(canvas, box)
        hp, mp = round(self.bars["ada"][0]), round(self.bars["ada"][1])
        f.draw(canvas, CATALOG.player["name"].upper(), (box.x + 4, box.y + 3), render.INK)
        f.draw(canvas, f"{hp}/{ada.max_hp}", (box.x + 52, box.y + 3), render.FOREST)
        f.draw(canvas, t("panel.level", level=self.battle.guardian.level), (box.right - 16, box.y + 3), render.SLATE)
        f.draw(canvas, t("panel.hp"), (box.x + 4, box.y + 11), render.AMBER)
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 11, 100, 5), hp, ada.max_hp,
                     render.hp_colour(hp, ada.max_hp))
        f.draw(canvas, t("panel.mp"), (box.x + 4, box.y + 18), render.BLUE)
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 18, 70, 5), mp, ada.max_mp,
                     render.SKY)
        f.draw(canvas, f"{mp}/{ada.max_mp}", (box.x + 88, box.y + 18), render.NAVY)
        runes = t("panel.codex", count=len(self.battle.codex.pages))
        f.draw(canvas, runes, (box.x, box.y - 8), render.GOLD, shadow=render.INK)
        if ada.exhausted:
            f.draw(canvas, t("panel.exhausted"), (box.right - f.width(t("panel.exhausted")), box.y - 8),
                   render.RED, shadow=render.INK)

    def _draw_debug(self, canvas):
        """F1: what the brain was thinking, straight from Brain.explain()."""
        f = render.font()
        battle = self.battle
        lines = [f"DEBUG (F1)   seed {battle.seed}   round {battle.state.turn}   "
                 f"turn: {battle.whose_turn}   looks used: {battle.state.scries_used}"]
        if self.reasoning:
            for key, value in self.reasoning.items():
                lines.extend(wrap(f"{key}: {value}", 76))
        else:
            lines.append("The guardian has not decided anything yet.")
        lines.append(f"steering now: {self.order.behaviour} {self.order.target}   "
                     f"book: {len(battle.state.foe_book)} queries")
        render.cover(canvas, pygame.Rect(4, 4, 312, 8 + len(lines) * render.LINE_H),
                     (*render.INK, 235))
        for i, line in enumerate(lines):
            f.draw(canvas, line, (8, 8 + i * render.LINE_H),
                   render.GOLD if i == 0 else render.MINT)


# ------------------------------------------------------------------ result

class ResultScene(Scene):
    def __init__(self, game, battle: Battle):
        super().__init__(game)
        self.battle = battle
        self.won = battle.winner == "ada"
        self.confused = battle.winner == "confused"     # the world broke: nobody won
        conn = battle.conn
        try:
            self.queries, self.casts = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(rows_cast), 0) FROM query_log WHERE caster = ?",
                (battle.state.ada.name,)).fetchone()
        except Exception:                                # the player dropped the log
            self.queries, self.casts = len(battle.state.ada_casts), 0
        # The Codex records the guardian's own query as the example for the rune (design doc 3.6).
        self.key = battle.guardian.key
        self.rune = battle.guardian.signature
        self.codex = next((sql for sql in battle.state.foe_book if self.rune in sql), None)
        self.next = next_guardian(self.key) if self.won else self.key
        if self.key in ORDER:
            game.record_battle(dict(getattr(battle, "stats", {}) or
                                    {"guardian": self.key, "result": battle.winner,
                                     "rounds": battle.state.turn}))
        self.saved = False
        if self.won and self.key in ORDER:
            # Autosave after every guardian defeated (D12): the runes it grants are kept, and
            # the story stands at the next guardian (or the end of this build).
            state = game.state
            game.runes |= battle.state.ada.runes | {self.rune}
            if self.key not in state.beaten:
                state.beaten.append(self.key)
            state.at = self.next or "end"
            self.saved = game.autosave()

    def enter(self):
        self.game.audio.play("victory" if self.won else "defeat")

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.running = False
        elif is_confirm_key(event):
            self.game.seed += 1                      # a new, still reproducible battle
            if not self.won:                         # try the same guardian again (D12)
                state = self.game.state
                state.retries[self.key] = state.retries.get(self.key, 0) + 1
                tired = settings_screen.ACCESSIBILITY.get("defeat_fatigue", 0.0)
                state.fatigue = round(min(1.0, state.fatigue + tired), 3)
                self.game.switch(BattleScene(self.game, self.key))   # HP and MP restored
                return
            # Runes are kept after a victory, and a defeated guardian always grants its own
            # (design doc 2.4: "each region's guardian grants the keyword"), even if Ada won
            # before the Invitation.
            self.game.runes |= self.battle.state.ada.runes | {self.rune}
            if self.next is None:                    # the end of this build
                self.game.switch(TitleScene(self.game))
            else:
                self.game.switch(DialogueScene(self.game, f"{self.next}_intro", self.next))

    def draw(self, canvas):
        f = render.font()
        draw_backdrop(canvas, ground_y=150)
        headline = t("result.victory") if self.won else t("result.confusion") if self.confused \
            else t("result.defeat")
        colour, shade = (render.BUTTER, render.AMBER) if self.won else \
            (render.LAVENDER, render.DUSK) if self.confused else (render.RED, render.WINE)
        f.draw_big(canvas, headline, ((320 - f.big_width(headline, TITLE_DOT)) // 2, 14),
                   colour, TITLE_DOT, shadow=shade, outline=render.INK)
        outcome = "victory" if self.won else "confused" if self.confused else "defeat"
        lines = self.game.dialogue.get(f"{self.key}_{outcome}", self.game.dialogue[outcome])
        y = 52
        for said in lines:
            for line in wrap(said, 76):                   # a long line (or translation) wraps
                f.draw(canvas, line, ((320 - f.width(line)) // 2, y), render.WHITE)
                y += 9
        state = self.battle.state
        stats = [t("result.stats", turn=state.turn, queries=self.queries, casts=self.casts),
                 t("result.stats_hp", hp=state.ada.hp, max=state.ada.max_hp, seed=self.battle.seed)]
        y += 6
        for line in stats:
            f.draw(canvas, line, ((320 - f.width(line)) // 2, y), render.LILAC)
            y += 9
        if self.codex and self.rune in state.ada.runes:
            y += 6
            box = pygame.Rect(30, y, 260, 30)
            render.panel(canvas, box)
            f.draw(canvas, t("result.codex", rune=self.rune, foe=state.foe.name),
                   (box.x + 4, box.y + 3), render.VIOLET)
            for i, line in enumerate(wrap(self.codex, 62)[:2]):
                f.draw(canvas, line, (box.x + 4, box.y + 12 + i * render.LINE_H), render.INK)
        if self.won and self.next is None:
            end = self.game.dialogue.get("end_of_slice", "")
            f.draw(canvas, end, ((320 - f.width(end)) // 2, 156), render.BUTTER)
            prompt = t("result.to_title")
        elif self.won:
            prompt = t("result.continue")
        else:
            prompt = t("result.retry")
        if (self.time // 500) % 2 == 0:
            f.draw(canvas, prompt, ((320 - f.width(prompt)) // 2, 166), render.WHITE,
                   shadow=render.INK)
