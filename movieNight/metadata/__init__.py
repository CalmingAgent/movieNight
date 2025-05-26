"""
metadata
~~~~~~~~
Top-level package that bundles:

* core  – dataclasses + repository
* api_clients – TMDb / OMDb / YouTube singletons
* analytics   – similarity, scoring helpers
"""

# ── core objects ──────────────────────────────────────────────────────────
from movieNight.metadata.core.models import Movie                     # re-export
from movieNight.metadata.core.repo   import MovieRepo as repo         # singleton façade

# ── shared API clients ────────────────────────────────────────────────────
from movieNight.metadata.api_clients.tmdb_client    import client as tmdb_client
from movieNight.metadata.api_clients.omdb_client    import client as omdb_client
from movieNight.metadata.api_clients.youtube_client import client as yt_client

# ── analytics convenience ────────────────────────────────────────────────
from movieNight.metadata.analytics.scoring    import (
    calculate_probability_to_watch,
    calculate_weighted_totals,
)
from movieNight.metadata.analytics.similarity import calculate_similarity as calculate_group_similarity

# ── misc helpers used by GUI ---------------------------------------------
from movieNight.metadata.international_reference import rating_to_age_group
from movieNight.utils              import locate_trailer

__all__ = [
    "Movie",
    "repo",
    "tmdb_client",
    "omdb_client",
    "yt_client",
    "calculate_probability_to_watch",
    "calculate_weighted_totals",
    "calculate_group_similarity",
    "rating_to_age_group",
    "locate_trailer",
]