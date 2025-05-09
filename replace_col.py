#!/usr/bin/env python3
"""
rename_mpaa_column.py

Usage
=====
    python rename_mpaa_column.py path/to/movie_night.db

What it does
============
1. Opens the SQLite file.
2. Tries:    ALTER TABLE movies RENAME COLUMN mpaa TO rating_cert;
3. If that fails (older SQLite), it:
       • creates movies_new with the new column name
       • copies all rows
       • drops the old table
       • renames movies_new → movies
4. Prints a success message or the error encountered.
"""
import sqlite3, sys, pathlib, shutil

DB_PATH = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "movie_night.db")

if not DB_PATH.exists():
    sys.exit(f"❌  File not found: {DB_PATH}")

# --- optional safety backup ----
backup = DB_PATH.with_suffix(".bak")
shutil.copy2(DB_PATH, backup)
print(f"🗂️  Backup created: {backup}")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

try:
    # -------- fast path (SQLite ≥ 3.25) ----------
    cur.execute("ALTER TABLE movies RENAME COLUMN mpaa TO rating_cert;")
    conn.commit()
    print("✅  Column renamed with ALTER TABLE.")
except sqlite3.OperationalError as e:
    if "no such column" in str(e):
        print("ℹ️  Column already renamed; nothing to do.")
    elif "near \"COLUMN\"" in str(e):
        print("⚠️  Old SQLite version; using manual copy method…")

        cur.execute("PRAGMA foreign_keys = OFF;")   # avoid FK issues

        # 1. create a new table with the updated schema
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='movies';")
        create_sql = cur.fetchone()[0]
        create_sql = create_sql.replace("(mpaa ", "(rating_cert ")
        cur.executescript(f"""
            {create_sql[:-1]}_new{create_sql[create_sql.find('('):]};
            INSERT INTO movies_new
            SELECT
                id, title, year, release_window,
                mpaa AS rating_cert,              -- rename on copy
                duration_seconds, youtube_link,
                box_office_expected, box_office_actual,
                google_trend_score, actor_trend_score,
                combined_score, franchise, origin_country
            FROM movies;
            DROP TABLE movies;
            ALTER TABLE movies_new RENAME TO movies;
        """)
        conn.commit()
        print("✅  Column renamed via manual copy.")
    else:
        print("❌  SQLite error:", e)
        conn.close()
        sys.exit(1)

conn.close()
print("Done – remember to update your Python code to use 'rating_cert'.")