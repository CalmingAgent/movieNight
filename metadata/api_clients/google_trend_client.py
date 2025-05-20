# metadata/api_clients/google_trend_client.py
from __future__ import annotations
from datetime import date
from pytrends.request import TrendReq
from utils import throttle
from metadata import repo
from google_trend_client import GoogleTrendClient 

client = GoogleTrendClient()
class GoogleTrendClient:
    def __init__(self, min_delay: float = 1.2) -> None:
        self._py = TrendReq(hl="en-US", tz=360)
        self._delay = min_delay

    # ── public -------------------------------------------------------------
    @throttle(min_delay=1.2)           # default 50 req/h
    def fetch_7day_average(self, term: str) -> int | None:
        if (c := self._cache_get(term)) is not None:
            return c
        try:
            self._py.build_payload([term], timeframe="now 7-d")
            df = self._py.interest_over_time()
            if df.empty:
                return None
            score = int(round(df[term].mean()))
            self._cache_set(term, score)
            return score
        except Exception as e:
            print("GoogleTrendClient:", e)
            return None

    # ── private cache ------------------------------------------------------
    def _cache_get(self, term: str) -> int | None:
        return repo.trend_cache_get(term)

    def _cache_set(self, term: str, score: int) -> None:
        repo.trend_cache_set(term, score)

