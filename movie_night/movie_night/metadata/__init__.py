"""
metadata
~~~~~~~~
Top-level package that bundles:

* core  – dataclasses + repository
* api_clients – TMDb / OMDb / YouTube singletons
* analytics   – similarity, scoring helpers
"""

# ── core objects ──────────────────────────────────────────────────────────
from movie_night.metadata.core.models import Movie                     # re-export
from movie_night.metadata.core.repo   import MovieRepo as repo         # singleton façade

# ── shared API clients ────────────────────────────────────────────────────
from movie_night.metadata.api_clients.tmdb_client    import client as tmdb_client
from movie_night.metadata.api_clients.omdb_client    import client as omdb_client
from movie_night.metadata.api_clients.youtube_client import client as yt_client
from movie_night.metadata.api_clients.google_trend_client import client as trend_client

# ── analytics convenience ────────────────────────────────────────────────
from movie_night.metadata.analytics.scoring    import (
    calculate_probability_to_watch,
    calculate_weighted_total,
)
from movie_night.metadata.analytics.similarity import calculate_similarity as calculate_group_similarity

# ── misc helpers used by GUI ---------------------------------------------
from movie_night.metadata.international_reference import rating_to_age_group
from movie_night.utils              import locate_trailer

__all__ = [
    "Movie",
    "repo",
    "tmdb_client",
    "omdb_client",
    "yt_client",
    "trend_client",
    "calculate_probability_to_watch",
    "calculate_weighted_total",
    "calculate_group_similarity",
    "rating_to_age_group",
    "locate_trailer",
]