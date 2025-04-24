from __future__ import annotations
import os
import re
import io
import json
import random
import sys
from tkinter import messagebox
from pathlib import Path
from dotenv import load_dotenv
import pickle
import datetime
from typing import Optional, List
import requests
import subprocess
import openpyxl



from pathlib import Path
import datetime, random, importlib

from PySide6.QtCore    import Qt, QSize, Slot
from PySide6.QtGui     import QAction, QIcon, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QStackedWidget, QPushButton,
    QLineEdit, QFileDialog, QSplitter, QFrame, QTableWidget,
    QTableWidgetItem, QSizePolicy, QDialog, QCheckBox, QDialogButtonBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from difflib import get_close_matches

# --------------------- CONFIGURATION --------------------- #
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "secret.env"
LOG_FILE = BASE_DIR / "trailer_debug.log"
auto_update_script = BASE_DIR / "autoUpdate.py"
probability_script = BASE_DIR/ "probability.py"

# JSON and local XLSX storage
TRAILERS_DIR = BASE_DIR / "Video_Trailers"
NUMBERS_DIR = BASE_DIR / "Numbers"
GHIB_FILE = BASE_DIR / "ghib.xlsx"
ICON = lambda n: QIcon(str(BASE_DIR / "icons" / f"{n}.svg"))

# The new file to track reported/wrong trailers
UNDER_REVIEW_FILE = BASE_DIR / "underReviewURLs.json"

# Service account + client secrets
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "service_secret.json"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
YOUTUBE_TOKEN_FILE = BASE_DIR / "youtube_token.pickle"

# Quota-limited Google Drive scope (read spreadsheet as XLSX)
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# YouTube scope for user-level actions
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]

# For searching YouTube
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# App Constants
ACCENT  = "#3b82f6"  # Tailwind ‘blue-500’
# stub import for the forthcoming probability pipeline
def movie_prob(title: str) -> float:
    try:
        prob_mod = importlib.import_module("probability")
        return float(prob_mod.get_prob(title))
    except Exception:
        return 0.0            # placeholder until probability.py exists

# ----------------- ENVIRONMENT LOADING ------------------- #
load_dotenv(ENV_PATH)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not SPREADSHEET_ID:
    raise EnvironmentError("Missing Spreadsheet ID in secret.env")

if not YOUTUBE_API_KEY:
    raise EnvironmentError("Missing YOUTUBE_API_KEY in secret.env")


# ---------------- UTILS + LOGGING ---------------- #
def log_debug(message: str) -> None:
    """
    Log debug messages to file with a timestamp.
    """
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def sanitize_filename(name: str) -> str:
    """Remove characters invalid for filenames; strip leading/trailing spaces."""
    return re.sub(r'[<>:"/\\|?*-]', '', name.strip())


def normalize(text: str) -> str:
    """Lowercase the string and remove all non-alphanumeric characters."""
    return re.sub(r'[^a-z0-9]', '', text.strip().lower())


def fuzzy_search(target: str, candidates: List[str], cutoff=0.8) -> Optional[str]:
    """
    Return the best fuzzy match for 'target' within 'candidates'.
    By default, cutoff=0.8 for an 80% match requirement.
    """
    from difflib import get_close_matches
    matches = get_close_matches(target, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None

def open_in_windows_default(url: str):
    subprocess.run(["wslview", url])


# ---------------- REPORTING WRONG TRAILERS ---------------- #
def report_trailer(movie_name: str, youtube_url: str):
    """
    1) Load (or create) underReviewURLs.json
    2) data[movie_name] = youtube_url
    3) Rewrite in multiline JSON
    4) Show a popup confirming the report
    """
    if not UNDER_REVIEW_FILE.exists():
        UNDER_REVIEW_FILE.write_text("{}", encoding="utf-8")

    try:
        data = json.loads(UNDER_REVIEW_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}

    data[movie_name] = youtube_url  # Overwrite or set

    # Write multiline JSON
    lines = ["{"]
    keys = list(data.keys())
    for i, k in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        val = data[k].replace('"', '\\"') if data[k] else ""
        lines.append(f'  "{k}": "{val}"{comma}')
    lines.append("}")

    UNDER_REVIEW_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    log_debug(f"[REPORT] Marked '{movie_name}' => {youtube_url} as under review.")
    tk.messagebox.showinfo("Reported", f"Marked trailer for '{movie_name}' as under review.")

def open_report_dialog(selected_movies: List[str], trailer_lookup: dict):
    """
    Open a new window with checkboxes for each movie from selected_movies.
    User can check the ones they want to report. On confirm, it logs them.
    """
    dialog = tk.Toplevel(root)
    dialog.title("Report Trailers")
    dialog.configure(bg=BACKGROUND_COLOR)
    center_window(dialog, 400, 400)

    label = tk.Label(dialog, text="Select trailers to report:", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR)
    label.pack(pady=10)

    var_dict = {}
    for movie in selected_movies:
        var = tk.IntVar()
        chk = tk.Checkbutton(dialog, text=movie, variable=var, bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR, selectcolor=HIGHLIGHT_COLOR)
        chk.pack(anchor="w")
        var_dict[movie] = var

    def confirm_report():
        for movie, var in var_dict.items():
            if var.get() == 1:
                url = trailer_lookup.get(movie)
                if url:
                    report_trailer(movie, url)
        dialog.destroy()

    def cancel():
        dialog.destroy()

    btn_frame = tk.Frame(dialog, bg=BACKGROUND_COLOR)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Report Selected", command=confirm_report, bg=BUTTON_COLOR, fg=FOREGROUND_COLOR).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Cancel", command=cancel, bg=BUTTON_COLOR, fg=FOREGROUND_COLOR).pack(side="left", padx=5)
