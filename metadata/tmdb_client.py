from __future__ import annotations

import sys
from typing import Optional, Dict, Any, List
import datetime as _dt

import requests

from ..utils import log_debug, normalize
from ..settings import TMDB_API_KEY
from service import MovieNightDB
import international_reference


class TMDBClient:
    """Thin wrapper around The Movie Database (TMDb) that persists to SQLite."""
    BASE_URL = "https://api.themoviedb.org/3"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, db: MovieNightDB, api_key: str | None = None):
        self.db = db
        self.api_key = api_key or TMDB_API_KEY

    # ------------------------------------------------------------------
    # Public – High‑level helper
    # ------------------------------------------------------------------
    def get_or_fetch_movie(self, title: str) -> Optional[Dict[str, Any]]:
        """Return a *movies* row (dict‑like) from DB; fetch + insert if absent.

        1. Exact‑title lookup in `movies`.
        2. If not found, call TMDb; on success, insert the row & genres.
        """
        row = self.db.cur.execute(
            "SELECT * FROM movies WHERE LOWER(title)=LOWER(?)", (title,)
        ).fetchone()
        if row:
            return dict(row)

        # ---- TMDb fetch --------------------------------------------------
        meta = self._fetch_metadata(title)
        if not meta:
            return None

        movie_id = self.db.add_movie(meta["movie_fields"])

        # genres
        for gname in meta["genres"]:
            gid = self._ensure_genre(gname)
            self.db.cur.execute(
                "INSERT OR IGNORE INTO movie_genres (movie_id, genre_id) VALUES (?,?)",
                (movie_id, gid),
            )
        self.db.conn.commit()
        return self.db.cur.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()

    # ------------------------------------------------------------------
    # Internal helpers – API calls
    # ------------------------------------------------------------------
    def _search_exact(self, title: str) -> Optional[dict]:
        """Search TMDb pages 1–2; return movie JSON on *exact* title match."""
        norm_query = normalize(title)
        all_results: List[dict] = []
        for page in (1, 2):
            r = requests.get(
                f"{self.BASE_URL}/search/movie",
                params={"api_key": self.api_key, "query": title, "page": page},
                timeout=10,
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

    def _fetch_metadata(self, title: str) -> Optional[dict]:
    
        """Return a dict with *movie_fields* and *genres* extracted from TMDb."""
        m = self._search_exact(title)
        if not m:
            return None
        tmdb_id = m["id"]
        log_debug(f"TMDb → matched ID={tmdb_id} for “{title}”")

        # ── fetch details ───────────────────────────────────────────────
        det = requests.get(
            f"{self.BASE_URL}/movie/{tmdb_id}",
            params={"api_key": self.api_key, "append_to_response": "release_dates,videos"},
            timeout=10,
        ).json()

        # ---- runtime / year / release window --------------------------
        release_date = det.get("release_date", "")  # yyyy-mm-dd
        year = int(release_date[:4]) if release_date else None
        origin = (
            det["production_countries"][0]["iso_3166_1"]
            if det.get("production_countries") else "US")
        origin = origin.upper()
        release_window = self.classify_release_window(release_date, origin)

        # ---- MPAA rating ---------------------------------------------
        rating_cert = self.extract_cert(det, origin)

        # ---- Trailer (YouTube) ---------------------------------------
        trailer_url = None
        for v in det.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
                break

        # ---- Build movie_fields dict ---------------------------------
        movie_fields = {
            "title": det.get("title"),
            "year": year,
            "release_window": release_window,
            "rating_cert": rating_cert,
            "duration_seconds": det.get("runtime", 0) * 60 if det.get("runtime") else None,
            "youtube_link": trailer_url,
            "origin_country": origin
            # remaining fields left NULL – app can fill later
        }
        genres = [g["name"] for g in det.get("genres", [])]
        return {"movie_fields": movie_fields, "genres": genres}

    @staticmethod
    def classify_release_window(date_str: str, country: str | None = "US") -> str:
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
    def extract_cert(details: dict, country="US", release_type=3):
        blocks = details.get("release_dates", {}).get("results", [])
        for b in blocks:
            if b["iso_3166_1"] == country:
                for rd in b["release_dates"]:
                    if rd["type"] == release_type and rd["certification"]:
                        return rd["certification"]
        return None