from __future__ import annotations
import datetime, random, urllib.parse
from typing  import Dict, List, Tuple, Optional

from PySide6.QtCore import QObject, QThread

from movieNight.settings          import GHIBLI_SHEET_PATH, SPREADSHEET_ID
from movieNight.utils             import locate_trailer, log_debug, open_url_host_browser
from movieNight.metadata import repo
from movieNight.movie_api.scrapers import IMDbScraper
from movieNight.metadata.analytics.update_service import enrich_movie, update_scores_and_trends   
from movieNight.movie_api import sheets_xlsx
from movieNight.gui.workers import _MetaWorker, _CollectWorker, _URLWorker

# type alias for what we return to the GUI
GenerateResult = Tuple[List[str], Dict[str, str | None]]

def generate_movies(sheet_name_input: str, attendee_count: int) -> GenerateResult:
    """
    Randomly choose *(attendee_count + 1)* movies linked to the given
    spreadsheet tab **that already have a YouTube trailer**.

    Parameters
    ----------
    sheet_name_input
        Name of the Google-Sheet tab (must exist in spreadsheet_themes).
    attendee_count
        Positive integer; we return N + 1 movies.

    Returns
    -------
    chosen_titles
        List of movie titles (length = attendee_count + 1).
    trailer_map
        Dict {title → youtube_link}.
    """
    # ── validation ───────────────────────────────────────────────────
    sheet = sheet_name_input.strip()
    if attendee_count <= 0:
        raise ValueError("Enter a positive attendee count.")
    if not sheet:
        raise ValueError("Sheet name?")

    # ── candidate pool from DB ──────────────────────────────────────
    movie_ids = repo.ids_for_sheet(sheet)
    if not movie_ids:
        raise ValueError("Sheet not found.")

    # fetch (mid, title, link) once – avoids per-movie queries later
    rows = [
        (mid,
         (m := repo.by_id(mid)).title,
         m.youtube_link)
        for mid in movie_ids
    ]
    pool = [(t, link) for _id, t, link in rows if link]   # keep only with trailer

    if attendee_count + 1 > len(pool):
        raise ValueError("Not enough movies on that sheet with trailers.")

    # ── random pick ─────────────────────────────────────────────────
    chosen = random.sample(pool, attendee_count + 1)
    chosen_titles = [t for t, _ in chosen]
    trailer_map: Dict[str, str] = {t: link for t, link in chosen}

    # ── open YT playlist in host browser ────────────────────────────
    video_ids = [link.split("v=")[-1].split("&")[0] for link in trailer_map.values()]
    if video_ids:
        playlist = (
            "https://www.youtube.com/watch_videos"
            f"?video_ids={','.join(video_ids)}"
            f"&title={urllib.parse.quote_plus(f'Movie Night {datetime.date.today()}')}"
            "&feature=share"
        )
        open_url_host_browser(playlist)

    return chosen_titles, trailer_map

# ------------------------------------------------------------------
def add_remove_movie(current: list[str], pool: list[str], delta: int) -> list[str]:
    """
    +1 ⇒ add a random title from *pool* not already in list
    –1 ⇒ remove one random title (but keep ≥1)
    Returns new list.
    """
    lst = current.copy()
    if delta > 0:
        choice = random.choice([t for t in pool if t not in lst])
        lst.append(choice)
    elif len(lst) > 1:
        lst.pop(random.randrange(len(lst)))
    return lst

def update_data() -> None:
    sheets_xlsx.download_spreadsheet_as_xlsx(SPREADSHEET_ID, GHIBLI_SHEET_PATH)
    touched: set[int] = set()

    for tab in sheets_xlsx.get_non_green_tabs(SPREADSHEET_ID):
        theme_id = repo.ensure_spreadsheet_theme(tab)
        titles   = sheets_xlsx.get_movie_titles_from_sheet(GHIBLI_SHEET_PATH, tab)

        present  = repo.titles_to_ids(titles)
        new_rows = [{"title": t} for t in titles if t not in present]
        new_ids  = repo.bulk_insert_movies(new_rows)
        present.update({r["title"]: mid for r, mid in zip(new_rows, new_ids)})
        repo.link_movies_to_spreadsheet_theme(list(present.values()), theme_id)

        scraper = IMDbScraper(min_delay=1.5)   # once per tab
        for title, mid in present.items():
            # full enrichment + recalc
            enrich_movie(mid, scraper)
            update_scores_and_trends(mid)

            movie = repo.by_id(mid)
            if not movie.youtube_link:
                url, *_ = locate_trailer(title)
                if url:
                    repo.update_youtube_link(mid, url)

            touched.add(mid)

    log_debug(f"Update data complete ({len(touched)} movies refreshed).")

      
# ───────────────────────── Controller helpers exposed to UI ───────────────
def _start_worker(worker: QObject, stat_page):
    dlg = stat_page.open_progress(worker.__class__.__name__.replace("_", " "))
    thr = QThread()
    worker.moveToThread(thr)

    worker.progress.connect(dlg.set_progress)
    worker.message.connect(dlg.set_message)
    worker.finished.connect(lambda ok: dlg.accept() if ok else dlg.reject())
    worker.finished.connect(thr.quit)
    worker.finished.connect(worker.deleteLater)
    thr.finished.connect(thr.deleteLater)

    thr.started.connect(worker.run)
    thr.start()


def start_update_metadata(full: bool, stat_page):
    """Kick off the TMDb→OMDb→IMDb metadata worker."""
    stat_page.enable_meta_continue(False)        # disable until worker finishes
    _start_worker(_MetaWorker(full), stat_page)


def start_update_urls(full: bool, stat_page):
    """Kick off the trailer‐URL repair/update worker."""
    stat_page.enable_url_continue(False)
    _start_worker(_URLWorker(full), stat_page)
    
def start_collect_data(stat_page):
    "bulk collect 1,000's of movies worker"
    stat_page.enable_collect(False)
    _start_worker(_CollectWorker(), stat_page)