# Refactored and Cleaned Up Movie Picker App with YouTube API Fallback and Displaying YouTube Video Titles
import os
import re
import json
import random
import webbrowser
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from PIL import Image, ImageTk
from yt_dlp import YoutubeDL
import datetime
from difflib import get_close_matches
from typing import Optional, List
import requests

# --------------------- CONFIGURATION --------------------- #
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "secret.env"
TRAILERS_DIR = BASE_DIR / "Video_Trailers"
PLAYLIST_DIR = BASE_DIR / "VLC_playlist"
NUMBERS_DIR = BASE_DIR / "Numbers"
LOG_FILE = BASE_DIR / "trailer_debug.log"
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "service_secret.json"
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
VLC_EXE_PATH = Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe")
MOVIE_SHEET_RANGE = "!A:A"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# -------------DARK MODE THEME COLORS --------------------- #
BACKGROUND_COLOR = "#2e2e2e"
FOREGROUND_COLOR = "#e0e0e0"
BUTTON_COLOR = "#444444"
HIGHLIGHT_COLOR = "#5c5c5c"
ERROR_COLOR = "#ff4c4c"
FALLBACK_COLOR = "#ffa500"

# ----------------- ENVIRONMENT LOADING ------------------- #
load_dotenv(ENV_PATH)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not SPREADSHEET_ID:
    raise EnvironmentError("Missing Spreadsheet ID in secret.env")
if not YOUTUBE_API_KEY:
    raise EnvironmentError("Missing YOUTUBE_API_KEY in secret.env")

# ---------------- UTILS ---------------- #
def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*-]', '', name.strip())

def normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.strip().lower())

def fuzzy_search(target: str, candidates: List[str]) -> Optional[str]:
    matches = get_close_matches(target, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None

def log_debug(message: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"{message}\n")

def youtube_api_search(query: str) -> Optional[tuple]:
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

# ---------------- GOOGLE SHEETS ---------------- #
def get_sheet_service():
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SHEETS_SCOPES)
    return build("sheets", "v4", credentials=creds)

def fetch_movie_list(sheet_name: str) -> List[str]:
    service = get_sheet_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}{MOVIE_SHEET_RANGE}"
    ).execute()
    return [row[0].strip() for row in result.get("values", []) if row and row[0].strip()]

# ---------------- MOVIE / IMAGE RANDOMIZER ---------------- #
def pick_random_movies(movies: List[str], count: int) -> List[str]:
    return random.SystemRandom().sample(movies, k=count)

def load_random_image(directory: Path, prefix: str, max_num: int):
    path = directory / f"{prefix}_{random.randint(1, max_num)}.png"
    return ImageTk.PhotoImage(Image.open(path)) if path.exists() else None

def load_direction_image():
    direction = random.choice(["clockwise", "counter_clockwise"])
    path = NUMBERS_DIR / f"{direction}.png"
    return ImageTk.PhotoImage(Image.open(path)) if path.exists() else None

# ---------------- TRAILER HANDLING ---------------- #
def get_stable_youtube_url(youtube_url: str) -> str:
    try:
        with YoutubeDL({'quiet': True, 'skip_download': True, 'format': 'best'}) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return info.get('url', youtube_url)
    except Exception as e:
        log_debug(f"[ERROR] yt-dlp failed: {e}")
        return youtube_url

