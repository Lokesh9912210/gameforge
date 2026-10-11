"""The AI crew: a designer, a developer and a QA reviewer, built with CrewAI."""
import re
import time
import warnings

import requests

from . import config

# CrewAI prints a harmless pydantic warning about task callbacks; hide it.
warnings.filterwarnings("ignore", message="function callbacks cannot be serialized")

# Rules every generated game must follow so it runs in the browser (pygbag).
RULES = """
STRICT RULES FOR THE CODE:
- One single file, maximum 300 lines. Only use: pygame, asyncio, math, random, sys.
- No images, no sound files, no font files. Draw everything with pygame.draw and pygame.font.Font(None, size).
  Never use pygame.font.SysFont, pygame.image.load or pygame.mixer.
- Keyboard only (no mouse). Window size 800x600.
- Start playing immediately when the program runs. Do NOT add a title or menu screen.
  If you really need one, it must show "Press SPACE or ENTER to Start" and must start the game when SPACE or ENTER is pressed.
- Show the controls as a short line of text on screen while playing.
- When the game ends, show the result and "Press R to restart"; pressing R must restart the game.
- Every game state must have a way to leave it. Never create a state that no key can exit.
- Structure it exactly like this:
    import asyncio, pygame, math, random, sys
    async def main():
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        clock = pygame.time.Clock()
        ... setup ...
        while True:
            handle events (QUIT -> pygame.quit(); return)
            update
            draw
            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0)   # REQUIRED every frame
    asyncio.run(main())
- Never quit or close the game when a key such as Escape is pressed (a browser page cannot close). Only the QUIT event may end main(). Do not mention "Esc to quit".
- Never use input(), time.sleep(), or exit().
- Output ONE complete ```python code block, then a short 'How to play' section. Nothing else.
- Never return partial code, never write '...' or 'rest of code here'. Always the FULL file.
"""


def _strip_cache_breakpoint_patch():
    """Some CrewAI versions add a 'cache_breakpoint' field that Groq rejects.
    This removes it right before a request goes out (only matters on the litellm route)."""
    try:
        import litellm
    except ImportError:
        return
    if getattr(litellm, "_cb_patched", False):
        return
    orig_completion, orig_acompletion = litellm.completion, litellm.acompletion

    def strip(messages):
        if isinstance(messages, list):
            return [{k: v for k, v in m.items() if k != "cache_breakpoint"} if isinstance(m, dict) else m
                    for m in messages]
        return messages

    def completion(*a, **kw):
        if "messages" in kw:
            kw["messages"] = strip(kw["messages"])
        return orig_completion(*a, **kw)

    async def acompletion(*a, **kw):
        if "messages" in kw:
            kw["messages"] = strip(kw["messages"])
        return await orig_acompletion(*a, **kw)

    litellm.completion, litellm.acompletion = completion, acompletion
    litellm._cb_patched = True


# Best first. The list is only a preference; any other chat model is used as a fallback.
PREFERENCE = ("llama-3.3-70b", "gpt-oss-120b", "qwen3-32b", "kimi", "llama-4", "gpt-oss", "qwen", "llama")


def candidate_models() -> list[str]:
    """Models to try, best first. If LLM_MODEL is set in .env, only that one is used."""
    if config.LLM_MODEL:
        return [config.LLM_MODEL]
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Put it in the .env file.")
    try:
        resp = requests.get(
            f"{config.LLM_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not list Groq models (check GROQ_API_KEY and your internet): {e}") from e
    ids = sorted(m["id"] for m in resp.json()["data"])
    skip = ("whisper", "guard", "tts", "orpheus", "embed", "safeguard", "compound")
    usable = [m for m in ids if not any(x in m.lower() for x in skip)]
    ordered = []
    for pref in PREFERENCE:
        ordered += [m for m in usable if pref in m.lower() and m not in ordered]
    ordered += [m for m in usable if m not in ordered]
    if not ordered:
        raise RuntimeError("No usable chat model found for this Groq key.")
    return ordered


def make_llm(model: str):
    from crewai import LLM

    _strip_cache_breakpoint_patch()
    return LLM(
        model=f"openai/{model}",           # Groq speaks the OpenAI protocol
        base_url=config.LLM_BASE_URL,
        api_key=config.GROQ_API_KEY or "none",
        temperature=0.2,                   # low = fewer random mistakes
        max_tokens=6000,                   # enough for a 300-line game, small enough for free-tier limits
    )


# ---- Groq rate limits (HTTP 429) ----
def is_rate_limit(e: Exception) -> bool:
    t = str(e).lower()
    return "429" in t or "rate limit" in t or "rate_limit" in t or "too large" in t


