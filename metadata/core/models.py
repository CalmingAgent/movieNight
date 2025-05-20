# Movie dataclass (+ any simple DTOs)
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class Movie:
    id: int
    title: str
    plot_desc: str | None = None
    year: int | None = None
    release_window: str | None = None
    rating_cert: str | None = None
    duration_seconds: int | None = None
    youtube_link: str | None = None
    box_office_expected: float | None = None
    box_office_actual: float | None = None
    google_trend_score: int | None = None
    actor_trend_score: float | None = None
    combined_score: float | None = None
    franchise: str | None = None
    origin: str | None = None

    @property
    def age_bucket(self) -> str:
        from metadata.international_reference import rating_to_age_group
        return rating_to_age_group(self.origin, self.rating_cert)