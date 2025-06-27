from __future__ import annotations
from typing import Dict, Callable, Any, Optional
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
import re
from typing import Tuple
from rapidfuzz import fuzz
from numpy.linalg import norm
from numpy import dot

_ST = SentenceTransformer("all-MiniLM-L6-v2")      # 384-d SBERT

# ---------- Public-facing container ----------
Fingerprint = Dict[str, Any]       # {'imdb_id': 'tt123', 'title': '…', …}

# ---------- Registry of converters ----------
_NORMALIZERS: Dict[str, Callable[[dict], Fingerprint]] = {}

def register(source: str):
    def _wrap(fn: Callable[[dict], Fingerprint]):
        _NORMALIZERS[source.upper()] = fn
        return fn
    return _wrap

# ---------- Helpers used by all normalisers ----------
_MINUTES_RE = re.compile(r"(\d+)\s*min", re.I)
def _minutes(raw: str | int | None) -> Optional[int]:
    if raw is None:                               return None
    if isinstance(raw, int):                      return raw
    m = _MINUTES_RE.search(raw)
    return int(m.group(1)) if m else None

def _year(raw: str | None) -> Optional[int]:
    if not raw:                                  return None
    try:                                         return int(raw[:4])
    except ValueError:                           return None

def _embed(text: str) -> list[float]:
    return _ST.encode(text or "", normalize_embeddings=True)

# ---------- Always-present keys ----------
def blank() -> Fingerprint:
    return dict.fromkeys(
        ("imdb_id", "title", "runtime", "year", "title_emb"), None
    )

_TOL_RT   = 10      # ±10 minutes
_TOL_YEAR = 1
_THRESHOLD = 0.80

def _cosine_emb(e1, e2) -> float:
    denom = norm(e1) * norm(e2)
    return float(dot(e1, e2) / denom) if denom else 0.0

def same_movie(a: Fingerprint, b: Fingerprint) -> Tuple[bool, float]:
    # 1) IMDb IDs (hard yes / no)
    if a["imdb_id"] and b["imdb_id"]:
        return (a["imdb_id"] == b["imdb_id"], 1.0 if a["imdb_id"] == b["imdb_id"] else 0.0)

    score, weight = 0.0, 0.0

    # 2) Title cosine 60 %
    if a["title_emb"] and b["title_emb"]:
        s = _cosine_emb(a["title_emb"], b["title_emb"])
        score += 0.60 * s; weight += 0.60

    # 3) Runtime diff 20 %
    if a["runtime"] and b["runtime"]:
        s = 1.0 if abs(a["runtime"] - b["runtime"]) <= _TOL_RT else 0.0
        score += 0.20 * s; weight += 0.20

    # 4) Year diff 20 %
    if a["year"] and b["year"]:
        s = 1.0 if abs(a["year"] - b["year"]) <= _TOL_YEAR else 0.0
        score += 0.20 * s; weight += 0.20

    if weight == 0:                 # not enough data
        return (False, 0.0)

    return (score / weight >= _THRESHOLD, score / weight)