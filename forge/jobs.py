"""Job queue: one game is built at a time (keeps within the free API rate limits)."""
import json
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import builder, checker, config, crew_build

SAMPLES = Path(__file__).parent / "samples"
JOB_ID = re.compile(r"^[a-f0-9]{8}$")

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=1)

# stage -> text shown to the user
MESSAGES = {
    "queued": "Waiting for the build queue",
    "design": "Designing the game",
    "code": "Writing the code",
    "review": "Reviewing the code",
    "test": "Play-testing it automatically",
    "build": "Building the browser version",
    "done": "Ready to play",
}


def _job_dir(job_id: str) -> Path:
    return config.GAMES_DIR / job_id


def _save(job: dict):
    d = _job_dir(job["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")


def _update(job_id: str, **fields):
    with _lock:
        job = _jobs[job_id]
        job.update(fields)
        _save(job)


def _set_stage(job_id: str, stage: str):
    _update(job_id, stage=stage, message=MESSAGES[stage])


def load_existing():
    """Re-read finished games from disk when the server starts."""
    for p in config.GAMES_DIR.glob("*/job.json"):
        try:
            job = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") in ("queued", "running"):
            job.update(status="failed", error="The server restarted while this game was being built.")
        _jobs[job["id"]] = job


def submit(idea: str) -> dict:
    job_id = uuid.uuid4().hex[:8]
    job = {
        "id": job_id, "idea": idea, "status": "queued", "stage": "queued",
        "message": MESSAGES["queued"], "created": time.time(), "finished": None,
        "repairs": 0, "model": None, "howto": "", "play_url": None, "code_url": None, "error": None,
    }
    with _lock:
        _jobs[job_id] = job
        _save(job)
    _executor.submit(_run, job_id)
    return job


def _can_rebuild(job: dict) -> bool:
    """A game that failed only at the browser-build step still has good code; its build can be retried."""
    return (job["status"] == "failed" and job.get("stage") == "build"
            and (_job_dir(job["id"]) / "main.py").exists())


def _view(job: dict) -> dict:
    return {**job, "can_rebuild": _can_rebuild(job)}


def get(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        return _view(job) if job else None


def recent(limit: int = 12) -> list[dict]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)
        return [_view(j) for j in jobs[:limit]]


def rebuild(job_id: str):
    """Retry only the browser build of a game whose build failed. No AI calls are made."""
    with _lock:
        job = _jobs.get(job_id)
        if not job or not _can_rebuild(job):
            return None
    _update(job_id, status="queued", stage="queued", message=MESSAGES["queued"],
            error=None, finished=None, created=time.time())
    _executor.submit(_rebuild, job_id)
    return get(job_id)


def _rebuild(job_id: str):
    job_dir = _job_dir(job_id)
    try:
        _update(job_id, status="running")
        _set_stage(job_id, "build")
        main_py = job_dir / "main.py"
        main_py.write_text(crew_build.to_ascii(main_py.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        error = builder.build_game(job_dir)
        if error:
            raise RuntimeError(error)
        _update(job_id, status="done", stage="done", message=MESSAGES["done"], finished=time.time(),
                play_url=f"/games/{job_id}/build/web/", code_url=f"/games/{job_id}/main.py")
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _update(job_id, status="failed", stage="build", finished=time.time(), error=str(e)[:1500])


def _mock_generate(attempt: int) -> str:
    time.sleep(0.6)
    name = "neon_duel_stuck.py" if (config.MOCK == "repair" and attempt == 0) else "neon_duel_fixed.py"
    code = (SAMPLES / name).read_text(encoding="utf-8")
    return f"```python\n{code}```\n\n### How to play\nP1: WASD to move, F to shoot. P2: arrow keys to move, Enter to shoot. First to win 2 rounds wins."


def _short(e: Exception) -> str:
    return " ".join(str(e).split())[:230]


def _run_crew_with_fallback(job_id: str, idea: str):
    """Try the best model; if Groq's free-tier limits block it, move on to the next model."""
    problems = []
    for model in crew_build.candidate_models()[: config.MAX_MODELS_TO_TRY]:
        llm = crew_build.make_llm(model)
        _update(job_id, model=model)
        _set_stage(job_id, "design")
        try:
            raw = crew_build.call_with_retry(
                lambda: crew_build.run_crew(idea, llm, lambda stage: _set_stage(job_id, stage)),
                on_wait=lambda s: _update(job_id, message=f"Groq free-tier limit: waiting {int(s)}s, then continuing"),
            )
            return raw, llm
        except Exception as e:  # noqa: BLE001
            if not crew_build.is_rate_limit(e):
                raise
            problems.append(f"- {model}: {_short(e)}")
            _update(job_id, message="A Groq limit blocked this model. Trying another one")
    raise RuntimeError(
        "Groq's free-tier limits blocked every model that was tried. Wait a minute and try again. "
        "If it keeps happening, open console.groq.com/settings/limits, pick a model with a higher "
        "tokens-per-minute limit, and set LLM_MODEL=<that model> in the .env file.\n\nDetails:\n" + "\n".join(problems)
    )


def _run(job_id: str):
    job_dir = _job_dir(job_id)
    try:
        _update(job_id, status="running")
        idea = get(job_id)["idea"]
        llm = None

        # 1. Crew: design -> code -> review
        _set_stage(job_id, "design")
        if config.MOCK:
            for stage in ("design", "code", "review"):
                _set_stage(job_id, stage)
                time.sleep(0.4)
            raw = _mock_generate(0)
        else:
            raw, llm = _run_crew_with_fallback(job_id, idea)
        code = crew_build.extract_code(raw)
        _update(job_id, howto=crew_build.extract_howto(raw))

        # 2. Automatic play-test, with up to MAX_REPAIRS automatic repairs
        _set_stage(job_id, "test")
        problem = None
        for attempt in range(config.MAX_REPAIRS + 1):
            problem = checker.check_game(job_dir, code)
            if problem is None:
                break
            if attempt == config.MAX_REPAIRS:
                break
            _update(job_id, repairs=attempt + 1, message=f"Fixing a problem automatically (attempt {attempt + 1})")
            if config.MOCK:
                code = crew_build.extract_code(_mock_generate(attempt + 1))
            else:
                code = crew_build.call_with_retry(
                    lambda: crew_build.repair_game(llm, code, problem),
                    on_wait=lambda s: _update(job_id, message=f"Groq rate limit: waiting {int(s)}s"))
        if problem:
            raise RuntimeError(f"The game still had a problem after {config.MAX_REPAIRS} automatic repairs.\n{problem}")

        # 3. Browser build
        _set_stage(job_id, "build")
        build_error = builder.build_game(job_dir)
        if build_error:
            raise RuntimeError(build_error)

        _update(job_id, status="done", stage="done", message=MESSAGES["done"], finished=time.time(),
                play_url=f"/games/{job_id}/build/web/", code_url=f"/games/{job_id}/main.py")
    except Exception as e:  # noqa: BLE001 - show any failure to the user instead of dying silently
        traceback.print_exc()
        _update(job_id, status="failed", finished=time.time(), error=str(e)[:1500])
