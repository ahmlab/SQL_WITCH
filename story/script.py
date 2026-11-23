"""The screenplay format: dialogue as plain text writers can edit (docs/WRITING.md).

    # a comment
    == glade_intro ==
    [scene glade] [book] [sfx book]
    Grimoire: Welcome to Codd, witch. {pause 300} Here the world is a database.
    Ada: A... {speed slow}talking{speed normal} book?
    <<if next == "tutorial">>
    Grimoire: Then show me. {wave}Practice{/wave} first.
    <<else>>
    Grimoire: Ask the {color gold}slime{/color}.
    <<endif>>
    <<set met_grimoire = true>>
    -> Who are you? => who
    -> Let's go. => go
    [end]

- `== id ==` starts a node; `speaker: text` is a line (`: text` has no speaker: narration).
- `[name args]` are stage directions for the next line (or the node, if nothing follows):
  scene, sleep, book, slime, knight, portrait, music, sfx, shake, wait, point, refill, reveal...
  The format does not know them: the scene that plays the script does.
- Inline, in a line's text: {speed fast|normal|slow}, {pause 300}, {instant}, {wave}...{/wave},
  {shake}...{/shake}, {color gold}...{/color}, {rune WHERE}. Any other {name} is a value filled
  in when the line is shown (ICU placeholders: {foe}, {count, plural, ...}).
- `-> text => node` offers a choice; `<<if>>`, `<<elif>>`, `<<else>>`, `<<endif>>` branch on
  conditions like `codex.WHERE`, `integrity == damaged`, `fatigue > 0.7`; `<<set x = 1>>` sets a
  variable; `<<jump node>>` goes on elsewhere; `[end]` stops.
- Every spoken line gets a stable i18n key, story.<file>.<node>.<n> (n counts the node's lines
  from 1), and its English text is the catalog's source (prompt 04 extracts it).

The parser reports mistakes with the file, the line number and what is wrong. ScriptRunner walks
a node like a writer reads it. Never imports pygame.

STATUS: parser with clear errors, inline markup, conditions, variables, choices, runner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from magic.db import DATA_DIR

STORY_DIR = DATA_DIR / "story"
COMMANDS = {"speed", "pause", "instant", "wave", "/wave", "shake", "/shake", "color", "/color",
            "rune"}
SPEEDS = {"slow": 0.5, "normal": 1.0, "fast": 2.0}


class ScriptError(ValueError):
    """A mistake in a script, with where it is."""

    def __init__(self, file: str, line: int, message: str):
        self.file, self.line = file, line
        super().__init__(f"{file}, line {line}: {message}")


# ------------------------------------------------------------------ inline markup

@dataclass(frozen=True)
class Token:
    """A piece of a line: text with a style, or a timing command."""
    kind: str                       # text | pause | speed | instant
    text: str = ""
    value: float = 0.0              # ms for pause, a multiplier for speed
    wave: bool = False
    shake: bool = False
    color: str | None = None
    rune: bool = False


_INLINE = re.compile(r"\{([^{}]*)\}")


def tokens(text: str) -> list[Token]:
    """Split a line's text into styled text and timing commands. Unknown {names} stay text."""
    out: list[Token] = []
    style = {"wave": False, "shake": False, "color": None}
    pos = 0

    def add(chunk: str, **extra) -> None:
        if chunk:
            out.append(Token("text", chunk, wave=style["wave"], shake=style["shake"],
                             color=style["color"], **extra))

    for match in _INLINE.finditer(text):
        body = match.group(1).strip()
        word, _, arg = body.partition(" ")
        if word not in COMMANDS or (word == "rune" and not arg):
            continue                               # a placeholder like {foe}: plain text
        add(text[pos:match.start()])
        pos = match.end()
        arg = arg.strip()
        if word == "pause":
            out.append(Token("pause", value=float(arg or 300)))
        elif word == "speed":
            out.append(Token("speed", value=SPEEDS.get(arg, _float(arg, 1.0))))
        elif word == "instant":
            out.append(Token("instant"))
        elif word in ("wave", "shake"):
            style[word] = True
        elif word in ("/wave", "/shake"):
            style[word[1:]] = False
        elif word == "color":
            style["color"] = arg or None
        elif word == "/color":
            style["color"] = None
        elif word == "rune":
            add(arg, rune=True)
    add(text[pos:])
    return out


def plain(text: str) -> str:
    """The text a reader sees, without the inline commands."""
    return "".join(t.text for t in tokens(text) if t.kind == "text")


def _float(text: str, default: float) -> float:
    try:
        return float(text)
    except ValueError:
        return default


