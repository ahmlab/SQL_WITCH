"""The query editor on the Grimoire's left page (design doc 6.5).

Typing is the controller, so the editor must feel solid before it feels clever:
- characters arrive as TEXTINPUT events (pygame.key.start_text_input()), so any keyboard
  layout works; editing keys arrive as KEYDOWN;
- Enter starts a new line, Ctrl+Enter casts;
- Up/Down walk the query history when the cursor is on the first/last line;
- TAB completes table, column and keyword names (tables and columns from PRAGMA table_info);
  while typing, the most likely completion is shown faded after the cursor, and TAB or the
  right arrow accepts it;
- syntax colours come from sqlglot.tokenize(); keywords of locked runes are drawn grey and
  struck through, so the player sees what they cannot use yet.

STATUS: editing, history, TAB completion with a faded suggestion, colouring, locked runes.
"""

from __future__ import annotations

import pygame
import sqlglot
from sqlglot.errors import TokenError
from sqlglot.tokens import TokenType

from engine import render

# The words that spell each rune. ON belongs to JOIN; SUBQUERY has no word of its own.
RUNE_WORDS = {
    "WHERE": {"WHERE"},
    "ORDER BY": {"ORDER BY", "ORDER"},
    "LIMIT": {"LIMIT"},
    "JOIN": {"JOIN", "ON", "INNER", "LEFT", "CROSS"},
    "GROUP BY": {"GROUP BY", "GROUP"},
    "HAVING": {"HAVING"},
    "DISTINCT": {"DISTINCT"},
    "WITH": {"WITH"},
    "IS NULL": {"IS"},
    "COALESCE": {"COALESCE"},
}
KEYWORDS = ["SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "LIMIT", "ORDER BY",
            "ASC", "DESC", "JOIN", "ON", "AS", "GROUP BY", "HAVING", "COUNT", "SUM",
            "DISTINCT", "IS NULL", "COALESCE", "WITH"]

# Every single word that belongs to a keyword: finishing one of these makes the rune glow.
KEYWORD_WORDS = {w for k in KEYWORDS for w in k.split()}

STYLE_COLOURS = {
    "plain": render.INK,
    "keyword": render.VIOLET,
    "locked": render.GREY,
    "string": render.WINE,
    "number": render.AMBER,
    "name": render.TEAL,
    "punct": render.SLATE,
}
GHOST_COLOUR = (*render.GREY, 170)      # half-transparent: a hint, not text you typed
GHOST_MIN = 2                           # letters typed before a suggestion appears
_PUNCT = {TokenType.COMMA, TokenType.DOT, TokenType.L_PAREN, TokenType.R_PAREN,
          TokenType.SEMICOLON, TokenType.STAR, TokenType.EQ, TokenType.GT, TokenType.LT,
          TokenType.GTE, TokenType.LTE, TokenType.NEQ}


def locked_words(unlocked: set[str]) -> set[str]:
    """Every keyword that belongs to a rune Ada has not learned yet."""
    words = set()
    for rune, spelled in RUNE_WORDS.items():
        if rune not in unlocked:
            words |= spelled
    return words


def _tokens(text: str):
    """Tokenize, closing a half-typed string so colouring keeps working while typing."""
    for suffix in ("", "'", '"'):
        try:
            return sqlglot.tokenize(text + suffix, read="sqlite")
        except TokenError:
            continue
    return []


def colour_styles(text: str, locked: set[str], names: set[str]) -> list[str]:
    """One style name per character of text: keyword, locked, string, number, name..."""
    styles = ["plain"] * len(text)
    lowered = {n.lower() for n in names}
    for token in _tokens(text):
        word = token.text.upper()
        if token.token_type == TokenType.STRING:
            style = "string"
        elif token.token_type == TokenType.NUMBER:
            style = "number"
        elif word in locked:
            style = "locked"
        elif token.token_type in _PUNCT:
            style = "punct"
        elif token.token_type == TokenType.VAR and token.text.lower() in lowered:
            style = "name"
        elif token.token_type != TokenType.VAR or word in {"COALESCE", "COUNT", "SUM"}:
            style = "keyword" if token.text.replace(" ", "").isalpha() else "plain"
        else:
            style = "plain"
        for i in range(token.start, min(token.end + 1, len(text))):
            styles[i] = style
    return styles


def schema_tables(conn) -> list[str]:
    return [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]


