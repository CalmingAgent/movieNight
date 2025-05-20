# gui/main_window.py
from __future__ import annotations
import datetime, random, urllib.parse, sys

from PySide6.QtCore    import Qt, Slot
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QMainWindow, QListWidget, QListWidgetItem,
    QStackedWidget, QSplitter, QMessageBox
)

from ..settings       import ICON
from .picker_page     import PickerPage
from .stat_page       import StatsPage
from .controller      import (
    generate_movies,
    update_data,                       # “Update XLSX + DB” button, still here
    start_update_metadata,
    start_update_urls,
    add_remove_movie
)
from .movie_card      import MovieCard
from metadata         import repo

# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Night")
        self.resize(960, 600)

        # ── pages ----------------------------------------------------------
        self.picker_page = PickerPage(self)
        self.stats_page  = StatsPage()

        # ── sidebar --------------------------------------------------------
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(170)
        for icon_name, label in [
            ("grid", "RNJesus"),
            ("bar-chart-line", "Maintenance"),
        ]:
            item = QListWidgetItem(ICON(icon_name), label)
            item.setTextAlignment(Qt.AlignHCenter)
            self.nav_list.addItem(item)

        # ── stacked widget -------------------------------------------------
        self.pages = QStackedWidget()
        self.pages.addWidget(self.picker_page)
        self.pages.addWidget(self.stats_page)
        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)

        splitter = QSplitter()
        splitter.addWidget(self.nav_list)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # ── toolbar --------------------------------------------------------
        tb = self.addToolBar("Main")
        act = QAction(ICON("refresh"), "Re-roll", self)
        act.setShortcut("Ctrl+R")
        act.triggered.connect(self._on_generate)
        tb.addAction(act)

        # ── connect StatsPage buttons → controller helpers -----------------
        sp = self.stats_page
        sp.request_update_meta.connect(
            lambda full: start_update_metadata(full, sp)
        )
        sp.request_update_urls.connect(
            lambda full: start_update_urls(full, sp)
        )

    # ======================================================================
    # Slots
    # ======================================================================
    @Slot()
    def _on_update(self):
        """Manually invoke full update_data() (XLSX sync)."""
        update_data()
        QMessageBox.information(self, "Update complete",
                                "Spreadsheet themes & trailers refreshed.")

    @Slot()
    def _on_generate(self):
        """Validate UI, call generate_movies(), update grid or show error."""
        try:
            attendee_count = int(self.picker_page.attendee_input.text().strip())
            sheet_name     = self.picker_page.sheet_input.text().strip()
            picks, trailer_map = generate_movies(sheet_name, attendee_count)
        except ValueError as err:
            QMessageBox.warning(self, "Error", str(err))
            return

        # cache pool for +/- buttons
        self._all_titles_for_sheet = [
            repo.by_id(mid).title
            for mid in repo.ids_for_sheet(sheet_name)
        ]
        self._last_titles = picks
        self.picker_page.display_movies(picks, trailer_map)

    @Slot(int)
    def _on_add_remove(self, delta: int):
        cur  = [w.title() for w in self.picker_page.findChildren(MovieCard)]
        pool = getattr(self, "_all_titles_for_sheet", [])
        if not pool:
            return
        new  = add_remove_movie(cur, pool, delta)
        self.picker_page.display_movies(
            new, {t: repo.by_id(repo.get_movie_id_by_title(t)).youtube_link for t in new}
        )
