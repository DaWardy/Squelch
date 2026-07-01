from __future__ import annotations
"""CustomLayoutTab — user-created shortcut tab.

Panels are NEVER reparented. Each assigned panel gets a navigation card
that shows the panel title and a 'Go to tab' button. Original panels remain
fully functional in their own tab slots at all times.

Rearranging cards within the custom tab is supported via the unlock mode.
"""
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QSizePolicy, QMdiArea, QMdiSubWindow,
)

from ui.panel import SquelchPanel

if TYPE_CHECKING:
    from core.config import Config


class _PanelCard(QFrame):
    """A card representing an assigned panel.  Click 'Go' to navigate to it."""

    navigate_requested = pyqtSignal()
    remove_requested   = pyqtSignal(str)    # panel_key
    move_left          = pyqtSignal(str)    # panel_key
    move_right         = pyqtSignal(str)    # panel_key

    def __init__(self, panel_key: str, panel_title: str,
                 parent: QWidget | None = None,
                 summary_widget: QWidget | None = None):
        super().__init__(parent)
        self._key = panel_key
        self.setObjectName("CustomTabPanelCard")
        # Inside an MDI sub-window the card fills the user-resizable frame,
        # so it expands both ways rather than sitting at a fixed width.
        self.setMinimumWidth(180 if summary_widget is not None else 150)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Title
        self._title_lbl = QLabel(panel_title)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet("font-weight:bold;font-size:12px;")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._title_lbl)

        # Live summary bound to the shared backend (if this panel has one).
        # It reflects/drives the same singleton the full panel uses.
        if summary_widget is not None:
            summary_widget.setParent(self)
            root.addWidget(summary_widget)

        root.addStretch(1)

        # Navigate button — only for whole-tab shortcut cards. À-la-carte
        # widget cards are self-contained (they show live content bound to the
        # shared backend), so they don't need an 'Open tab' link.
        if summary_widget is None:
            nav_btn = QToolButton()
            nav_btn.setText("Open tab →")
            nav_btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            nav_btn.setToolTip(f"Switch to the {panel_title} tab")
            nav_btn.clicked.connect(self.navigate_requested)
            root.addWidget(nav_btn)

        # Reorder row (hidden until unlock mode)
        self._reorder_row = QWidget()
        rl = QHBoxLayout(self._reorder_row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        self._left_btn  = QToolButton()
        self._left_btn.setText("◀")
        self._left_btn.setFixedWidth(30)
        self._left_btn.setToolTip("Move left")
        self._left_btn.clicked.connect(lambda: self.move_left.emit(self._key))
        self._right_btn = QToolButton()
        self._right_btn.setText("▶")
        self._right_btn.setFixedWidth(30)
        self._right_btn.setToolTip("Move right")
        self._right_btn.clicked.connect(lambda: self.move_right.emit(self._key))
        remove_btn = QToolButton()
        remove_btn.setText("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove from this custom tab")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._key))
        rl.addWidget(self._left_btn)
        rl.addWidget(self._right_btn)
        rl.addStretch(1)
        rl.addWidget(remove_btn)
        self._reorder_row.hide()
        root.addWidget(self._reorder_row)

    def set_unlock_mode(self, unlocked: bool) -> None:
        self._reorder_row.setVisible(unlocked)

    def set_can_move_left(self, yes: bool) -> None:
        self._left_btn.setEnabled(yes)

    def set_can_move_right(self, yes: bool) -> None:
        self._right_btn.setEnabled(yes)


