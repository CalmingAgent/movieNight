from __future__ import annotations
from PySide6.QtCore    import Qt, Signal, Slot # type: ignore
from PySide6.QtWidgets import ( # type: ignore
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
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
    """Page that hosts the four maintenance buttons."""

    # UI requests emitted to MainWindow → controller.py
    request_update_meta   = Signal(bool)   # full = True / continue = False
    request_update_urls   = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # ── groupbox with 4 buttons ---------------------------------------
        box  = QGroupBox("Maintenance Tasks")
        grid = QHBoxLayout(box)

        self.btn_meta     = QPushButton("Update metadata")
        self.btn_urls     = QPushButton("Update URLs")
        self.btn_meta_ctn = QPushButton("Continue")
        self.btn_urls_ctn = QPushButton("Continue")
        self.btn_collect  = QPushButton("Collect Data")

        # status labels (“42 / 156”) – start hidden
        self.lbl_meta_st  = QLabel("", alignment=Qt.AlignLeft)
        self.lbl_url_st   = QLabel("", alignment=Qt.AlignLeft)

        for b in (self.btn_meta, self.btn_urls, self.btn_meta_ctn, self.btn_urls_ctn):
            b.setMinimumWidth(120)
            b.setAutoDefault(False)

        self.btn_meta_ctn.setEnabled(False)
        self.btn_urls_ctn.setEnabled(False)

        # layout: [Full update]  |  [Continue]  [status]
        grid.addWidget(self.btn_meta)
        grid.addWidget(self.btn_meta_ctn)
        grid.addWidget(self.lbl_meta_st)
        grid.addSpacing(20)
        grid.addWidget(self.btn_urls)
        grid.addWidget(self.btn_urls_ctn)
        grid.addWidget(self.lbl_url_st)

        root.addWidget(box)
        self.setLayout(root)

    def _connect(self) -> None:
        self.btn_meta.clicked.connect(lambda: self.request_update_meta.emit(True))
        self.btn_urls.clicked.connect(lambda: self.request_update_urls.emit(True))
        self.btn_collect.clicked.connect(lambda: self.request_collect.emit(True))
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
