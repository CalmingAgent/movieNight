from __future__ import annotations
from PySide6.QtCore    import Qt, Signal, Slot # type: ignore
from PySide6.QtWidgets import ( # type: ignore
    QWidget, QVBoxLayout, QGridLayout, QPushButton, QLabel,
    QProgressBar, QDialog, QDialogButtonBox, QGroupBox
)

# -------------------------------------------------------------------------
class _ProgressDialog(QDialog):
    """Tiny modal displaying a label + indeterminate or % bar."""
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, flags=Qt.Dialog | Qt.WindowTitleHint)
        self.setWindowTitle(title)
        self.setFixedWidth(300)

        self.label = QLabel("Starting…", alignment=Qt.AlignCenter)
        self.bar   = QProgressBar()
        self.bar.setRange(0, 0)           # busy by default

        box = QVBoxLayout(self)
        box.addWidget(self.label)
        box.addWidget(self.bar)

        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(self.reject)
        box.addWidget(bb)

    # public helpers for worker threads
    @Slot(int, int)
    def set_progress(self, done: int, total: int) -> None:
        self.bar.setRange(0, total)
        self.bar.setValue(done)

    @Slot(str)
    def set_message(self, txt: str) -> None:
        self.label.setText(txt)


# -------------------------------------------------------------------------
class StatsPage(QWidget):
    """Page that hosts the maintenance buttons arranged in a grid."""
    request_update_meta   = Signal(bool)   # full=True / continue=False
    request_update_urls   = Signal(bool)
    request_update_collect  = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # ── groupbox with our buttons in a QGridLayout ────────────────
        box  = QGroupBox("Maintenance Tasks")
        grid = QGridLayout(box)

        # Row 0, left‐side (metadata) widgets
        self.btn_meta      = QPushButton("Update metadata")
        self.btn_meta_ctn  = QPushButton("Continue")
        self.lbl_meta_st   = QLabel("", alignment=Qt.AlignLeft)

        # Row 0, right‐side (URLs) widgets
        self.btn_urls      = QPushButton("Update URLs")
        self.btn_urls_ctn  = QPushButton("Continue")
        self.lbl_url_st    = QLabel("", alignment=Qt.AlignLeft)

        # Row 1, Collect button (goes into the “gap” column)
        self.btn_collect   = QPushButton("Collect Data")

        # ── configure sizes / disable continues initially ─────────────
        for w in (
            self.btn_meta, self.btn_meta_ctn,
            self.btn_urls, self.btn_urls_ctn,
            self.btn_collect
        ):
            w.setMinimumWidth(120)
            w.setAutoDefault(False)

        self.btn_meta_ctn.setEnabled(False)
        self.btn_urls_ctn.setEnabled(False)

        # ── place widgets into the grid ───────────────────────────────
        # Row 0:
        grid.addWidget(self.btn_meta,     0, 0)
        grid.addWidget(self.btn_meta_ctn, 0, 1)
        grid.addWidget(self.lbl_meta_st,  0, 2)

        # (empty column 3 on row 0)

        grid.addWidget(self.btn_urls,     0, 4)
        grid.addWidget(self.btn_urls_ctn, 0, 5)
        grid.addWidget(self.lbl_url_st,   0, 6)

        # Row 1 (Collect button goes in column 3)
        grid.addWidget(self.btn_collect,  1, 3, alignment=Qt.AlignHCenter)

        # ── column stretch so that column 3 expands to fill spare space ─
        for col in (0,1,2,4,5,6):
            grid.setColumnStretch(col, 0)
        grid.setColumnStretch(3, 1)

        root.addWidget(box)
        self.setLayout(root)

    def _connect(self) -> None:
        # full‐run clicks
        self.btn_meta.clicked.connect(lambda: self.request_update_meta.emit(True))
        self.btn_urls.clicked.connect(lambda: self.request_update_urls.emit(True))
        self.btn_collect.clicked.connect(lambda: self.request_update_collect.emit(True))

        # continue clicks
        self.btn_meta_ctn.clicked.connect(lambda: self.request_update_meta.emit(False))
        self.btn_urls_ctn.clicked.connect(lambda: self.request_update_urls.emit(False))

    # ----- slots called by controller to flip state ------------------------
    @Slot(bool)
    def enable_meta_continue(self, show: bool) -> None:
        self.btn_meta_ctn.setEnabled(show)

    @Slot(bool)
    def enable_url_continue(self, show: bool) -> None:
        self.btn_urls_ctn.setEnabled(show)

    # forward progress-dialog factory so controller can pop one
    def open_progress(self, title: str) -> _ProgressDialog:
        dlg = _ProgressDialog(title, self)
        dlg.show()
        return dlg
        # These let the controller show “done / total” next to each Continue
    
    @Slot(int, int)
    def set_meta_status(self, done: int, total: int) -> None:
        txt = f"{done} / {total}" if total else ""
        self.lbl_meta_st.setText(txt)

    @Slot(int, int)
    def set_url_status(self, done: int, total: int) -> None:
        txt = f"{done} / {total}" if total else ""
        self.lbl_url_st.setText(txt)
