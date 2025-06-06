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

# --------------------- CONFIGURATION --------------------- #
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "secret.env"
TRAILERS_DIR = BASE_DIR / "Video_Trailers"
PLAYLIST_DIR = BASE_DIR / "VLC_playlist"
NUMBERS_DIR = BASE_DIR / "Numbers"
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "service_secret.json"
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
VLC_EXE_PATH = Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe")

# ----------------- ENVIRONMENT LOADING ------------------- #
load_dotenv(ENV_PATH)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise EnvironmentError("Missing Spreadsheet ID in secret.env")

# ---------------- UTILS ---------------- #
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*-]', '', name.strip())

def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.strip().lower())

# ---------------- GOOGLE SHEETS ---------------- #
def get_sheet_service():
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SHEETS_SCOPES)
    return build("sheets", "v4", credentials=creds)

def fetch_movie_list(sheet_name):
    service = get_sheet_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A:A"
    ).execute()
    return [row[0].strip() for row in result.get("values", []) if row and row[0].strip()]

# ---------------- MOVIE / IMAGE RANDOMIZER ---------------- #
def pick_random_movies(movies, count):
    return random.SystemRandom().sample(movies, k=count)

def load_random_image(directory, prefix, max_num):
    path = directory / f"{prefix}_{random.randint(1, max_num)}.png"
    return ImageTk.PhotoImage(Image.open(path)) if path.exists() else None

def load_direction_image():
    direction = random.choice(["clockwise", "counter_clockwise"])
    path = NUMBERS_DIR / f"{direction}.png"
    return ImageTk.PhotoImage(Image.open(path)) if path.exists() else None

# ---------------- TRAILER HANDLING ---------------- #
def get_stable_youtube_url(youtube_url):
    try:
        with YoutubeDL({'quiet': True, 'skip_download': True, 'format': 'best[ext=mp4]'}) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return info.get('url', youtube_url)
    except Exception as e:
        print(f"[ERROR] yt-dlp failed: {e}")
        return youtube_url

def locate_trailer(sheet_name, movie_title):
    trailer_dir = TRAILERS_DIR / sheet_name.strip()
    movie_title_clean = movie_title.strip()
    safe_movie_filename = sanitize_filename(movie_title_clean)

    local_file = trailer_dir / f"{safe_movie_filename}.mp4"
    if local_file.exists():
        return str(local_file)

    urls_file = trailer_dir / "urls.json"
    if urls_file.exists():
        try:
            with urls_file.open(encoding="utf-8") as f:
                url_dict = json.load(f)
            normalized_dict = {normalize(k.strip()): v for k, v in url_dict.items()}
            url = normalized_dict.get(normalize(movie_title_clean))
            return get_stable_youtube_url(url) if url and "youtube.com" in url else url
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decoding failed: {e}")
    return None

# ---------------- PLAYLIST CREATION ---------------- #
def create_m3u(filepath, items):
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

    for movie in selected_movies:
        trailer = locate_trailer(sheet, movie)
        label = tk.Label(middle_frame, text=movie, fg="blue", cursor="hand2", wraplength=280, justify="left")
        label.pack(anchor="w", pady=2)

        if trailer:
            playlist_items.append((movie, trailer))
            label.bind("<Button-1>", lambda e, url=trailer: webbrowser.open(url))
        else:
            label.config(text=f"{movie}: No trailer found")

    if playlist_items:
        PLAYLIST_DIR.mkdir(exist_ok=True)
        playlist_path = PLAYLIST_DIR / f"{datetime.date.today()}_Movie_Night.m3u"
        create_m3u(playlist_path, playlist_items)

        try:
            command = [
                str(VLC_EXE_PATH),
                "--one-instance",
                str(playlist_path),
                "--playlist-autostart",
                "--loop",
                "--fullscreen",
                "--verbose=2"
            ]
            subprocess.Popen(command)
        except Exception as e:
            print(f"[ERROR launching VLC]: {e}")
    else:
        messagebox.showinfo("No Trailers", "No valid trailers found.")

    if (direction_img := load_direction_image()):
        dir_label = tk.Label(right_frame, image=direction_img)
        dir_label.image = direction_img
        dir_label.pack(pady=10)

    if (number_img := load_random_image(NUMBERS_DIR, "number", attendee_count)):
        num_label = tk.Label(right_frame, image=number_img)
        num_label.image = number_img
        num_label.pack(pady=10)

# ---------------- MAIN APP WITH SCROLL ---------------- #
root = tk.Tk()
root.title("Random Movie Picker")

left_frame = tk.Frame(root, padx=10, pady=10)
left_frame.pack(side="left", fill="y")

# Scrollable middle frame
middle_container = tk.Frame(root, padx=10, pady=10)
middle_container.pack(side="left", fill="both", expand=True)

middle_canvas = tk.Canvas(middle_container)
middle_canvas.pack(side="left", fill="both", expand=True)

scrollbar = tk.Scrollbar(middle_container, orient="vertical", command=middle_canvas.yview)
scrollbar.pack(side="right", fill="y")

middle_canvas.configure(yscrollcommand=scrollbar.set)
middle_canvas.bind('<Configure>', lambda e: middle_canvas.configure(scrollregion=middle_canvas.bbox("all")))

middle_frame = tk.Frame(middle_canvas)
middle_canvas.create_window((0, 0), window=middle_frame, anchor="nw")

# Optional: Mousewheel support
middle_canvas.bind_all("<MouseWheel>", lambda e: middle_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

right_frame = tk.Frame(root, padx=10, pady=10)
right_frame.pack(side="right", fill="y")

tk.Label(middle_frame, text="Movie Names").pack()
tk.Label(right_frame, text="Direction & Starting Pos").pack()

tk.Label(left_frame, text="Number of Attendees:").pack(pady=5)
num_people_entry = tk.Entry(left_frame)
num_people_entry.pack(pady=5)

tk.Label(left_frame, text="Sheet Name:").pack(pady=5)
sheet_name_entry = tk.Entry(left_frame)
sheet_name_entry.pack(pady=5)

tk.Button(left_frame, text="Start", command=on_start).pack(pady=10)

root.bind('<Return>', on_start)

center_window(root)
root.mainloop()
