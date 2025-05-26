# json_cache.py

from pathlib import Path

from .json_functions import load_json_dict, write_json_dict
from ..utils           import log_debug, normalize, print_progress_bar_cmdln
from ..movie_api.tmdb            import tmdb_find_trailer
from ..movie_api.youtube         import search_youtube_api

def find_trailer_fallback_cache(movie_title: str, master_cache: dict[str,str]) -> str | None:
    """
    1) Try master_cache (dict of normalized_title → url),
    2) Fallback to TMDB, then YouTube.
    """
    norm = normalize(movie_title)
    if url := master_cache.get(norm):
        log_debug(f"Cache hit for '{movie_title}'")
        return url

    if tmdb_url := tmdb_find_trailer(movie_title):
        master_cache[norm] = tmdb_url
        return tmdb_url

    if yt := search_youtube_api(f"{movie_title} official hd trailer"):
        master_cache[norm] = yt[0]
        return yt[0]

    log_debug(f"No trailer found for '{movie_title}'")
    return None

def fill_missing_urls_in_json_with_cache(
    json_file: Path,
    movies: list[str],
    master_cache: dict[str,str]
) -> None:
    """
    Ensure every movie in `movies` has a URL in json_file; fill from cache or APIs.
    """
    data = load_json_dict(json_file)

    missing = [m for m in movies if not data.get(m)]
    total   = len(missing)
    if total == 0:
        log_debug(f"No missing URLs in {json_file.name}")
        return

    for i, title in enumerate(missing, start=1):
        print_progress_bar_cmdln(i-1, total, prefix="Searching", suffix="done")
        if url := find_trailer_fallback_cache(title, master_cache):
            data[title] = url
            log_debug(f"Filled '{title}' → {url}")
    print_progress_bar(total, total, prefix="Searching", suffix="done")

    write_json_dict(json_file, data)
    log_debug(f"Updated {json_file.name}")
