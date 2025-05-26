"""
metadata.api_clients
~~~~~~~~~~~~~~~~~~~~
Thin wrappers around external REST / scraping APIs.
Import *client* singletons if you only need one global instance.
"""

from movieNight.metadata.api_clients.tmdb_client    import client as tmdb_client
from movieNight.metadata.api_clients.omdb_client    import client as omdb_client
from movieNight.metadata.api_clients.youtube_client import client as yt_client
from movieNight.metadata.api_clients.google_trend_client import client as trend_client

__all__ = ["tmdb_client", "omdb_client", "yt_client", "trend_client" ]