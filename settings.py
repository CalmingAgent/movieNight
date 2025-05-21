from pathlib import Path
import os
from dotenv import load_dotenv
from PySide6.QtGui import QIcon # type: ignore

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(BASE_DIR / "secret.env")

SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID")
YOUTUBE_API_KEY  = os.getenv("YOUTUBE_API_KEY")
TMDB_API_KEY     = os.getenv("TMDB_API_KEY")
OMDB_API_KEY     = os.getenv("OMDB_API_KEY")

if not SPREADSHEET_ID:
    raise EnvironmentError("Missing SPREADSHEET_ID in .env")
if not YOUTUBE_API_KEY:
    raise EnvironmentError("Missing YOUTUBE_API_KEY in .env")
if not TMDB_API_KEY:
    raise EnvironmentError("Missing TMDB_API_KEY in .env")

# File / folder paths
TRAILER_FOLDER      = BASE_DIR / "Video_Trailers"
TRAILER_FOLDER.mkdir(exist_ok=True)
GHIBLI_SHEET_PATH   = BASE_DIR / "ghib.xlsx"
UNDER_REVIEW_PATH   = BASE_DIR / "underReviewURLs.json"
SERVICE_ACCOUNT_KEY = BASE_DIR / "service_secret.json"
CLIENT_SECRET_PATH  = BASE_DIR / "client_secret.json"
USER_TOKEN_PATH     = BASE_DIR / "youtube_token.pickle"
LOG_PATH            = BASE_DIR / "trailer_debug.log"
AUTO_UPDATE_SCRIPT  = BASE_DIR / "autoUpdate.py"
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "service_secret.json"
DATABASE_PATH       = BASE_DIR / "movie_night.sqlite"
SCHEMA_PATH          = BASE_DIR / "movie_night_schema.sql"
GRADED_MOVIES       = "seen"


# API scopes and URLs
DRIVE_SCOPES       = ["https://www.googleapis.com/auth/drive.readonly"]
SHEETS_SCOPES      = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
YOUTUBE_SCOPES     = ["https://www.googleapis.com/auth/youtube"]
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# UI constants
ACCENT_COLOR = "#3b82f6"
ICON = lambda name: QIcon(str(BASE_DIR / "icons" / f"{name}.svg"))

META_SCORE_WEIGHTS = {
    "imdb": 0.4,
    "rt_critic": 0.2,
    "rt_audience": 0.2,
    "metacritic": 0.2
}
TREND_PROBABILITY_WEIGHTS = {
    "google_trend": 0.4,
    "actor_trend": 0.4,
    "combined_score": 0.2
    }
TREND_ACTOR = {
    "google_trend": .6,
    "imdb_popular": .4
}