def wait_hint(e: Exception):
    """Seconds Groq says to wait ('Please try again in 7.2s' / '1m5.2s'), or None."""
    m = re.search(r"try again in (?:(\d+)m)?\s*(\d+(?:\.\d+)?)s", str(e))
    return (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else None


def call_with_retry(fn, on_wait=None, tries: int = 3):
    """Run fn(). On a short per-minute rate limit, wait the time Groq asks for and try again.
    A 'request too large' error (the model's limit is below what we need) is raised immediately."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            wait = wait_hint(e)
            if (not is_rate_limit(e) or "too large" in str(e).lower()
                    or wait is None or wait > 75 or i == tries - 1):
                raise
            if on_wait:
                on_wait(wait)
            time.sleep(wait + 1)


def run_crew(idea: str, llm, on_stage) -> str:
    """Run designer -> developer -> QA. Returns the raw text of the final answer."""
    from crewai import Agent, Crew, Process, Task

    designer = Agent(
        role="Creative Game Designer",
        goal="Turn the user's idea into a small, fun, feasible 2D game design",
        backstory=(
            "You are an experienced game designer who turns vague ideas into clear game designs: "
            "core loop, rules, win/lose conditions, basic entities, controls and feel. "
            "You keep it small enough to build in one Pygame file using only drawn shapes."
        ),
        llm=llm, verbose=False,
    )
    developer = Agent(
        role="Senior Python Game Developer",
        goal="Write complete, working Pygame code for the described game",
        backstory=(
            "You are a senior software engineer specialised in Pygame. You write structured, readable "
            "code with a proper game loop, event handling and drawing, and you always produce a "
            "complete runnable .py file." + RULES
        ),
        llm=llm, verbose=False,
    )
    qa = Agent(
        role="QA Engineer & Code Reviewer",
        goal="Find and fix bugs so the game is playable from the first second",
        backstory=(
            "You are a meticulous QA engineer. You check that the code runs, implements every designed "
            "feature, can be started and played with the keyboard, and has no state the player can get "
            "stuck in. You output the FINAL improved code." + RULES
        ),
        llm=llm, verbose=False,
    )

    t_design = Task(
        description=(
            "Take the user's game idea: {game_idea}. "
            "1. Expand it into a fun, simple 2D game. "
            "2. Describe: objective, controls (keyboard only), entities, win/lose. "
            "3. Keep it small: 1 screen, max 4 entities, max 5 mechanics, no assets. "
            "Output format: ## Game Design Document with Title, Genre, Objective, Controls, Entities, Mechanics."
        ),
        expected_output="A clear markdown game design document",
        agent=designer,
        callback=lambda _out: on_stage("code"),
    )
    t_code = Task(
        description=(
            "Using the game design from the previous task, write a COMPLETE standalone Python script "
            "using Pygame that implements the game. Follow the STRICT RULES in your backstory exactly. "
            "Implement every item in the design document. Add simple comments. "
            "Final answer MUST be ONLY the Python code block and a short How to play section."
        ),
        expected_output="One complete ```python block followed by a How to play section",
        agent=developer, context=[t_design],
        callback=lambda _out: on_stage("review"),
    )
    t_review = Task(
        description=(
            "Review the Python code from the previous task. "
            "1. Check for syntax and runtime errors. 2. Verify it matches the design document. "
            "3. Check that the game starts immediately (or from a clearly labelled start key) and cannot get stuck. "
            "4. Check that `await asyncio.sleep(0)` is inside the main loop and the file ends with `asyncio.run(main())`. "
            "5. Fix problems. Return the FULL file, never partial code or '...'. "
            "Final answer MUST be ONLY the complete Python code block and a short How to play section."
        ),
        expected_output="Final runnable Pygame script in one ```python block, then a How to play section",
        agent=qa, context=[t_design, t_code],
    )

    crew = Crew(agents=[designer, developer, qa], tasks=[t_design, t_code, t_review],
                process=Process.sequential, verbose=False)
    return crew.kickoff(inputs={"game_idea": idea}).raw


# Typographic characters models like to put in comments and strings -> plain ASCII.
_ASCII_FIXES = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
    "\u2026": "...", "\u2192": "->", "\u2190": "<-", "\u00d7": "x", "\u2022": "*", "\u00a0": " ",
    "\u2500": "-", "\u2501": "-", "\u2502": "|", "\u2550": "=", "\u2551": "|",
}


def to_ascii(code: str) -> str:
    """Generated games must be plain ASCII: Windows tools (pygbag) read files with a legacy encoding and
    crash on characters like box-drawing lines, and the browser's default font cannot draw them anyway."""
    for bad, good in _ASCII_FIXES.items():
        code = code.replace(bad, good)
    return code.encode("ascii", "ignore").decode("ascii")


def extract_code(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # drop reasoning text some models add
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    code = max(blocks, key=len).strip() if blocks else text.strip()
    return to_ascii(code) + "\n"


def extract_howto(text: str) -> str:
    """The 'How to play' text that follows the code block, if any."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    after = re.split(r"```(?:python)?\s*\n.*?```", text, maxsplit=1, flags=re.S)
    tail = after[-1] if len(after) > 1 else ""
    tail = re.sub(r"^#+\s*How to play\s*", "", tail.strip(), flags=re.I)
    return tail.strip()[:1200]


def repair_game(llm, code: str, error: str) -> str:
    reply = llm.call(
        f"Fix this pygame program. Problem found by automatic testing:\n{error}\n\n{RULES}\n\n"
        f"CODE:\n```python\n{code}\n```\nReturn the FULL corrected file in one ```python block."
    )
    return extract_code(reply)
