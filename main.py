from signal import Signals
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore    import QObject, QThread, Signal, Slot        
from settings import DATABASE_PATH

from .utils       import apply_dark_palette
from .settings    import ICON, ACCENT_COLOR
from gui.main_window import MainWindow
from gui.controller   import update_data 


# ────────────────────────────────────────────────────────────────────────────
# 1 ▸ Tiny worker object → easy to reuse for other jobs later
# ────────────────────────────────────────────────────────────────────────────
class UpdateWorker(QObject):
    finished = Signal(bool)          # True = ran ok, False = raised

    @Slot()
    def run(self) -> None:
        try:
            update_data()
            self.finished.emit(True)
        except Exception as e:
            print("Update failed:", e)
            self.finished.emit(False)
# ────────────────────────────────────────────────────────────────────────────
# 2 ▸ Application entry
# ────────────────────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    apply_dark_palette(app)

    # -------- optional “check for updates?” dialog --------------------
    reply = QMessageBox.question(
        None,
        "Update?",
        "Check for data updates now?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )

    # -------- create main window immediately -------------------------
    window = MainWindow()            # no db arg needed now
    window.show()

    # -------- if user chose Yes, spin a worker thread ----------------
    if reply == QMessageBox.Yes:
        thr     = QThread()
        worker  = UpdateWorker()
        worker.moveToThread(thr)

        thr.started.connect(worker.run)
        worker.finished.connect(thr.quit)
        worker.finished.connect(worker.deleteLater)
        thr.finished.connect(thr.deleteLater)

        worker.finished.connect(lambda ok: window.setEnabled(True))
        window.setEnabled(False)     # grey-out while updating
        thr.start()

    # -------- run the event-loop -------------------------------------
    sys.exit(app.exec())

# Python entry-point guard
if __name__ == "__main__":
    main()