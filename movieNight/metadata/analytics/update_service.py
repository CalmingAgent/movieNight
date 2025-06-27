# update_scores_and_trends(movie_id)
from __future__ import annotations
from typing import Any, Dict, Optional

from movieNight.metadata.analytics.scoring import calculate_combined_score, calculate_actor_trend_score
from movieNight.utils import locate_trailer
from movieNight.metadata import (
    repo, tmdb_client, omdb_client, trend_client, trend_client)
from movieNight.metadata.api_clients.errors import rate_limit_reached #Not defined yet
from movieNight.metadata.analytics.fairness import (
    Baselines, gtrend_fair, actor_trend_fair, combined_score_fair)
from movieNight.metadata.identity.fingerprint import same_movie, _NORMALIZERS

# ─────────────────────────  0 ▸ baselines  ──────────────────────────
# Build once at module-import time
BASE = Baselines(
    pop_by_country    = repo.population_share_by_country(),
    movies_by_country = repo.catalogue_share_by_country(),
)
INTERNET_PEN = repo.internet_penetration_by_country()   # {ISO: 0‥1}
# ───────────────────────────────────────────────────────────────────────────
# 1 ▸ combined-score recomputation for ONE movie-id
# ───────────────────────────────────────────────────────────────────────────
# ───────────────────────── 1 ▸ combined score  ──────────────────────
def recalc_combined_fair(movie_id: int) -> None:
    movie = repo.by_id(movie_id)
    r = repo.current_ratings_dict(movie_id)   # {'IMDB': (78,1234), …}

    # build {src: (score, n)} even if you only have ONE column / src
    ratings = {
        "IMDB"        : (r.get("IMDB", 0),      r.get("IMDB_N", 0)),
        "RTCritic"    : (r.get("RT_CRITIC", 0), r.get("RT_CRITIC_N", 0)),
        "RTAudience"  : (r.get("RT_AUDIENCE",0),r.get("RT_AUDIENCE_N",0)),
        "MetacriticCrit": (r.get("METACRITIC",0),r.get("METACRITIC_N",0)),
    }
    new_score = combined_score_fair(movie, ratings, BASE)
    repo.update_movie_field(movie_id, "combined_score", new_score)

# keep alias for old name
recalculate_combined_score = recalc_combined_fair


# ───────────────────────────────────────────────────────────────────────────
# 2 ▸ full refresh of ratings + trends for ONE movie-id
# ───────────────────────────────────────────────────────────────────────────
def update_scores_and_trends(movie_id: int) -> None:
    """Refresh ratings + FAIR trend / combined score for one movie."""
    m      = repo.by_id(movie_id)
    title  = m.title

    # 2.1  ⎯ ratings─────────────────────────────────────
    if (t := tmdb_client.fetch_user_rating(title)):
        repo.upsert_rating(movie_id, "TMDB", t[0] * 10, t[1])

    if (om := omdb_client.get_ratings(title=title)):
        for src, val in om.items():
            if val is not None:
                repo.upsert_rating(movie_id, src.upper(), val)

    # 2.2  ⎯ Google Trend (fair) ─────────────────────────────────────
    if repo.is_movie_field_missing(movie_id, "google_trend_score"):
        if (gt := trend_client.fetch_7day_average(title)) is not None:
            fair_gt = gtrend_fair(gt, m.origin, BASE, INTERNET_PEN)
            repo.update_movie_field(movie_id, "google_trend_score", fair_gt)

    # 2.3  ⎯ Actor Trend (fair) ──────────────────────────────────────
    if repo.is_movie_field_missing(movie_id, "actor_trend_score"):
        if (ats_raw := calculate_actor_trend_score(title)) is not None:
            fair_ats = actor_trend_fair(
                imdb_pop = ats_raw,          # assuming that fn returns IMDb pop
                gtrend   = m.google_trend_score or 0,
                movie    = m,
                base     = BASE,
            )
            repo.update_movie_field(movie_id, "actor_trend_score", fair_ats)

    # 2.4  ⎯ Combined score ─────────────────────────────────────────
    recalc_combined_fair(movie_id)

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
        
def safe_omdb_payload(
    *,
    tmdb_blob: Dict[str, Any],
    title: str,
    imdb_id: str | None,
    runtime_sec: int | None,
    release_date: str | None
) -> Optional[Dict[str, Any]]:
    """
    1) Try OMDb by IMDb ID.
    2) Fall back to title search + heuristic pick.
    3) Confirm with same_movie().
    Return raw OMDb JSON ONLY if it’s a confident match.
    """
    # ––– Step 1: ID lookup –––
    if imdb_id:
        if (blob := omdb_client.get_by_id(imdb_id)):
            return blob                     # exact hit

    # ––– Step 2: title search –––
    blob = omdb_client.smart_fetch(
        title        = title,
        imdb_id      = None,
        runtime      = runtime_sec // 60 if runtime_sec else None,
        release_date = release_date,
    )
    if not blob:
        return None

    # ––– Step 3: compare fingerprints –––
    fp_tm  = _NORMALIZERS["TMDB"](tmdb_blob)
    fp_om  = _NORMALIZERS["OMDB"](blob)
    is_same, score = same_movie(fp_tm, fp_om)
    return blob if is_same else None

def omdb_to_columns(blob: Dict[str, Any]) -> Dict[str, Any]:
    """Map OMDb JSON → your movies table columns. No business rules here."""
    col = {}
    if rt := omdb_client.extract_runtime(blob):
        col["duration_seconds"] = rt
    if bo := omdb_client.extract_box_office(blob):
        col["box_office_actual"] = bo
    if plot := blob.get("Plot"):
        col["plot_desc"] = plot
    return col

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
            
    # ── write tmdb_id and franchise first ─
    if "tmdb_id" in mf and repo.is_movie_field_missing(movie_id, "tmdb_id"):
        repo.update_movie_tmdb_id(movie_id, mf["tmdb_id"])

    if "franchise" in mf and mf.get("franchise") and repo.is_movie_field_missing(movie_id, "franchise"):
        repo.update_movie_franchise(movie_id, mf["franchise"])

    # ══════════ 2. OMDb fallback ═══════════════════════════════════════
    if repo.is_movie_field_missing(movie_id, "duration_seconds"):
        rt = omdb_client.get_runtime_seconds(title=title)
        if rt:
            repo.update_movie_field(movie_id, "duration_seconds", rt)

    if repo.is_movie_field_missing(movie_id, "box_office_actual"):
        bo = omdb_client.get_box_office(title=title)
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
        gt = trend_client.fetch_7day_average(title)
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