# ---------------- YOUTUBE TRAILER SEARCH (RUNTIME) ---------------- #
def youtube_api_search(query: str) -> Optional[tuple]:
    """
    If the user picks a sheet and we want a fallback for a single trailer at runtime
    (this is separate from the big autoUpdate job).
    """
    params = {
        "part": "snippet",
        "q": query,
        "key": YOUTUBE_API_KEY,
        "videoDuration": "short",
        "maxResults": 1,
        "type": "video"
    }
    try:
        response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        data = response.json()
        if "items" in data and data["items"]:
            video_id = data["items"][0]["id"]["videoId"]
            video_title = data["items"][0]["snippet"]["title"]
            return f"https://www.youtube.com/watch?v={video_id}", video_title
    except Exception as e:
        log_debug(f"[ERROR] YouTube API search failed: {e}")
    return None


def locate_trailer(sheet_name: str, movie_title: str) -> (Optional[str], str, Optional[str]):
    """
    1) Look up a trailer in <sheetName>Urls.json
    2) If none found, fallback to a direct single-call YouTube search
    3) Return (url, source, video_title)
    """
    safe_sheet = sanitize_filename(sheet_name).replace(" ", "")
    urls_file = Path(TRAILERS_DIR) / f"{safe_sheet}Urls.json"
    if urls_file.exists():
        try:
            with urls_file.open("r", encoding="utf-8") as f:
                url_dict = json.load(f)
            normalized_dict = {normalize(k): v for k, v in url_dict.items()}
            key = normalize(movie_title)
            matched_url = (
                normalized_dict.get(key)
                or normalized_dict.get(fuzzy_search(key, list(normalized_dict.keys())) or '')
            )
            if matched_url and "youtube.com" in matched_url:
                return matched_url, "json", None
            elif matched_url:
                return matched_url, "json", None
        except json.JSONDecodeError as e:
            log_debug(f"[ERROR] JSON decoding failed: {e}")

    # Fallback single YouTube search if not found in JSON
    api_result = youtube_api_search(movie_title + " official hd trailer")
    if api_result:
        api_url, yt_video_title = api_result
        return api_url, "youtube", yt_video_title

    return None, "", None


# ---------------- YOUTUBE PLAYLIST CREATION ---------------- #
def get_youtube_service():
    """
    Create and return an authorized YouTube Data API client using OAuth (user-level).
    Reuses credentials in 'youtube_token.pickle'.
    """
    creds = None
    YOUTUBE_TOKEN_FILE = BASE_DIR / "youtube_token.pickle"
    if YOUTUBE_TOKEN_FILE.exists():
        with open(YOUTUBE_TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(YOUTUBE_TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)


def create_youtube_playlist(title: str, video_ids: List[str]) -> Optional[str]:
    """
    Create an unlisted YouTube playlist named 'title' and populate it with video_ids.
    Return the playlist URL or None on failure.
    """
    try:
        youtube = get_youtube_service()
        playlist = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": "Auto-generated playlist by Movie Picker App",
                },
                "status": {"privacyStatus": "unlisted"}
            },
        ).execute()

        playlist_id = playlist["id"]
        for vid in video_ids:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": vid
                        }
                    }
                },
            ).execute()

        return f"https://www.youtube.com/playlist?list={playlist_id}"
    except Exception as e:
        log_debug(f"[ERROR] YouTube playlist creation failed: {e}")
    return None


