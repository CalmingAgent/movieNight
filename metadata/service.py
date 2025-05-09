#Math calculations, predictions and a facade to call other metadata files (get_meta_(argument))

# - Program calculates probability of us watching a movie (given random titles of the number of
#   people attending equals the upper bound, inclusive)
# - Use density curves for frequency of people coming to movies, 
#   each column would be weighted higher for higher
#   Attendency of movie night
# - Get Standard Deviation of each column to weight each score biased
#   to weight the score further
# - Get Metadata from movies: year, genre, mpaa rating, number of votes on ratings,
#   IMdb, rotten tomatoes, and metacritic rating, trend score
# - Need to disern what model to use, use a residal plot to disern if there is a good fit.
# - Could use R^2 to get the percentage to try to minamize this.
# - Need to compare if the movies are similar, duh? Where was I going with this? 
# Ah, I remember. Need to compare the meta data on the list to see how similar a movie is to the rest on the randomly picked list
# this will tell me how different the movies are from each other. if they are all similar, I would probably need to weight differently or handle
# -would also need to get number of YT view for calculations
#Example Tables:

# -- Movies (one row per film)
# CREATE TABLE movies (
#   id                   INTEGER PRIMARY KEY,
#   title                TEXT    NOT NULL,  --title of movie
#   year                 INTEGER,           --year of release
#   release_window       TEXT,              -- when it was released: summer, holiday, etc
#   mpaa                 TEXT,              --MPAA rating
#   duration_seconds     INTEGER,           --duration of movie
#   youtube_link         TEXT,              --YouTube trailer link
#   box_office_expected  NUMERIC(12,2),     --expected box office money
#   box_office_actual    NUMERIC(12,2),     --actual box office earnings
#   google_trend_score   INTEGER,           --the trend score from google trends
#   actor_trend_score    REAL,              --the trend and if the actor is relvant today          
#   combined_score       REAL,              --weighted meta-score
#   franchise            TEXT               --if it's a sequal or a franchise
# );

# CREATE TABLE ratings (
#   movie_id     INTEGER REFERENCES movies(id),
#   source       TEXT NOT NULL,     -- e.g. 'IMDB', 'RT_CRITIC', 'RT_AUDIENCE', 'Metacritic'
#   type         TEXT,              -- 'critic' | 'audience' | 'aggregated'
#   score        REAL,              -- typically 0-100 scale
#   num_reviews  INTEGER,
#   PRIMARY KEY (movie_id, source)
# );

# CREATE TABLE genres (
#   id    INTEGER PRIMARY KEY,
#   name  TEXT UNIQUE
# );

# CREATE TABLE movie_genres (
#   movie_id  INTEGER REFERENCES movies(id),
#   genre_id  INTEGER REFERENCES genres(id),
#   PRIMARY KEY (movie_id, genre_id)
# );

#for creating the theme for the movie, IE: revenge, underdog, dystopia
# CREATE TABLE themes (
#   id    INTEGER PRIMARY KEY,
#   name  TEXT UNIQUE
# );

# CREATE TABLE spreadsheet_themes (
#   id    INTEGER PRIMARY KEY,
#   name  TEXT UNIQUE
# );

# CREATE TABLE movie_spreadsheet_themes (
#   movie_id  INTEGER REFERENCES movies(id),
#   spreadsheet_theme_id  INTEGER REFERENCES spread_themes(id),
#   PRIMARY KEY (movie_id, theme_id)
# );

# CREATE TABLE movie_themes (
#   movie_id  INTEGER REFERENCES movies(id),
#   theme_id  INTEGER REFERENCES themes(id),
#   PRIMARY KEY (movie_id, theme_id)
# );
from dataclasses import dataclass
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from ..settings import META_SCORE_WEIGHTS, TREND_PROBABILITY_WEIGHTS, DATABASE_PATH 
import sqlite3

@dataclass
class Movie:
    title: str
    year: int
    release_window: str
    rating_cert: str
    duration: int
    youtube_link: str
    box_office_expected: float
    box_office_actual: float
    google_trend_score: int
    actor_trend_score: float
    combined_score: float
    franchise: str

    def calculate_meta_combined_score(self, imdb: float, rt_critic: float, rt_audience: float, metacritic: float, weights=None) -> float:
        weights = weights or META_SCORE_WEIGHTS
        self.combined_score = round(
            imdb * weights["imdb"] +
            rt_critic * weights["rt_critic"] +
            rt_audience * weights["rt_audience"] +
            metacritic * weights["metacritic"], 2
        )
        return self.combined_score

    def calculate_probability_to_watch(self) -> float:
        #placeholder for actually calculating
        trend_weight = TREND_PROBABILITY_WEIGHTS
        return round(
            trend_weight["google_trend"] * (self.google_trend_score / 100) +
            trend_weight["actor_trend"] * min(self.actor_trend_score, 1.0) +
            trend_weight["combined_score"] * (self.combined_score / 100), 3
        )

    def calculate_similarity(self, other: 'Movie') -> float:
        # Simplified example: compare based on score and duration; will use cosine similarity later
        score_diff = abs(self.combined_score - other.combined_score) / 100
        duration_diff = abs(self.duration - other.duration) / max(self.duration, other.duration, 1)
        similarity = 1.0 - ((score_diff + duration_diff) / 2)
        return round(similarity, 3)

    
