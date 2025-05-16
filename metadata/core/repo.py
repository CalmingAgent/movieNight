"""metadata.core.repo
Domain-level repository for Movie-night data.

All SQL lives here; other layers import this module instead of touching
`sqlite3` directly.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set

from metadata.movie_night_db import execute, executemany, commit, connection
from metadata.core.models import Movie

_ALLOWED_MOVIE_COLS: Set[str] = {
    "title", "plot_desc", "year", "release_window", "rating_cert", "duration_seconds",
    "youtube_link", "box_office_expected", "box_office_actual",
    "google_trend_score", "actor_trend_score", "combined_score",
    "franchise", "origin",
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
        gid = execute("SELECT id FROM genres WHERE name=?", (name,)).fetchone()
        if gid:
            return gid["id"]
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
    def link_movie_to_sheet_theme(movie_id: int, sheet: str) -> None:
        """Connect *movie_id* with a Google-sheet tab in link table."""
        tid = MovieRepo._ensure_spreadsheet_theme(sheet)
        execute(
            "INSERT OR IGNORE INTO movie_spreadsheet_themes "
            "(movie_id, spreadsheet_theme_id) VALUES (?,?)",
            (movie_id, tid),
        )
        commit()

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
