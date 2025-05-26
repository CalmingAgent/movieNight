from __future__ import annotations
import random
import datetime

from PySide6.QtGui import QPainter, QBrush, QPen
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Slot
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QGridLayout, QProgressBar, QLabel,
    QDialog, QCheckBox, QDialogButtonBox, QToolButton,
    QComboBox, QFormLayout, QGroupBox, QFrame
)

from ..settings import ICON, ACCENT_COLOR
from ..utils import make_number_pixmap, open_url_host_browser
from metadata import repo
from metadata.analytics.similarity import calculate_similarity
from metadata.analytics.scoring import (
    calculate_weighted_totals,
    calculate_probability_to_watch,
    calculate_expected_grade,
)
from .movie_card import MovieCard
from .controller import generate_movies, add_remove_movie


class RangeSlider(QWidget):
    """
    A horizontal slider with two handles (lower & upper) to pick a continuous range.
    Emits `rangeChanged(lower: int, upper: int)`.
    """
    rangeChanged = Signal(int, int)

    def __init__(self, minimum: int, maximum: int, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._lo = minimum
        self._hi = maximum
        self.setMinimumHeight(40)
        self._dragging: str | None = None

    def lower(self) -> int:
        return self._lo

    def upper(self) -> int:
        return self._hi

    def setRange(self, lo: int, hi: int) -> None:
        self._lo = max(self._min, min(lo, self._max))
        self._hi = max(self._min, min(hi, self._max))
        if self._lo > self._hi:
            self._lo, self._hi = self._hi, self._lo
        self.rangeChanged.emit(self._lo, self._hi)
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        w = self.width()
        h = self.height()
        groove_y = h // 2 - 4
        # draw groove
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(Qt.lightGray))
        p.drawRect(0, groove_y, w, 8)
        # draw selected span
        lo_x = int((self._lo - self._min) / (self._max - self._min) * w)
        hi_x = int((self._hi - self._min) / (self._max - self._min) * w)
        p.setBrush(QBrush(QBrush(ACCENT_COLOR)))
        p.drawRect(lo_x, groove_y, hi_x - lo_x, 8)
        # draw handles
        for x in (lo_x, hi_x):
            p.setBrush(QBrush(Qt.white))
            p.setPen(QPen(Qt.darkGray))
            p.drawEllipse(QPointF(x, groove_y + 4), 8, 8)

    def mousePressEvent(self, ev) -> None:
        x = ev.pos().x()
        w = self.width()
        lo_x = (self._lo - self._min) / (self._max - self._min) * w
        hi_x = (self._hi - self._min) / (self._max - self._min) * w
        self._dragging = 'lo' if abs(x - lo_x) < abs(x - hi_x) else 'hi'

    def mouseMoveEvent(self, ev) -> None:
        if not self._dragging:
            return
        x = ev.pos().x()
        frac = min(max(x / self.width(), 0.0), 1.0)
        val = round(self._min + frac * (self._max - self._min))
        if self._dragging == 'lo':
            self._lo = min(val, self._hi)
        else:
            self._hi = max(val, self._lo)
        self.rangeChanged.emit(self._lo, self._hi)
        self.update()

    def mouseReleaseEvent(self, ev) -> None:
        self._dragging = None


