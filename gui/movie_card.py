from __future__ import annotations
from PySide6.QtCore    import Qt, QPropertyAnimation # type: ignore
from PySide6.QtWidgets import ( # type: ignore
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
)

from ..settings import ACCENT_COLOR
from ..utils    import open_url_host_browser


class MovieCard(QFrame):
    """Mini-card with title + probability, expected grade, duration."""

    def __init__(
        self,
        title: str,
        trailer_url: str | None,
        probability: float,
        grade: str,
        duration_seconds: int | None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("MovieCardItem")
        self.setFrameShape(QFrame.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ── title link (or plain text) ───────────────────────────────────
        anchor = f'<a href="{trailer_url}">{title}</a>' if trailer_url else title
        link   = QLabel(anchor)
        link.setTextFormat(Qt.RichText)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link.setWordWrap(True)
        link.setCursor(Qt.PointingHandCursor)
        if trailer_url:
            link.setOpenExternalLinks(False)
            link.linkActivated.connect(open_url_host_browser)
        root.addWidget(link)

        # ── footer row: prob | grade | duration ─────────────────────────
        footer = QHBoxLayout()            

        # probability pill (left)
        prob_text = f"{probability:.0%}"
        pill = QLabel(prob_text, alignment=Qt.AlignCenter)
        if probability >= 0.70:
            bg, fg = "#2ecc71", "#000000"
        elif probability >= 0.40:
            bg, fg = "#f1c40f", "#000000"
        else:
            bg, fg = ACCENT_COLOR, "#ffffff"
        pill.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:6px; padding:2px 8px;"
        )

        # expected grade (center)
        grade_lbl = QLabel(grade or "—", alignment=Qt.AlignCenter)
        grade_lbl.setStyleSheet("font-weight:bold;")

        # duration (right)
        if duration_seconds:
            h, m = divmod(duration_seconds // 60, 60)
            dur_lbl = QLabel(f"{h} h {m:02d} m", alignment=Qt.AlignRight)
        else:
            dur_lbl = QLabel("—", alignment=Qt.AlignRight)

        # add widgets to footer ❷
        footer.addWidget(pill,      0, Qt.AlignLeft)
        footer.addWidget(grade_lbl, 0, Qt.AlignHCenter)
        footer.addWidget(dur_lbl,   0, Qt.AlignRight)
        root.addLayout(footer)
        root.addStretch()

        # ── hover shadow effect ──────────────────────────────────────────
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(4)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    # ------------------------------------------------------------------
    # hover animation
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
