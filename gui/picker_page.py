import random
from PySide6.QtCore    import Qt, Slot  # type: ignore
from PySide6.QtWidgets import (         # type: ignore
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QGridLayout, QProgressBar, QLabel,
    QSizePolicy, QDialog, QCheckBox, QDialogButtonBox, QMessageBox
)

from ..settings import ICON, ACCENT_COLOR
from .movie_card import MovieCard
from ..utils      import make_number_pixmap
from metadata     import repo
from metadata.analytics.similarity import calculate_similarity
from metadata.analytics.scoring    import (
    calculate_weighted_totals,
    calculate_probability_to_watch,
    calculate_expected_grade,
)

class PickerPage(QWidget):
    DIRECTIONS = ["Clockwise", "Counter-Clockwise"]

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self._connect_signals()

        self.direction_label.hide()
        self.number_label.hide()
        self._last_titles: list[str] = []  # initialize here

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(20)

        # ── Left controls & stats ──
        controls = QVBoxLayout()
        self.attendee_input = QLineEdit(placeholderText="# attendees")
        self.sheet_input    = QLineEdit(placeholderText="Sheet name")
        self.generate_btn   = QPushButton("Generate Movies")
        self.update_btn     = QPushButton("Update Data")
        self.btn_plus_one   = QPushButton("+1")
        self.btn_minus_one  = QPushButton("-1")
        for b in (self.btn_minus_one, self.btn_plus_one):
            b.setFixedWidth(28)

        # hook up +1/–1 and main buttons
        for btn in (self.generate_btn, self.update_btn, self.btn_minus_one, self.btn_plus_one):
            btn.setAutoDefault(False)
            btn.setFlat(True)
            controls.addWidget(btn)
        controls.insertWidget(0, self.sheet_input)
        controls.insertWidget(0, self.attendee_input)

        # Stats card
        stats_card   = QWidget()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setSpacing(4)

        header = QLabel("Group Metrics", alignment=Qt.AlignCenter)
        header.setProperty("class", "StatsHeader")

        self.similarity_label = QLabel("Similarity: —", alignment=Qt.AlignCenter)
        self.similarity_label.setProperty("class", "StatsValue")

        self.similarity_bar = QProgressBar()
        self.similarity_bar.setRange(0, 100)
        self.similarity_bar.setTextVisible(False)

        self.weighted_label = QLabel("Weighted Score: —", alignment=Qt.AlignCenter)
        self.weighted_label.setProperty("class", "StatsValue")

        for w in (header, self.similarity_label, self.similarity_bar, self.weighted_label):
            stats_layout.addWidget(w)

        controls.addWidget(stats_card)
        controls.addStretch()
        main_layout.addLayout(controls)

        # ── Center movie grid ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("MovieCardContainer")
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(12)
        self.scroll_area.setWidget(container)
        main_layout.addWidget(self.scroll_area, 2)

        # ── Right direction & report ──
        right = QVBoxLayout()
        self.direction_label = QLabel(objectName="DirectionTile", alignment=Qt.AlignCenter)
        self.number_label    = QLabel(objectName="NumberTile",    alignment=Qt.AlignCenter)
        for lbl in (self.direction_label, self.number_label):
            lbl.setMinimumSize(80, 80)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lbl.setScaledContents(True)
        right.addWidget(self.direction_label, alignment=Qt.AlignHCenter)
        right.addWidget(self.number_label,    alignment=Qt.AlignHCenter)

        self.report_btn = QPushButton("Report Trailers")
        self.report_btn.setEnabled(False)
        right.addWidget(self.report_btn)
        right.addStretch()
        main_layout.addLayout(right)

    def _connect_signals(self):
        self.generate_btn.clicked.connect(self.main_window._on_generate)
        self.update_btn.clicked.connect(self.main_window._on_update)
        self.attendee_input.returnPressed.connect(self.main_window._on_generate)
        self.sheet_input.returnPressed.connect(self.main_window._on_generate)
        self.btn_plus_one.clicked.connect(lambda: self.main_window._on_add_remove(+1))
        self.btn_minus_one.clicked.connect(lambda: self.main_window._on_add_remove(-1))
        # **new**:
        self.report_btn.clicked.connect(self._open_report_dialog)

    def display_movies(self, titles: list[str], trailer_map: dict[str, str]):
        # remember for “Report Trailers”
        self._last_titles = titles.copy()
        self.report_btn.setEnabled(True)

        # clear…
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

        # figure out cols…
        card_w  = 200
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.horizontalSpacing()
        avail   = self.scroll_area.viewport().width() - margins.left() - margins.right()
        cols    = max(1, (avail + spacing) // (card_w + spacing))

        # map titles → Movie objects once
        movies = []
        for t in titles:
            mid = repo.id_by_title(t)
            if mid is not None:
                movies.append(repo.by_id(mid))

        # populate grid
        for idx, movie in enumerate(movies):
            url   = trailer_map.get(movie.title, "")
            prob  = calculate_probability_to_watch([movie])
            grade = calculate_expected_grade([movie])
            dur_s = movie.duration_seconds
            card  = MovieCard(movie.title, url, prob, grade, dur_s, self)

            r, c = divmod(idx, cols)
            self.grid_layout.addWidget(card, r, c)

        # …and show direction/number
        direction    = random.choice(self.DIRECTIONS)
        icon_map     = {
            "Clockwise":          "arrow-clockwise",
            "Counter-Clockwise":  "arrow-counterclockwise",
        }
        arrow_name   = icon_map[direction]
        max_attendees = int(self.attendee_input.text() or "1")
        rand_num     = random.randint(1, max_attendees)
        side         = min(self.direction_label.width(),
                           self.direction_label.height(), 124)

        arrow_pix  = ICON(arrow_name).pixmap(side, side)
        number_pix = make_number_pixmap(rand_num, size=side)
        self.direction_label.setPixmap(arrow_pix)
        self.number_label.setPixmap(number_pix)
        self.direction_label.show()
        self.number_label.show()

        # now the group‐stats
        sim_pct  = int(calculate_similarity(movies) * 100)
        wt_score = calculate_weighted_totals(movies) * 100

        self.similarity_label.setText(f"Similarity: {sim_pct}%")
        self.similarity_bar.setValue(sim_pct)
        self.weighted_label.setText(f"Weighted Score: {wt_score:.1f}")

    @Slot()
    def _open_report_dialog(self):
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
