from __future__ import annotations

import re
import pickle
from yt_dlp import YoutubeDL
from typing import Optional, Tuple

import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from ...settings import  (YOUTUBE_SEARCH_URL, YOUTUBE_API_KEY,
    CLIENT_SECRET_PATH, USER_TOKEN_PATH, YOUTUBE_SCOPES)
from ...utils    import normalize, log_debug, fuzzy_match
from metadata.movie_night_db    import MovieNightDB
from youtube_client import YTClient

client = YTClient()

class YTClient:
    """
    A thin wrapper for YT API
    """
    def __init__(self, db: MovieNightDB, api_key: str | None = None):
        self.db = db
        self.api_key = api_key or YOUTUBE_API_KEY
        
    def search_youtube_api(self, query: str) -> Optional[tuple[str, str]]:
        params = {
            "part": "snippet",
            "q": query,
            "key": self.api_key,          # use instance key
            "videoDuration": "short",
            "maxResults": 1,
            "type": "video",
        }
        try:
            r = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
            item = r.json().get("items", [None])[0]
            if item:
                vid  = item["id"]["videoId"]
                title = item["snippet"]["title"]
                return f"https://www.youtube.com/watch?v={vid}", title
        except Exception as exc:
            log_debug(f"YouTube API search error: {exc}")
        return None

    @staticmethod
    def _extract_video_id(url_or_id: str) -> str | None:
        """Return the 11‑char YouTube video ID or *None* if it can’t be parsed."""
        # Already an ID
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
            return url_or_id

        # Full or shortened URLs
        patterns = [
            r"(?:v=|\/videos\/|embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})",
        ]
        for pat in patterns:
            m = re.search(pat, url_or_id)
            if m:
                return m.group(1)
        return None 

    def get_video_views(self, url_or_id: str) -> Optional[int]:
        """Return the public *viewCount* for a YouTube video or *None* on error."""
        vid = YTClient._extract_video_id(url_or_id)
        if not vid:
            log_debug("get_video_views: could not parse video ID")
            return None

        params = {"part": "statistics", "id": vid, "key": self.api_key}
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
    # Main convenience method (DB → API)
    # ------------------------------------------------------------------
    def lookup_trailer_in_db(self, title: str) -> tuple[Optional[str], str]:
        row = self.db.cur.execute(
            "SELECT youtube_link FROM movies WHERE LOWER(title)=LOWER(?)",
            (title,)
        ).fetchone()
        if row and row["youtube_link"]:
            return row["youtube_link"], "db"

        self.db.cur.execute(
            "SELECT title, youtube_link FROM movies WHERE youtube_link IS NOT NULL"
        )
        rows = self.db.cur.fetchall()
        if rows:
            norm_map = {normalize(r["title"]): r["youtube_link"] for r in rows}
            key = fuzzy_match(normalize(title), list(norm_map))
            if key:
                return norm_map[key], "db_fuzzy"
        return None, ""
    
    def search_trailer_youtube(self, title: str) -> tuple[Optional[str], Optional[str]]:
        return self.search_youtube_api(f"{title} official trailer")
    def set_movie_trailer(self, movie_id: int, url: str) -> None:
        self.db.update_movie_field(movie_id, "youtube_link", url)


    # ------------------------------------------------------------------
    # Playlist helper
    # ------------------------------------------------------------------
    
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
    @staticmethod
    def get_video_duration_sec(video_url: str) -> int | None:
        """Return length in seconds, or None on failure (no Google API key needed)."""
        ydl_opts = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
                return info.get("duration")
            except Exception as exc:
                log_debug(f"yt-dlp duration error: {exc}")
                return None
        
