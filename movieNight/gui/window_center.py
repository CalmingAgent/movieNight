"""
window_center
~~~~~~~~~~~~~
One–shot centring helper that works on X11 / Wayland / WSLg / Windows / macOS.
Call ``center_when_shown(widget)`` **before** ``show()`` / ``exec()``.
"""

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtGui  import QGuiApplication
from PySide6.QtWidgets import QWidget


class _CenterOnceFilter(QObject):
    """Internal event-filter: centre after the native window is ready."""
    def __init__(self, widget: QWidget) -> None:
        super().__init__(widget)
        self._widget = widget
        widget.installEventFilter(self)

    # ------------------------------------------------------------------ Qt
    def eventFilter(self, obj, ev):
        if obj is self._widget and ev.type() == QEvent.Type.Show:
            # defer to allow the compositor to realise final geometry
            QTimer.singleShot(0, self._center_and_remove)
        return False

    # ----------------------------------------------------------------- misc
