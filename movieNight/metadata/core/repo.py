"""metadata.core.repo
Domain-level repository for Movie-night data.

All SQL lives here; other layers import this module instead of touching
`sqlite3` directly.
"""

from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Optional, Set
from datetime import date

from movieNight.metadata.movie_night_db import execute, executemany, commit, connection
from movieNight.metadata.core.models import Movie

_ALLOWED_MOVIE_COLS: Set[str] = {
    "title", "plot_desc", "year", "release_window", "rating_cert", "duration_seconds",
    "youtube_link", "box_office_expected", "box_office_actual",
    "google_trend_score", "actor_trend_score", "combined_score",
    "franchise", "origin", "tmdb_id"
}


class MovieRepo:
    """High-level CRUD and query helpers for Movie objects."""

    # ───────────────────────────── writers ──────────────────────────
    @staticmethod
    def add_user(name: str) -> int:
        """Insert a new *user* row (no duplicate names) and return its id.

        If the name already exists the statement is ignored and the existing
        row-id is returned.
        """
        execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))
        row = execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()
        return row["id"]

    @staticmethod
    def add_movie(data: Dict[str, Any]) -> int:
        """Insert one row into **movies** and return the new row-id.

        Parameters
        ----------
        data
            Dict whose keys are a subset of `_ALLOWED_MOVIE_COLS`.

        Raises
        ------
        ValueError
            If *data* contains unknown column names.
        sqlite3.IntegrityError
            For UNIQUE / FK violations (re-raised after rollback).
        """
        unknown = set(data) - _ALLOWED_MOVIE_COLS
        if unknown:
            raise ValueError(f"Unknown movie columns: {', '.join(unknown)}")

        cols = ", ".join(data)
        ph   = ", ".join("?" for _ in data)
        sql  = f"INSERT INTO movies ({cols}) VALUES ({ph})"

        cur = execute(sql, tuple(data.values()))
        new_id = cur.lastrowid 
        commit()
        return new_id
    @staticmethod
    def add_rating(user_id: int, movie_id: int, rating: float) -> None:
        """Insert or update a *user → movie* rating (0-100 scale)."""
        execute(
            "INSERT OR REPLACE INTO user_ratings (user_id, movie_id, rating)"
            " VALUES (?,?,?)",
            (user_id, movie_id, rating),
        )
        commit()

    @staticmethod
    def update_movie_field(movie_id: int, field: str, value: Any) -> None:
        """Update a single scalar column on **movies**.

        Only columns in `_ALLOWED_MOVIE_COLS` are permitted.
        """
        if field not in _ALLOWED_MOVIE_COLS:
            raise ValueError(f"Illegal movie field: {field}")
        execute(f"UPDATE movies SET {field}=? WHERE id=?", (value, movie_id))
        commit()

    # ───────────────────────────── look-ups ──────────────────────────
    @staticmethod
    def by_id(movie_id: int) -> Optional[Movie]:
        """Return a `Movie` dataclass for *movie_id* or **None** if not found."""
        row = execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
        return Movie(**dict(row)) if row else None

    @staticmethod
    def ids_for_sheet(sheet: str) -> List[int]:
        """Movie-ids linked to a Google-sheet *tab* (via `spreadsheet_themes`)."""
        sheet = sheet.strip()
        tid_row = execute(
            "SELECT id FROM spreadsheet_themes WHERE name=?", (sheet,)
        ).fetchone()
        if not tid_row:
            return []
        rows = execute(
            "SELECT movie_id FROM movie_spreadsheet_themes "
            "WHERE spreadsheet_theme_id=?", (tid_row["id"],)
        ).fetchall()
        return [r["movie_id"] for r in rows]

    @staticmethod
    def id_by_title(title: str) -> Optional[int]:
        """Find movie id by main or alias title."""
        row = execute("SELECT id FROM movies WHERE title=?", (title,)).fetchone()
        if row:
            return row["id"]
        row = execute(
            "SELECT movie_id FROM movie_aliases WHERE alt_title=?", (title,)
        ).fetchone()
        return row["movie_id"] if row else None


    @staticmethod
    def genres(movie_id: int) -> Set[str]:
        """Return the set of genre names linked to *movie_id*."""
        rows = execute(
            "SELECT g.name FROM genres g JOIN movie_genres mg ON mg.genre_id=g.id "
            "WHERE mg.movie_id=?", (movie_id,)
        ).fetchall()
        return {r["name"] for r in rows}

    @staticmethod
    def themes(movie_id: int) -> Set[str]:
        """Return the set of theme names linked to *movie_id*."""
        rows = execute(
            "SELECT t.name FROM themes t JOIN movie_themes mt ON mt.theme_id=t.id "
            "WHERE mt.movie_id=?", (movie_id,)
        ).fetchall()
        return {r["name"] for r in rows}
    @staticmethod
    def get_youtube_link(movie_id: int) -> str | None:
        row = execute(
            "SELECT youtube_link FROM movies WHERE id=?", (movie_id,)
        ).fetchone()
        return row["youtube_link"] if row else None

    @staticmethod
    def update_youtube_link(movie_id: int, url: str | None) -> None:
        execute("UPDATE movies SET youtube_link=? WHERE id=?", (url, movie_id))
        commit()

    # ─────────────────────── genre / theme helpers ────────────────────
    @staticmethod
    def _ensure_genre(name: str) -> int:
        """Return genre-id, inserting a new row if needed."""
        row = execute("SELECT id FROM genres WHERE name=?", (name,)).fetchone()
        if row:
         return row["id"]
        cur = execute("INSERT INTO genres(name) VALUES(?)", (name,))
        commit()
        return cur.lastrowid

    @staticmethod
    def link_movie_genre(movie_id: int, genre_name: str) -> None:
        """Insert *(movie_id, genre_id)* into **movie_genres** if missing."""
        gid = MovieRepo._ensure_genre(genre_name)
        execute(
            "INSERT OR IGNORE INTO movie_genres VALUES (?,?)",
            (movie_id, gid),
        )
        commit()

    # ─────────────────── spreadsheet-theme helpers ────────────────────
    @staticmethod
    def _ensure_spreadsheet_theme(name: str) -> int:
        """Return theme-id for Google sheet tab, inserting if absent."""
        tid = execute(
            "SELECT id FROM spreadsheet_themes WHERE name=?", (name,)
        ).fetchone()
        if tid:
            return tid["id"]
        cur = execute("INSERT INTO spreadsheet_themes(name) VALUES(?)", (name,))
        commit()
        return cur.lastrowid
    
    @staticmethod
    def ensure_spreadsheet_theme(name: str) -> int:
        """
        Public alias for `_ensure_spreadsheet_theme`.
        Returns the spreadsheet_theme id, creating it if needed.
        """
        return MovieRepo._ensure_spreadsheet_theme(name)

    @staticmethod
    def link_movie_to_sheet_theme(movie_id: int, sheet: str) -> None:
        """Connect *movie_id* with a Google-sheet tab in link table."""
        tid = MovieRepo._ensure_spreadsheet_theme(sheet)
        execute(
            "INSERT OR IGNORE INTO movie_spreadsheet_themes "
            "(movie_id, spreadsheet_theme_id) VALUES (?,?)",
            (movie_id, tid),
        )
        commit()
        
    @staticmethod
    def list_spreadsheet_themes() -> list[str]:
        """
        Return a sorted list of all sheet‐tab names in the spreadsheet_themes table.
        """
        rows = execute("SELECT name FROM spreadsheet_themes ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    # ───────────────────────── aggregates / views ─────────────────────
    @staticmethod
    def update_user_attendance_counts() -> None:
        """Recompute `users.attendance_count` from the `user_ratings` table."""
        execute(
            "UPDATE users SET attendance_count = ("
            "  SELECT COUNT(*) FROM user_ratings ur WHERE ur.user_id = users.id"
            ")"
        )
        commit()

    @staticmethod
    def average_rating(movie_id: int) -> Optional[float]:
        """Return the mean user rating for *movie_id* or **None** if none."""
        row = execute(
            "SELECT AVG(rating) AS avg FROM user_ratings WHERE movie_id=?",
            (movie_id,)
        ).fetchone()
        return row["avg"]
    
    @staticmethod
    def get_google_trend_score(movie_id: int) -> Optional[int]:
        """Return the stored 7-day Google trend score (0-100) for *movie_id*."""
        row = execute(
            "SELECT google_trend_score FROM movies WHERE id=?",
            (movie_id,)
        ).fetchone()
        return row["google_trend_score"] if row else None

    @staticmethod
    def get_actor_trend_score(movie_id: int) -> Optional[float]:
        """Average top-actor popularity that was last stored for this film."""
        row = execute(
            "SELECT actor_trend_score FROM movies WHERE id=?", (movie_id,)
        ).fetchone()
        return row["actor_trend_score"] if row else None

    @staticmethod
    def get_combined_score(movie_id: int) -> Optional[float]:
        """Return the meta-critic combined score (0-100) for *movie_id*."""
        row = execute(
            "SELECT combined_score FROM movies WHERE id=?", (movie_id,)
        ).fetchone()
        return row["combined_score"] if row else None
    
    @staticmethod
    def is_movie_field_missing(movie_id: int, field: str) -> bool:
        """
        Return True if *field* is NULL / empty for the given movie.

        Raises
        ------
        ValueError  if *field* is not a valid column.
        """
        if field not in _ALLOWED_MOVIE_COLS and field != "tmdb_id":
            raise ValueError(f"Unknown movie column: {field}")

        row = execute(
            f"SELECT {field} FROM movies WHERE id=?",
            (movie_id,)
        ).fetchone()

        if not row:
            return True                         # no such movie ⇒ “missing”

        val = row[field]
        return val is None or (isinstance(val, str) and val.strip() == "")
        # ───────────────────────────── bulk helpers ──────────────────────────
    @staticmethod
    def bulk_insert_movies(rows: List[Dict[str, Any]]) -> List[int]:
        """Insert many movie dicts at once. Returns list of new row-ids.

        Assumes every dict key ∈ `_ALLOWED_MOVIE_COLS`.
        """
        if not rows:
            return []

        cols = rows[0].keys()
        ph   = ", ".join("?" * len(cols))
        sql  = f"INSERT INTO movies ({', '.join(cols)}) VALUES ({ph})"

        params = [tuple(r[c] for c in cols) for r in rows]
        executemany(sql, params)
        commit()

        first_id = execute("SELECT last_insert_rowid()").fetchone()[0] - len(rows) + 1
        return list(range(first_id, first_id + len(rows)))

    @staticmethod
    def titles_to_ids(titles: List[str]) -> Dict[str, int]:
        """Return {title: id} for every title that already exists."""
        if not titles:
            return {}
        q = ",".join("?" * len(titles))
        rows = execute(f"SELECT id, title FROM movies WHERE title IN ({q})", tuple(titles)).fetchall()
        return {r["title"]: r["id"] for r in rows}
    
    # ───────────────────────── kv  (resume points etc.) ───────────────────
    @staticmethod
    def get_kv(key: str) -> str | None:
        row = execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    @staticmethod
    def set_kv(key: str, value: str) -> None:
        execute(
            "INSERT OR REPLACE INTO kv_store(key, value) VALUES(?,?)",
            (key, value)
        )
        commit()

    # ───────────────────────── bulk movie id helpers ─────────────────────
    @staticmethod
    def movie_ids_sorted(resume_after: int | None = None) -> list[int]:
        if resume_after:
            rows = execute(
                "SELECT id FROM movies WHERE id>? ORDER BY id",
                (resume_after,)
            ).fetchall()
        else:
            rows = execute("SELECT id FROM movies ORDER BY id").fetchall()
        return [r["id"] for r in rows]

    @staticmethod
    def movies_missing_trailer(resume_after: int | None = None):
        sql = (
            "SELECT id, title FROM movies "
            "WHERE (youtube_link IS NULL OR youtube_link='') "
        )
        params = ()
        if resume_after:
            sql += "AND id>? "
            params = (resume_after,)
        rows = execute(sql + "ORDER BY id", params).fetchall()
        return rows         # list[sqlite3.Row]
    
    # ratings helper for enrich_movie
    @staticmethod
    def current_ratings_dict(movie_id: int) -> Dict[str, float]:
        rows = execute(
            "SELECT source, score FROM ratings WHERE movie_id=?", (movie_id,)
        ).fetchall()
        return {r["source"]: r["score"] for r in rows}
    @staticmethod
    def movies_missing_trend() -> list[sqlite3.Row]:
        return execute("SELECT id FROM movies WHERE google_trend_score IS NULL").fetchall()
   
   #Google trend helps
    @staticmethod 
    def trend_cache_get(term: str) -> int | None:
        """
        Return a cached 7-day average Google-Trend score for *term*
        or None if not in the cache for today.
        """
        row = execute(
            "SELECT value FROM trend_cache WHERE term=? AND as_of=?",
            (term, date.today())
        ).fetchone()
        return int(row["value"]) if row else None

    @staticmethod
    def trend_cache_set(term: str, score: int) -> None:
        """
        Store today's trend *score* (0-100) for *term*.
        """
        execute(
            "INSERT OR REPLACE INTO trend_cache(term, as_of, value) VALUES (?,?,?)",
            (term, date.today(), str(score))
        )
        commit()
        
    @staticmethod
    def link_movies_to_spreadsheet_theme(movie_ids: list[int], theme_id: int) -> None:
        """
        Insert (movie_id, theme_id) rows into movie_spreadsheet_themes, ignoring duplicates.
        """
        if not movie_ids:
            return
        params = [(mid, theme_id) for mid in movie_ids]
        executemany(
            "INSERT OR IGNORE INTO movie_spreadsheet_themes "
            "(movie_id, spreadsheet_theme_id) VALUES (?,?)",
            params,
        )
        commit()
    
    
    @staticmethod    
    def total_movie_count() -> int:
        return execute("SELECT COUNT(*) AS n FROM movies").fetchone()["n"]
    @staticmethod
    def count_movies_without_trailer() -> int:
        return execute(
            "SELECT COUNT(*) AS n FROM movies WHERE youtube_link IS NULL OR youtube_link=''"
        ).fetchone()["n"]
        
    @staticmethod
    def id_by_tmdb(tmdb_id: int) -> int | None:
        """Return local movie_id for a given TMDb external id, if any."""
        row = execute("SELECT id FROM movies WHERE tmdb_id=?", (tmdb_id,)).fetchone()
        return row["id"] if row else None
    
    @staticmethod
    def list_origins() -> list[str]:
        rows = execute("SELECT DISTINCT origin FROM movies WHERE origin IS NOT NULL").fetchall()
        return [r["origin"] for r in rows]

    @staticmethod
    def list_genres() -> list[str]:
        rows = execute("SELECT name FROM genres ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    @staticmethod
    def list_themes() -> list[str]:
        rows = execute("SELECT name FROM themes ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    
repo = MovieRepo()