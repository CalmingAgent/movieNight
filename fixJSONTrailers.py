#script for replacing URL's Manually, if Broken or the wrong linkimport tkinter as tk
import tkinter as tk
import json
import os
import re
from pathlib import Path


# ---------------- CONFIGURATION ---------------- #
BASE_DIR = Path(__file__).resolve().parent
UNDER_REVIEW_FILE = BASE_DIR / "underReviewURLs.json"
TRAILERS_DIR = BASE_DIR / "Video_Trailers"
BACKGROUND_COLOR = "#2e2e2e"
FOREGROUND_COLOR = "#e0e0e0"
ENTRY_COLOR = "#5c5c5c"
BUTTON_COLOR = "#444444"

# ---------------- HELPERS ---------------- #
def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.strip().lower())

def load_under_review():
    try:
        with open(UNDER_REVIEW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def update_json_files(updated_map):
    for json_file in TRAILERS_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            changed = False
            for original_title, new_url in updated_map.items():
                for k in list(data.keys()):
                    if normalize(k) == normalize(original_title):
                        data[k] = new_url
                        changed = True
            if changed:
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            continue

# ---------------- GUI SETUP ---------------- #
def open_update_gui():
    root = tk.Tk()
    root.title("Update Reported Trailer URLs")
    root.configure(bg=BACKGROUND_COLOR)

    frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    frame.pack(padx=10, pady=10)

    tk.Label(frame, text="Update YouTube URLs for Reported Movies:", fg=FOREGROUND_COLOR, bg=BACKGROUND_COLOR).pack(pady=5)

    entries = {}
    reported = load_under_review()

    for movie, old_url in reported.items():
        row = tk.Frame(frame, bg=BACKGROUND_COLOR)
        row.pack(fill="x", pady=2)
        label = tk.Label(row, text=movie, width=40, anchor="w", bg=BACKGROUND_COLOR, fg=FOREGROUND_COLOR)
        label.pack(side="left")
        entry = tk.Entry(row, width=60, bg=ENTRY_COLOR, fg=FOREGROUND_COLOR, insertbackground=FOREGROUND_COLOR)
        entry.insert(0, old_url)
        entry.pack(side="right", fill="x", expand=True)
        entries[movie] = entry

    def apply_updates():
        updates = {movie: ent.get().strip() for movie, ent in entries.items() if ent.get().strip()}
        update_json_files(updates)
        messagebox.showinfo("Success", "All JSON files updated successfully.")
        root.destroy()

    tk.Button(
        frame,
        text="Apply Updates",
        command=apply_updates,
        bg=BUTTON_COLOR,
        fg=FOREGROUND_COLOR
    ).pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    open_update_gui()