#schema class for database
class MovieNightDB:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._initialize_schema()

    def _initialize_schema(self):
        self.cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            attendance_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER,
            release_window TEXT,
            rating_cert TEXT,
            duration_seconds INTEGER,
            youtube_link TEXT,
            box_office_expected NUMERIC(12,2),
            box_office_actual NUMERIC(12,2),
            google_trend_score INTEGER,
            actor_trend_score REAL,
            combined_score REAL,
            franchise TEXT
        );

        CREATE TABLE IF NOT EXISTS user_ratings (
            user_id INTEGER REFERENCES users(id),
            movie_id INTEGER REFERENCES movies(id),
            rating REAL CHECK (rating >= 0 AND rating <= 100),
            PRIMARY KEY (user_id, movie_id)
        );
        
        CREATE TABLE IF NOT EXISTS ratings (
            movie_id INTEGER REFERENCES movies(id),
            source TEXT NOT NULL,                   -- e.g. 'IMDB', 'RT_CRITIC', 'RT_AUDIENCE', 'Metacritic'
            type TEXT,                              -- 'critic' | 'audience' | 'aggregated'
            score REAL,                             -- 0-100 scale
            num_reviews INTEGER,
            PRIMARY KEY (movie_id, source)
        );

        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS movie_genres (
            movie_id INTEGER REFERENCES movies(id),
            genre_id INTEGER REFERENCES genres(id),
            PRIMARY KEY (movie_id, genre_id)
        );

        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS movie_themes (
            movie_id INTEGER REFERENCES movies(id),
            theme_id INTEGER REFERENCES themes(id),
            PRIMARY KEY (movie_id, theme_id)
        );
        
        CREATE TABLE IF NOT EXISTS spreadsheet_themes (
            id    INTEGER PRIMARY KEY,
            name  TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS movie_spreadsheet_themes (
          movie_id  INTEGER REFERENCES movies(id),
          spreadsheet_theme_id  INTEGER REFERENCES spread_theme(id),
          PRIMARY KEY (movie_id, spreadsheet_theme_id)
        );

        CREATE VIEW IF NOT EXISTS user_attendance AS
        SELECT
            users.id AS user_id,
            users.name AS name,
            COUNT(user_ratings.movie_id) AS attendance_count
        FROM users
        LEFT JOIN user_ratings ON users.id = user_ratings.user_id
        GROUP BY users.id;
        """)
        self.conn.commit()
        
    def add_user(self, name: str):
        self.cur.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))
        self.conn.commit()
    
    def add_movie(self, movie_data: dict) -> int:
        keys = ', '.join(movie_data.keys())
        placeholders = ', '.join(['?'] * len(movie_data))
        query = f"INSERT INTO movies ({keys}) VALUES ({placeholders})"
        self.cur.execute(query, tuple(movie_data.values()))
        self.conn.commit()
        return self.cur.lastrowid
    
    def add_rating(self, user_id: int, movie_id: int, rating: float):
        self.cur.execute("""
            INSERT OR REPLACE INTO user_ratings (user_id, movie_id, rating)
            VALUES (?, ?, ?)
        """, (user_id, movie_id, rating))
        self.conn.commit()
        
    def get_all_movies(self):
        self.cur.execute("SELECT * FROM movies")
        return self.cur.fetchall()
    
    def get_user_rating(self, user_id: int, movie_id: int):
        self.cur.execute("SELECT rating FROM user_ratings WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
        return self.cur.fetchone()
    
    def update_attendance_counts(self):
        self.cur.execute("""
            UPDATE users
            SET attendance_count = (
                SELECT COUNT(*)
                FROM user_ratings
                WHERE user_ratings.user_id = users.id
            )
        """)
        self.conn.commit()
        
    def get_movie_id_by_title(self, title: str) -> int | None:
        self.cur.execute("SELECT id FROM movies WHERE title = ?", (title,))
        row = self.cur.fetchone()
        return row["id"] if row else None
    
    def update_movie_field(self, movie_id: int, field_name: str, new_value):
        allowed_fields = {
            "title", "year", "release_window", "rating_cert", "duration_seconds",
            "youtube_link", "box_office_expected", "box_office_actual",
            "google_trend_score", "actor_trend_score", "combined_score", "franchise"
        }

        if field_name not in allowed_fields:
            raise ValueError(f"'{field_name}' is not an allowed field for update.")

        query = f"UPDATE movies SET {field_name} = ? WHERE id = ?"
        self.cur.execute(query, (new_value, movie_id))
        self.conn.commit()




    def close(self):
        self.conn.close()
        
    
        

import random

def movie_probability(title: str) -> float:
    """Stub: return a random 'probability' for a movie."""
    return random.random()

def calculate_weighted_totals(titles: list[str]) -> float:
    """Stub: return a random weighted total for a list of titles."""
    return random.random()

def calculate_group_similarity(titles: list[str]) -> float:
    """Stub: return a random similarity score for a list of titles."""
    return random.random()