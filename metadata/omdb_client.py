#other movie databases for metadata
# movieNight/metadata/omdb_client.py

import os
import requests

class OMDBClient:
    """
    Simple wrapper for the OMDB API.
    """
    BASE_URL = "http://www.omdbapi.com/"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_movie_data(self, title: str) -> dict:
        params = {"apikey": self.api_key, "t": title}
        resp = requests.get(self.BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
