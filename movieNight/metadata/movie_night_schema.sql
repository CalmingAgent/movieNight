CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT  NOT NULL,
    attendance_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS movies (
    id                    INTEGER PRIMARY KEY,
    tmdb_id               INTEGER UNIQUE,
    imdb_id               TEXT UNIQUE,
    title                 TEXT NOT NULL,
    plot_desc             TEXT,
    release_date          DATE,
    release_window        TEXT,
    rating_cert           TEXT,
    duration_seconds      INTEGER,
    youtube_link          TEXT,
    box_office_expected   NUMERIC(12,2),
    box_office_actual     NUMERIC(12,2),
    franchise_id          INTEGER REFERENCES franchises(id),
    origin_iso2           TEXT REFERENCES countries(iso2),
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movie_trends(
    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    as_of    DATE    NOT NULL,
    google_trend_score  INTEGER,
    actor_trend_score   REAL,
    PRIMARY KEY(movie_id, as_of)
);

CREATE TABLE franchises(
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE countries(
    iso2 TEXT PRIMARY KEY,  -- 'US','JP'
    name TEXT
);

CREATE TABLE IF NOT EXISTS user_ratings (
    user_id  INTEGER NOT NULL
             REFERENCES users(id)   ON DELETE CASCADE,
    movie_id INTEGER NOT NULL
             REFERENCES movies(id)  ON DELETE CASCADE,
    rating   REAL     NOT NULL CHECK (rating BETWEEN 0 AND 100),
    PRIMARY KEY (user_id, movie_id)
);

CREATE TABLE IF NOT EXISTS ratings (        -- critic / audience pulls
    movie_id    INTEGER NOT NULL
                REFERENCES movies(id)  ON DELETE CASCADE,
    source      TEXT    NOT NULL,         -- 'IMDB', 'RT_CRITIC', …
    type        TEXT    CHECK (type IN ('critic','audience','aggregated')),
    score       REAL,
    num_reviews INTEGER,
    PRIMARY KEY (movie_id, source)
);
CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INTEGER NOT NULL
             REFERENCES movies(id)   ON DELETE CASCADE,
    genre_id INTEGER NOT NULL
             REFERENCES genres(id),
    PRIMARY KEY (movie_id, genre_id)
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_themes (
    movie_id INTEGER NOT NULL REFERENCES movies(id),
    theme_id INTEGER NOT NULL REFERENCES themes(id),
    PRIMARY KEY (movie_id, theme_id)
);

CREATE TABLE IF NOT EXISTS spreadsheet_themes (
    id    INTEGER PRIMARY KEY,
    name  TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_spreadsheet_themes (
    movie_id  INTEGER NOT NULL
              REFERENCES movies(id)         ON DELETE CASCADE,
    spreadsheet_theme_id  INTEGER NOT NULL
              REFERENCES spreadsheet_themes(id),
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

-- one row per gathering 
CREATE TABLE IF NOT EXISTS movie_nights (
    id          INTEGER PRIMARY KEY,
    session_dt  TEXT    NOT NULL,                  -- '2025-05-23 19:30'
    attendee_count  INTEGER NOT NULL,              -- how many people showed up
    winner_movie_id INTEGER REFERENCES movies(id),  -- film actually screened
    host_note   TEXT                               -- optional “Bob’s place – tacos”
);

CREATE TABLE IF NOT EXISTS night_candidates (
    night_id INTEGER NOT NULL
             REFERENCES movie_nights(id) ON DELETE CASCADE,
    movie_id INTEGER NOT NULL
             REFERENCES movies(id)       ON DELETE CASCADE,
    PRIMARY KEY (night_id, movie_id)
);

CREATE TABLE IF NOT EXISTS movie_aliases (
    movie_id INTEGER NOT NULL
             REFERENCES movies(id)   ON DELETE CASCADE,
    alt_title TEXT,
    PRIMARY KEY (movie_id, alt_title)
);

CREATE TABLE IF NOT EXISTS trend_cache (
    term   TEXT NOT NULL,     -- e.g. "Oppenheimer", "Ryan Gosling"
    as_of  DATE NOT NULL,     -- ISO-8601 "YYYY-MM-DD" (UTC)
    value  TEXT,              -- 0-100; TEXT so '' can represent “no data”
    PRIMARY KEY (term, as_of)
);

CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS fairness_audit (
    as_of      TEXT PRIMARY KEY,
    metric     TEXT,
    value      REAL,
    by_group   TEXT
);

ALTER TABLE movies
  ADD FOREIGN KEY (franchise_id)  REFERENCES franchises(id) ON DELETE SET NULL,
  ADD FOREIGN KEY (origin_iso2)   REFERENCES countries(iso2) ON DELETE SET NULL;