# - Program calculates probability of us watching a movie (given random titles of the number of
#   people attending equals the upper bound, inclusive)
# - Use density curves for frequency of people coming to movies, 
#   each column would be weighted higher for higher
#   Attendency of movie night
# - Get Standard Deviation of each column to weight each score biased
#   to weight the score further
# - Get Metadata from movies: year, genre, mpaa rating, number of votes on ratings,
#   IMdb, rotten tomatoes, and metacritic rating, trend score

def get_prob(movie_title: str) -> float:
    # compute probability 0 – 1
    return 1




