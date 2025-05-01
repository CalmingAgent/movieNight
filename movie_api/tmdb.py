import sys
import requests

from ..settings import TMDB_API_KEY
from ..utils    import normalize, log_debug

def tmdb_find_trailer(movie_title: str) -> str | None:
    """
    Query TMDb for an exact match, then fetch its trailer link.
    Returns YouTube URL or None.
    """
    norm_query = normalize(movie_title)
    results: list[dict] = []

    for page in (1, 2):
        resp = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"api_key": TMDB_API_KEY, "query": movie_title, "page": page},
            timeout=10
        )
        if resp.status_code == 429:
            log_debug("TMDb rate limit reached.")
            sys.exit(1)
        data = resp.json().get("results", [])
        if not data:
            break
        results.extend(data)
        if page >= resp.json().get("total_pages", 1):
            break

    # filter exact matches
    matches = [m for m in results if normalize(m.get("title", "")) == norm_query]
    if len(matches) != 1:
        return None

    movie_id = matches[0]["id"]
    log_debug(f"TMDb matched ID={movie_id} for '{movie_title}'")

    # fetch /videos
    vids = requests.get(
        f"https://api.themoviedb.org/3/movie/{movie_id}/videos",
        params={"api_key": TMDB_API_KEY},
        timeout=10
    ).json().get("results", [])

    for vid in vids:
        if vid.get("site") == "YouTube" and vid.get("type") == "Trailer":
            key = vid.get("key")
            return f"https://www.youtube.com/watch?v={key}"
    return None
