from fairlearn.metrics import MetricFrame, demographic_parity_difference
from recmetrics import diversity
import pandas as pd

def group_parity(y_true: pd.Series, y_pred: pd.Series, sensitive: pd.Series):
    """Δ Demographic-parity across sensitive groups (e.g. region, gender)."""
    frame = MetricFrame(
        metrics=demographic_parity_difference,
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=sensitive,
    )
    return frame.overall, frame.by_group.to_dict()

def rec_list_diversity(rec_lists: list[list[int]], repo):
    """Intra-list diversity score for each user list."""
    genre_sets = [[repo.genres(mid) for mid in lst] for lst in rec_lists]
    return diversity.intralist_diversity(genre_sets)
