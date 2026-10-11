"""Turns main.py into a browser game with pygbag."""
import os
import subprocess
import sys
from pathlib import Path

BUILD_TIMEOUT_SECONDS = 300


def build_game(job_dir: Path):
    """Returns None on success, otherwise an error message."""
    cmd = [
        sys.executable, "-m", "pygbag", "--build",
        "--version", "0.9", "--PYBUILD", "3.12",
        "--cdn", "https://pygame-web.github.io/archives/0.9/",
        "main.py",
    ]
    try:
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # Windows: read files as UTF-8
        proc = subprocess.run(cmd, cwd=job_dir, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=BUILD_TIMEOUT_SECONDS, env=env)
    except subprocess.TimeoutExpired:
        return ("The browser build did not finish in 5 minutes. The build tool (pygbag) needs internet access "
                "to pygame-web.github.io. Check your connection, firewall or VPN, then try again.")
    index = job_dir / "build" / "web" / "index.html"
    if proc.returncode != 0 or not index.exists():
        return "The browser build failed:\n" + (proc.stderr or proc.stdout)[-1200:]
    return None
