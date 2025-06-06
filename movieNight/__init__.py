"""
movieNight
~~~~~~~~~~

Top-level package for the Movie Night application.

Exports:
  - SPREADSHEET_ID, YOUTUBE_API_KEY, TRAILER_FOLDER
  - Utility functions: normalize, sanitize, fuzzy_match, make_number_pixmap, log_debug, apply_dark_palette
  - MainWindow GUI and core actions: generate_movies, update_trailer_urls
"""

# settings
from movieNight.settings import SPREADSHEET_ID, YOUTUBE_API_KEY, TRAILER_FOLDER

# utils
from movieNight.utils import (
    normalize,
    sanitize,
    fuzzy_match,
    make_number_pixmap,
    log_debug,
    apply_dark_palette,
)

# GUI entrypoint
from movieNight.gui.main_window import MainWindow

# core logic
from movieNight.gui.controller import generate_movies, update_trailer_urls

__all__ = [
    # settings
    "SPREADSHEET_ID",
    "YOUTUBE_API_KEY",
    "TRAILER_FOLDER",
    # utils
    "normalize",
    "sanitize",
    "fuzzy_match",
    "make_number_pixmap",
    "log_debug",
    "apply_dark_palette",
    # GUI
    "MainWindow",
    # core actions
    "generate_movies",
    "update_trailer_urls",
]
