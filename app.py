"""GameForge web server.  Start it with:  python run.py"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from forge import __version__, config, jobs

app = FastAPI(title="GameForge")
jobs.load_existing()
print(f"GameForge version {__version__}", flush=True)


class IdeaIn(BaseModel):
    idea: str


@app.post("/api/jobs")
def create_job(body: IdeaIn):
    idea = " ".join(body.idea.split())
    if len(idea) < config.MIN_IDEA_CHARS:
        raise HTTPException(400, "Describe the game in a few more words.")
    if len(idea) > config.MAX_IDEA_CHARS:
        raise HTTPException(400, f"Keep the idea under {config.MAX_IDEA_CHARS} characters.")
    return jobs.submit(idea)


@app.get("/api/jobs/{job_id}")
def read_job(job_id: str):
    job = jobs.get(job_id) if jobs.JOB_ID.match(job_id) else None
    if not job:
        raise HTTPException(404, "Game not found.")
    return job


@app.post("/api/jobs/{job_id}/rebuild")
def rebuild_job(job_id: str):
    job = jobs.rebuild(job_id) if jobs.JOB_ID.match(job_id) else None
    if not job:
        raise HTTPException(400, "Only a game that failed at the browser-build step can be rebuilt.")
    return job


@app.get("/api/version")
def version():
    return {"version": __version__}


@app.get("/api/jobs")
def list_jobs():
    return jobs.recent()


@app.get("/")
def index():
    return FileResponse(config.ROOT / "static" / "index.html")

app.mount("/games", StaticFiles(directory=config.GAMES_DIR, html=True), name="games")
