from __future__ import annotations

import sys
from typing import Optional, Any, List
import datetime as _dt

import requests

from movieNight.utils import log_debug, normalize, throttle
from movieNight.settings import TMDB_API_KEY
from movieNight.metadata.movie_night_db import MovieNightDB
import international_reference
from tmdb_client import TMDBClient

client = TMDBClient()

class TMDBClient:
    """Thin wrapper around The Movie Database (TMDb) that persists to SQLite."""
    BASE_URL = "https://api.themoviedb.org/3"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, db: MovieNightDB, api_key: str | None = None):
        self.db = db
        self.api_key = api_key
        if not self.api_key:
                raise RuntimeError("No TMDB apit key passed")

    @throttle(min_delay=0.4)                 # ≈ 2.5 req/sec
    def _get(self, path: str, **params):
        params["api_key"] = self.api_key
        return requests.get(f"{self.BASE_URL}{path}", params=params, timeout=10)
    # ------------------------------------------------------------------
    # Public – High‑level helper
    # ------------------------------------------------------------------
    def fetch_metadata(self, title: str) -> dict | None:
        """
        Query TMDb for *title* and return

            {
                "movie_fields": { … },   # ready for INSERT/UPDATE
                "genres": ["Action", "Adventure", …]
            }

        • No database calls
        • No local state mutated
        • Returns None if the title can’t be matched on TMDb
        """
        match = self._search_exact(title)
        if not match:
            return None                         # nothing matched

        movie_id = match["id"]
        log_debug(f"TMDb → matched ID={movie_id} for “{title}”")

        details = requests.get(
            f"{self.BASE_URL}/movie/{movie_id}",
            params={
                "api_key": self.api_key,
                "append_to_response": "release_dates,videos",
            },
            timeout=10,
        ).json()

        # ── Release window / origin country ──────────────────────────
        release_date = details.get("release_date", "")            # 'YYYY-MM-DD'
        origin       = (
            details.get("production_countries", [{}])[0].get("iso_3166_1", "US")
        ).upper()
        release_win  = self._classify_release_window(release_date, origin)

        # ── Certification (MPAA / BBFC / …) ─────────────────────────
        rating_cert  = self._extract_cert(details, origin)

        # ── First YouTube trailer (if any) ───────────────────────────
        trailer_url = None
        for v in details.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
                break

        movie_fields = {
            "title":             details.get("title"),
            "year":              int(release_date[:4]) if release_date else None,
            "release_window":    release_win,
            "rating_cert":       rating_cert,                 # renamed column
            "duration_seconds":  details.get("runtime", 0) * 60 if details.get("runtime") else None,
            "youtube_link":      trailer_url,
            "origin_country":    origin,
            # box_office, trend scores, etc. can stay NULL for now
        }

        genres = [g["name"] for g in details.get("genres", [])]

        return {"movie_fields": movie_fields, "genres": genres}

    # ------------------------------------------------------------------
    # Internal helpers – API calls
    # ------------------------------------------------------------------
    def _search_exact(self, title: str) -> Optional[dict]:
        """Search TMDb pages 1–2; return movie JSON on *exact* title match."""
        norm_query = normalize(title)
        all_results: List[dict] = []
        for page in (1, 2):
            r = self._get(
                "/search/movie",
                query=title,
                page=page
                )
            if r.status_code == 429:
                log_debug("TMDb rate limit reached – exiting…")
                sys.exit(1)
            payload = r.json()
            results = payload.get("results", [])
            all_results.extend(results)
            if page >= payload.get("total_pages", 1):
                break
        matches = [m for m in all_results if normalize(m.get("title", "")) == norm_query]
        return matches[0] if len(matches) == 1 else None

    # inside TMDBClient
    def _fetch_metadata(self, title: str) -> dict | None:
        """
        Return {
            "movie_fields": { … },   # ready for DB insert/update
            "genres":       [str, …]
        }
        or None if an exact-title match is not found.
        """
        match = self._search_exact(title)
        if not match:
            return None

        tmdb_id = match["id"]
        log_debug(f"TMDb → matched ID={tmdb_id} for “{title}”")

        # ── details call (throttled) ──────────────────────────────────
        det = self._get(
            f"/movie/{tmdb_id}",
            append_to_response="release_dates,videos"
        ).json()

        # ---------------- basic fields --------------------------------
        release_date  = det.get("release_date", "")                    # 'YYYY-MM-DD'
        year          = int(release_date[:4]) if release_date else None
        origin        = (det.get("production_countries", [{}])[0]
                        .get("iso_3166_1", "US")).upper()
        release_win   = self._classify_release_window(release_date, origin)
        rating_cert   = self._extract_cert(det, origin)
        runtime_sec   = det.get("runtime") * 60 if det.get("runtime") else None

        # ---------------- trailer --------------------------------------
        trailer_url = next(
            (f"https://www.youtube.com/watch?v={v['key']}"
            for v in det.get("videos", {}).get("results", [])
            if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
            None
        )

        # ---------------- extra fields you requested -------------------
        box_office   = det.get("revenue") or None              # “actual” box-office
        franchise    = det.get("belongs_to_collection", {}).get("name")

        movie_fields = {
            "title":             det.get("title"),
            "year":              year,
            "release_window":    release_win,
            "rating_cert":       rating_cert,
            "duration_seconds":  runtime_sec,
            "youtube_link":      trailer_url,
            "origin_country":    origin,           # if you renamed, keep same label
            "box_office_actual": box_office,
            "franchise":         franchise,
        }

        genres = [g["name"] for g in det.get("genres", [])]
        return {"movie_fields": movie_fields, "genres": genres}

    
    def fetch_user_rating(self, title: str) -> tuple[float, int] | None:
        """
        Return `(vote_average_0_to_10, vote_count)` for *title* or **None**
        if the film can’t be matched.

        Notes
        -----
        * vote_average is TMDb’s 0–10 user score (one decimal place).
        * vote_count is the number of user ballots behind that average.
        * No DB writes, no commits – pure HTTP + JSON.
        """
        match = self._search_exact(title)
        if not match:
            return None                         # no exact title match

        movie_id = match["id"]

        details = requests.get(
            f"{self.BASE_URL}/movie/{movie_id}",
            params={"api_key": self.api_key, "fields": "vote_average,vote_count"},
            timeout=10,
        ).json()

        # TMDb always includes these two keys (default 0, 0)
        return float(details["vote_average"]), int(details["vote_count"])
    @staticmethod
    def _classify_release_window(date_str: str, country: str | None = "US") -> str:
        if not date_str:
            return ""
        try:
            dt = _dt.date.fromisoformat(date_str)
        except ValueError:
            return ""

        m, d = dt.month, dt.day
        country = country.upper()
        for (start, end), label in international_reference.COUNTRY_WINDOWS.get(country, []):
            if (m, d) >= start and (m, d) <= end:
                return label

        seasons = international_reference.SEASONS_SOUTH if country in international_reference.SOUTH_HEMI else international_reference.SEASONS_NORTH
        return seasons[((m % 12) // 3)]
    
    def _ensure_genre(self, name: str) -> int:
        row = self.db.cur.execute("SELECT id FROM genres WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
        self.db.cur.execute("INSERT INTO genres (name) VALUES (?)", (name,))
        self.db.conn.commit()
        return self.db.cur.lastrowid
    @staticmethod
    def _extract_cert(details: dict, country="US", release_type=3):
        blocks = details.get("release_dates", {}).get("results", [])
        for b in blocks:
            if b["iso_3166_1"] == country:
                for rd in b["release_dates"]:
                    if rd["type"] == release_type and rd["certification"]:
                        return rd["certification"]
        return None
    
    def get_countries(self) -> list[dict]:
        """
        Return the list of all TMDb-supported origin countries:
        [{ "iso_3166_1": "...", "english_name": "..." }, …]
        """
        resp = self._get("configuration/countries")   # your internal GET wrapper
        resp.raise_for_status()
        return resp.json()    

import sqlite3
from ...settings import DATABASE_PATH
def fix_short_durations(threshold_min: int = 5) -> None:
    con = sqlite3.connect(DATABASE_PATH)
    cur = con.cursor()
    bad = cur.execute(
        "SELECT id, youtube_link FROM movies WHERE duration_seconds < ?",
        (threshold_min * 60,),
    ).fetchall()
    for mid, url in bad:
        # attempt TMDb runtime refresh
        tmdb_meta = TMDBClient().fetch_metadata(title=None, imdb_id=None, db_id=mid)
        if tmdb_meta and tmdb_meta["movie_fields"]["duration_seconds"]:
            cur.execute(
                "UPDATE movies SET duration_seconds=? WHERE id=?",
                (tmdb_meta["movie_fields"]["duration_seconds"], mid),
            )
    con.commit()
    con.close()