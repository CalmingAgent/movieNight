# movie_night_qt.py
from __future__ import annotations
import os, re, json, random, subprocess, datetime, pickle, importlib
from pathlib import Path
from typing import Optional, List

import openpyxl
import requests
from dotenv import load_dotenv
from difflib import get_close_matches

from PySide6.QtCore    import Qt, QUrl, Slot
from PySide6.QtGui     import QAction, QIcon, QPalette, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QStackedWidget, QPushButton,
    QLineEdit, QSplitter, QScrollArea, QTableWidget, QTableWidgetItem,
    QDialog, QCheckBox, QDialogButtonBox, QMessageBox
)

# ───────────────────────── configuration ──────────────────────────
BASE_DIR          = Path(__file__).resolve().parent
ENV_PATH          = BASE_DIR / "secret.env"
LOG_FILE          = BASE_DIR / "trailer_debug.log"
auto_update_script= BASE_DIR / "autoUpdate.py"

TRAILERS_DIR = BASE_DIR / "Video_Trailers"
GHIB_FILE    = BASE_DIR / "ghib.xlsx"
UNDER_REVIEW_FILE = BASE_DIR / "underReviewURLs.json"

ICON = lambda n: QIcon(str(BASE_DIR / "icons" / f"{n}.svg"))
ACCENT = "#3b82f6"

# ───────────────────────── environment ────────────────────────────
load_dotenv(ENV_PATH)
SPREADSHEET_ID  = os.getenv("SPREADSHEET_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not SPREADSHEET_ID or not YOUTUBE_API_KEY:
    raise EnvironmentError("Missing SPREADSHEET_ID or YOUTUBE_API_KEY in env")

# ───────────────────────── palette helper ─────────────────────────
def apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window,        QColor("#202124"))
    p.setColor(QPalette.WindowText,    Qt.white)
    p.setColor(QPalette.Base,          QColor("#2b2c2e"))
    p.setColor(QPalette.AlternateBase, QColor("#323336"))
    p.setColor(QPalette.Button,        QColor("#2d2e30"))
    p.setColor(QPalette.ButtonText,    Qt.white)
    p.setColor(QPalette.Text,          Qt.white)
    p.setColor(QPalette.Link,          QColor(ACCENT))
    p.setColor(QPalette.Highlight,     QColor(ACCENT))
    p.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(p)

# ───────────────────────── small utils ────────────────────────────
def log_debug(message: str) -> None:
    """
    Log debug messages to file with a timestamp.
    """
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def normalize(s:str)->str: return re.sub(r'[^a-z0-9]','',s.lower().strip())

def fuzzy_search(t:str, cand:List[str], c=0.8)->Optional[str]:
    m=get_close_matches(t,cand,1,c);return m[0] if m else None

def movie_prob(title:str)->float:
    try: return float(importlib.import_module("probability").get_prob(title))
    except Exception: return 0.0

