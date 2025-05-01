import sys
from PySide6.QtWidgets import QApplication

from .utils       import apply_dark_palette
from .settings    import ICON, ACCENT_COLOR
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    apply_dark_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

# if __name__ == "__main__":
#     main()
