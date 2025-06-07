#!/usr/bin/env python3
"""
migrate_trailers.py
~~~~~~~~~~~~~~~~~~~
Copy *all* youtube_link values from the first-generation Movie-Night
database into the current database.

 • If the title already exists in the new DB   → overwrite its youtube_link
 • If the title is missing                     → insert a new row
   (only `title` + `youtube_link`; other fields stay NULL)
"""

from __future__ import annotations
import sqlite3, pathlib, sys

# ------------------------------------------------------------------ paths
OLD_DB = pathlib.Path("/mnt/d/Code/Movie_Night/movieNight/1st_movie_night.sqlite")
NEW_DB = pathlib.Path("/mnt/d/Code/Movie_Night/movieNight/movie_night.sqlite")


# ------------------------------------------------------------------ helpers
def connect(db_path: pathlib.Path) -> sqlite3.Connection:
    """Return a sqlite3.Connection with Row factory."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def migrate(old_db: pathlib.Path, new_db: pathlib.Path) -> None:
    src = connect(old_db)
    dst = connect(new_db)
    c_dst = dst.cursor()

    rows = src.execute(
        "SELECT title, youtube_link FROM movies "
        "WHERE youtube_link IS NOT NULL AND TRIM(youtube_link) != ''"
    ).fetchall()

    inserted = updated = 0

    for r in rows:
        title, link = r["title"], r["youtube_link"]

        existing = c_dst.execute("SELECT id FROM movies WHERE title=?", (title,)).fetchone()
        if existing:
            c_dst.execute(
                "UPDATE movies SET youtube_link=? WHERE id=?", (link, existing["id"])
            )
            updated += 1
        else:
            c_dst.execute(
                "INSERT INTO movies (title, youtube_link) VALUES (?,?)", (title, link)
            )
            inserted += 1

    dst.commit()
    src.close()
    dst.close()

    print(
        f"✔ Migration finished — {updated} links updated, "
        f"{inserted} new rows inserted."
    )


# ------------------------------------------------------------------ cli entry
if __name__ == "__main__":
    if not OLD_DB.exists():
        sys.exit(f"Old DB not found: {OLD_DB}")
    if not NEW_DB.exists():
        sys.exit(f"New DB not found: {NEW_DB}")

    migrate(OLD_DB, NEW_DB)
