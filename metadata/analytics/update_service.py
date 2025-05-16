# update_scores_and_trends(movie_id)

from metadata.analytics.scoring import calculate_meta_combined_score
from utils import trend_score
from metadata.api_clients import tmdb_client as tmdb, omdb_client as omdb


def recalculate_new_weighted_scores(title) -> None:
    db.get_rating(title)
    calculate_meta_combined_score(
        imdb        = r.get("imdb", 0),
        rt_critic   = r.get("rt_critic", 0),
        rt_audience = r.get("rt_audience", 0),
        metacritic  = r.get("metacritic", 0),
    )
    db.update_movie_field(id, "combined_score", combined_score)

def update_scores_and_trends(title) -> None:
    """
    1. Pull fresh TMDb user score, OMDb critic scores, Google trend,
        actor popularity.
    2. Upsert rating rows.
    3. Recompute combined_score via calculate_meta_combined_score().
    """
    # --- TMDb user -------------------------------------------------
    t = tmdb.fetch_user_rating(title)
    if t:
        db.upsert_rating(id, "TMDB", t[0]*10, t[1])  # scale 0-100

    # --- OMDb critic ----------------------------------------------
    om = omdb.get_ratings(title=title)
    if om:
        for src, val in om.items():
            if val is not None:
                db.upsert_rating(id, src, val)

    # --- Google trend (7-day avg) ---------------------------------
    gt = trend_score(title)
    if gt is not None:
        db.update_movie_field(id, "google_trend_score", gt)
        google_trend_score = gt

    # --- Actor trend (avg top-3 popularity) -----------------------
    pops = tmdb.top_actor_popularity(title, top_n=3)
    if pops:
        avg = round(sum(pops)/len(pops), 2)
        db.update_movie_field(id, "actor_trend_score", avg)
        actor_trend_score = avg

    # --- final combined score ------------------------------------
    recalculate_new_weighted_scores()

# ------------------------------------------------------------------
def new_movies_trend_calc() -> None:
    """
    For movies with NULL google_trend_score → fetch trend, actor popularity,
    ratings, and compute combined score.
    """
    mids = [r["id"] for r in db.cur.execute(
        "SELECT id FROM movies WHERE google_trend_score IS NULL").fetchall()]
    for mid in mids:
        Movie.from_id(mid).update_scores_and_trends()
