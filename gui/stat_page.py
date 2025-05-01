#placeholder
from PySide6.QtWidgets import QWidget, QTableWidget, QVBoxLayout

class StatsPage(QWidget):
    """Placeholder for future statistics view."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        layout.addWidget(self.table)