class FilterDialog(QDialog):
    """
    Modern filter dialog for refining "Random" movie picks.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Filters")
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Duration checkboxes
        self.chk_short = QCheckBox("< 1 hr")
        self.chk_medium = QCheckBox("1–2 hrs")
        self.chk_long = QCheckBox("> 2 hrs")
        dur_box = QHBoxLayout()
        for chk in (self.chk_short, self.chk_medium, self.chk_long):
            dur_box.addWidget(chk)
        form.addRow("Duration:", dur_box)

        # Rating checkboxes
        self.rating_checks: dict[int, QCheckBox] = {}
        rate_box = QHBoxLayout()
        for r in range(1, 11):
            cb = QCheckBox(str(r))
            self.rating_checks[r] = cb
            rate_box.addWidget(cb)
        form.addRow("Rating:", rate_box)

        # Year range slider
        current_year = datetime.date.today().year
        self.year_slider = RangeSlider(1888, current_year)
        self.year_slider.rangeChanged.connect(
            lambda lo, hi: self.lbl_year.setText(f"{lo} – {hi}"))
        self.lbl_year = QLabel(f"1888 – {current_year}")
        form.addRow("Year:" , QHBoxLayout())
        year_row = QHBoxLayout()
        year_row.addWidget(self.year_slider)
        year_row.addWidget(self.lbl_year)
        form.addRow(year_row)

        # Box office minimum
        self.rev_slider = RangeSlider(0, 1_000_000_000)
        self.rev_slider.rangeChanged.connect(
            lambda lo, hi: self.lbl_rev.setText(f">= {lo}"))
        self.lbl_rev = QLabel(">= 0")
        rev_row = QHBoxLayout()
        rev_row.addWidget(self.rev_slider)
        rev_row.addWidget(self.lbl_rev)
        form.addRow("Box Office:", rev_row)

        # Popularity threshold
        self.pop_slider = RangeSlider(0, 100)
        self.pop_slider.rangeChanged.connect(
            lambda lo, hi: self.lbl_pop.setText(f">= {lo}"))
        self.lbl_pop = QLabel(">= 0")
        pop_row = QHBoxLayout()
        pop_row.addWidget(self.pop_slider)
        pop_row.addWidget(self.lbl_pop)
        form.addRow("Popularity:", pop_row)
        
        
        # ── Origin ───────────────────────────────────────────────────────
        self.grp_origin    = QGroupBox("Origin")
        self.origin_checks = {}
        orig_layout = QVBoxLayout(self.grp_origin)
        for origin in repo.list_origins():
            cb = QCheckBox(origin)
            self.origin_checks[origin] = cb
            orig_layout.addWidget(cb)
        form.addRow("Origin:", self.grp_origin)

        # ── Genre ────────────────────────────────────────────────────────
        self.grp_genre    = QGroupBox("Genre")
        self.genre_checks = {}
        gen_layout = QVBoxLayout(self.grp_genre)
        for genre in repo.list_genres():
            cb = QCheckBox(genre)
            self.genre_checks[genre] = cb
            gen_layout.addWidget(cb)
        form.addRow("Genre:", self.grp_genre)

        # ── Theme ────────────────────────────────────────────────────────
        self.grp_theme    = QGroupBox("Theme")
        self.theme_checks = {}
        th_layout = QVBoxLayout(self.grp_theme)
        for theme in repo.list_themes():
            cb = QCheckBox(theme)
            self.theme_checks[theme] = cb
            th_layout.addWidget(cb)
        form.addRow("Theme:", self.grp_theme)



        layout.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def filters(self) -> dict:
        """Return current filter settings as a dict."""
        return {
            "duration": {
                "short": self.chk_short.isChecked(),
                "medium": self.chk_medium.isChecked(),
                "long": self.chk_long.isChecked(),
            },
            "ratings": [r for r, cb in self.rating_checks.items() if cb.isChecked()],
            "year_min": self.year_slider.lower(),
            "year_max": self.year_slider.upper(),
            "box_office_min": self.rev_slider.lower(),
            "popularity_min": self.pop_slider.lower(),
            "origin": [o for o, cb in self.origin_checks.items() if cb.isChecked()],
            "genre":  [g for g, cb in self.genre_checks.items()  if cb.isChecked()],
            "theme":  [t for t, cb in self.theme_checks.items()  if cb.isChecked()],
        }


class PickerPage(QWidget):
    DIRECTIONS = ["Clockwise", "Counter-Clockwise"]

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._filters: dict = {}
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(20)

        controls = QVBoxLayout()
        self.attendee_input = QLineEdit(placeholderText="# attendees")
        controls.addWidget(self.attendee_input)

        # sheet selector + filter
        h = QHBoxLayout()
        self.sheet_combo = QComboBox()
        sheets = sorted(repo.list_spreadsheet_themes())
        self.sheet_combo.addItems(sheets + ["Random"])
        h.addWidget(self.sheet_combo)
        self.btn_filter = QToolButton()
        self.btn_filter.setIcon(ICON("filter"))
        self.btn_filter.setEnabled(False)
        h.addWidget(self.btn_filter)
        controls.addLayout(h)

        self.generate_btn = QPushButton("Generate Movies")
        self.update_btn   = QPushButton("Update Data")
        controls.addWidget(self.generate_btn)
        controls.addWidget(self.update_btn)

        stats_card = QFrame()
        stats_card.setFrameShape(QFrame.StyledPanel)
        st = QVBoxLayout(stats_card)
        for text, prop in [
            ("Group Metrics", None),
            ("Similarity: —", "StatsValue"),
            ("", None),
            ("Weighted Score: —", "StatsValue")
        ]:
            lbl = QLabel(text, alignment=Qt.AlignCenter)
            if prop:
                lbl.setProperty("class", prop)
            st.addWidget(lbl)
        self.similarity_label = st.itemAt(1).widget()
        self.similarity_bar   = QProgressBar()
        self.similarity_bar.setRange(0, 100)
        self.similarity_bar.setTextVisible(False)
        st.insertWidget(2, self.similarity_bar)
        controls.addWidget(stats_card)
        controls.addStretch()
        main_layout.addLayout(controls)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.scroll_area.setWidget(container)
        main_layout.addWidget(self.scroll_area, 2)

        right = QVBoxLayout()
        self.direction_label = QLabel(alignment=Qt.AlignCenter)
        self.number_label    = QLabel(alignment=Qt.AlignCenter)
        for lbl in (self.direction_label, self.number_label):
            lbl.setMinimumSize(80, 80)
            lbl.setScaledContents(True)
            right.addWidget(lbl, alignment=Qt.AlignHCenter)
        self.report_btn = QPushButton("Report Trailers")
        self.report_btn.setEnabled(False)
        right.addWidget(self.report_btn)
        right.addStretch()
        main_layout.addLayout(right)

    def _connect_signals(self) -> None:
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_change)
        self.btn_filter.clicked.connect(self._open_filter_dialog)
        self.generate_btn.clicked.connect(self.main_window._on_generate)
        self.update_btn.clicked.connect(self.main_window._on_update)
        self.attendee_input.returnPressed.connect(self.main_window._on_generate)

    def _on_sheet_change(self, text: str) -> None:
        self.btn_filter.setEnabled(text == "Random")

    def _open_filter_dialog(self) -> None:
        dlg = FilterDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._filters = dlg.filters()

    def display_movies(self, titles: list[str], trailer_map: dict[str, str]):
        self._last_titles = titles.copy()
        self.report_btn.setEnabled(True)

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

        card_w    = 200
        margins   = self.grid_layout.contentsMargins()
        spacing   = self.grid_layout.horizontalSpacing()
        avail     = self.scroll_area.viewport().width() - margins.left() - margins.right()
        cols      = max(1, (avail + spacing) // (card_w + spacing))

        movies = [repo.by_id(repo.id_by_title(t)) for t in titles]
        for idx, movie in enumerate(movies):
            url   = trailer_map.get(movie.title, "")
            prob  = calculate_probability_to_watch([movie])
            grade = calculate_expected_grade([movie])
            dur_s = movie.duration_seconds
            card  = MovieCard(movie.title, url, prob, grade, dur_s, self)
            r, c  = divmod(idx, cols)
            self.grid_layout.addWidget(card, r, c)

        direction = random.choice(self.DIRECTIONS)
        icon_map  = {"Clockwise": "arrow-clockwise", "Counter-Clockwise": "arrow-counterclockwise"}
        arrow     = ICON(icon_map[direction]).pixmap(80, 80)
        number    = make_number_pixmap(random.randint(1, int(self.attendee_input.text() or "1")), size=80)
        self.direction_label.setPixmap(arrow)
        self.number_label.setPixmap(number)
        self.direction_label.show()
        self.number_label.show()

        sim_pct    = int(calculate_similarity(movies) * 100)
        wt_score   = calculate_weighted_totals(movies) * 100
        self.similarity_label.setText(f"Similarity: {sim_pct}%")
        self.similarity_bar.setValue(sim_pct)
        # Assuming weighted label update elsewhere
        
    @Slot()
    def _open_report_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Report Trailers")
        layout = QVBoxLayout(dialog)
        for t in self._last_titles:
            cb = QCheckBox(t)
            layout.addWidget(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dialog.accept)
        bb.rejected.connect(dialog.reject)
        layout.addWidget(bb)

        if dialog.exec() == QDialog.Accepted:
            reported = [cb.text() for cb in dialog.findChildren(QCheckBox) if cb.isChecked()]
            QMessageBox.information(self, "Reported", f"Thanks for reporting: {', '.join(reported)}")
