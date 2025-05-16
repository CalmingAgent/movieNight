
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
from typing import Optional, List
import webbrowser

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QPixmap, QPainter, QFont, QColor, QPalette
from PySide6.QtWidgets import QApplication

from .settings import LOG_PATH, ACCENT_COLOR


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
       
def trend_score(keyword: str) -> int | None:
    """
    Returns the 7-day average Google-Trends interest (0-100) for *keyword*.
    Requires `npm i -g google-trends-api`.
    """
    node_script = f"""
        const gtrends = require('google-trends-api');
        gtrends.interestOverTime({{ keyword: "{keyword}", startTime: new Date(Date.now()-7*24*3600*1000) }})
          .then(r => console.log(JSON.stringify(r)))
          .catch(_ => process.exit(1));
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".js", delete=False) as js:
        js.write(node_script)
    try:
        raw = subprocess.check_output(["node", js.name], timeout=20)
        obj = json.loads(raw)
        points = [v['value'][0] for v in obj["default"]["timelineData"]]
        return round(sum(points)/len(points))
    except Exception:
        return None
    finally:
        pathlib.Path(js.name).unlink(missing_ok=True)
        
def score_to_grade(score: float) -> str:
    bands = [
        ( 100, "S"), ( 97, "A+"), ( 92, "A"), ( 75, "A-"),
        ( 68, "B+"), ( 62, "B"), ( 55, "B-"),
        ( 48, "C+"), ( 42, "C"), ( 35, "C-"),
        ( 25, "D"), ( 15, "E"), (  0, "F"),
    ]