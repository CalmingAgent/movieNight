"""
gui
~~~
All Qt widgets, pages and controllers.

•  No direct SQL here – everything goes through `metadata.repo`.
•  Re-export the high-level symbols so the app can simply:

    from gui import MainWindow, generate_movies
"""

# ── controllers ──────────────────────────────────────────────────────────
from .controller import generate_movies, update_data

# ── widgets / pages ──────────────────────────────────────────────────────
from .main_window import MainWindow
from .movie_card  import MovieCard
from .picker_page import PickerPage
from .stat_page   import StatsPage

__all__ = [
    "generate_movies",
    "update_data",
    "MainWindow",
    "MovieCard",
    "PickerPage",
    "StatsPage",
]
