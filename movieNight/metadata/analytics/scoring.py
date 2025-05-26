# expected_grade(), watch_probability()

import random
from typing import Dict

from movieNight.settings import META_SCORE_WEIGHTS, TREND_PROBABILITY_WEIGHTS, TREND_ACTOR
from movieNight.metadata.core.repo import MovieRepo, repo


def calculate_combined_score(
    imdb: float,
    rt_critic: float,
    rt_audience: float,
    metacritic: float,
    weights: Dict[str, float] | None = None,
) -> float:
    weights = weights or META_SCORE_WEIGHTS
    combined_score = round(
        imdb        * weights["imdb"]        +
        rt_critic   * weights["rt_critic"]   +
        rt_audience * weights["rt_audience"] +
        metacritic  * weights["metacritic"],
        2,
    )
    return combined_score

def calculate_probability_to_watch(title) -> float:
    #placeholder for actually calculating
    trend_weight = TREND_PROBABILITY_WEIGHTS
    title_id = MovieRepo.id_by_title
    return round(
        trend_weight["google_trend"] * (MovieRepo.get_google_trend_score(title_id) / 100) +
        trend_weight["actor_trend"] * min(MovieRepo.get_actor_trend_score(title_id), 1.0) +
        trend_weight["combined_score"] * (MovieRepo.get_combined_score(title_id) / 100), 3
        )

def calculate_expected_grade():
    "compares movie to graded movies in the user_ratings and guess what the grade will be"
    return "--"
def calculate_weighted_total():
    return random(0,100)

def calculate_actor_trend_score():
    "calculates the actor score using google trend score and IMDB popularity "
    pass