# ------------------------------------------------------------------ the parsed script

@dataclass
class Line:
    speaker: str
    text: str                       # the source text, inline commands included
    key: str                        # the i18n key
    directions: list[tuple[str, list[str]]] = field(default_factory=list)
    lineno: int = 0


@dataclass
class Choice:
    options: list[tuple[str, str, str]]   # (text, target node, i18n key)
    lineno: int = 0


@dataclass
class Command:
    """A directive the runner executes: set, jump, end, or a branch (if/elif/else/endif)."""
    kind: str                       # set | jump | end | if | elif | else | endif | directions
    arg: str = ""
    directions: list[tuple[str, list[str]]] = field(default_factory=list)
    lineno: int = 0


@dataclass
class Node:
    id: str
    items: list = field(default_factory=list)


@dataclass
class Script:
    name: str
    nodes: dict[str, Node]

    def node(self, node_id: str) -> Node:
        if node_id not in self.nodes:
            raise KeyError(f"{self.name}: no node {node_id!r}")
        return self.nodes[node_id]

    def lines(self) -> list[Line]:
        """Every spoken line, in order (for extraction and tests)."""
        return [item for node in self.nodes.values() for item in node.items
                if isinstance(item, Line)]

    def keys(self) -> dict[str, str]:
        """i18n key -> English source text, for every line and choice."""
        out = {}
        for node in self.nodes.values():
            for item in node.items:
                if isinstance(item, Line):
                    out[item.key] = item.text
                elif isinstance(item, Choice):
                    out.update({key: text for text, _, key in item.options})
        return out


_NODE = re.compile(r"^==\s*([A-Za-z0-9_]+)\s*==$")
_DIRECTION = re.compile(r"\[([^\[\]]+)\]")
_LINE = re.compile(r"^([^:<\[\-=][^:]{0,40}?)?:\s?(.*)$")
_COMMAND = re.compile(r"^<<\s*(if|elif|else|endif|set|jump)\b\s*(.*?)\s*>>$")
_CHOICE = re.compile(r"^->\s*(.+?)\s*=>\s*([A-Za-z0-9_]+)\s*$")


def _directions(text: str) -> list[tuple[str, list[str]]]:
    out = []
    for body in _DIRECTION.findall(text):
        parts = _split_args(body)
        if parts:
            out.append((parts[0].lower(), parts[1:]))
    return out


def _split_args(body: str) -> list[str]:
    """Words, keeping "quoted phrases" together."""
    return [a.strip('"') for a in re.findall(r'"[^"]*"|\S+', body)]


def parse(text: str, name: str = "script") -> Script:
    """Parse a screenplay. Raises ScriptError with the file and line of the first mistake."""
    nodes: dict[str, Node] = {}
    current: Node | None = None
    pending: list[tuple[str, list[str]]] = []
    depth = 0
    counts: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if match := _NODE.match(line):
            if depth:
                raise ScriptError(name, lineno, "a node starts before the <<if>> above is closed "
                                                "with <<endif>>")
            node_id = match.group(1)
            if node_id in nodes:
                raise ScriptError(name, lineno, f"the node {node_id!r} is defined twice")
            _flush(current, pending, lineno)
            current = nodes[node_id] = Node(node_id)
            pending = []
            continue
        if current is None:
            raise ScriptError(name, lineno, "text before the first node: start with == name ==")
        if line == "[end]":
            _flush(current, pending, lineno)
            pending = []
            current.items.append(Command("end", lineno=lineno))
            continue
        if line.startswith("[") and _DIRECTION.sub("", line).strip() == "":
            pending += _directions(line)
            continue
        if line.startswith("<<"):
            match = _COMMAND.match(line)
            if not match:
                raise ScriptError(name, lineno, f"unknown command {line!r}: use <<if ...>>, "
                                                "<<elif ...>>, <<else>>, <<endif>>, <<set x = y>> "
                                                "or <<jump node>>")
            kind, arg = match.groups()
            if kind in ("if", "elif") and not arg:
                raise ScriptError(name, lineno, f"<<{kind}>> needs a condition")
            if kind == "if":
                depth += 1
            elif kind == "endif":
                if not depth:
                    raise ScriptError(name, lineno, "<<endif>> without an <<if>>")
                depth -= 1
            elif kind in ("elif", "else") and not depth:
                raise ScriptError(name, lineno, f"<<{kind}>> without an <<if>>")
            if kind == "set" and "=" not in arg:
                raise ScriptError(name, lineno, "<<set>> needs a name = value")
            if kind == "jump" and not re.fullmatch(r"[A-Za-z0-9_]+", arg):
                raise ScriptError(name, lineno, "<<jump>> needs a node name")
            current.items.append(Command(kind, arg, lineno=lineno))
            continue
        if line.startswith("->"):
            match = _CHOICE.match(line)
            if not match:
                raise ScriptError(name, lineno, "a choice is written -> text => node_name")
            text, target = match.groups()
            choice = current.items[-1] if current.items and isinstance(current.items[-1], Choice) \
                else None
            if choice is None:
                choice = Choice([], lineno)
                current.items.append(choice)
            counts[current.id] = counts.get(current.id, 0) + 1
            key = f"story.{name}.{current.id}.choice{counts[current.id]}"
            choice.options.append((text, target, key))
            continue
        lead = re.match(r"^((?:\[[^\[\]]+\]\s*)+)(.*)$", line)
        if lead:                                   # [book] Grimoire: ... directions first
            pending += _directions(lead.group(1))
            line = lead.group(2).strip()
        match = _LINE.match(line)
        if not match:
            raise ScriptError(name, lineno, f"not a line: write speaker: text (got {line!r})")
        speaker, said = (match.group(1) or "").strip(), match.group(2).strip()
        if said.count("{") != said.count("}"):
            raise ScriptError(name, lineno, "unbalanced { } in the text")
        counts[current.id] = counts.get(current.id, 0) + 1
        current.items.append(Line(speaker, said, f"story.{name}.{current.id}.{counts[current.id]}",
                                  pending, lineno))
        pending = []
    if depth:
        raise ScriptError(name, len(text.splitlines()), "an <<if>> is never closed with <<endif>>")
    _flush(current, pending, len(text.splitlines()))
    script = Script(name, nodes)
    _check_targets(script)
    return script


