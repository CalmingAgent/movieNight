# update_scores_and_trends(movie_id)
from __future__ import annotations
from typing import Any, Dict, Optional

from metadata.analytics.scoring import calculate_combined_score, calculate_actor_trend_score
from utils import trend_score, locate_trailer
from metadata import (
    repo, tmdb_client, omdb_client, yt_client          # shared singletons
)
from metadata.api_clients.errors import RateLimitReached #Not defined yet


# ───────────────────────────────────────────────────────────────────────────
# 1 ▸ combined-score recomputation for ONE movie-id
# ───────────────────────────────────────────────────────────────────────────
def recalculate_combined_score(movie_id: int) -> None:
    """
    Re-calculate movies.combined_score from whatever rating rows exist.
    """
    r: Dict[str, float] = repo.current_ratings_dict(movie_id)   # {'IMDB': 78, …}
    new_score = calculate_combined_score(
        imdb        = r.get("IMDB", 0),
        rt_critic   = r.get("RT_CRITIC", 0),
        rt_audience = r.get("RT_AUDIENCE", 0),
        metacritic  = r.get("METACRITIC", 0),
    )
    repo.update_movie_field(movie_id, "combined_score", new_score)

# alias for back-compat with your old name
recalculate_new_weighted_scores = recalculate_combined_score


# ───────────────────────────────────────────────────────────────────────────
# 2 ▸ full refresh of ratings + trends for ONE movie-id
# ───────────────────────────────────────────────────────────────────────────
def update_scores_and_trends(movie_id: int) -> None:
    """
    Refresh *all* numeric metadata for a movie:

        TMDb user rating  → ratings table
        OMDb critic scores → ratings table
        Google trend      → movies.google_trend_score
        Actor trend       → movies.actor_trend_score
        Combined score    → movies.combined_score
    """
    m = repo.by_id(movie_id)
    title = m.title

    # ── TMDb user rating ---------------------------------------------------
    if (t := tmdb_client.fetch_user_rating(title)):
        repo.upsert_rating(movie_id, "TMDB", t[0] * 10, t[1])   # 0-100 scale

    # ── OMDb critic scores -------------------------------------------------
    if (om := omdb_client.get_ratings(title=title)):
        for src, val in om.items():
            if val is not None:
                repo.upsert_rating(movie_id, src.upper(), val)

    # ── Google trend (7-day avg) ------------------------------------------
    if repo.is_movie_field_missing(movie_id, "google_trend_score"):
        if (gt := trend_score(title)) is not None:
            repo.update_movie_field(movie_id, "google_trend_score", gt)

    # ── Actor trend (median popularity of billed actors) ------------------
    if repo.is_movie_field_missing(movie_id, "actor_trend_score"):
        if (ats := calculate_actor_trend_score(title)) is not None:
            repo.update_movie_field(movie_id, "actor_trend_score", ats)

    # ── Combined meta score ----------------------------------------------
    recalculate_combined_score(movie_id)


# ───────────────────────────────────────────────────────────────────────────
# 3 ▸ batch refresh for every movie missing a trend score
# ───────────────────────────────────────────────────────────────────────────
def refresh_missing_trends() -> None:
    """
    For rows where `google_trend_score` IS NULL:
        → fetch trends, actor popularity, ratings, combined score.
    """
    mids = [
        r["id"] for r in repo.movies_missing_trend()   # helper below
    ]
    for mid in mids:
        update_scores_and_trends(mid)

def enrich_movie(movie_id: int, imdb_scraper=None) -> None:
    """
    Fill *missing* metadata fields for one movie row.

    Priority order
    --------------
    1. TMDb   – full metadata + genres
    2. OMDb   – runtime, box-office, plot
    3. IMDb   – rating histogram (via scraper)
    4. YouTube / yt-dl  – trailer URL
    5. Trends  – Google & actor popularity
    6. Combined score recalculation
    """
    m        = repo.by_id(movie_id)
    title    = m.title

    # ══════════ 1. TMDb ════════════════════════════════════════════════
    try:
        meta = tmdb_client.fetch_metadata(title)
    except RateLimitReached:
        raise                          # bubble up so worker pauses
    if meta:
        mf: Dict[str, Any] = meta.get("movie_fields", {})
        for col, val in mf.items():
            if val and repo.is_movie_field_missing(movie_id, col):
                repo.update_movie_field(movie_id, col, val)

        for g in meta.get("genres", []):
            repo.link_movie_genre(movie_id, g)

    # ══════════ 2. OMDb fallback ═══════════════════════════════════════
    if repo.is_movie_field_missing(movie_id, "duration_seconds"):
        rt = omdb_client.get_runtime_seconds(title=title)
        if rt:
            repo.update_movie_field(movie_id, "duration_seconds", rt)

    if repo.is_movie_field_missing(movie_id, "box_office_actual"):
        bo = omdb_client.get_boxoffice(title=title)
        if bo:
            repo.update_movie_field(movie_id, "box_office_actual", bo)

    if repo.is_movie_field_missing(movie_id, "plot_desc"):
        plot = omdb_client.get_plot(title=title)
        if plot:
            repo.update_movie_field(movie_id, "plot_desc", plot)

    # ══════════ 3. IMDb scraper ════════════════════════════════════════
    if imdb_scraper:
        imdb_id = omdb_client.get_imdb_id(title=title)
        if imdb_id:
            data = imdb_scraper.fetch_all(imdb_id)    # throttled inside scraper
            if data and "rating" in data:
                repo.upsert_rating(movie_id, "IMDB", data["rating"] * 10)

    # ══════════ 4. Trailer URL ════════════════════════════════════════
    if repo.is_movie_field_missing(movie_id, "youtube_link"):
        url, *_ = locate_trailer(title)
        if url:
            repo.update_youtube_link(movie_id, url)

    # ══════════ 5. Trend scores ════════════════════════════════════════
    if repo.is_movie_field_missing(movie_id, "google_trend_score"):
        gt = repo.fetch_google_trend(title)           # implement in repo
        if gt is not None:
            repo.update_movie_field(movie_id, "google_trend_score", gt)

    if repo.is_movie_field_missing(movie_id, "actor_trend_score"):
        ats = calculate_actor_trend_score(title)
        if ats is not None:
            repo.update_movie_field(movie_id, "actor_trend_score", ats)

    # ══════════ 6. Combined score ══════════════════════════════════════
    rdict = repo.current_ratings_dict(movie_id)        # NEW helper → repo
    score = calculate_combined_score(
        imdb        = rdict.get("IMDB", 0),
        rt_critic   = rdict.get("RT_CRITIC", 0),
        rt_audience = rdict.get("RT_AUDIENCE", 0),
        metacritic  = rdict.get("METACRITIC", 0),
    )
    repo.update_movie_field(movie_id, "combined_score", score)