class _PanelSubWindow(QMdiSubWindow):
    """A movable / resizable MDI frame that hosts one panel card.

    Emits ``closed`` (with the panel key) when the user closes it via the
    title-bar ✕, so the tab can drop the assignment.
    """

    closed = pyqtSignal(str)   # panel_key

    def __init__(self, panel_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._key = panel_key
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    def closeEvent(self, event) -> None:
        self.closed.emit(self._key)
        super().closeEvent(event)


class CustomLayoutTab(SquelchPanel, QWidget):
    """A build-your-own dashboard tab.

    Each chosen panel is placed in a movable / resizable MDI sub-window, so the
    user can lay out the info they want, where they want it, and still interact
    with it.  Panels are NEVER reparented out of the tab bar — each card is a
    lightweight view bound to the same shared backend the real panel uses
    (see ``custom_summaries``), or a plain 'Open tab →' link when no summary
    exists yet.
    """

    panel_unassign_requested  = pyqtSignal(str, str)  # tab_id, panel_key
    panel_navigate_requested  = pyqtSignal(str)        # panel_key

    def __init__(self, tab_id: str, title: str,
                 cfg: "Config", parent: QWidget | None = None):
        super().__init__(parent)
        self.panel_id    = tab_id
        self.panel_title = title
        self._cfg        = cfg
        self._assigned_keys: list[str] = []
        self._cards: dict[str, _PanelCard] = {}
        self._subwins: dict[str, _PanelSubWindow] = {}
        self._unlocked   = False
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_toolbar())

        self._placeholder = QLabel(
            "Use  ＋ Add panel  above to add widgets here.\n"
            "Each becomes a movable, resizable window — drag its title bar to\n"
            "move it, drag an edge to resize.  Original tabs are unaffected.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setObjectName("CustomTabPlaceholder")
        lay.addWidget(self._placeholder, 1)

        # MDI area — each assigned panel gets its own movable/resizable window.
        self._mdi = QMdiArea()
        self._mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)
        self._mdi.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mdi.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mdi.hide()
        lay.addWidget(self._mdi, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("CustomTabToolbar")
        bar.setFixedHeight(30)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(6, 3, 6, 3)
        hl.setSpacing(6)

        self._add_btn = QToolButton()
        self._add_btn.setText("＋ Add widget")
        # InstantPopup: the WHOLE button opens the menu on a single click
        # (MenuButtonPopup split the button so only the little arrow worked).
        self._add_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self._add_btn.setToolTip(
            "Add a widget to this dashboard — pick à-la-carte from any tab's\n"
            "widgets, or a whole-tab shortcut. Each opens in a movable,\n"
            "resizable window; the original tabs are unaffected.")
        hl.addWidget(self._add_btn)

        self._unlock_btn = QToolButton()
        self._unlock_btn.setText("✏️ Edit Layout")
        self._unlock_btn.setCheckable(True)
        self._unlock_btn.setToolTip(
            "Edit this custom tab — reorder cards with ◀ ▶, remove with ✕.\n"
            "Click again (✔ Done) when finished.")
        self._unlock_btn.toggled.connect(self._on_unlock_toggled)
        hl.addWidget(self._unlock_btn)

        hl.addStretch(1)
        return bar

    # ── Public API ─────────────────────────────────────────────────────────

    def set_add_menu(self, menu) -> None:
        self._add_btn.setMenu(menu)

    def assign_panel(self, panel_key: str, panel_title: str = "") -> None:
        """Add a navigation card for panel_key.  Never reparents the panel."""
        if panel_key in self._assigned_keys:
            return
        if not panel_title:
            panel_title = panel_key
        self._assigned_keys.append(panel_key)
        # A live summary bound to the shared backend, when this panel provides
        # one; otherwise the card is a plain 'Open tab →' navigation link.
        from ui.tabs.custom_summaries import make_summary
        summary = make_summary(panel_key, self._cfg)
        card = _PanelCard(panel_key, panel_title, self, summary_widget=summary)
        card.navigate_requested.connect(
            lambda: self.panel_navigate_requested.emit(panel_key))
        card.remove_requested.connect(self._on_card_remove)
        card.move_left.connect(self._on_move_left)
        card.move_right.connect(self._on_move_right)
        card.set_unlock_mode(self._unlocked)
        self._cards[panel_key] = card
        # Wrap the card in a movable / resizable MDI sub-window.
        sub = _PanelSubWindow(panel_key, self._mdi)
        sub.setWidget(card)
        sub.setWindowTitle(panel_title)
        sub.closed.connect(self._on_card_remove)
        self._mdi.addSubWindow(sub)
        sub.resize(240, 260)
        sub.show()
        self._subwins[panel_key] = sub
        self._refresh_visibility()
        self._refresh_reorder_buttons()

    def unassign_panel(self, panel_key: str) -> None:
        """Remove the navigation card for panel_key."""
        if panel_key not in self._assigned_keys:
            return
        self._assigned_keys.remove(panel_key)
        self._cards.pop(panel_key, None)
        sub = self._subwins.pop(panel_key, None)
        if sub is not None:
            # removeSubWindow detaches without firing closeEvent (avoids a
            # re-entrant _on_card_remove); the card is a child so it goes too.
            self._mdi.removeSubWindow(sub)
            sub.deleteLater()
        self._refresh_visibility()
        self._refresh_reorder_buttons()

    @property
    def assigned_keys(self) -> list[str]:
        return list(self._assigned_keys)

    # ── Internals ─────────────────────────────────────────────────────────

    def _on_card_remove(self, panel_key: str) -> None:
        self.unassign_panel(panel_key)
        self.panel_unassign_requested.emit(self.panel_id, panel_key)

    def _on_move_left(self, panel_key: str) -> None:
        idx = self._assigned_keys.index(panel_key)
        if idx <= 0:
            return
        self._assigned_keys[idx - 1], self._assigned_keys[idx] = (
            self._assigned_keys[idx], self._assigned_keys[idx - 1])
        self._rebuild_card_order()

    def _on_move_right(self, panel_key: str) -> None:
        idx = self._assigned_keys.index(panel_key)
        if idx >= len(self._assigned_keys) - 1:
            return
        self._assigned_keys[idx], self._assigned_keys[idx + 1] = (
            self._assigned_keys[idx + 1], self._assigned_keys[idx])
        self._rebuild_card_order()

    def _rebuild_card_order(self) -> None:
        """Reflect the new key order.

        With free-floating MDI windows the on-screen position is the user's to
        set, so ◀ ▶ only reorders the saved key list (which fixes restore order)
        and, as a convenience, tiles the windows in that order.
        """
        self._mdi.tileSubWindows()
        self._refresh_reorder_buttons()

    def _refresh_reorder_buttons(self) -> None:
        n = len(self._assigned_keys)
        for i, key in enumerate(self._assigned_keys):
            card = self._cards.get(key)
            if card:
                card.set_can_move_left(i > 0)
                card.set_can_move_right(i < n - 1)

    def _refresh_visibility(self) -> None:
        has_cards = bool(self._assigned_keys)
        self._placeholder.setVisible(not has_cards)
        self._mdi.setVisible(has_cards)

    def _on_unlock_toggled(self, unlocked: bool) -> None:
        self._unlocked = unlocked
        self._unlock_btn.setText("✔ Done" if unlocked else "✏️ Edit Layout")
        for card in self._cards.values():
            card.set_unlock_mode(unlocked)

    # ── SquelchPanel lifecycle ─────────────────────────────────────────────

    def save_state(self) -> dict:
        return {
            "title":    self.panel_title,
            "assigned": list(self._assigned_keys),
        }

    def restore_state(self, state: dict) -> None:
        for key in state.get("assigned", []):
            if key not in self._assigned_keys:
                self._assigned_keys.append(key)