def locate_trailer(sheet_name: str, movie_title: str) -> (Optional[str], str, Optional[str]):
    trailer_dir = TRAILERS_DIR / sheet_name.strip()
    safe_movie_filename = sanitize_filename(movie_title.strip())

    local_file = trailer_dir / f"{safe_movie_filename}.mp4"
    if local_file.exists():
        return str(local_file), "file", None

    urls_file = trailer_dir / "urls.json"
    if urls_file.exists():
        try:
            with urls_file.open(encoding="utf-8") as f:
                url_dict = json.load(f)
            normalized_dict = {normalize(k): v for k, v in url_dict.items()}
            key = normalize(movie_title)
            url = normalized_dict.get(key) or normalized_dict.get(fuzzy_search(key, list(normalized_dict.keys())) or '')
            if url and "youtube.com" in url:
                return get_stable_youtube_url(url), "json", None
            elif url:
                return url, "json", None
        except json.JSONDecodeError as e:
            log_debug(f"[ERROR] JSON decoding failed: {e}")

    mp4_files = list(trailer_dir.glob("*.mp4"))
    file_candidates = [normalize(f.stem) for f in mp4_files]
    fuzzy_file = fuzzy_search(normalize(movie_title), file_candidates)
    if fuzzy_file:
        matched_file = next((f for f in mp4_files if normalize(f.stem) == fuzzy_file), None)
        if matched_file:
            return str(matched_file), "fuzzy", None

    api_result = youtube_api_search(movie_title + " official trailer")
    if api_result:
        api_url, yt_video_title = api_result
        return get_stable_youtube_url(api_url), "youtube", yt_video_title

    return None, "", None

# ---------------- PLAYLIST CREATION ---------------- #
def create_m3u(filepath: Path, items: List[tuple]) -> None:
    if not PLAYLIST_DIR.exists():
        PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title, trailer in items:
            trailer_path = trailer if trailer.startswith("http") else f"file:///{trailer.replace(os.sep, '/')}"
            f.write(f"#EXTINF:-1,{title.strip()}\n{trailer_path}\n")

# ---------------- GUI SETUP ---------------- #
def center_window(window, width=800, height=800):
    screen_width, screen_height = window.winfo_screenwidth(), window.winfo_screenheight()
    x, y = (screen_width - width) // 2, (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# ---------------- BUTTON LOGIC ---------------- #
def on_start(event=None):
    try:
        attendee_count = int(num_people_entry.get().strip())
        if attendee_count <= 0:
            raise ValueError
    except ValueError:
        return messagebox.showerror("Error", "Enter a positive integer for attendees.")

    sheet = sheet_name_entry.get().strip()
    if not sheet:
        return messagebox.showerror("Error", "Provide a valid sheet name.")

    movies = fetch_movie_list(sheet)
    if not movies or attendee_count > len(movies):
        return messagebox.showerror("Error", "Insufficient movie data in sheet.")

    for frame in (middle_frame, right_frame):
        for widget in frame.winfo_children():
            widget.destroy()

    selected_movies = pick_random_movies(movies, attendee_count + 1)
    playlist_items = []

    col_frame1 = tk.Frame(middle_frame, bg=BACKGROUND_COLOR)
    col_frame1.grid(row=0, column=0, sticky="nw")
    col_frame2 = tk.Frame(middle_frame, bg=BACKGROUND_COLOR)
    col_frame2.grid(row=0, column=1, sticky="nw", padx=20)

    current_column = col_frame1
    lines_in_column = 0
    max_lines_per_column = 20

    for movie in selected_movies:
        trailer, source, yt_video_title = locate_trailer(sheet, movie)
        display_text = movie

        color = "white"
        if source == "youtube" and yt_video_title:
            color = FALLBACK_COLOR
            display_text += f" (YT: {yt_video_title})"

        if trailer:
            label = tk.Label(current_column, text=display_text, fg=color, cursor="hand2", wraplength=280, justify="left", bg=BACKGROUND_COLOR)
            label.pack(anchor="w", pady=2)
            playlist_items.append((movie, trailer))
            label.bind("<Button-1>", lambda e, url=trailer: webbrowser.open(url))
        else:
            label = tk.Label(current_column, text=f"{movie}: No trailer found", fg=ERROR_COLOR, wraplength=280, justify="left", bg=BACKGROUND_COLOR)
            label.pack(anchor="w", pady=2)

        root.update_idletasks()
        lines_in_column += 1
        if lines_in_column * (label.winfo_reqheight() + 4) >= middle_canvas.winfo_height() - 5 and current_column == col_frame1:
            current_column = col_frame2
            lines_in_column = 0

    if playlist_items:
        playlist_path = PLAYLIST_DIR / f"{datetime.date.today()}_Movie_Night.m3u"
        create_m3u(playlist_path, playlist_items)

        try:
            process = subprocess.Popen([
                str(VLC_EXE_PATH),
                "--one-instance",
                str(playlist_path),
                "--playlist-autostart",
                "--loop",
                "--fullscreen",
                "--verbose=2"
            ])
            root.after(100, check_vlc_process, process, attendee_count)
        except Exception as e:
            log_debug(f"[ERROR launching VLC]: {e}")
    else:
        messagebox.showinfo("No Trailers", "No valid trailers found.")


