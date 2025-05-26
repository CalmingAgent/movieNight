"""
metadata.analytics
~~~~~~~~~~~~~~~~~~
Stateless helper functions and small ML models.
"""

from .similarity import calculate_similarity
from .scoring    import (
    movie_probability,
    calculate_weighted_totals,
)

from .update_service import update_scores_and_trends   # batch helper

__all__ = [
    "calculate_similarity",
    "calculate_probability_to_watch",
    "calculate_weighted_totals",
    "update_scores_and_trends",
]
