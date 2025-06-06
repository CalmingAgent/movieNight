from PySide6.QtCore import QObject, Signal, Slot

from movieNight.metadata.api_clients import omdb_client, tmdb_client
from movieNight.movie_api.scrapers import IMDbScraper
from movieNight.utils import locate_trailer, log_debug
from movieNight.metadata.core.repo import MovieRepo as repo
from movieNight.metadata.analytics.update_service import enrich_movie, update_scores_and_trends

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
            log_debug(f"meta-worker error: {e}")
            self.finished.emit(False)

    # actual job
    def _run(self):
        # load last resume point (None == full run)
        last_kv = repo.get_kv("meta_resume")
        last    = int(last_kv) if last_kv and not self.full else None
        ids   = repo.movie_ids_sorted(resume_after=last)
        total = len(ids)

        self.progress.emit(0, total)                          # show busy bar

        for i, mid in enumerate(ids, start=1):
            self.message.emit(repo.by_id(mid).title)
            enrich_movie(mid, self.scraper)                   # single API sweep
            repo.set_kv("meta_resume", str(mid))
            self.progress.emit(i, total)

        repo.set_kv("meta_resume", "0")                   # clear resume



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
            log_debug(f"url-worker error: {e}")
            self.finished.emit(False)

    def _run(self):
        # load last resume point (None == full run)
        last_kv = repo.get_kv("url_resume")
        last    = int(last_kv) if last_kv and not self.full else None
        rows = repo.movies_missing_trailer(resume_after=last)
        total = len(rows)

        for i, row in enumerate(rows, start=1):
            mid, title = row["id"], row["title"]
            self.message.emit(title)

            url, *_ = locate_trailer(title)              # one lookup per movie
            if url:
                repo.update_youtube_link(mid, url)

            repo.set_kv("url_resume", str(mid))
            self.progress.emit(i, total)

        repo.set_kv("url_resume", "0")               # clear when finished

class _CollectWorker(QObject):
    """
    Worker that discovers and collects all movies per country
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