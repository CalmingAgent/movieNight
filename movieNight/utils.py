
import functools
import pathlib
import random
import re
import json
from datetime import datetime
import subprocess
from sys import platform
import tempfile
import time
from typing import Optional, List, Tuple
import webbrowser

from PySide6.QtCore    import Qt # type: ignore
from PySide6.QtGui     import QPixmap, QPainter, QFont, QColor, QPalette # type: ignore
from PySide6.QtWidgets import QApplication # type: ignore

from movieNight.settings import LOG_PATH, ACCENT_COLOR


def log_debug(message: str) -> None:
    """Append timestamped message to the log file."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    entry = f"[{ts}] {message}\n"
    try:
        LOG_PATH.write_text(entry, encoding="utf-8", append=True)  # Py 3.12+
    except TypeError:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry)


def normalize(text: str) -> str:
    """Lowercase, strip, and remove non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", text.strip().lower())


def sanitize(text: str) -> str:
    """Remove characters invalid in file names."""
    return re.sub(r'[<>:"/\\|?*]', '', text).strip()


def fuzzy_match(target: str, candidates: List[str], cutoff: float = 0.8) -> Optional[str]:
    """Return the best close match to `target`, or None."""
    from difflib import get_close_matches
    matches = get_close_matches(target, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def make_number_pixmap(
    number: int,
    size: int = 96,
    fg_color: str = "#ffffff",
    bg_color: str = "transparent",
    border_color: str = ACCENT_COLOR
) -> QPixmap:
    """
    Create a square pixmap with a rounded border and centered `number`.
    """
    pix = QPixmap(size, size)
    pix.fill(QColor(bg_color))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = painter.pen()
    pen.setWidth(4)
    pen.setColor(QColor(border_color))
    painter.setPen(pen)
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 10, 10)

    font = QFont("Arial", int(size * 0.55), QFont.Bold)
    painter.setFont(font)
    painter.setPen(QColor(fg_color))
    painter.drawText(pix.rect(), Qt.AlignCenter, str(number))

    painter.end()
    return pix


def apply_dark_palette(app: QApplication) -> None:
    """Apply a dark Fusion palette to the application."""
    palette = QPalette()
    palette.setColor(QPalette.Window,        QColor("#202124"))
    palette.setColor(QPalette.WindowText,    Qt.white)
    palette.setColor(QPalette.Base,          QColor("#2b2c2e"))
    palette.setColor(QPalette.AlternateBase, QColor("#323336"))
    palette.setColor(QPalette.Button,        QColor("#2d2e30"))
    palette.setColor(QPalette.ButtonText,    Qt.white)
    palette.setColor(QPalette.Text,          Qt.white)
    palette.setColor(QPalette.Link,          QColor(ACCENT_COLOR))
    palette.setColor(QPalette.Highlight,     QColor(ACCENT_COLOR))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setStyle("Fusion")
    app.setPalette(palette)
    
def print_progress_bar_cmdln(
    iteration: int,
    total: int,
    prefix: str = "",
    suffix: str = "",
    length: int = 40,
) -> None:
    """
    Display or update a text-based progress bar in the console.

    :param iteration: current iteration (0-based or 1-based is okay)
    :param total: total number of iterations
    :param prefix: text to display before the bar
    :param suffix: text to display after the bar
    :param length: character width of the bar
    """
    if total <= 0:
        return

    fraction = iteration / float(total)
    filled_length = int(length * fraction)
    bar = "█" * filled_length + "-" * (length - filled_length)
    percent = round(100 * fraction, 1)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end="\r")
    if iteration >= total:
        print()

def open_url_host_browser(url: str) -> None:
    """Opens *url* with host OS default browser (WSL-aware)."""
    if "microsoft-standard" in platform.uname().release.lower():
        subprocess.Popen(["powershell.exe", "-c", f"Start-Process '{url}'"])
    else:
        webbrowser.open(url)

def throttle(min_delay: float = 1.0):
    """
    Decorator that sleeps `min_delay ±0.3 s` between *network* calls on the
    same function – thread-safe for a single GUI thread.
    """
    def wrap(fn):
        last_hit = 0.0
        @functools.wraps(fn)
        def inner(*a, **kw):
            nonlocal last_hit
            wait = min_delay - (time.time() - last_hit)
            if wait > 0:
                time.sleep(wait + random.uniform(0, 0.3))
            out = fn(*a, **kw)
            last_hit = time.time()
            return out
        return inner
    return wrap
       
def score_to_grade(score: float) -> str:
    bands = [
        ( 100, "S"), ( 97, "A+"), ( 92, "A"), ( 75, "A-"),
        ( 68, "B+"), ( 62, "B"), ( 55, "B-"),
        ( 48, "C+"), ( 42, "C"), ( 35, "C-"),
        ( 25, "D"), ( 15, "E"), (  0, "F"),
    ]

# --- helpers ----------------------------------------------------------------
_YT_RE = re.compile(r"(?:youtu\.be/|v=)([\w\-]{11})")

def _valid(url: str | None) -> bool:
    return url and _YT_RE.search(url)

def _make_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# --- public API --------------------------------------------------------------
@throttle(min_delay=0.4)            # ⇠ stay well under 40 req / 10 s (TMDb)
def locate_trailer( title: str) -> Tuple[str | None, str, float]:
    """
    Find a trailer URL for *title*.

    *sheet* is accepted for backward-compatibility but ignored; DB now
    stores only one `youtube_link` per movie.

    Returns (url | None, source, confidence)
    """
    from movieNight.metadata.api_clients import tmdb_client, yt_client
    from movieNight.metadata.core import repo
    # 0. DB cache -------------------------------------------------------------
    mid = repo.get_movie_id_by_title(title)
    if mid:
        url = repo.by_id(mid).youtube_link
        if _valid(url):
            return url, "db", 1.00

    # 1. TMDb (exact) ---------------------------------------------------------
    best = tmdb_client.fetch_videos_exact(title)
    if best and _valid(best):
        return best, "tmdb", 0.95

    # 2. yt-dl on TMDb slug ---------------------------------------------------
    if best := tmdb_client.try_slug_search(title):
        vid = yt_client.search_first_match(best + " trailer", exact=True)
        if vid:
            return _make_url(vid), "yt_dl", 0.80

    # 3. raw YouTube search ---------------------------------------------------
    vid = yt_client.search_first_match(title + " trailer", exact=False, max_retries=3)
    if vid:
        return _make_url(vid), "youtube", 0.60

    return None, "none", 0.0