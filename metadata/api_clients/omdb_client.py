# movieNight/metadata/omdb_client.py
from __future__ import annotations

import os, re, functools, requests
from typing import Any, Dict, Optional, Tuple, List

from ...utils import log_debug, throttle
from omdb_client import OMDBClient

OMDB_URL = "http://www.omdbapi.com/" 
client = OMDBClient()
class OMDBClient:
    """
    Stateless wrapper around OMDb that exposes **granular** accessors.
    One HTTP fetch is cached per title / IMDb-id, so you never hit
    omdbapi.com more than once for the same film.
    """

    # ────────────────────────────────────────────────────────────────
    # Construction
    # ────────────────────────────────────────────────────────────────
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OMDB_API_KEY")
        if not self.api_key:
            raise RuntimeError("OMDB_API_KEY not set and no api_key passed")

    # ────────────────────────────────────────────────────────────────
    # Internal – one cached JSON payload per movie
    # ────────────────────────────────────────────────────────────────
    @functools.lru_cache(maxsize=512)
    @throttle(min_delay=.6)
    def _payload(self, *, imdb_id: str | None, title: str | None) -> dict | None:
        if not imdb_id and not title:
            raise ValueError("Provide imdb_id or title")

        params = {"apikey": self.api_key, "plot": "short"}
        params["i" if imdb_id else "t"] = imdb_id or title

        try:
            resp = requests.get(OMDB_URL, params=params, timeout=8)
            data = resp.json()
            if data.get("Response") == "True":
                return data
        except Exception as exc:
            log_debug(f"OMDb fetch error: {exc}")
        return None

    # helper decorator to avoid copy-pasting the *payload* retrieval
    def _omdb_call(fn):
        @functools.wraps(fn)
        def wrapper(self, *, imdb_id: str | None = None, title: str | None = None):
            data = self._payload(imdb_id=imdb_id, title=title)
            return fn(self, data or {})
        return wrapper

    # ────────────────────────────────────────────────────────────────
    # Basic identification
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_title(self, d: dict) -> Optional[str]:
        return d.get("Title")

    @_omdb_call
    def get_year(self, d: dict) -> Optional[int]:
        try: return int(d.get("Year", "")[:4])
        except ValueError: return None

    @_omdb_call
    def get_imdb_id(self, d: dict) -> Optional[str]:
        return d.get("imdbID")

    # ────────────────────────────────────────────────────────────────
    # Textual info
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_plot(self, d: dict) -> Optional[str]:
        return None if d.get("Plot") == "N/A" else d.get("Plot")

    @_omdb_call
    def get_awards(self, d: dict) -> Optional[str]:
        return None if d.get("Awards") == "N/A" else d.get("Awards")

    # ────────────────────────────────────────────────────────────────
    # Runtime & dates
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_runtime_seconds(self, d: dict) -> Optional[int]:
        m = re.match(r"(\\d+)\\s*min", d.get("Runtime", ""))
        return int(m.group(1)) * 60 if m else None

    @_omdb_call
    def get_released_date(self, d: dict) -> Optional[str]:
        return None if d.get("Released") in ("N/A", None) else d["Released"]

    @_omdb_call
    def get_dvd_date(self, d: dict) -> Optional[str]:
        return None if d.get("DVD") in ("N/A", None) else d["DVD"]

    # ────────────────────────────────────────────────────────────────
    # Money & performance
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_box_office(self, d: dict) -> Optional[int]:
        s = d.get("BoxOffice")
        if s and s.startswith("$"):
            try: return int(s[1:].replace(",", ""))
            except ValueError: pass
        return None

    @_omdb_call
    def get_imdb_votes(self, d: dict) -> Optional[int]:
        try: return int(d.get("imdbVotes", "").replace(",", ""))
        except ValueError: return None

    # ────────────────────────────────────────────────────────────────
    # Credits & companies
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_director(self, d: dict) -> Optional[str]:
        return None if d.get("Director") == "N/A" else d.get("Director")

    @_omdb_call
    def get_writer(self, d: dict) -> Optional[str]:
        return None if d.get("Writer") == "N/A" else d.get("Writer")

    @_omdb_call
    def get_actors(self, d: dict) -> Optional[str]:
        return None if d.get("Actors") == "N/A" else d.get("Actors")

    @_omdb_call
    def get_production_company(self, d: dict) -> Optional[str]:
        return None if d.get("Production") == "N/A" else d.get("Production")

    @_omdb_call
    def get_website(self, d: dict) -> Optional[str]:
        return None if d.get("Website") == "N/A" else d.get("Website")

    # ────────────────────────────────────────────────────────────────
    # Categorical lists
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_genres(self, d: dict) -> List[str]:
        raw = d.get("Genre", "") or ""
        return [g.strip() for g in raw.split(",") if g.strip()]

    @_omdb_call
    def get_languages(self, d: dict) -> List[str]:
        raw = d.get("Language", "") or ""
        return [l.strip() for l in raw.split(",") if l.strip()]

    @_omdb_call
    def get_countries(self, d: dict) -> List[str]:
        raw = d.get("Country", "") or ""
        return [c.strip() for c in raw.split(",") if c.strip()]

    # ────────────────────────────────────────────────────────────────
    # Poster
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_poster_url(self, d: dict) -> Optional[str]:
        return None if d.get("Poster") == "N/A" else d.get("Poster")

    # ────────────────────────────────────────────────────────────────
    # Ratings block
    # ────────────────────────────────────────────────────────────────
    @_omdb_call
    def get_ratings(self, d: dict) -> Dict[str, float | None]:
        r = {
            "imdb":       self._score10_to_100(d.get("imdbRating")),
            "rt_critic":  None,
            "rt_audience": None,
            "metacritic": self._metascore(d.get("Metascore")),
        }
        for src in d.get("Ratings", []):
            if src["Source"] == "Rotten Tomatoes":
                r["rt_critic"] = self._percent(src["Value"])
        return r

    # ────────────────────────────────────────────────────────────────
    # Tiny parsing helpers
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _score10_to_100(txt: str | None) -> Optional[float]:
        try: return round(float(txt) * 10, 1)
        except (TypeError, ValueError): return None

    @staticmethod
    def _percent(txt: str | None) -> Optional[float]:
        if txt and txt.endswith("%"):
            try: return float(txt.rstrip("%"))
            except ValueError: pass
        return None

    @staticmethod
    def _metascore(txt: str | None) -> Optional[float]:
        try: return float(txt.split("/")[0])
        except (AttributeError, ValueError): return None
