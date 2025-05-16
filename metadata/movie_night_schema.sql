CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    attendance_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    plot_desc TEXT,
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
    franchise TEXT,
    origin TEXT
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

-- one row per gathering 
CREATE TABLE IF NOT EXISTS movie_nights (
    id          INTEGER PRIMARY KEY,
    session_dt  TEXT    NOT NULL,                  -- '2025-05-23 19:30'
    attendee_count  INTEGER NOT NULL,              -- how many people showed up
    winner_movie_id INTEGER REFERENCES movies(id),  -- film actually screened
    host_note   TEXT                               -- optional “Bob’s place – tacos”
);
CREATE TABLE IF NOT EXISTS night_candidates (
    night_id   INTEGER REFERENCES movie_nights(id),
    movie_id   INTEGER REFERENCES movies(id),
    PRIMARY KEY (night_id, movie_id)
);

CREATE TABLE IF NOT EXISTS movie_aliases (
    movie_id INTEGER REFERENCES movies(id),
    alt_title TEXT,
    PRIMARY KEY (movie_id, alt_title)
);
