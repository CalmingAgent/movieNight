#!/usr/bin/env python3
"""
add_origin_country.py

Usage:
    python add_origin_country.py [path/to/your.db]

If the column already exists, it simply tells you and quits.
"""
import sqlite3
import sys
from pathlib import Path

def main(db_path: str = "movie_night.db") -> None:
    db = Path(db_path)
    if not db.exists():
        print(f"❌  Database file not found: {db}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # --- check current schema
    cur.execute("PRAGMA table_info(movies)")
    cols = [row[1] for row in cur.fetchall()]

    if "origin_country" in cols:
        print("✅  Column 'origin_country' already exists – nothing to do.")
        return

    # --- migrate
    cur.execute("ALTER TABLE movies ADD COLUMN origin_country TEXT")  # nullable
    conn.commit()

    # --- confirm
    cur.execute("PRAGMA table_info(movies)")
    for cid, name, col_type, *_ in cur.fetchall():
        if name == "origin_country":
            print(f"✅  Added column 'origin_country' (type: {col_type}).")
            break

    conn.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "movie_night.db")