def _flush(node: Node | None, pending: list, lineno: int) -> None:
    """Directions with no line after them belong to the node itself (e.g. [music hearth])."""
    if node is not None and pending:
        node.items.append(Command("directions", directions=list(pending), lineno=lineno))


def _arg(text: str) -> str:
    return f'"{text}"' if (" " in text or not text) else text


def dump(script: Script) -> str:
    """The script written back as text; parse(dump(s)) gives the same script."""
    out: list[str] = []
    for node in script.nodes.values():
        out.append(f"== {node.id} ==")
        for item in node.items:
            if isinstance(item, Line):
                lead = " ".join(f"[{' '.join([n] + [_arg(a) for a in args])}]"
                                for n, args in item.directions)
                said = f"{item.speaker}: {item.text}" if item.speaker else f": {item.text}"
                out.append(f"{lead} {said}" if lead else said)
            elif isinstance(item, Choice):
                out.extend(f"-> {text} => {target}" for text, target, _ in item.options)
            elif item.kind == "directions":
                out.append(" ".join(f"[{' '.join([n] + [_arg(a) for a in args])}]"
                                    for n, args in item.directions))
            elif item.kind == "end":
                out.append("[end]")
            elif item.kind in ("else", "endif"):
                out.append(f"<<{item.kind}>>")
            else:
                out.append(f"<<{item.kind} {item.arg}>>")
        out.append("")
    return "\n".join(out)


def _check_targets(script: Script) -> None:
    for node in script.nodes.values():
        for item in node.items:
            targets = []
            if isinstance(item, Choice):
                targets = [(t, item.lineno) for _, t, _ in item.options]
            elif isinstance(item, Command) and item.kind == "jump":
                targets = [(item.arg, item.lineno)]
            for target, lineno in targets:
                if target not in script.nodes:
                    raise ScriptError(script.name, lineno, f"there is no node {target!r}")


def load(name: str, folder: Path = STORY_DIR) -> Script:
    path = Path(folder) / f"{name}.script"
    return parse(path.read_text(encoding="utf-8"), name)


_LOADED: dict[str, Script] = {}


def get(name: str) -> Script:
    """A script from data/story/, parsed once."""
    if name not in _LOADED:
        _LOADED[name] = load(name)
    return _LOADED[name]


def all_scripts(folder: Path = STORY_DIR) -> dict[str, Script]:
    return {p.stem: load(p.stem, folder) for p in sorted(Path(folder).glob("*.script"))}


# ------------------------------------------------------------------ conditions

_TOKEN = re.compile(r'\s*(>=|<=|==|!=|>|<|\(|\)|"[^"]*"|\'[^\']*\'|[A-Za-z_][A-Za-z0-9_.]*|-?\d+(?:\.\d+)?)')


