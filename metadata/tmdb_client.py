##TMDB calls returning metadata
# movieNight/metadata/tmdb_client.py

import os
import requests
from ..utils import log_debug, normalize_title, youtube_api_search, get_video_duration_sec

class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"
    API_KEY  = os.getenv("TMDB_API_KEY")

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or self.API_KEY
        if not self.api_key:
            raise RuntimeError("TMDB_API_KEY not set")

    def find_trailer(self, movie_title: str) -> str | None:
        """
        Search TMDB for an exact match on movie_title; returns a YouTube URL or None.
        """
        # port your tmdb_find_trailer(...) logic here,
        # replacing global API_KEY references with self.api_key
        ...

    def search_fallback(self, movie_title: str) -> str | None:
        """
        Fallback to YouTube search if TMDB fails or gives ambiguous/zero results.
        """
        return youtube_api_search(f"{movie_title} official trailer")[0]