def check_vlc_process(process, attendee_count):
    if process.poll() is None:
        root.after(1000, check_vlc_process, process, attendee_count)
    else:
        if (direction_img := load_direction_image()):
            dir_label = tk.Label(right_frame, image=direction_img, bg=BACKGROUND_COLOR)
            dir_label.image = direction_img
            dir_label.pack(pady=10)

        if (number_img := load_random_image(NUMBERS_DIR, "number", attendee_count)):
            num_label = tk.Label(right_frame, image=number_img, bg=BACKGROUND_COLOR)
            num_label.image = number_img
            num_label.pack(pady=10)

# ---------------- MAIN APP WITH SCROLL AND DARK MODE ---------------- #
root = tk.Tk()
root.title("Random Movie Picker")
root.configure(bg=BACKGROUND_COLOR)

left_frame = tk.Frame(root, padx=10, pady=10, bg=BACKGROUND_COLOR)
left_frame.pack(side="left", fill="y")

middle_container = tk.Frame(root, padx=10, pady=10, bg=BACKGROUND_COLOR)
middle_container.pack(side="left", fill="both", expand=True)

middle_canvas = tk.Canvas(middle_container, bg=BACKGROUND_COLOR, highlightthickness=0)
middle_canvas.pack(side="left", fill="both", expand=True)

scrollbar = tk.Scrollbar(middle_container, orient="vertical", command=middle_canvas.yview, bg=BACKGROUND_COLOR)
scrollbar.pack(side="right", fill="y")

middle_canvas.configure(yscrollcommand=scrollbar.set)
middle_canvas.bind('<Configure>', lambda e: middle_canvas.configure(scrollregion=middle_canvas.bbox("all")))

middle_frame = tk.Frame(middle_canvas, bg=BACKGROUND_COLOR)
middle_canvas.create_window((0, 0), window=middle_frame, anchor="nw")

middle_canvas.bind_all("<MouseWheel>", lambda e: middle_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

right_frame = tk.Frame(root, padx=10, pady=10, bg=BACKGROUND_COLOR)
right_frame.pack(side="right", fill="y")

# Labels and Inputs
tk.Label(middle_frame, text="Movie Names", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR).grid(row=0, column=0, columnspan=2, sticky="nw")
tk.Label(right_frame, text="Direction & Starting Pos", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR).pack()

num_label = tk.Label(left_frame, text="Number of Attendees:", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR)
num_label.pack(pady=5)
num_people_entry = tk.Entry(left_frame, bg=HIGHLIGHT_COLOR, fg=FOREGROUND_COLOR, insertbackground=FOREGROUND_COLOR)
num_people_entry.pack(pady=5)

sheet_label = tk.Label(left_frame, text="Sheet Name:", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR)
sheet_label.pack(pady=5)
sheet_name_entry = tk.Entry(left_frame, bg=HIGHLIGHT_COLOR, fg=FOREGROUND_COLOR, insertbackground=FOREGROUND_COLOR)
sheet_name_entry.pack(pady=5)

start_button = tk.Button(left_frame, text="Start", command=on_start, bg=BUTTON_COLOR, fg=FOREGROUND_COLOR, activebackground=HIGHLIGHT_COLOR)
start_button.pack(pady=10)

root.bind('<Return>', on_start)

center_window(root)
root.mainloop()