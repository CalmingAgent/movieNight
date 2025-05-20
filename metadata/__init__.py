"""
metadata
~~~~~~~~
Top-level package that bundles:

* core  – dataclasses + repository
* api_clients – TMDb / OMDb / YouTube singletons
* analytics   – similarity, scoring helpers
"""

# ── core objects ──────────────────────────────────────────────────────────
from .core.models import Movie                     # re-export
from .core.repo   import MovieRepo as repo         # singleton façade

# ── shared API clients ────────────────────────────────────────────────────
from .api_clients.tmdb_client    import client as tmdb_client
from .api_clients.omdb_client    import client as omdb_client
from .api_clients.youtube_client import client as yt_client

# ── analytics convenience ────────────────────────────────────────────────
from .analytics.scoring    import (
    movie_probability,
    calculate_weighted_totals,
)
from .analytics.similarity import calculate_similarity as calculate_group_similarity

# ── misc helpers used by GUI ---------------------------------------------
from international_reference import rating_to_age_group
from ..utils.locate_trailer              import locate_trailer

__all__ = [
    "Movie",
    "repo",
    "tmdb_client",
    "omdb_client",
    "yt_client",
    "movie_probability",
    "calculate_weighted_totals",
    "calculate_group_similarity",
    "rating_to_age_group",
    "locate_trailer",
]