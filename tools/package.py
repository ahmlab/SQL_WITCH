"""Build a runnable bundle of the game for this operating system: python -m tools.package

Uses PyInstaller to make a folder bundle (dist/sql-witch/) with the interpreter, pygame-ce,
sqlglot and the game's data/ and assets/ next to the code, so the paths the modules compute from
their own __file__ keep working inside the bundle. After building, the bundle is started with
--smoke-test; a bundle that cannot show its title fails the build.

    python -m tools.package              # build and smoke-test
    python -m tools.package --no-test    # build only

CI runs this weekly on Linux, macOS and Windows and uploads the folder (.github/workflows).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "sql-witch"
SEP = ";" if os.name == "nt" else ":"          # PyInstaller's --add-data separator


def build() -> Path:
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        raise SystemExit("PyInstaller is missing: pip install -r requirements.txt")
    args = [
        str(ROOT / "main.py"), "--name", NAME, "--noconfirm", "--clean",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # sqlglot loads its dialects by name at run time: PyInstaller cannot see those imports.
        "--collect-submodules", "sqlglot",
        "--add-data", f"{ROOT / 'data'}{SEP}data",
        "--add-data", f"{ROOT / 'assets'}{SEP}assets",
    ]
    if sys.platform == "darwin":
        args.append("--windowed")                  # a .app; the smoke test runs its binary
    pyinstaller.run(args)
    return ROOT / "dist" / NAME


def executable(bundle: Path) -> Path:
    if sys.platform == "darwin" and (ROOT / "dist" / f"{NAME}.app").exists():
        return ROOT / "dist" / f"{NAME}.app" / "Contents" / "MacOS" / NAME
    return bundle / (f"{NAME}.exe" if os.name == "nt" else NAME)


def smoke_test(bundle: Path) -> None:
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    run = subprocess.run([str(executable(bundle)), "--smoke-test"], env=env,
                         capture_output=True, text=True, timeout=120)
    print(run.stdout.strip())
    if run.returncode != 0 or "smoke test" not in run.stdout:
        print(run.stderr, file=sys.stderr)
        raise SystemExit(f"the bundle did not start (exit code {run.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package SQL Witch with PyInstaller.")
    parser.add_argument("--no-test", action="store_true", help="skip the smoke test")
    args = parser.parse_args(argv)
    shutil.rmtree(ROOT / "dist" / NAME, ignore_errors=True)
    bundle = build()
    if not args.no_test:
        smoke_test(bundle)
    print(f"bundle ready: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
