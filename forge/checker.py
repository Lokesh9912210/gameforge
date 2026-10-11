"""Checks a generated game: quick static checks, then a headless play-test."""
import ast
import re
import json
import os
import subprocess
import sys
from pathlib import Path

RUNNER = Path(__file__).with_name("playtest_runner.py")

# Things that work on a desktop but break in the browser build.
BROWSER_UNSAFE = {
    "input(": "input() blocks the browser; remove it.",
    "time.sleep(": "time.sleep() freezes the browser; use `await asyncio.sleep(0)` instead.",
    "SysFont": "pygame.font.SysFont is not available in the browser; use pygame.font.Font(None, size).",
    "image.load(": "Image files are not available; draw with pygame.draw instead.",
    "mixer.Sound(": "Sound files are not available; remove sound.",
    "mixer.music.load(": "Music files are not available; remove music.",
}


def static_check(code: str):
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError on line {e.lineno}: {e.msg}"
    if "asyncio.sleep(0)" not in code:
        return "Missing `await asyncio.sleep(0)` inside the main loop (required for the browser build)."
    if "asyncio.run(" not in code:
        return "The file must end with `asyncio.run(main())`."
    for needle, why in BROWSER_UNSAFE.items():
        if needle in code:
            return f"Found `{needle}`: {why}"
    if re.search(r"K_ESCAPE[^\n]*\n(?:[^\n]*\n){0,4}?[^\n]*pygame\.quit\(", code):
        return ("Pressing Escape quits the game. A browser page cannot close, so the screen goes blank. "
                "Remove the Escape-to-quit handling and any 'Esc to quit' text; only the QUIT event may end main().")
    return None


def check_game(job_dir: Path, code: str):
    """Write main.py, then check it. Returns None if the game passes, otherwise a problem description."""
    job_dir.mkdir(parents=True, exist_ok=True)
    problem = static_check(code)
    if problem:
        return problem
    main_py = job_dir / "main.py"
    main_py.write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "main.py"],
            cwd=job_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return "The play-test timed out: the game blocks or never reaches its main loop."
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("PLAYTEST_RESULT "):
            result = json.loads(line[len("PLAYTEST_RESULT "):])
            return None if result["ok"] else result["reason"]
    return "The play-test could not run the game:\n" + (proc.stderr or proc.stdout)[-1200:]
