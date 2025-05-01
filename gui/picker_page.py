import random

from PySide6.QtCore    import Qt, Slot
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QWidgetItem, QGridLayout, QProgressBar, QLabel,
    QSizePolicy, QDialog, QCheckBox, QDialogButtonBox, QMessageBox
)

from ..settings        import ICON
from .movie_card      import MovieCard
from ..utils           import make_number_pixmap
from ..metadata.service         import calculate_group_similarity, calculate_weighted_totals
from .button_logic    import generate_movies


class PickerPage(QWidget):
    DIRECTIONS = ["Clockwise", "Counter-Clockwise"]

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self._connect_signals()

        self.direction_label.hide()
        self.number_label.hide()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(20)

        # ── Left controls & stats ──
        controls = QVBoxLayout()
        self.attendee_input = QLineEdit(placeholderText="# attendees")
        self.sheet_input    = QLineEdit(placeholderText="Sheet name")
        self.generate_btn   = QPushButton("Generate Movies")
        self.update_btn     = QPushButton("Update URLs")

        for btn in (self.generate_btn, self.update_btn):
            btn.setAutoDefault(False)
            btn.setFlat(True)
            controls.addWidget(btn)
        controls.insertWidget(0, self.sheet_input)
        controls.insertWidget(0, self.attendee_input)

        # Stats card
        stats_card = QWidget()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setSpacing(4)

        header = QLabel("Group Metrics", alignment=Qt.AlignCenter)
        header.setProperty("class", "StatsHeader")

        self.similarity_label = QLabel("Similarity: —", alignment=Qt.AlignCenter)
        self.similarity_label.setProperty("class", "StatsValue")

        self.similarity_bar   = QProgressBar()
        self.similarity_bar.setRange(0, 100)
        self.similarity_bar.setTextVisible(False)

        self.weighted_label   = QLabel("Weighted Score: —", alignment=Qt.AlignCenter)
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

    def display_movies(self, titles: list[str], trailer_map: dict[str, str]):
        # Clear old cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

        # Compute columns
        card_w  = 200
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.horizontalSpacing()
        avail   = self.scroll_area.viewport().width() - margins.left() - margins.right()
        cols    = max(1, (avail + spacing) // (card_w + spacing))

        # Populate
        for idx, title in enumerate(titles):
            url  = trailer_map.get(title, "")
            prob = calculate_group_similarity([title])  # or movie_probability
            card = MovieCard(title, url, prob, self)
            row, col = divmod(idx, cols)
            self.grid_layout.addWidget(card, row, col)

        # Random direction + number
        direction = random.choice(self.DIRECTIONS)
        icon_map  = {
            "Clockwise":          "arrow-clockwise",
            "Counter-Clockwise":  "arrow-counterclockwise",
        }
        icon_name     = icon_map[direction]
        max_number    = int(self.attendee_input.text() or "1")
        random_number = random.randint(1, max_number)
        side = min(self.direction_label.width(), self.direction_label.height(), 124)

        arrow_pix   = ICON(icon_name).pixmap(side, side)
        number_pix  = make_number_pixmap(random_number, size=side)
        self.direction_label.setPixmap(arrow_pix)
        self.number_label.setPixmap(number_pix)
        self.direction_label.show()
        self.number_label.show()

        # Update stats bar
        sim_pct = int(calculate_group_similarity(titles) * 100)
        wt_score = calculate_weighted_totals(titles) * 100
        self.similarity_label.setText(f"Similarity: {sim_pct}%")
        self.similarity_bar.setValue(sim_pct)
        self.weighted_label.setText(f"Weighted Score: {wt_score:.1f}")

    @Slot()
    def _open_report_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Report Trailers")
        layout = QVBoxLayout(dialog)
        boxes = [QCheckBox(t) for t in getattr(self, "_last_titles", [])]
        for cb in boxes:
            layout.addWidget(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dialog.accept)
        bb.rejected.connect(dialog.reject)
        layout.addWidget(bb)

        if dialog.exec() == QDialog.Accepted:
            # handle reported titles
            reported = [cb.text() for cb in boxes if cb.isChecked()]
            QMessageBox.information(self, "Reported", f"Thanks for reporting: {', '.join(reported)}")
