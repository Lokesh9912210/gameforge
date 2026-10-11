"""Central settings, read from environment variables (and the .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GAMES_DIR = ROOT / "games"
GAMES_DIR.mkdir(exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "")  # optional: exact Groq model ID, e.g. openai/gpt-oss-120b

MAX_REPAIRS = int(os.getenv("MAX_REPAIRS", "3"))
MAX_MODELS_TO_TRY = int(os.getenv("MAX_MODELS_TO_TRY", "4"))  # how many different models to try on rate limits
MIN_IDEA_CHARS = 8
MAX_IDEA_CHARS = 400

# Development switches (no API key needed):
#   GAMEFORGE_MOCK=1       -> use a built-in sample game instead of calling the AI
#   GAMEFORGE_MOCK=repair  -> first return a broken game so you can watch the auto-repair loop
MOCK = os.getenv("GAMEFORGE_MOCK", "")
