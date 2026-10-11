# GameForge

Type a 2D game idea, wait a few minutes, and play the finished game in your browser.

Three AI agents (designer, developer, QA reviewer, built with CrewAI) design and write a Pygame game.
A script then **play-tests it automatically** with no window, presses keys on its behalf, and sends any problem
back to the AI to fix (up to 3 times). The game is then compiled to run in the browser with pygbag.

## How it works

```
Browser page ──POST idea──▶ FastAPI ──▶ job queue (one game at a time)
                                          │
        1. CrewAI crew: design → code → review      (Groq LLM)
        2. Play-test: crash? stuck on a menu? frozen? ──fail──▶ ask the AI to repair (max 3x)
        3. pygbag: main.py → playable web build
                                          │
Browser page ◀── status every 2 s ────────┘   →  /games/<id>/build/web/
```

| File | What it does |
|---|---|
| `app.py` | Web server and API (`POST /api/jobs`, `GET /api/jobs/<id>`) |
| `forge/crew_build.py` | The three agents, their rules, model selection |
| `forge/checker.py`, `forge/playtest_runner.py` | Static checks and the headless play-test |
| `forge/builder.py` | Browser build with pygbag |
| `forge/jobs.py` | Job queue, stages, automatic repair loop |
| `static/index.html` | The website |
| `tests/check_playtest.py` | Proves the play-tester accepts good games and rejects broken ones |

## Setup (about 10 minutes)

You need: **Python 3.12** (3.10 to 3.13 also work), internet, and a free Groq API key from https://console.groq.com/keys

### Windows (PowerShell)
```powershell
cd path\to\gameforge
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```
If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

### Mac or Linux
```bash
cd path/to/gameforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

In `.env`, replace `paste-your-groq-key-here` with your key, then save.

## Run

```
python run.py
```

Your browser opens at http://localhost:8000. Type an idea (or click an example) and press **Build game**.
Keep the terminal window open while the website is in use. Stop it with Ctrl+C.

The first build downloads the pygbag tools, so it is slower. Playing a game also needs internet,
because the browser loads the game engine from `pygame-web.github.io`.

## Try it without an API key

```
# Windows PowerShell
$env:GAMEFORGE_MOCK="repair"; python run.py
# Mac / Linux
GAMEFORGE_MOCK=repair python run.py
```

This uses a built-in sample game. With `repair`, the first version is deliberately broken (stuck on a menu),
so you can watch the play-tester catch it and the repair step fix it.

## Check the play-tester

```
python tests/check_playtest.py
```
Expected: 2 lines say `PASS` (good games) and 6 say `FAIL` (broken games it correctly rejects).

## Troubleshooting

| Problem | Fix |
|---|---|
| `GROQ_API_KEY is missing` | Fill in `.env` and restart `python run.py` |
| Failed with 401 / invalid API key | Create a new key at console.groq.com and update `.env` |
| Failed with 429 / "Request too large" / rate limit | Groq's free tier limits tokens per minute for each model, and some models allow too few for a whole game. GameForge already skips such a model, waits out short limits, and tries up to 4 models. If every model is blocked, wait a minute, or open https://console.groq.com/settings/limits, pick a model with a higher tokens-per-minute limit and put `LLM_MODEL=<that model>` in `.env` |
| `Could not list Groq models` | Check your internet, VPN or firewall |
| Build says it did not finish in 5 minutes | pygbag cannot reach `pygame-web.github.io`. Check internet, VPN or firewall |
| Build failed with `UnicodeDecodeError ... cp1252` (Windows) | Fixed in this version: generated code is cleaned to plain ASCII and the build runs in UTF-8 mode. Update to the latest zip |
| An old error keeps showing after an update | Stop the server (Ctrl+C), start `python run.py` again, and check the terminal prints `GameForge version 1.4`. The same version is shown at the bottom of the web page. Old failed games stay in the list; use **Retry build** on them or build a new one |
| A game failed at the build step but its code is fine | Click **Retry the build** (shown on the failed screen and in Recent games). It rebuilds the same code and makes no AI calls |
| Slow or odd file errors | Keep the project outside OneDrive-synced folders (for example `C:\dev\gameforge`); OneDrive can lock files while they are being built |
| Game page is blank or says "Ready to start" | Click inside the game once, then use the keys |
| A specific model is wanted | Add `LLM_MODEL=<exact id from console.groq.com>` to `.env` |

## Limits (honest ones, worth mentioning in an interview)

- One game is built at a time; it is a local app, not a multi-user service.
- The AI-written game is executed on your computer during the play-test. This is fine for a personal project.
  A public deployment would need a sandbox (for example a locked-down Docker container).
- The play-tester can tell that a game reacts to keys, not that it is fun or balanced.
- Quality depends on the model and on how specific the idea is.

## Security

Never commit `.env`. It is already listed in `.gitignore`. If a key is ever pushed to GitHub, delete it in the Groq console and create a new one.
