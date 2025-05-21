from __future__ import annotations
from itertools import count
import datetime, random, urllib.parse
from typing  import Dict, List, Tuple, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from metadata.api_clients import omdb_client, tmdb_client
from metadata.international_reference import COUNTRY_WINDOWS

from ..settings          import GHIBLI_SHEET_PATH, SPREADSHEET_ID
from ..utils             import locate_trailer, log_debug, open_url_host_browser
from metadata import repo
from movie_api.scrapers import IMDbScraper
from metadata.analytics.update_service import enrich_movie, update_scores_and_trends   
from movie_api import sheets_xlsx

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
        theme_id = repo._ensure_spreadsheet_theme(tab)
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

    
# persistent resume state (store last movie_id checked)
def _get_resume_point(kind: str) -> Optional[int]:
    v = repo.get_kv(kind)
    return int(v) if v else None

def _set_resume_point(kind: str, movie_id: int) -> None:
    repo.set_kv(kind, str(movie_id))


# ───────────────────────── Worker skeletons ───────────────────────────────
class _MetaWorker(QObject):
    progress  = Signal(int, int)
    message   = Signal(str)
    finished  = Signal(bool)

    def __init__(self, full: bool):
        super().__init__()
        self.full = full
        self.scraper = IMDbScraper(min_delay=1.5)

    @Slot()
    def run(self):
        repo.attach_thread()
        try:
            self._run()
            self.finished.emit(True)
        except Exception as e:
            print("meta-worker error:", e)
            self.finished.emit(False)

    # actual job
    def _run(self):
        last  = _get_resume_point("meta_resume") if not self.full else None
        ids   = repo.movie_ids_sorted(resume_after=last)
        total = len(ids)

        self.progress.emit(0, total)                          # show busy bar

        for i, mid in enumerate(ids, start=1):
            self.message.emit(repo.by_id(mid).title)
            enrich_movie(mid, self.scraper)                   # single API sweep
            _set_resume_point("meta_resume", mid)
            self.progress.emit(i, total)

        _set_resume_point("meta_resume", 0)                   # clear resume



class _URLWorker(QObject):
    progress = Signal(int, int)
    message  = Signal(str)
    finished = Signal(bool)

    def __init__(self, full: bool):
        super().__init__()
        self.full = full

    @Slot()
    def run(self):
        repo.attach_thread()
        try:
            self._run()
            self.finished.emit(True)
        except Exception as e:
            print("url-worker error:", e)
            self.finished.emit(False)

    def _run(self):
        last = _get_resume_point("url_resume") if not self.full else None
        rows = repo.movies_missing_trailer(resume_after=last)
        total = len(rows)

        for i, row in enumerate(rows, start=1):
            mid, title = row["id"], row["title"]
            self.message.emit(title)

            url, *_ = locate_trailer(title)              # one lookup per movie
            if url:
                repo.update_youtube_link(mid, url)

            _set_resume_point("url_resume", mid)
            self.progress.emit(i, total)

        _set_resume_point("url_resume", 0)               # clear when finished

class _CollectWorker(QObject):
    """
    Worker that discovers and collects all movies per country+window
    with vote_average>=5 OR no rating, then enriches + stores them.
    """
    progress = Signal(int, int)
    message  = Signal(str)
    finished = Signal(bool)

    def __init__(self):
        super().__init__()
        self.tmdb    = tmdb_client.TMDBClient()
        self.omdb    = omdb_client.OMDBClient()
        self.scraper = IMDbScraper(min_delay=1.5)

    @Slot()
    def run(self):
        # ensure thread uses its own SQLite connection
        repo.attach_thread()

        # 1) fetch all supported country codes from TMDb
        countries = [c["iso_3166_1"] for c in self.tmdb.get_countries()]

        seen_tmdb_ids: set[int] = set()
        total_processed = 0

        # tell UI we’re busy (unknown total)
        self.progress.emit(0, 0)

        for country in countries:
            page = 1
            while True:
                movies = self.tmdb.discover_movies(
                    region=country,
                    vote_average_gte=5,
                    include_null_votes=True,
                    page=page
                )
                if not movies:
                    break

                for m in movies:
                    tmdb_id = m.get("id")
                    if not tmdb_id or tmdb_id in seen_tmdb_ids:
                        continue
                    seen_tmdb_ids.add(tmdb_id)

                    title = m.get("title") or m.get("name") or "<untitled>"
                    self.message.emit(f"{country} → {title}")

                    # upsert by tmdb_id
                    mid = repo.id_by_tmdb(tmdb_id)
                    if not mid:
                        mid = repo.add_movie({
                            "title":   title,
                            "tmdb_id": tmdb_id,
                            "year":    (m.get("release_date") or "")[:4] or None,
                        })

                    # full metadata sweep
                    enrich_movie(mid, self.scraper)
                    update_scores_and_trends(mid)

                    # trailer only if missing
                    movie = repo.by_id(mid)
                    if not movie.youtube_link:
                        url, *_ = locate_trailer(title)
                        if url:
                            repo.update_youtube_link(mid, url)

                    total_processed += 1
                    self.progress.emit(total_processed, 0)

                page += 1

        self.finished.emit(True)
        
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
    stat_page.enable_meta_continue(False)        # disable until worker finishes
    _start_worker(_MetaWorker(full), stat_page)


def start_update_urls(full: bool, stat_page):
    stat_page.enable_url_continue(False)
    _start_worker(_URLWorker(full), stat_page)
    
def start_collect(self):
    self.stat_page.enable_collect(False)
    _start_worker(_CollectWorker(), self.stat_page)