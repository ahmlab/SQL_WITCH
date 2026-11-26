"""The Statistics screen (title menu and pause): how the player is doing, for the player.

Six pages, LEFT/RIGHT to turn: casting, technique, tables, queries (real execution time, rows
scanned vs returned, and the query plan: shows when an index was used), battles, habits.
R switches between this run and every run of the profile. E exports the log as CSV and the
Scrolls as a .sql file into the save folder (exports/<profile>/).

The numbers come from save/stats.py, computed from the save's own log.

STATUS: six pages, this run / all runs, export.
"""

from __future__ import annotations

import pygame

from ai.roster import GUARDIANS
from engine import render
from i18n import CATALOG, t
from save import stats

PAGES = ("casting", "technique", "tables", "queries", "battles", "habits")
TABLES = {"witch", "spells", "items", "enemies", "foe_spells", "type_chart", "query_log"}


class StatsScene:
    PLACE = "menu"

    def __init__(self, game, back, state=None):
        self.game, self.back, self.time = game, back, 0
        self.state = state                    # a profile's save (from the title), or the session
        self.page, self.all_runs, self.note = 0, False, ""

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt):
        self.time += dt

    def data(self) -> dict:
        signatures = {key: g.signature for key, g in GUARDIANS.items()}
        state = self.state or self.game.snapshot()
        return stats.summary(state, signatures, TABLES,
                             run=None if self.all_runs else state.run_id)

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.game.switch(self.back)
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.page = (self.page + (1 if event.key == pygame.K_RIGHT else -1)) % len(PAGES)
        elif event.key == pygame.K_r:
            self.all_runs = not self.all_runs
        elif event.key == pygame.K_e:
            self.note = t("stats.exported", folder=str(self.export()))

    def export(self):
        root = self.game.saves.root if self.game.saves else None
        if root is None:
            return ""
        folder = root / "exports" / (self.game.profile_id or "guest")
        folder.mkdir(parents=True, exist_ok=True)
        state = self.state or self.game.snapshot()
        (folder / "log.csv").write_text(stats.export_csv(state.log), encoding="utf-8")
        (folder / "scrolls.sql").write_text(stats.export_scrolls_sql(state.scrolls),
                                            encoding="utf-8")
        return folder

    @staticmethod
    def who(guardian: str) -> str:
        """A guardian in words ("the Asterisk Slime"), as the Load screen names places."""
        return t(f"menu.at.{guardian}") if CATALOG.has(f"menu.at.{guardian}") else guardian

    def lines(self) -> list[str]:
        d, page = self.data(), PAGES[self.page]
        if page == "casting":
            c = d["casting"]
            trend = " ".join(f"{int(x * 100)}" for x in c["efficiency_trend"][-10:])
            return [t("stats.casting.queries", **c), t("stats.casting.waste", **c),
                    t("stats.casting.rows", **c), t("stats.casting.trend", trend=trend or "-")]
        if page == "technique":
            tech = d["technique"]
            out = [t("stats.technique.uses", name=name, count=count)
                   for name, count in tech["counts"].items()] or [t("stats.none")]
            out += [t("stats.technique.learned", technique=k, guardian=self.who(v["guardian"]),
                      before=v["before"], since=v["since"]) for k, v in tech["learned"].items()]
            return out
        if page == "tables":
            tables = d["tables"]
            out = [t("stats.tables.uses", name=n, count=c) for n, c in tables["counts"].items()]
            if tables["never"]:
                out.append(t("stats.tables.never", tables=", ".join(tables["never"])))
            return out or [t("stats.none")]
        if page == "queries":
            out = []
            for q in d["queries"][-8:]:
                out.append(q["sql"][:70])
                out.append(t("stats.queries.line", ms=f"{q['ms']:.2f}", scanned=q["scanned"],
                             returned=q["returned"], plan=" / ".join(q["plan"]) or "-"))
            return out or [t("stats.none")]
        if page == "battles":
            b = d["battles"]
            out = [t("stats.battles.total", **{k: b[k] for k in ("battles", "won", "rounds",
                                                                 "rewinds", "tricks",
                                                                 "scrolls")}),
                   t("stats.battles.time", minutes=round(b["seconds"] / 60, 1))]
            out += [t("stats.battles.retries", guardian=self.who(g), count=n)
                    for g, n in b["retries"].items()]
            return out
        h = d["habits"]
        places = ", ".join(f"{k} {round(v / 60, 1)}" for k, v in h["time_in"].items())
        fatigue = " ".join(f"{int(x * 100)}" for x in h["fatigue"][-10:]) or "-"
        return [t("stats.habits.sessions", count=h["sessions"],
                  minutes=round(h["seconds"] / 60, 1)),
                t("stats.habits.places", places=places or "-"),
                t("stats.habits.fatigue", values=fatigue)]

    def draw(self, canvas):
        f = render.font()
        canvas.fill(render.NIGHT)
        title = t(f"stats.page.{PAGES[self.page]}")
        f.draw(canvas, t("stats.title"), (12, 8), render.BUTTER)
        f.draw(canvas, title, (308 - f.width(title), 8), render.GOLD)
        scope = t("stats.all_runs") if self.all_runs else t("stats.this_run")
        f.draw(canvas, scope, (12, 18), render.GREY)
        from engine.grimoire import wrap
        y = 30
        for line in self.lines():
            for part in wrap(line, 74) or [""]:
                if y < 160:
                    f.draw(canvas, part, (12, y), render.LILAC)
                y += 8
        if self.note:
            f.draw(canvas, self.note[:76], (12, 160), render.GOLD)
        f.draw(canvas, t("stats.keys"), (12, 170), render.GREY)
