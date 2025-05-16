"""
metadata package
================
Exports the shared singletons (API clients, repository) and the most commonly
used analytics helpers so that the rest of the code base can simply

    from metadata import repo, tmdb_client, calculate_similarity

without worrying about internal paths.
"""

# ────────────────────────────────────────────────────────────────────────────
# data models (pure dataclasses)
# ────────────────────────────────────────────────────────────────────────────
from .core import models                      # e.g. models.Movie

# ────────────────────────────────────────────────────────────────────────────
# repository – domain-level persistence façade
# ────────────────────────────────────────────────────────────────────────────
from .core.repo import MovieRepo as repo      # thread-aware, SQL lives inside

# ────────────────────────────────────────────────────────────────────────────
# shared API-client singletons
# ────────────────────────────────────────────────────────────────────────────
from .api_clients.tmdb_client    import client as tmdb_client
from .api_clients.omdb_client    import client as omdb_client
from .api_clients.youtube_client import client as yt_client

# ────────────────────────────────────────────────────────────────────────────
# analytics convenience
# ────────────────────────────────────────────────────────────────────────────
from .analytics.scoring    import (
    movie_probability,
    calculate_weighted_totals,
)
from .analytics.similarity import calculate_similarity as calculate_group_similarity

__all__ = [
    "models",
    "repo",                     # new: replaces old DB singleton
    "tmdb_client",
    "omdb_client",
    "yt_client",
    "movie_probability",
    "calculate_weighted_totals",
    "calculate_group_similarity",
]