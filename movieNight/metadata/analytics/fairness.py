"""
fair_score
~~~~~~~~~~
Utilities that inject demographic– and diversity-aware weighting into
all numeric signals (trend scores, combined score, …).

Public helpers
--------------
fairness_bonus(movie, baselines)        -> float  0‥?  extra points
actor_trend_fair(imdb_pop, gtrend, …)   -> float  0‥100
gtrend_fair(raw_trend, country, …)      -> float  0‥100
combined_score_fair(movie, histograms, mc, rt, baselines) -> float 0‥100
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Mapping

# ─────────────────────── 1 ▸ constants & baseline snapshots
# (populate these at start-up – see §3)
@dataclass(slots=True)
class Baselines:
    pop_by_country: Mapping[str, float]          # internet users / world
    movies_by_country: Mapping[str, float]       # share in your catalogue


# ─────────────────────── 2 ▸ generic helpers
def fairness_bonus(movie, base: Baselines, *, k: float = 5.0) -> float:
    """Return +k points if movie’s *origin* is under-represented."""
    global_share = base.pop_by_country.get(movie.origin, 0.0)
    cat_share    = base.movies_by_country.get(movie.origin, 0.0)
    gap          = max(global_share - cat_share, 0.0)          #   0‥1
    return round(k * gap, 2)                                   # 0‥k


def _posterior(hist: np.ndarray) -> tuple[float, float]:
    """Beta–Binomial posterior (μ, σ²) for a 10-bucket rating histogram."""
    k = np.arange(1, 11)               # stars 1‥10
    n = hist.sum()
    if n == 0:
        return 0.0, 1.0
    α = 1 + (k * hist).sum()
    β = 1 + ((11 - k) * hist).sum()
    μ = α / (α + β) * 10
    var = (α * β) / ((α + β) ** 2 * (α + β + 1)) * 100
    return μ, var


def _w_demo(source: str, movie, base: Baselines) -> float:
    """Heuristic demographic / exposure weight for a *source*."""
    penalty = {
        "IMDb"          : 1.5,   # male / US skew
        "MetacriticCrit": 1.2,
        "RTCritic"      : 1.2,
    }.get(source, 1.0)
    gap     = max(base.pop_by_country.get(movie.origin, 0)
                  - base.movies_by_country.get(movie.origin, 0), 0)
    origin_bonus = 1 + gap * 3                    # up to ×1.3
    return origin_bonus / penalty


# ─────────────────────── 3 ▸ public scoring helpers

def actor_trend_fair(imdb_pop: float,
                     gtrend: float,
                     movie,
                     base: Baselines) -> float:
    """
    0-100 actor trend = 30 % IMDb popularity + 70 % Google Trends,
    *then* boosted by fairness_bonus.
    """
    raw   = 0.3 * imdb_pop + 0.7 * gtrend
    bonus = fairness_bonus(movie, base) / 2       # max +2.5
    return round(min(raw + bonus, 100), 2)


def gtrend_fair(raw_trend: float,
                country: str,
                base: Baselines,
                internet_pen: Mapping[str, float]) -> float:
    """
    Normalise raw Google Trends by internet penetration of *country* and
    cap to 100.
    """
    pen = max(internet_pen.get(country, 0.35), 0.05)   # avoid /0
    norm = raw_trend / pen
    return min(round(norm, 2), 100.0)


def combined_score_fair(movie,
                         histograms: Mapping[str, np.ndarray],
                         mc: dict, rt: dict,
                         base: Baselines) -> float:
    """
    Fuse IMDb/TMDb/RT-audience histograms + Metacritic/RT-critic means
    into one 0-100 score, with diversity weighting.
    """
    mus, wts = [], []
    for src, hist in histograms.items():
        μ, σ2 = _posterior(hist)
        w_qty = 1 / σ2
        w     = w_qty * _w_demo(src, movie, base)
        mus.append(μ);  wts.append(w)

    if mc["n"]:
        mus.append(mc["score"] / 10)
        wts.append(mc["n"] * _w_demo("MetacriticCrit", movie, base))

    mus.append(rt["critic"] / 10)
    wts.append(rt["n"] * _w_demo("RTCritic", movie, base))

    raw = np.average(mus, weights=wts) * 10          # → 0-100
    final = min(raw + fairness_bonus(movie, base), 100)
    return round(final, 2)
