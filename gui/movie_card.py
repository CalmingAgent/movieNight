from PySide6.QtCore    import Qt
from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
)

from ..settings import ACCENT_COLOR
from ..utils    import make_number_pixmap


class MovieCard(QFrame):
    """A clickable card showing a movie title link and its probability pill."""

    def __init__(self, title: str, trailer_url: str, probability: float, parent=None):
        super().__init__(parent)
        self.setObjectName("MovieCardItem")
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title link
        link = QLabel(f'<a href="{trailer_url}">{title}</a>')
        link.setTextFormat(Qt.RichText)
        link.setOpenExternalLinks(True)
        link.setWordWrap(True)
        layout.addWidget(link)

        # Probability pill
        prob_text = f"{probability:.2f}"
        pill = QLabel(prob_text, alignment=Qt.AlignCenter)
        if probability >= 0.7:
            bg, fg = "#2ecc71", "#000000"
        elif probability >= 0.4:
            bg, fg = "#f1c40f", "#000000"
        else:
            bg, fg = ACCENT_COLOR, "#ffffff"
        pill.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:6px; padding:2px 8px;")
        layout.addWidget(pill, alignment=Qt.AlignHCenter)
        layout.addStretch()

        # Hover shadow
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(4)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    def enterEvent(self, event):
        super().enterEvent(event)
        anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        anim.setDuration(200)
        anim.setEndValue(16)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        anim.setDuration(200)
        anim.setEndValue(4)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
