# metadata/__init__.py

# models.py likely defines your ORM classes
from . import models

# API clients
from .omdb_client    import OMDBClient
from .tmdb_client    import TMDBClient
from .youtube_client import YouTubeClient

# your service-layer helpers
from .service import movie_probability, calculate_weighted_totals, calculate_group_similarity

__all__ = [
    "models",
    "OMDBClient",
    "TMDBClient",
    "YouTubeClient",
    "movie_probability",
    "calculate_weighted_totals",
    "calculate_group_similarity",
]
