from __future__ import annotations
from PySide6.QtCore    import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QDialog, QDialogButtonBox
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

        # --- button row ----------------------------------------------------
        btn_row = QHBoxLayout()
        self.btn_meta      = QPushButton("Update metadata")
        self.btn_urls      = QPushButton("Update URLs")
        self.btn_meta_ctn  = QPushButton("Continue metadata")
        self.btn_urls_ctn  = QPushButton("Continue URLs")

        for b in (self.btn_meta, self.btn_urls, self.btn_meta_ctn, self.btn_urls_ctn):
            b.setMinimumWidth(140)
            b.setAutoDefault(False)
        # continue buttons start disabled
        self.btn_meta_ctn.setEnabled(False)
        self.btn_urls_ctn.setEnabled(False)

        btn_row.addWidget(self.btn_meta)
        btn_row.addWidget(self.btn_urls)
        btn_row.addWidget(self.btn_meta_ctn)
        btn_row.addWidget(self.btn_urls_ctn)
        root.addLayout(btn_row)

        self.setLayout(root)

    def _connect(self) -> None:
        self.btn_meta.clicked.connect(lambda: self.request_update_meta.emit(True))
        self.btn_urls.clicked.connect(lambda: self.request_update_urls.emit(True))
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
