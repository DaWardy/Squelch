from __future__ import annotations
"""CustomLayoutTab — user-created tab with embedded, resizable panel split.

Panels are borrowed from the main tab bar only while this tab is active.
When the user navigates away, panels return to their original tab bar slots
automatically, so they remain accessible from both locations.
"""
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QSplitter, QFrame,
)

from ui.panel import SquelchPanel

if TYPE_CHECKING:
    from core.config import Config


class _PanelSlotFrame(QWidget):
    """Wraps an embedded panel with a thin header bar and a remove (unassign) button."""

    unassign_requested = pyqtSignal(str)  # panel_key

    def __init__(self, panel: QWidget, panel_key: str,
                 panel_title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._panel = panel
        self._panel_key = panel_key

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QFrame()
        header.setObjectName("CustomTabPanelHeader")
        header.setFixedHeight(22)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 0, 4, 0)
        hl.setSpacing(4)
        lbl = QLabel(panel_title)
        lbl.setStyleSheet("font-weight:bold;font-size:11px;")
        remove_btn = QToolButton()
        remove_btn.setText("✕")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setToolTip(
            f"Unassign '{panel_title}' — panel returns to its own tab")
        remove_btn.clicked.connect(
            lambda: self.unassign_requested.emit(self._panel_key))
        hl.addWidget(lbl, 1)
        hl.addWidget(remove_btn)

        lay.addWidget(header)
        lay.addWidget(panel, 1)


class CustomLayoutTab(SquelchPanel, QWidget):
    """A tab that shows multiple panels side-by-side in a resizable split.

    Panels are *assigned* to this tab by key.  While this tab is active,
    MainWindow moves those panel widgets here.  When the user navigates away,
    MainWindow returns them to the regular tab bar — so panels are always
    accessible from both their original tab and from this view.
    """

    panel_unassign_requested = pyqtSignal(str, str)   # tab_id, panel_key

    def __init__(self, tab_id: str, title: str,
                 cfg: "Config", parent: QWidget | None = None):
        super().__init__(parent)
        self.panel_id = tab_id
        self.panel_title = title
        self._cfg = cfg
        # Keys the user has assigned here (persisted)
        self._assigned_keys: list[str] = []
        # Keys currently embedded (runtime — may differ while panels are away)
        self._slot_keys: list[str] = []
        self._frames: dict[str, _PanelSlotFrame] = {}
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_toolbar())

        self._placeholder = QLabel(
            "Use  ＋ Add panel  above to place panels here.\n"
            "Panels remain accessible from their own tabs too.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setObjectName("CustomTabPlaceholder")
        lay.addWidget(self._placeholder, 1)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.hide()
        lay.addWidget(self._splitter, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("CustomTabToolbar")
        bar.setFixedHeight(30)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(6, 3, 6, 3)
        hl.setSpacing(6)

        self._add_btn = QToolButton()
        self._add_btn.setText("＋ Add panel")
        self._add_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._add_btn.setToolTip(
            "Choose a panel to embed here.\n"
            "It will still be accessible from its own tab.")
        hl.addWidget(self._add_btn)

        flip_btn = QToolButton()
        flip_btn.setText("⇄ Flip")
        flip_btn.setToolTip("Switch between horizontal and vertical split")
        flip_btn.clicked.connect(self._flip_orientation)
        hl.addWidget(flip_btn)

        hl.addStretch(1)
        return bar

    # ── Public API ─────────────────────────────────────────────────────────

    def set_add_menu(self, menu) -> None:
        self._add_btn.setMenu(menu)

    def assign_panel(self, panel_key: str) -> None:
        """Record that this panel belongs here (does not embed it yet)."""
        if panel_key not in self._assigned_keys:
            self._assigned_keys.append(panel_key)

    def unassign_panel(self, panel_key: str) -> None:
        """Remove from assignment list (does not release widget — caller must)."""
        if panel_key in self._assigned_keys:
            self._assigned_keys.remove(panel_key)
        if not self._assigned_keys and self._splitter.isHidden():
            pass  # placeholder already showing

    def embed_panel(self, panel: QWidget, panel_key: str,
                    panel_title: str) -> None:
        """Move a panel widget into the splitter (called by MainWindow on tab activate)."""
        if panel_key in self._frames:
            return
        frame = _PanelSlotFrame(panel, panel_key, panel_title, self)
        frame.unassign_requested.connect(
            lambda pk: self.panel_unassign_requested.emit(self.panel_id, pk))
        self._frames[panel_key] = frame
        self._slot_keys.append(panel_key)
        self._splitter.addWidget(frame)
        frame.show()
        panel.show()
        if self._placeholder.isVisible():
            self._placeholder.hide()
            self._splitter.show()

    def release_panel(self, panel_key: str) -> QWidget | None:
        """Extract panel widget from splitter (called by MainWindow on tab deactivate)."""
        frame = self._frames.pop(panel_key, None)
        if frame is None:
            return None
        panel = frame._panel
        panel.setParent(None)
        frame.setParent(None)
        frame.deleteLater()
        if panel_key in self._slot_keys:
            self._slot_keys.remove(panel_key)
        if not self._slot_keys:
            self._splitter.hide()
            self._placeholder.show()
        return panel

    @property
    def assigned_keys(self) -> list[str]:
        return list(self._assigned_keys)

    @property
    def slot_keys(self) -> list[str]:
        return list(self._slot_keys)

    # ── Internals ─────────────────────────────────────────────────────────

    def _flip_orientation(self) -> None:
        H, V = Qt.Orientation.Horizontal, Qt.Orientation.Vertical
        self._splitter.setOrientation(
            V if self._splitter.orientation() == H else H)

    # ── SquelchPanel lifecycle ─────────────────────────────────────────────

    def save_state(self) -> dict:
        return {
            "title":       self.panel_title,
            "assigned":    list(self._assigned_keys),
            "orientation": (
                "H" if self._splitter.orientation() == Qt.Orientation.Horizontal
                else "V"),
        }

    def restore_state(self, state: dict) -> None:
        orient = (Qt.Orientation.Horizontal
                  if state.get("orientation", "H") == "H"
                  else Qt.Orientation.Vertical)
        self._splitter.setOrientation(orient)
        for key in state.get("assigned", []):
            self.assign_panel(key)