def evaluate(expression: str, variables: dict) -> object:
    """A small, safe expression language: names (dotted: codex.WHERE), numbers, strings, bare
    words as strings (integrity == damaged), comparisons, and, or, not, parentheses."""
    words = _TOKEN.findall(expression)
    if "".join(words).replace(" ", "") != expression.replace(" ", ""):
        raise ValueError(f"cannot read the condition {expression!r}")
    pos = 0

    def peek():
        return words[pos] if pos < len(words) else None

    def take():
        nonlocal pos
        pos += 1
        return words[pos - 1]

    def atom():
        word = take()
        if word == "(":
            value = either()
            take()
            return value
        if word[0] in "\"'":
            return word[1:-1]
        if re.fullmatch(r"-?\d+(\.\d+)?", word):
            return float(word)
        if word in ("true", "false"):
            return word == "true"
        return lookup(word, variables)

    def comparison():
        left = atom()
        if peek() in ("==", "!=", ">", "<", ">=", "<="):
            op, right = take(), atom()
            return _compare(left, op, right)
        return left

    def negation():
        if peek() == "not":                       # looser than ==, as in Python
            take()
            return not negation()
        return comparison()

    def both():
        value = negation()
        while peek() == "and":
            take()
            right = negation()
            value = bool(value) and bool(right)
        return value

    def either():
        value = both()
        while peek() == "or":
            take()
            right = both()
            value = bool(value) or bool(right)
        return value

    return either()


class _Missing(str):
    """A name that is not set: false in a condition, its own name when compared as a word."""

    def __bool__(self):
        return False


def lookup(name: str, variables: dict) -> object:
    value: object = variables
    for part in name.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif hasattr(value, part) and not isinstance(value, dict):
            value = getattr(value, part)
        else:
            return _Missing(name)                  # a bare word, like damaged
    return value


def _compare(left, op, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, str):
        right = _float(right, right)
    if isinstance(right, (int, float)) and isinstance(left, str):
        left = _float(left, left)
    try:
        return {"==": left == right, "!=": left != right}[op] if op in ("==", "!=") else \
            {">": left > right, "<": left < right, ">=": left >= right, "<=": left <= right}[op]
    except TypeError:
        return False


# ------------------------------------------------------------------ the runner

class ScriptRunner:
    """Walks a node: next() returns the next Line or Choice, or None at the end."""

    def __init__(self, script: Script, node: str, variables: dict | None = None):
        self.script = script
        self.variables = variables if variables is not None else {}
        self.node = script.node(node)
        self.pos = 0
        self.stack: list[bool] = []            # for each open <<if>>: is a branch running?
        self.taken: list[bool] = []            # for each open <<if>>: was a branch taken?
        self.pending_directions: list[tuple[str, list[str]]] = []
        self.finished = False

    def _active(self) -> bool:
        return all(self.stack)

    def next(self):
        while not self.finished and self.pos < len(self.node.items):
            item = self.node.items[self.pos]
            self.pos += 1
            if isinstance(item, Command):
                if item.kind == "if":
                    ok = self._active() and bool(evaluate(item.arg, self.variables))
                    self.stack.append(ok)
                    self.taken.append(ok)
                    continue
                if item.kind == "elif":
                    parent = all(self.stack[:-1])
                    ok = parent and not self.taken[-1] and bool(evaluate(item.arg, self.variables))
                    self.stack[-1] = ok
                    self.taken[-1] = self.taken[-1] or ok
                    continue
                if item.kind == "else":
                    parent = all(self.stack[:-1])
                    self.stack[-1] = parent and not self.taken[-1]
                    self.taken[-1] = True
                    continue
                if item.kind == "endif":
                    self.stack.pop()
                    self.taken.pop()
                    continue
                if not self._active():
                    continue
                if item.kind == "set":
                    name, _, value = item.arg.partition("=")
                    self.variables[name.strip()] = evaluate(value.strip(), self.variables)
                elif item.kind == "jump":
                    self.node, self.pos, self.stack, self.taken = \
                        self.script.node(item.arg), 0, [], []
                elif item.kind == "end":
                    self.finished = True
                continue
            if not self._active():
                continue
            return item
        self.finished = True
        return None

    def choose(self, choice: Choice, index: int) -> None:
        _, target, _ = choice.options[index]
        self.node, self.pos, self.stack, self.taken = self.script.node(target), 0, [], []

    def lines(self) -> list[Line]:
        """Run to the end (no choices), collecting the lines: for linear scenes and tests."""
        out = []
        while (item := self.next()) is not None:
            if isinstance(item, Choice):
                self.choose(item, 0)
                continue
            out.append(item)
        return out
