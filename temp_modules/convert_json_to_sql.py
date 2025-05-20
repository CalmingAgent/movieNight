#a script that will convert all JSON's to SQL, will not need after running onceimport json
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))
from movieNight.metadata.service import MovieNightDB
from movieNight.metadata.youtube_client import YTClient
from movieNight.utils import normalize, log_debug

TRAILER_FOLDER = Path(__file__).resolve().parents[1] / "Video_Trailers"
db = MovieNightDB()
yt = YTClient()


def import_trailers_from_json():
    db._initialize_schema() 

    for json_path in TRAILER_FOLDER.glob("*Urls.json"):
        theme_name = json_path.stem.replace("Urls", "").strip()
        print(f"📂 Processing theme: {theme_name}")

        db.cur.execute("INSERT OR IGNORE INTO spreadsheet_themes (name) VALUES (?)", (theme_name,))
        db.conn.commit()

        db.cur.execute("SELECT id FROM spreadsheet_themes WHERE name = ?", (theme_name,))
        theme_id = db.cur.fetchone()["id"]

        data = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"📁 {json_path.name} contains {len(data)} entries")

        print("🔍 Looking for JSON files in:", TRAILER_FOLDER.resolve())
        print("🗂️  Files found:", list(TRAILER_FOLDER.glob("*Urls.json")))
        for movie_title, youtube_link in data.items():
            print(f"  🎞️ Checking: {movie_title}")
            duration = yt.get_video_duration_sec(youtube_link)
            print(f"    ⏱️ Fetched duration: {duration} seconds")
            if not duration:
                print(f"    ❌ Skipped: could not fetch duration for {youtube_link}")
                continue
            if duration < 60:
                print(f"    ❌ Skipped: duration {duration}s is too short")
                continue

            db.cur.execute("SELECT id FROM movies WHERE title = ?", (movie_title,))
            row = db.cur.fetchone()
            if row:
                movie_id = row["id"]
                db.update_movie_field(movie_id, "youtube_link", youtube_link)
                print(f"    ✅ Updated existing movie: {movie_title}")
            else:
                movie_data = {
                    "title": movie_title,
                    "year": None,
                    "release_window": None,
                    "mpaa": None,
                    "duration_seconds": duration,
                    "youtube_link": youtube_link,
                    "box_office_expected": None,
                    "box_office_actual": None,
                    "google_trend_score": None,
                    "actor_trend_score": None,
                    "combined_score": None,
                    "franchise": None
                }
                movie_id = db.add_movie(movie_data)
                print(f"    ✅ Inserted new movie: {movie_title}")

            db.cur.execute("""
                INSERT OR IGNORE INTO movie_spreadsheet_themes (movie_id, spreadsheet_theme_id)
                VALUES (?, ?)
            """, (movie_id, theme_id))
            db.conn.commit()
        # List all tables
    db.cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", db.cur.fetchall())

    # Show schema of a specific table
    # List all tables
    db.cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    table_names = [row['name'] for row in db.cur.fetchall()]
    print("\n📦 Tables Found:")
    for name in table_names:
        print(f"- {name}")

    # Show schema for each table
    print("\n🧩 Table Schemas:")
    for name in table_names:
        db.cur.execute(f"PRAGMA table_info({name});")
        columns = db.cur.fetchall()
        print(f"\n{name}:")
        for col in columns:
            print(f"  - {dict(col)}")
            
    print("\n🔍 Orphan Check: Foreign Key Integrity\n")

    # Define checks: (child_table, foreign_key_column, parent_table, parent_key_column)
    fk_checks = [
        ("movie_genres", "movie_id", "movies", "id"),
        ("movie_genres", "genre_id", "genres", "id"),
        ("movie_themes", "movie_id", "movies", "id"),
        ("movie_themes", "theme_id", "themes", "id"),
        ("movie_spreadsheet_themes", "movie_id", "movies", "id"),
        ("movie_spreadsheet_themes", "spreadsheet_theme_id", "spreadsheet_themes", "id"),
        ("user_ratings", "user_id", "users", "id"),
        ("user_ratings", "movie_id", "movies", "id"),
        ("ratings", "movie_id", "movies", "id")
    ]

    for child_table, fk_col, parent_table, parent_col in fk_checks:
        query = f"""
            SELECT {fk_col} FROM {child_table}
            WHERE {fk_col} NOT IN (
                SELECT {parent_col} FROM {parent_table}
            )
        """
        db.cur.execute(query)
        orphaned = db.cur.fetchall()

        if orphaned:
            print(f"❌ {child_table}.{fk_col} has {len(orphaned)} invalid references to {parent_table}.{parent_col}")
        else:
            print(f"✅ {child_table}.{fk_col} is clean against {parent_table}.{parent_col}")
    
    db.cur.execute("SELECT * FROM movies ORDER BY title ASC")
    rows = db.cur.fetchall()
    
    print(f"\n🎬 Found {len(rows)} movie(s):\n")
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Title: {row['title']}")
        print(f"Year: {row['year']}, MPAA: {row['mpaa']}, Duration: {row['duration_seconds']}s")
        print(f"Release Window: {row['release_window']}, Franchise: {row['franchise']}")
        print(f"YouTube: {row['youtube_link']}")
        print(f"Box Office: Expected ${row['box_office_expected']}, Actual ${row['box_office_actual']}")
        print(f"Trend Score: {row['google_trend_score']}, Actor Trend: {row['actor_trend_score']}")
        print(f"Combined Score: {row['combined_score']}")
        print("-" * 50)
if __name__ == "__main__":
    import_trailers_from_json()
