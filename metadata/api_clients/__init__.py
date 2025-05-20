"""
metadata.api_clients
~~~~~~~~~~~~~~~~~~~~
Thin wrappers around external REST / scraping APIs.
Import *client* singletons if you only need one global instance.
"""

from .tmdb_client    import client as tmdb_client
from .omdb_client    import client as omdb_client
from .youtube_client import client as yt_client
from .google_trend_client import client as trend_client

__all__ = ["tmdb_client", "omdb_client", "yt_client", "trend_client" ]