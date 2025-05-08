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
from .button_logic    import generate_movies, update_trailer_urls
from .picker_page     import PickerPage
from .stat_page       import StatsPage
from metadata.service import MovieNightDB


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
        update_trailer_urls()
        QMessageBox.information(self, "Update Complete", "Trailer URLs have been refreshed.")

    @Slot()
    def _on_generate(self):
        """Gather input, call button_logic.generate_movies, update UI or show errors."""
        try:
            titles, lookup = generate_movies(
                self.picker_page.attendee_input.text(),
                self.picker_page.sheet_input.text(),
                self
            )
        except ValueError as err:
            QMessageBox.warning(self, "Input Error", str(err))
            return

        self.picker_page.display_movies(titles, lookup)
