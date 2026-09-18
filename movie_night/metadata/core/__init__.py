"""
metadata.core
~~~~~~~~~~~~~
Domain layer – pure dataclasses & repository.
"""

from .models import Movie
from .repo   import MovieRepo as repo

__all__ = ["Movie", "repo"]
