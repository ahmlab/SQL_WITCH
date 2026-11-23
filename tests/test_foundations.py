"""Prompt 01: the new packages exist, the smoke test runs, and the text-literal lint is ready."""

import ast
import re
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NEW_MODULES = ["story", "i18n", "save", "magic.world", "magic.spellbook", "magic.fatigue",
               "engine.animation", "engine.dialogue", "engine.hud", "engine.settings"]


@pytest.mark.parametrize("name", NEW_MODULES)
def test_every_new_module_imports_and_has_a_header_with_a_status(name):
    module = importlib.import_module(name)
    assert module.__doc__ and "STATUS:" in module.__doc__


def test_pygame_free_packages_stay_pygame_free():
    code = ("import sys, magic.world, magic.spellbook, magic.fatigue, story, i18n, save; "
            "sys.exit('pygame' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0


def test_the_game_passes_its_smoke_test():
    run = subprocess.run([sys.executable, "main.py", "--smoke-test"], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0 and "smoke test" in run.stdout


def test_claude_md_is_short_and_has_the_rules():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) < 200
    for must in ("Decision Log", "hard rules", "Do not", "i18n key"):
        assert must in text


def test_the_ime_spike_runs_and_draws_chinese():
    run = subprocess.run([sys.executable, "-m", "tools.spike_ime", "--synthetic"], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0
    assert "TEXTINPUT   text='学习'" in run.stdout and "glyphs missing: none" in run.stdout


# ------------------------------------------------------------------ no literal text on screen

PACKAGES = ["engine", "story", "magic", "ai"]
DRAW_CALLS = {"draw", "say", "show_miscast", "draw_big"}       # what puts text on screen


def literal_texts() -> list[str]:
    """String literals handed straight to something that draws or narrates text."""
    found = []
    for package in PACKAGES:
        for path in (ROOT / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in DRAW_CALLS and len(node.args) >= 2):
                    continue
                text = node.args[1] if node.func.attr in ("draw", "draw_big") else node.args[0]
                if isinstance(text, (ast.Constant, ast.JoinedStr)) and \
                        (not isinstance(text, ast.Constant) or isinstance(text.value, str)):
                    if isinstance(text, ast.Constant) and (not text.value.strip(" *.v>")
                                                           or len(text.value.strip()) == 1):
                        continue                    # a mark or a lone glyph (the sleeper's z)
                    if isinstance(text, ast.JoinedStr) and not any(
                            isinstance(v, ast.Constant) and re.search(r"[A-Za-z]", v.value)
                            for v in text.values):
                        continue                    # numbers and values only: "30/30"
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def test_no_user_facing_text_is_written_in_code():
    assert literal_texts() == []