def pick_random_movies(movies: List[str], count: int) -> List[str]:
    """Randomly sample 'count' distinct movies from the 'movies' list."""
    return random.SystemRandom().sample(movies, k=count)

        
class PickerPage(QWidget):
    """Left: picker; Right: controls & images."""
    def __init__(self, parent: "MainWindow"):
        super().__init__()
        self.win = parent

        outer = QHBoxLayout(self)

        # ---------- left controls ----------
        ctrl = QVBoxLayout()
        self.attendees_in = QLineEdit();  self.attendees_in.setPlaceholderText("# attendees")
        self.sheet_in     = QLineEdit();  self.sheet_in.setPlaceholderText("Sheet name")
        gen_btn = QPushButton("Generate Movies")
        upd_btn = QPushButton("Update URLs")
        gen_btn.clicked.connect(self.win.generate_movies)
        upd_btn.clicked.connect(self.win.update_urls)

        ctrl.addWidget(self.attendees_in)
        ctrl.addWidget(self.sheet_in)
        ctrl.addWidget(gen_btn)
        ctrl.addWidget(upd_btn)
        ctrl.addStretch()
        outer.addLayout(ctrl, 0)

        # ---------- middle: scroll area with movie labels ----------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.list_container)
        outer.addWidget(self.scroll, 2)

        # ---------- right: extra widgets ----------
        right = QVBoxLayout()
        self.stats_lbl  = QLabel("", alignment=Qt.AlignCenter)
        self.report_btn = QPushButton("Report Trailers")
        self.report_btn.clicked.connect(self.report_trailers)
        right.addWidget(self.stats_lbl)
        right.addWidget(self.report_btn)
        right.addStretch()
        outer.addLayout(right, 0)
    # −−− helpers −−−#
def populate(self, movies: list[str], trailer_lookup: dict[str, str]):
    """Replace current list with HTML links + probability badges."""
    # clear previous widgets
    while (child := self.list_layout.takeAt(0)):
        if child.widget():
            child.widget().deleteLater()

    for title in movies:
        url   = trailer_lookup.get(title, "")
        prob  = f"{movie_prob(title):.02f}"

        if not url:                     # no trailer at all → plain grey text
            html = f'<span style="color:#888">{title} (no trailer)</span> '\
                   f'<span style="color:#aaa">({prob})</span>'
            lbl = QLabel(html)
            lbl.setTextFormat(Qt.RichText)
        else:
            colour = "#ffa500" if "youtube.com" in url else "#ffffff"
            html   = (
                f'<a href="{url}" style="text-decoration:none;color:{colour};">'
                f'{title}</a> &nbsp;<span style="color:#aaa">({prob})</span>'
            )
            lbl = QLabel(html)
            lbl.setTextFormat(Qt.RichText)
            lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
            lbl.setOpenExternalLinks(False)     # we open manually
            # • capture 'url' NOW so late-binding doesn’t bite
            lbl.linkActivated.connect(
                lambda _ignored, link=url: QDesktopServices.openUrl(QUrl(link))
            )

        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.list_layout.addWidget(lbl)

