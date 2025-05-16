# main_window.py

import random
import urllib.parse
import datetime
import subprocess

from PySide6.QtCore    import Qt, Slot, QUrl
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QMainWindow, QListWidget, QListWidgetItem,
    QStackedWidget, QSplitter, QMessageBox
)

from ..settings        import ICON
from .controller    import add_remove_movie, update_data, generate_movies 
from .picker_page     import PickerPage
from .stat_page       import StatsPage
from metadata.movie_night_db import MovieNightDB
import movie_card


class MainWindow(QMainWindow):
    def __init__(self, db: MovieNightDB):
        super().__init__()
        self.setWindowTitle("Movie Night")
        self.db = db
        self.resize(960, 600)

        # pages
        self.picker_page = PickerPage(self)
        self.stats_page  = StatsPage()

        # sidebar
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(170)
        for icon_name, label in [("grid", "RNJesus"), ("bar-chart-line", "Movie Stats")]:
            item = QListWidgetItem(ICON(icon_name), label)
            item.setTextAlignment(Qt.AlignHCenter)
            self.nav_list.addItem(item)

        # stacked widget
        self.pages = QStackedWidget()
        self.pages.addWidget(self.picker_page)
        self.pages.addWidget(self.stats_page)
        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)

        splitter = QSplitter()
        splitter.addWidget(self.nav_list)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # toolbar
        toolbar = self.addToolBar("Main")
        refresh_action = QAction(ICON("refresh"), "Re-roll", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self._on_generate)
        toolbar.addAction(refresh_action)

    @Slot()
    def _on_update(self):
        """Invoke the Update URLs routine."""
        update_data()
        QMessageBox.information(self, "Update Complete", "Trailer URLs have been refreshed.")

    @Slot()
    def _on_generate(self):
        """Gather input, call button_logic.generate_movies, update UI or show errors."""
        try:
            attendee_count = int(self.picker_page.attendee_input.text().strip())
            picks, trailer_map = generate_movies(
                self.picker_page.sheet_input.text().strip(),
                attendee_count,
            )
        except ValueError as err:
            QMessageBox.warning(self, "Error", str(err))
            return

        self._last_titles = picks                       # so the OK/NG dialog works
        self.picker_page.display_movies(picks, trailer_map)
        
    @Slot()
    def _on_add_remove(self, delta: int):
        cur  = [w.title() for w in self.picker_page.findChildren(movie_card)]
        pool = self._all_titles_for_sheet   # cache set in _on_generate
        new  = add_remove_movie(cur, pool, delta)
        self.picker_page.display_movies(new, {t: locate_trailer("", t)[0] for t in new})
