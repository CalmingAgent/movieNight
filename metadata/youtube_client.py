from __future__ import annotations

import re
import pickle
from yt_dlp import YoutubeDL
from typing import Optional, Tuple

import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from ..settings import  (YOUTUBE_SEARCH_URL, YOUTUBE_API_KEY,
    CLIENT_SECRET_PATH, USER_TOKEN_PATH, YOUTUBE_SCOPES)
from ..utils    import normalize, log_debug, fuzzy_match
from service    import MovieNightDB

class YTClient:
    """
    A thin wrapper for YT API
    """
    def __init__(self, db: MovieNightDB, api_key: str | None = None):
        self.db = db
        self.api_key = api_key or YOUTUBE_API_KEY

    # ------------------------------------------------------------------
    # YouTube search helpers (public so orchestration layer can choose)
    # ------------------------------------------------------------------
    @staticmethod
    def search_youtube_api(query: str) -> Optional[Tuple[str, str]]:
        """Return *(video_url, title)* using **YouTube Data API v3**."""
        params = {
            "part": "snippet",
            "q": query,
            "key": YOUTUBE_API_KEY,
            "videoDuration": "short",
            "maxResults": 1,
            "type": "video",
        }
        try:
            resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
            items = resp.json().get("items", [])
            if items:
                vid_id = items[0]["id"]["videoId"]
                title = items[0]["snippet"]["title"]
                return f"https://www.youtube.com/watch?v={vid_id}", title
        except Exception as exc:
            log_debug(f"YouTube API search error: {exc}")
        return None
    
    @staticmethod
    def get_video_views(url_or_id: str) -> Optional[int]:
        """Return the public *viewCount* for a YouTube video or *None* on error."""
        vid = YTClient._extract_video_id(url_or_id)
        if not vid:
            log_debug("get_video_views: could not parse video ID")
            return None

        params = {"part": "statistics", "id": vid, "key": YOUTUBE_API_KEY}
        try:
            resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10)
            items = resp.json().get("items", [])
            if items:
                views = int(items[0]["statistics"].get("viewCount", 0))
                return views
        except Exception as exc:
            log_debug(f"YouTube views lookup error: {exc}")
        return None

    @staticmethod
    def search_with_yt_dlp(query: str) -> Optional[Tuple[str, str]]:
        """Raw **yt-dlp** search helper – *never called automatically.*"""
        opts = {"quiet": True, "skip_download": True, "format": "best[ext=mp4]/best"}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entries = info.get("entries") or []
                if entries:
                    vid = entries[0]
                    return vid.get("webpage_url"), vid.get("title")
        except Exception as exc:
            log_debug(f"yt-dlp search error: {exc}")
        return None

    # ------------------------------------------------------------------
    # Main convenience method (DB → API) – **no yt‑dlp fallback**
    # ------------------------------------------------------------------
    def locate_trailer(self, title: str) -> Tuple[Optional[str], str, Optional[str]]:
        """Locate a trailer URL and store it in the DB if newly found.

        Order of attempts:
        1. Exact title match in DB (`movies.youtube_link`).
        2. Fuzzy match in DB (only rows with a link).
        3. YouTube Data API lookup.

        Returns `(url, source, api_title_if_any)` where `source` ∈ {`db`,
        `db_fuzzy`, `youtube_api`, ``}.
        """
        # 1) Exact match -------------------------------------------------------
        row = self.db.cur.execute(
            "SELECT id, youtube_link FROM movies WHERE LOWER(title) = LOWER(?)",
            (title,),
        ).fetchone()
        if row and row["youtube_link"]:
            return row["youtube_link"], "db", None

        # 2) Fuzzy DB match ----------------------------------------------------
        self.db.cur.execute("SELECT id, title, youtube_link FROM movies WHERE youtube_link IS NOT NULL")
        rows = self.db.cur.fetchall()
        if rows:
            norm_map = {normalize(r["title"]): (r["youtube_link"], r["id"]) for r in rows}
            match_key = fuzzy_match(normalize(title), list(norm_map))
            if match_key:
                url, _ = norm_map[match_key]
                return url, "db_fuzzy", None

        # 3) YouTube Data API --------------------------------------------------
        result = self.search_youtube_api(f"{title} official trailer")
        if result:
            url, api_title = result
            # Persist back to DB
            if row:  # we had a row without a link
                self.db.update_movie_field(row["id"], "youtube_link", url)
            else:
                movie_id = self.db.get_movie_id_by_title(title)
                if movie_id:
                    self.db.update_movie_field(movie_id, "youtube_link", url)
                else:
                    self.db.add_movie({"title": title, "youtube_link": url})
            return url, "youtube_api", api_title

        return None, "", None

    # ------------------------------------------------------------------
    # Playlist helper (unchanged)
    # ------------------------------------------------------------------
    @staticmethod
    def _get_youtube_service():
        creds = None
        if USER_TOKEN_PATH.exists():
            creds = pickle.loads(USER_TOKEN_PATH.read_bytes())
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), YOUTUBE_SCOPES)
                creds = flow.run_local_server(port=0)
            USER_TOKEN_PATH.write_bytes(pickle.dumps(creds))
        return build("youtube", "v3", credentials=creds)

    def create_youtube_playlist(self, title: str, video_ids: list[str]) -> Optional[str]:
        try:
            svc = self._get_youtube_service()
            pl = (
                svc.playlists()
                .insert(
                    part="snippet,status",
                    body={
                        "snippet": {"title": title, "description": "Auto-generated by Movie Night"},
                        "status": {"privacyStatus": "unlisted"},
                    },
                )
                .execute()
            )
            pid = pl["id"]
            for vid in video_ids:
                svc.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": pid,
                            "resourceId": {"kind": "youtube#video", "videoId": vid},
                        }
                    },
                ).execute()
            return f"https://www.youtube.com/playlist?list={pid}"
        except Exception as exc:
            log_debug(f"YouTube playlist error: {exc}")
        return None
    
    @staticmethod
    def get_video_duration_sec(video_url: str) -> int | None:
        """Return length in seconds, or None on failure (no Google API key needed)."""
        ydl_opts = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
                return info.get("duration")
            except Exception as exc:
                print("yt-dlp error:", exc)
                return None
        
