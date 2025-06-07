"""
gui
~~~
All Qt widgets, pages and controllers.

•  No direct SQL here – everything goes through `metadata.repo`.
•  Re-export the high-level symbols so the app can simply:

    from gui import MainWindow, generate_movies
"""

from movieNight.gui.controller import (
    generate_movies,
    add_remove_movie,
    update_data,              # small sheet sync
    start_update_metadata,    # bulk TMDb/OMDb/IMDb scrape
    start_update_urls,        # bulk trailer‐URL fixup
    start_collect_data,       # bulk data collection stub
)
from movieNight.gui.main_window  import MainWindow
from movieNight.gui.picker_page  import PickerPage
from movieNight.gui.movie_card   import MovieCard
from movieNight.gui.stat_page    import StatsPage

__all__ = [
    "generate_movies", "add_remove_movie",
    "update_data",
    "start_update_metadata", "start_update_urls", "start_collect_data",
    "MainWindow", "PickerPage", "MovieCard", "StatsPage",
]