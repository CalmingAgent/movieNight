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
# the calculations differently, depending on the STD of the random movies

#Example Tables:

# -- Movies (one row per film)
# CREATE TABLE movies (
#   id                   INTEGER PRIMARY KEY,
#   title                TEXT    NOT NULL,
#   year                 INTEGER,
#   mpaa                 TEXT,
#   duration_seconds     INTEGER,
#   youtube_link         TEXT,
#   projected_audience   REAL,     -- probability 0–1
#   box_office_expected  NUMERIC(12,2),
#   box_office_actual    NUMERIC(12,2),
#   google_trend_score   INTEGER,
#   combined_score       REAL      -- your weighted meta-score
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

# CREATE TABLE themes (
#   id    INTEGER PRIMARY KEY,
#   name  TEXT UNIQUE
# );

# CREATE TABLE movie_themes (
#   movie_id  INTEGER REFERENCES movies(id),
#   theme_id  INTEGER REFERENCES themes(id),
#   PRIMARY KEY (movie_id, theme_id)
# );


import random
import rng_movie
def get_calc_weighted_ratings(movie_titles):
    return float(random.randint(0,100)/100)
def get_prob(movie_title: str) -> float:
    # compute probability 0 – 1
    return float(random.randint(0,100)/100)
def get_similarity(movie_titles: list)-> float:
    #compare how similar all the movies are in the random movies
    return float(random.randint(0,100)/100)