# ───────────────────────── trailer lookup ─────────────────────────
YOUTUBE_SEARCH_URL="https://www.googleapis.com/youtube/v3/search"
def youtube_api_search(q:str)->Optional[tuple[str,str]]:
    try:
        r=requests.get(YOUTUBE_SEARCH_URL,params={
            "part":"snippet","q":q,"key":YOUTUBE_API_KEY,
            "videoDuration":"short","maxResults":1,"type":"video"})
        j=r.json()
        if j.get("items"):
            vid=j["items"][0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={vid}", j["items"][0]["snippet"]["title"]
    except Exception as e: log_debug(f"YT search err: {e}")
    return None

def locate_trailer(sheet:str,title:str)->tuple[Optional[str],str,Optional[str]]:
    urls_file=TRAILERS_DIR/f"{re.sub(r'\\s+','',sheet)}Urls.json"
    if urls_file.exists():
        data=json.loads(urls_file.read_text(encoding="utf-8"))
        norm={normalize(k):v for k,v in data.items()}
        key=normalize(title)
        url=norm.get(key) or norm.get(fuzzy_search(key,list(norm)) or '')
        if url: return url,"json",None
    res=youtube_api_search(title+" official trailer")
    return (res[0],"youtube",res[1]) if res else (None,"",None)

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

# ───────────────────────── GUI pieces ─────────────────────────────
class ReportDialog(QDialog):
    def __init__(self,parent,movies):
        super().__init__(parent); self.setWindowTitle("Report trailers")
        lay=QVBoxLayout(self); self.box=[]
        for m in movies:
            b=QCheckBox(m); lay.addWidget(b); self.box.append(b)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        lay.addWidget(btns); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
    def selected(self): return [b.text() for b in self.box if b.isChecked()]

class PickerPage(QWidget):
    def __init__(self,parent:"MainWindow"):
        super().__init__(); self.win=parent
        outer=QHBoxLayout(self)

        # left controls
        ctrl=QVBoxLayout()
        self.att_in,QInt=QLineEdit(),QLineEdit()
        self.att_in.setPlaceholderText("# attendees")
        self.sheet_in=QLineEdit(); self.sheet_in.setPlaceholderText("Sheet name")
        gen=QPushButton("Generate Movies"); gen.clicked.connect(parent.generate_movies)
        upd=QPushButton("Update URLs");    upd.clicked.connect(parent.update_urls)
        for w in (self.att_in,self.sheet_in,gen,upd): ctrl.addWidget(w)
        ctrl.addStretch(); outer.addLayout(ctrl)

        # middle list
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self.container=QWidget(); self.vlay=QVBoxLayout(self.container); self.vlay.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container); outer.addWidget(self.scroll,2)

        # right side
        rlay=QVBoxLayout()
        self.stats_lbl=QLabel("",alignment=Qt.AlignCenter)
        self.report_btn=QPushButton("Report Trailers"); self.report_btn.setEnabled(False)
        self.report_btn.clicked.connect(self.report_trailers)
        rlay.addWidget(self.stats_lbl); rlay.addWidget(self.report_btn); rlay.addStretch()
        outer.addLayout(rlay)

    # called by MainWindow
    def populate(self,movies,tr_lookup):
        while (item:=self.vlay.takeAt(0)): item.widget().deleteLater()
        self._movies,self._lookup=movies,tr_lookup
        for m in movies:
            url=tr_lookup.get(m,""); p=f"{movie_prob(m):.02f}"
            if url:
                col="#ffa500" if "youtube" in url else "#fff"
                html=f'<a href="{url}" style="color:{col};text-decoration:none">{m}</a> <span style="color:#aaa">({p})</span>'
                lbl=QLabel(html); lbl.setTextFormat(Qt.RichText)
                lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
                lbl.setOpenExternalLinks(False)
                lbl.linkActivated.connect(lambda _,link=url:QDesktopServices.openUrl(QUrl(link)))
            else:
                lbl=QLabel(f'<span style="color:#888">{m} (no trailer)</span> <span style="color:#aaa">({p})</span>',textFormat=Qt.RichText)
            lbl.setWordWrap(True); self.vlay.addWidget(lbl)
        self.report_btn.setEnabled(bool(movies))

    @Slot()
    def report_trailers(self):
        dlg=ReportDialog(self,self._movies)
        if dlg.exec()==QDialog.Accepted:
            for m in dlg.selected():
                report_trailer(m,self._lookup.get(m,""))
            QMessageBox.information(self,"Reported","Thanks for the feedback!")

class StatsPage(QWidget):
    def __init__(self): super().__init__(); self.table=QTableWidget(0,3)
    def load_stats(self,data): ...

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Movie Night"); self.resize(960,600)
        self.picker, self.stats = PickerPage(self), StatsPage()
        self.nav=QListWidget(); self.nav.setFixedWidth(170)
        self.pages=QStackedWidget()
        for name,ico,widget in (("Picker","grid",self.picker),("Stats","bar",self.stats)):
            self.nav.addItem(QListWidgetItem(ICON(ico),f"  {name}")); self.pages.addWidget(widget)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        sp=QSplitter(); sp.addWidget(self.nav); sp.addWidget(self.pages); sp.setStretchFactor(1,1)
        self.setCentralWidget(sp)
        tb=self.addToolBar("Main")
        act=QAction(ICON("refresh"),"Re-roll",self); act.setShortcut("Ctrl+R"); act.triggered.connect(self.generate_movies); tb.addAction(act)

    # ─── buttons ───────────────────────────────────────────────
    @Slot() 
    def update_urls(self): subprocess.run(["python",auto_update_script],check=False)

    @Slot()
    def generate_movies(self):
        try: n=int(self.picker.att_in.text().strip()); assert n>0
        except Exception: return QMessageBox.warning(self,"Error","Enter a positive attendee count.")
        sheet_name=self.picker.sheet_in.text().strip()
        if not sheet_name: return QMessageBox.warning(self,"Error","Sheet name?")
        if not GHIB_FILE.exists(): return QMessageBox.warning(self,"Error","Run Update URLs first.")

        wb=openpyxl.load_workbook(GHIB_FILE,read_only=True)
        sheets={normalize(s):s for s in wb.sheetnames}
        chosen=sheets.get(normalize(sheet_name)) or sheets.get(fuzzy_search(normalize(sheet_name),list(sheets)))
        if not chosen: return QMessageBox.warning(self,"Error","Sheet not found.")
        movies=[r[0] for r in wb[chosen].iter_rows(min_row=1,max_col=1,values_only=True) if r[0]]
        if n+1>len(movies): return QMessageBox.warning(self,"Error","Not enough movies.")
        pick=random.sample(movies,n+1)
        lookup={m:locate_trailer(chosen,m)[0] for m in pick}

        # build playlist
        ids=[u.split("v=")[-1].split("&")[0] for u in lookup.values() if u and "watch?v=" in u]
        if ids:
            url=create_youtube_playlist(f"Movie Night {datetime.date.today()}",ids)
            if url: QDesktopServices.openUrl(QUrl(url))
        self.picker.populate(pick,lookup)
# ───────────────────────── entry - point ─────────────────────────
def main():
    app=QApplication([]); apply_dark_palette(app)
    MainWindow().show(); app.exec()

if __name__=="__main__": main()
