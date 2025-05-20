# movieNight/movie_api/scrappers.py
from __future__ import annotations

import json, re, time, random, requests
from typing import Dict, Any, Optional

from ..utils import log_debug   # your existing logger

# ---------- Regex patterns--------------------------------------
_HISTOGRAM_RE   = re.compile(rb'"rating_histogram":\s*(\[[^\]]+\])', re.DOTALL)
_DEMOGRAPHIC_RE = re.compile(rb'"demographic_data":\s*(\{.+?\})\s*,\s*"ratings_bar"', re.DOTALL)
_TOP250_RE      = re.compile(rb'"topRank":\s*(\d+)', re.DOTALL)
_MOVIEMETER_RE  = re.compile(rb'"moviemeter":\s*(\d+)', re.DOTALL)

class IMDbScraper:
    """
    Fetch rating histogram + demographic splits from IMDb ratings page
    with built-in polite throttling.

    Parameters
    ----------
    min_delay : float
        Minimum seconds between successive network requests
        (default 1.0).  A ±0.3 s jitter is added to avoid looking like
        a fixed-interval bot.
    """

    RATING_URL = "https://www.imdb.com/title/{imdb_id}/ratings"

    def __init__(self, *, min_delay: float = 1.0, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent":
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            }
        )
        self._min_delay = min_delay
        self._last_hit  = 0.0   # epoch timestamp of previous fetch

    # ------------------------------------------------------------------ public
    def fetch_all(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Return histogram, demographic splits, ranks – or None if parse fails."""
        html = self._get_raw(imdb_id)
        if not html:
            return None

        hist = self._parse_histogram(html)
        if hist is None:
            return None

        demo = self._parse_demographic(html)
        rank = self._extract_int(_TOP250_RE, html)
        heat = self._extract_int(_MOVIEMETER_RE, html)

        return {
            "histogram":    hist,
            "demographics": demo,
            "top250_rank":  rank,
            "moviemeter":   heat,
        }

    # --------------------------------------------------------- network & delay
    def _get_raw(self, imdb_id: str) -> Optional[bytes]:
        # ---- throttle --------------------------------------------------
        wait = self._min_delay - (time.time() - self._last_hit)
        if wait > 0:
            time.sleep(wait + random.uniform(0.0, 0.3))
        # ---------------------------------------------------------------
        try:
            resp = self.session.get(self.RATING_URL.format(imdb_id=imdb_id), timeout=8)
            self._last_hit = time.time()
            if resp.status_code == 200:
                return resp.content
            log_debug(f"IMDb HTTP {resp.status_code} for {imdb_id}")
        except requests.RequestException as exc:
            log_debug(f"IMDb network error: {exc}")
        return None

    # ----------------------------------------------------------- parsing bits
    def _parse_histogram(self, html: bytes) -> Optional[Dict[int, int]]:
        m = _HISTOGRAM_RE.search(html)
        if not m:
            return None
        try:
            bins = json.loads(m.group(1))
            return {b["rating"]: b["votes"] for b in bins}
        except (ValueError, KeyError) as exc:
            log_debug(f"IMDb histogram JSON error: {exc}")
            return None

    def _parse_demographic(self, html: bytes) -> Dict[str, Dict[str, float]]:
        m = _DEMOGRAPHIC_RE.search(html)
        if not m:
            return {}
        try:
            table = json.loads(m.group(1))
            flat: Dict[str, Dict[str, float]] = {}
            for group, ages in table.items():
                for age, blob in ages.items():
                    key = f"{group[0]}{age}" if age != "all" else group[0]
                    flat[key] = {"rating": blob.get("rating"), "votes": blob.get("votes")}
            if "all" in table:
                flat["all"] = {
                    "rating": table["all"]["all"]["rating"],
                    "votes": table["all"]["all"]["votes"],
                }
            return flat
        except (ValueError, KeyError, TypeError) as exc:
            log_debug(f"IMDb demographic JSON error: {exc}")
            return {}

    @staticmethod
    def _extract_int(pattern: re.Pattern, html: bytes) -> Optional[int]:
        m = pattern.search(html)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None
