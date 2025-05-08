import sys
from PySide6.QtWidgets import QApplication
from settings import DATABASE_PATH

from .utils       import apply_dark_palette
from .settings    import ICON, ACCENT_COLOR
from gui.main_window import MainWindow
from metadata.service import MovieNightDB


def main() -> None:
    app = QApplication(sys.argv)
    
    db = MovieNightDB(DATABASE_PATH)
    app.aboutToQuit.connect(db.close)
    
    apply_dark_palette(app)
    window = MainWindow(db)
    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)

# if __name__ == "__main__":
#     main()
