"""
analytics.similarity
~~~~~~~~~~~~~~~~~~~~
Pair-wise similarity for a list[Movie].

Public function
---------------
calculate_similarity(movies, repo=global_repo)
    -> list[(id_a, id_b, similarity)]
"""

from __future__ import annotations
import math
from itertools import combinations
from typing import Iterable, List, Sequence, Set, Tuple

from movieNight.metadata.core.models import Movie
from movieNight.metadata.core.repo   import MovieRepo, repo            # singleton
from movieNight.metadata.international_reference import rating_to_age_group


# ── tiny math helpers ───────────────────────────────────────────────────────
def _cosine(v1: Sequence[float], v2: Sequence[float]) -> float:
    dot  = sum(a * b for a, b in zip(v1, v2))
    norm = math.sqrt(sum(a * a for a in v1)) * math.sqrt(sum(b * b for b in v2))
    return dot / norm if norm else 0.0


def _jaccard(a: Set[str], b: Set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


# ── public API ─────────────────────────────────────────────────────────────
def calculate_similarity(
    movies: List[Movie],
    repo: MovieRepo = repo,
) -> List[Tuple[int, int, float]]:
    """Return (movie_id_a, movie_id_b, similarity) for each unique pair.

    Similarity ∈ [0, 1]  (1 = identical by our metric).

    Parameters
    ----------
    movies
        List of `Movie` dataclass instances.
    repo
        Repository used to fetch genres / themes (defaults to the global one).
    """
    unique = {m.id: m for m in movies}.values()             # deduplicate
    results: list[Tuple[int, int, float]] = []

    for m1, m2 in combinations(unique, 2):
        sim = _pair_similarity(m1, m2, repo)
        results.append((m1.id, m2.id, sim))

    return results


# ── internal helpers ───────────────────────────────────────────────────────
def _pair_similarity(a: Movie, b: Movie, repo: MovieRepo) -> float:
    num = _numeric_similarity(a, b)
    cat = _categorical_similarity(a, b, repo)
    return round(0.60 * num + 0.40 * cat, 3)


# numeric part – cosine on 6 scaled dims
def _numeric_similarity(a: Movie, b: Movie) -> float:
    return _cosine(_vec(a), _vec(b))


def _vec(m: Movie) -> Tuple[float, ...]:
    def yr(y):  return ((y or 2000) - 2000) / 50.0
    def dur(s): return (s or 0) / 3600.0
    def box(x): return math.log10(max(x, 1.0)) if x else 0.0
    def pct(x): return (x or 0) / 100.0

    return (
        yr(m.year),
        dur(m.duration_seconds),
        box(m.box_office_actual),
        pct(m.google_trend_score),
        pct(m.combined_score),
        pct(m.actor_trend_score),
    )


# categorical part – exact matches + Jaccard overlaps
def _categorical_similarity(a: Movie, b: Movie, repo: MovieRepo) -> float:
    exact = [
        a.release_window == b.release_window,
        rating_to_age_group(a.origin, a.rating_cert)
        == rating_to_age_group(b.origin, b.rating_cert),
        a.origin == b.origin,
    ]
    exact_score = sum(exact) / len(exact)                    # 0‥1

    genre_score = _jaccard(repo.genres(a.id),  repo.genres(b.id))
    theme_score = _jaccard(repo.themes(a.id),  repo.themes(b.id))

    return (exact_score + genre_score + theme_score) / 3.0