class StatsPage(QWidget):
    """Shows historical stats (placeholder demo)."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Movie", "Times Picked", "Avg. Score"])
        lay.addWidget(self.table)

    def load_stats(self, stats: list[tuple[str,int,float]]):
        self.table.setRowCount(len(stats))
        for r,(m,c,s) in enumerate(stats):
            self.table.setItem(r,0,QTableWidgetItem(m))
            self.table.setItem(r,1,QTableWidgetItem(str(c)))
            self.table.setItem(r,2,QTableWidgetItem(f"{s:.2f}")) 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Night")
        self.resize(960, 600)

        # sidebar navigation
        self.nav   = QListWidget();  self.nav.setFixedWidth(170)
        self.pages = QStackedWidget()
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        # pages
        self.picker = PickerPage(self);  self.add_page("Picker", "grid")
        self.stats  = StatsPage();       self.add_page("Stats",  "bar")

        # layout
        body = QSplitter();  body.setHandleWidth(1)
        body.addWidget(self.nav);  body.addWidget(self.pages);  body.setStretchFactor(1,1)
        self.setCentralWidget(body)

        # toolbar actions
        self.new_act = QAction(ICON("refresh"), "Re-roll", self)
        self.new_act.setShortcut("Ctrl+R")
        self.new_act.triggered.connect(self.generate_movies)
        self.addToolBar("Main").addAction(self.new_act)

    def add_page(self, name: str, ico: str):
        self.nav.addItem(QListWidgetItem(ICON(ico), f"  {name}"))
        self.pages.addWidget(getattr(self, name.lower()))
#----------------Button Callbacks ----------#    
    @Slot()
    def update_urls(self):
        """
        When the user clicks "Update Sheets":
        1) Call autoUpdate.py (which handles the entire updating logic).
        """
        try:
            subprocess.run(["python", str(auto_update_script)], check=True)
            log_debug("[INFO] Ran autoUpdate.py successfully.")
            messagebox.showinfo("Sheets Updated", "Sheets + JSON updated successfully.")
        except Exception as e:
            log_debug(f"[ERROR] Failed running autoUpdate.py: {e}")
            QMessageBox.warning(self,"Error", f"Failed running autoUpdate.py: {e}")
    @Slot()
    def generate_movies(self):
        from difflib import get_close_matches
        raw_attendees = self.attendees_in.text().strip()
        try:
            attendee_count = int(raw_attendees)
            if attendee_count <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
            self, "Input error",
            "Enter a positive whole number for the number of attendees.")
            return

        raw_sheet_input = self.sheet_in.text().strip()
        if not raw_sheet_input:
            return QMessageBox.warning(self,"Error", "Provide a valid sheet name.")

        # Make sure local XLSX is present. 
        if not GHIB_FILE.exists():
            return QMessageBox.warning(self,"Error", "No local XLSX found. Try 'Update Sheets' first.")

        # Load local sheets from the xlsx
        wb = openpyxl.load_workbook(GHIB_FILE, read_only=True)
        all_local_sheets = wb.sheetnames

        # Build a normalized map for fuzzy searching
        sheet_map = {}
        for s in all_local_sheets:
            norm = re.sub(r"\s+", "", s.lower())
            sheet_map[norm] = s

        user_normal = re.sub(r"\s+", "", raw_sheet_input.lower())
        chosen_sheet = sheet_map.get(user_normal)

        if not chosen_sheet:
            # If no direct match, do fuzzy
            possible_keys = list(sheet_map.keys())
            best_key = fuzzy_search(user_normal, possible_keys, cutoff=0.8)
            if best_key:
                chosen_sheet = sheet_map[best_key]

        if not chosen_sheet:
            return QMessageBox.warning(self,"Error", f"No local sheet matched '{raw_sheet_input}' (80% cutoff).")

        # Now we have a valid sheet
        sheet = wb[chosen_sheet]
        movies = []
        for row in sheet.iter_rows(min_row=1, max_col=1, values_only=True):
            val = row[0]
            if val and str(val).strip():
                movies.append(str(val).strip())
        if not movies or attendee_count > len(movies):
            return QMessageBox.warning(self,"Error", f"Insufficient movie data in sheet '{chosen_sheet}'.")
        # Randomly pick movies
        selected_movies = pick_random_movies(movies, attendee_count + 1)
        playlist_video_ids = []
        trailer_lookup = {m: locate_trailer(chosen_sheet, m)[0]
                  for m in selected_movies}

        
        #build video-id list for the playlist
        for m, url in trailer_lookup.items():
            if url and "youtube.com/watch?v=" in url:
                vid = url.split("v=")[-1].split("&")[0]
                playlist_video_ids.append(vid)

        #update UI  (shows links + probability badge)
        self.picker.populate(selected_movies, trailer_lookup)

        # 5) optional stats page refresh
        self.stats.load_stats([
            (m, random.randint(1, 12), random.uniform(1, 5))
            for m in selected_movies
        ])

        # 6) make + open playlist
        if playlist_video_ids:
            title = f"Movie Night {datetime.date.today()}"
            url = create_youtube_playlist(title, playlist_video_ids)
            if url:
                QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(self, "No Trailers", "No valid trailers found.")

        # 7) hand data to the Report button
        self.picker.enable_report_button(selected_movies, trailer_lookup)
# ---------------- MAIN APP---------------- #
def main():
    app = QApplication([])
    import qdarktheme;  qdarktheme.setup_theme("dark", corner_shape="rounded", custom_colors={"primary": ACCENT})
    win = MainWindow();  win.show()
    app.exec()

if __name__ == "__main__":
    main()