def schema_words(conn) -> list[str]:
    """Table and column names for TAB completion, read with PRAGMA table_info."""
    words = []
    for table in schema_tables(conn):
        words.append(table)
        words.extend(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
    return sorted(set(words))


class QueryEditor:
    """A small multi-line editor. The cursor is (row, col) into self.lines."""

    def __init__(self, names: list[str] = (), unlocked: set[str] = frozenset(),
                 columns: int = 36, visible_lines: int = 7, tables: list[str] = ()):
        self.lines: list[str] = [""]
        self.row = self.col = 0
        self.history: list[str] = []
        self._history_pos: int | None = None
        self._draft = ""
        self.names = list(names)
        self.tables = set(tables)           # offered first right after FROM or JOIN
        self.unlocked = set(unlocked)
        self.columns = columns              # characters per visual line before wrapping
        self.visible_lines = visible_lines
        self._tab: tuple[str, list[str], int] | None = None   # (prefix, matches, index)

    # ------------------------------------------------------------ text

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str) -> None:
        self.lines = text.split("\n") or [""]
        self.row = len(self.lines) - 1
        self.col = len(self.lines[self.row])

    def insert(self, chars: str) -> None:
        for char in chars:
            if char == "\n":
                self.newline()
            elif char.isprintable() and char != "\t":
                line = self.lines[self.row]
                self.lines[self.row] = line[:self.col] + char + line[self.col:]
                self.col += 1

    def newline(self) -> None:
        line = self.lines[self.row]
        self.lines[self.row:self.row + 1] = [line[:self.col], line[self.col:]]
        self.row, self.col = self.row + 1, 0

    def backspace(self) -> None:
        if self.col > 0:
            line = self.lines[self.row]
            self.lines[self.row] = line[:self.col - 1] + line[self.col:]
            self.col -= 1
        elif self.row > 0:                       # join with the line above
            above = self.lines[self.row - 1]
            self.lines[self.row - 1] = above + self.lines.pop(self.row)
            self.row, self.col = self.row - 1, len(above)

    def delete(self) -> None:
        line = self.lines[self.row]
        if self.col < len(line):
            self.lines[self.row] = line[:self.col] + line[self.col + 1:]
        elif self.row < len(self.lines) - 1:
            self.lines[self.row] = line + self.lines.pop(self.row + 1)

    def move(self, dx: int) -> None:
        if dx < 0 and self.col == 0 and self.row > 0:
            self.row -= 1
            self.col = len(self.lines[self.row])
        elif dx > 0 and self.col == len(self.lines[self.row]) and self.row < len(self.lines) - 1:
            self.row, self.col = self.row + 1, 0
        else:
            self.col = max(0, min(len(self.lines[self.row]), self.col + dx))

    def up(self) -> None:
        if self.row > 0:
            self.row -= 1
            self.col = min(self.col, len(self.lines[self.row]))
        else:
            self.recall(-1)

    def down(self) -> None:
        if self.row < len(self.lines) - 1:
            self.row += 1
            self.col = min(self.col, len(self.lines[self.row]))
        else:
            self.recall(+1)

    def clear(self) -> None:
        self.lines, self.row, self.col = [""], 0, 0

    # ------------------------------------------------------------ history

    def recall(self, step: int) -> None:
        """Walk the history. Walking past the newest entry returns to the unsent draft."""
        if not self.history:
            return
        if self._history_pos is None:
            if step > 0:
                return
            self._draft = self.text
            self._history_pos = len(self.history)
        self._history_pos = max(0, min(len(self.history), self._history_pos + step))
        if self._history_pos == len(self.history):
            self.set_text(self._draft)
            self._history_pos = None
        else:
            self.set_text(self.history[self._history_pos])

    def submit(self) -> str | None:
        """Ctrl+Enter: hand the query over, remember it, and clear the page."""
        sql = self.text.strip()
        if not sql:
            return None
        if not self.history or self.history[-1] != sql:
            self.history.append(sql)
        self._history_pos = None
        self.clear()
        return sql

    # ------------------------------------------------------------ completion

    def _word_before_cursor(self) -> str:
        line = self.lines[self.row][:self.col]
        start = len(line)
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
            start -= 1
        return line[start:]

    def _matches(self, prefix: str) -> list[str]:
        """Names and keywords that start with prefix, shortest first, in the player's case."""
        locked = locked_words(self.unlocked)       # never suggest a rune Ada cannot read
        pool = set(self.names) | {k for k in KEYWORDS if k not in locked}
        before = self.lines[self.row][:self.col - len(prefix)].split()
        wants_table = bool(before) and before[-1].upper() in ("FROM", "JOIN")
        found = sorted((w for w in pool if w.lower().startswith(prefix.lower())),
                       key=lambda w: (not (wants_table and w in self.tables), len(w), w))
        if prefix.islower():                 # "sel" -> "select", "SEL" -> "SELECT"
            found = [w.lower() if w.isupper() else w for w in found]
        return found

    def suggestion(self) -> str:
        """The rest of the most likely word, shown faded after the cursor ("SE" -> "LECT").
        Only at the end of a line, after 2+ letters, and never once the word is complete."""
        line = self.lines[self.row]
        prefix = self._word_before_cursor()
        if self.col != len(line) or len(prefix) < GHOST_MIN or self._tab:
            return ""
        matches = self._matches(prefix)
        if not matches or any(m.lower() == prefix.lower() for m in matches):
            return ""
        return matches[0][len(prefix):]

    def accept_suggestion(self) -> bool:
        rest = self.suggestion()
        if rest:
            self.insert(rest)
        return bool(rest)

    def complete(self) -> None:
        """TAB: complete the word before the cursor; TAB again cycles through the matches."""
        before = self.lines[self.row][:self.col]
        if self._tab and before.endswith(self._tab[1][self._tab[2]]):
            prefix, matches, index = self._tab
            erase = len(matches[index])
            index = (index + 1) % len(matches)
        else:
            prefix = self._word_before_cursor()
            matches = self._matches(prefix) if prefix else []
            if not matches:
                return
            erase, index = len(prefix), 0
        for _ in range(erase):
            self.backspace()
        self.insert(matches[index])
        self._tab = (prefix, matches, index)

    # ------------------------------------------------------------ events

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Feed one pygame event. Returns the query when the player casts it (Ctrl+Enter)."""
        if event.type == pygame.TEXTINPUT:
            self._tab = None
            self.insert(event.text)
            return None
        if event.type != pygame.KEYDOWN:
            return None
        key, ctrl = event.key, bool(event.mod & pygame.KMOD_CTRL)
        if key != pygame.K_TAB:
            self._tab = None
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if ctrl:
                return self.submit()
            self.newline()
        elif key == pygame.K_BACKSPACE:
            self.backspace()
        elif key == pygame.K_DELETE:
            self.delete()
        elif key == pygame.K_LEFT:
            self.move(-1)
        elif key == pygame.K_RIGHT:
            if not self.accept_suggestion():       # at the end of a line, -> takes the ghost
                self.move(+1)
        elif key == pygame.K_UP:
            self.up()
        elif key == pygame.K_DOWN:
            self.down()
        elif key == pygame.K_HOME:
            self.col = 0
        elif key == pygame.K_END:
            self.col = len(self.lines[self.row])
        elif key == pygame.K_TAB:
            self.complete()
        elif key == pygame.K_l and ctrl:
            self.clear()
        return None

    # ------------------------------------------------------------ drawing

    def visual_lines(self) -> tuple[list[tuple[int, int, str]], tuple[int, int]]:
        """Wrap long lines every self.columns characters.
        Returns [(row, start_col, text)] and the cursor's visual (line, column)."""
        out, cursor, width = [], (0, 0), self.columns
        for r, line in enumerate(self.lines):
            chunks = [line[s:s + width] for s in range(0, len(line), width)] or [""]
            if r == self.row:
                # A cursor right after a full chunk stays at the end of that chunk.
                i = min(self.col // width, len(chunks) - 1)
                cursor = (len(out) + i, self.col - i * width)
            out.extend((r, i * width, chunk) for i, chunk in enumerate(chunks))
        return out, cursor

    def cursor_xy(self, topleft: tuple[int, int]) -> tuple[int, int]:
        """Where the cursor is drawn, in canvas pixels, when the editor sits at topleft."""
        _, (line, col) = self.visual_lines()
        first = max(0, line - self.visible_lines + 1)
        return (topleft[0] + col * render.ADVANCE, topleft[1] + (line - first) * render.LINE_H)

    def word_before_cursor(self) -> str:
        return self._word_before_cursor()

    def draw(self, surface: pygame.Surface, topleft: tuple[int, int], time_ms: int,
             focused: bool = True) -> None:
        f = render.font()
        x0, y0 = topleft
        locked = locked_words(self.unlocked)
        names = set(self.names)
        lines, (cursor_line, cursor_col) = self.visual_lines()
        first = max(0, cursor_line - self.visible_lines + 1)       # scroll to the cursor
        styles_by_row = {r: colour_styles(line, locked, names)
                         for r, line in enumerate(self.lines)}
        for n, (r, start, text) in enumerate(lines[first:first + self.visible_lines]):
            y = y0 + n * render.LINE_H
            styles = styles_by_row[r][start:start + len(text)]
            styles += ["plain"] * (len(text) - len(styles))
            render.draw_coloured(surface, text, [STYLE_COLOURS[st] for st in styles], (x0, y))
            for i, style in enumerate(styles):
                if style == "locked":       # strike-through: a rune Ada cannot read yet
                    x = x0 + i * render.ADVANCE
                    pygame.draw.line(surface, render.RED, (x - 1, y + 2), (x + 3, y + 2))
        ghost = self.suggestion() if focused else ""
        if ghost and first <= cursor_line < first + self.visible_lines:
            room = max(0, self.columns - cursor_col)               # stay on the page
            render.font().draw(surface, ghost[:room],
                               (x0 + cursor_col * render.ADVANCE,
                                y0 + (cursor_line - first) * render.LINE_H), GHOST_COLOUR)
        if focused and (time_ms // 500) % 2 == 0:                     # blinking cursor
            cx = x0 + cursor_col * render.ADVANCE - 1
            cy = y0 + (cursor_line - first) * render.LINE_H
            pygame.draw.line(surface, render.INK, (cx, cy - 1), (cx, cy + render.GLYPH_H - 1))
