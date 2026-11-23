"""How wide text is, in cells of the game's 4-pixel text grid. Never imports pygame.

Latin, Greek and Cyrillic letters take one cell; Chinese characters (and other East Asian wide
or full-width characters) take two, so a line of Chinese of 20 characters is as wide as 40
English letters. Layout, wrapping and the text layer all measure with these two functions.

STATUS: one or two cells per character (Unicode East Asian Width).
"""

from __future__ import annotations

import unicodedata


def cells(char: str) -> int:
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def text_cells(text: str) -> int:
    return sum(cells(c) for c in text)


def cut(text: str, max_cells: int) -> str:
    """The longest start of `text` that fits `max_cells`."""
    used = 0
    for i, char in enumerate(text):
        used += cells(char)
        if used > max_cells:
            return text[:i]
    return text


# ------------------------------------------------------------------ wrapping

# Kinsoku (CJK line breaking): these never start a line...
NO_START = set("，。、；：！？）」』》〉】〕…—,.;:!?)]}%")
# ...and these never end one.
NO_END = set("（「『《〈【〔([{")


def _pieces(word: str) -> list[str]:
    """A word as breakable pieces: Latin runs stay whole, each wide character stands alone
    (Chinese breaks between any two characters), punctuation sticks to what it follows."""
    out: list[str] = []
    run = ""
    for char in word:
        if cells(char) == 2 or char in NO_START or char in NO_END:
            if run:
                out.append(run)
                run = ""
            out.append(char)
        else:
            run += char
    if run:
        out.append(run)
    return out


def wrap(text: str, width: int) -> list[str]:
    """Lines of at most `width` cells. Spaced scripts break between words (no hyphenation);
    Chinese between characters, with the kinsoku rules; a piece longer than a line is cut.
    Newlines start new lines; runs of spaces count as one."""
    lines: list[str] = []
    paragraphs = text.split("\n")
    for p, paragraph in enumerate(paragraphs):
        before = len(lines)
        _wrap_paragraph(paragraph, width, lines)
        if len(lines) == before and len(paragraphs) > 1 and p < len(paragraphs) - 1:
            lines.append("")                          # an empty line the writer asked for
    return lines


def _wrap_paragraph(text: str, width: int, lines: list[str]) -> None:
    width = max(1, width)
    line = ""
    for w, word in enumerate(text.split()):
        for i, piece in enumerate(_pieces(word)):
            spaced = i == 0 and bool(line)
            joined = line + (" " if spaced else "") + piece
            if text_cells(joined) <= width:
                line = joined
                continue
            if piece in NO_START and line and not spaced and cells(line[-1]) == 2:
                carry, line = line[-1], line[:-1]      # pull the last character down with it
                lines.append(line.rstrip())
                line = carry + piece
                continue
            if line and line[-1] in NO_END:            # an opening bracket goes along
                carry, line = line[-1], line[:-1]
                if line.strip():
                    lines.append(line.rstrip())
                line = carry + piece
            else:
                if line:
                    lines.append(line)
                line = piece
            while text_cells(line) > width:            # one piece wider than the line: cut
                head = cut(line, width) or line[:1]
                lines.append(head)
                line = line[len(head):]
    if line:
        lines.append(line)
