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
    QFrame, QScrollArea, QSizePolicy,
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
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._key = panel_key
        self.setObjectName("CustomTabPanelCard")
        self.setFixedWidth(160)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
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

        root.addStretch(1)

        # Navigate button
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


class CustomLayoutTab(SquelchPanel, QWidget):
    """A tab that shows navigation cards for user-chosen panels.

    Panels are NEVER moved out of the tab bar.  Clicking a card's 'Open tab'
    button emits ``panel_navigate_requested`` so MainWindow can switch to the
    correct tab.  Cards can be reordered by the user in unlock mode.
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
        self._unlocked   = False
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_toolbar())

        self._placeholder = QLabel(
            "Use  ＋ Add panel  above to add shortcuts here.\n"
            "Original tabs are unaffected — panels always remain accessible.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setObjectName("CustomTabPlaceholder")
        lay.addWidget(self._placeholder, 1)

        # Scroll area for cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.hide()

        self._card_container = QWidget()
        self._card_layout = QHBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(12, 12, 12, 12)
        self._card_layout.setSpacing(10)
        self._card_layout.addStretch(1)  # trailing stretch keeps cards left-aligned
        self._scroll.setWidget(self._card_container)
        lay.addWidget(self._scroll, 1)

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
            "Add a panel shortcut to this tab.\n"
            "The original panel stays in its own tab — nothing is moved.")
        hl.addWidget(self._add_btn)

        self._unlock_btn = QToolButton()
        self._unlock_btn.setText("🔓 Rearrange")
        self._unlock_btn.setCheckable(True)
        self._unlock_btn.setToolTip(
            "Unlock card order — use ◀ ▶ to reorder, ✕ to remove")
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
        card = _PanelCard(panel_key, panel_title, self)
        card.navigate_requested.connect(
            lambda: self.panel_navigate_requested.emit(panel_key))
        card.remove_requested.connect(self._on_card_remove)
        card.move_left.connect(self._on_move_left)
        card.move_right.connect(self._on_move_right)
        card.set_unlock_mode(self._unlocked)
        self._cards[panel_key] = card
        # Insert before the trailing stretch (last item)
        insert_pos = self._card_layout.count() - 1
        self._card_layout.insertWidget(insert_pos, card)
        self._refresh_visibility()
        self._refresh_reorder_buttons()

    def unassign_panel(self, panel_key: str) -> None:
        """Remove the navigation card for panel_key."""
        if panel_key not in self._assigned_keys:
            return
        self._assigned_keys.remove(panel_key)
        card = self._cards.pop(panel_key, None)
        if card:
            card.setParent(None)
            card.deleteLater()
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
        """Re-insert card widgets in the correct order."""
        for card in self._cards.values():
            self._card_layout.removeWidget(card)
        for key in self._assigned_keys:
            card = self._cards.get(key)
            if card:
                insert_pos = self._card_layout.count() - 1
                self._card_layout.insertWidget(insert_pos, card)
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
        self._scroll.setVisible(has_cards)

    def _on_unlock_toggled(self, unlocked: bool) -> None:
        self._unlocked = unlocked
        self._unlock_btn.setText("🔒 Lock" if unlocked else "🔓 Rearrange")
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
