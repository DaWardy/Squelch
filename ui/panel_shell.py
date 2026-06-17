from __future__ import annotations
"""PanelShell — workspace-mode window.

Runs alongside MainWindow. When the user activates workspace mode
(View → Workspace Mode), MainWindow hands its panel instances to
PanelShell, which wraps each one in a QDockWidget for free-form
arrangement.

Key features:
  • Each SquelchPanel becomes a dockable, floatable, closeable dock.
  • Workspace geometry + visible panels saved to JSON.
  • Built-in presets: HF Ops, Digital, Winlink, Custom.
  • View menu controls which panels are shown.
  • Falls back to MainWindow tab-mode if something breaks.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QMenu, QMessageBox,
    QInputDialog, QHBoxLayout, QLabel, QToolButton,
)

from ui.panel import SquelchPanel

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)

# ── Built-in workspace presets ─────────────────────────────────────────────
PRESETS: dict[str, dict] = {
    "HF Ops": {
        "visible": ["rig", "modes", "band_conditions", "log"],
        "description": "Rig control + FT8/modes + band conditions + log",
    },
    "Digital Monitoring": {
        "visible": ["sdr", "digital", "map", "modes"],
        "description": "SDR waterfall + digital decoder + heard map",
    },
    "Winlink": {
        "visible": ["winlink", "band_conditions", "localrf", "rig"],
        "description": "Winlink + propagation + local repeaters",
    },
    "Full Station": {
        "visible": ["rig", "modes", "sdr", "digital", "log",
                    "band_conditions", "map", "localrf"],
        "description": "All operational panels",
    },
}


def _title_bar_qss(t) -> str:
    return (f"background:{t.bg_secondary};"
            f"border-bottom:1px solid {t.border};")

def _title_bar_locked_qss(t) -> str:
    return (f"background:{t.meter_bg};"
            f"border-bottom:1px solid {t.accent};")

def _btn_qss(t) -> str:
    return (
        f"QToolButton{{background:{t.bg_tertiary};color:{t.fg_primary};"
        f"border:1px solid {t.border};border-radius:3px;"
        f"padding:1px 4px;font-size:11px;min-width:20px;min-height:20px;}}"
        f"QToolButton:hover{{background:{t.tab_selected_bg};}}"
        f"QToolButton:pressed{{background:{t.bg_primary};}}"
    )

def _close_qss(t) -> str:
    return (_btn_qss(t)
            .replace(f"QToolButton:hover{{background:{t.tab_selected_bg};}}",
                     "QToolButton:hover{background:#a04040;}"))

def _float_qss(t) -> str:
    return (_btn_qss(t)
            .replace(f"QToolButton:hover{{background:{t.tab_selected_bg};}}",
                     "QToolButton:hover{background:#404080;}"))

def _lock_qss(t) -> str:
    return (_btn_qss(t)
            .replace(f"QToolButton:hover{{background:{t.tab_selected_bg};}}",
                     "QToolButton:hover{background:#406040;}"))

def _zone_qss(t) -> str:
    return (_btn_qss(t)
            .replace(f"QToolButton:hover{{background:{t.tab_selected_bg};}}",
                     "QToolButton:hover{background:#504020;}"))

def _label_qss(t) -> str:
    return f"color:{t.fg_primary};font-weight:bold;font-size:12px;"

_ZONE_AREAS = {
    "← Left":   Qt.DockWidgetArea.LeftDockWidgetArea,
    "→ Right":   Qt.DockWidgetArea.RightDockWidgetArea,
    "↑ Top":    Qt.DockWidgetArea.TopDockWidgetArea,
    "↓ Bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
}

_MOVABLE_FEATURES = (
    QDockWidget.DockWidgetFeature.DockWidgetMovable
    | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    | QDockWidget.DockWidgetFeature.DockWidgetClosable
)
_LOCKED_FEATURES = QDockWidget.DockWidgetFeature.DockWidgetClosable


class _PanelTitleBar(QWidget):
    """Custom title bar for PanelDock with per-panel lock and zone controls.

    Replaces the default QDockWidget title bar so we can add:
      • Per-panel action buttons (panel_actions())
      • Zone button (⊞) — send this panel to a specific dock area
      • Lock button (🔓/🔒) — freeze position; other docks can't push it
      • Float button (⧉) and close button (✕)
    """

    def __init__(self, dock: "PanelDock", title: str, actions: list, theme_name: str = "Dark"):
        super().__init__(dock)
        from core.themes import get_theme
        self._dock = dock
        self._theme = get_theme(theme_name)
        self.setStyleSheet(_title_bar_qss(self._theme))
        self.setFixedHeight(28)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 4, 0)
        lay.setSpacing(3)

        lbl = QLabel(title)
        lbl.setStyleSheet(_label_qss(self._theme))
        lay.addWidget(lbl, 1)

        # Per-panel action buttons
        for action in actions:
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setStyleSheet(_btn_qss(self._theme))
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                if action.icon() and not action.icon().isNull()
                else Qt.ToolButtonStyle.ToolButtonTextOnly)
            lay.addWidget(btn)

        if actions:
            sep = QWidget()
            sep.setFixedWidth(1)
            sep.setStyleSheet(f"background:{self._theme.border};")
            lay.addWidget(sep)

        # Zone button — send to a specific dock area
        zone_btn = QToolButton()
        zone_btn.setText("⊞")
        zone_btn.setToolTip("Send to zone — dock this panel to a specific area")
        zone_btn.setStyleSheet(_zone_qss(self._theme))
        zone_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zone_menu = QMenu(zone_btn)
        for label, area in _ZONE_AREAS.items():
            act = zone_menu.addAction(label)
            act.triggered.connect(
                lambda _=False, a=area: self._send_to_zone(a))
        zone_menu.addSeparator()
        float_act = zone_menu.addAction("⧉ Float")
        float_act.triggered.connect(lambda: dock.setFloating(True))
        zone_btn.setMenu(zone_menu)
        lay.addWidget(zone_btn)

        # Lock button — freeze position so dragging others doesn't move this
        self._lock_btn = QToolButton()
        self._lock_btn.setText("🔓")
        self._lock_btn.setCheckable(True)
        self._lock_btn.setToolTip(
            "Lock panel — prevent it from moving when other panels are docked")
        self._lock_btn.setStyleSheet(_lock_qss(self._theme))
        self._lock_btn.toggled.connect(self._on_lock_toggled)
        lay.addWidget(self._lock_btn)

        # Float button
        float_btn = QToolButton()
        float_btn.setText("⧉")
        float_btn.setToolTip("Float / re-dock this panel")
        float_btn.setStyleSheet(_float_qss(self._theme))
        float_btn.clicked.connect(
            lambda: dock.setFloating(not dock.isFloating()))
        lay.addWidget(float_btn)

        # Close (hide) button
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setToolTip("Hide panel")
        close_btn.setStyleSheet(_close_qss(self._theme))
        close_btn.clicked.connect(dock.hide)
        lay.addWidget(close_btn)

    def _send_to_zone(self, area: Qt.DockWidgetArea):
        """Move this dock to the given area without disturbing locked panels."""
        shell = self._dock.parent()
        if isinstance(shell, QMainWindow):
            shell.addDockWidget(area, self._dock)
            self._dock.show()

    def _on_lock_toggled(self, locked: bool):
        self._dock.set_locked(locked)
        if locked:
            self._lock_btn.setText("🔒")
            self.setStyleSheet(_title_bar_locked_qss(self._theme))
        else:
            self._lock_btn.setText("🔓")
            self.setStyleSheet(_title_bar_qss(self._theme))

    def set_locked(self, locked: bool):
        """Sync button state when restoring from saved workspace."""
        self._lock_btn.setChecked(locked)


class PanelDock(QDockWidget):
    """QDockWidget wrapper for a SquelchPanel.

    Adds close-to-hide behaviour, exposes panel_id for serialisation,
    installs a custom title bar with lock and zone controls.
    """

    def __init__(self, panel: SquelchPanel, parent: QMainWindow,
                 theme_name: str = "Dark"):
        title = getattr(panel, "panel_title", "") or type(panel).__name__
        super().__init__(title, parent)
        self._panel = panel
        self._panel_id = getattr(panel, "panel_id", "")
        self._locked = False
        self.setWidget(panel)
        self.setObjectName(f"dock_{self._panel_id}")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFeatures(_MOVABLE_FEATURES)
        actions = panel.panel_actions() if hasattr(panel, "panel_actions") else []
        self._title_bar = _PanelTitleBar(self, title, actions, theme_name)
        self.setTitleBarWidget(self._title_bar)

    def set_locked(self, locked: bool):
        """Lock or unlock this dock's position."""
        self._locked = locked
        self.setFeatures(_LOCKED_FEATURES if locked else _MOVABLE_FEATURES)

    @property
    def is_locked(self) -> bool:
        return self._locked

    def restore_lock(self, locked: bool):
        """Restore lock state from saved workspace (syncs button too)."""
        self._title_bar.set_locked(locked)
        self.set_locked(locked)

    def closeEvent(self, event):
        """Hide rather than destroy — panel state is preserved."""
        self.hide()
        event.ignore()

    @property
    def panel_id(self) -> str:
        return self._panel_id

    @property
    def panel(self) -> SquelchPanel:
        return self._panel


class PanelShell(QMainWindow):
    """Workspace-mode main window.

    Instantiated by MainWindow when the user activates workspace mode.
    Takes ownership of the panel widgets (temporary reparenting) and
    returns them when workspace mode is deactivated.
    """

    def __init__(self, panels: dict[str, SquelchPanel],
                 cfg: "Config", parent: QWidget | None = None):
        super().__init__(parent)
        self.cfg = cfg
        self._panels = panels         # panel_id → SquelchPanel
        self._docks:  dict[str, PanelDock] = {}
        self._workspace_dir = self._get_workspace_dir()

        self.setWindowTitle("Squelch — Workspace")
        self.setDockNestingEnabled(True)

        self._build_docks()
        self._build_menus()

        # Restore saved geometry or load default preset
        saved = cfg.get("workspace.geometry", "")
        if saved:
            try:
                self.restoreState(QByteArray.fromBase64(saved.encode()))
                self.restoreGeometry(
                    QByteArray.fromBase64(
                        cfg.get("workspace.window_geometry", "").encode()))
            except Exception:
                self._apply_preset("HF Ops")
        else:
            self._apply_preset("HF Ops")
        # Restore locked panels
        for pid in cfg.get("workspace.locked_panels", []):
            if pid in self._docks:
                self._docks[pid].restore_lock(True)

        # Ctrl+Shift+1-4: quick-switch built-in presets
        from PyQt6.QtGui import QKeySequence, QShortcut
        for idx, name in enumerate(list(PRESETS)[:4], start=1):
            sc = QShortcut(
                QKeySequence(f"Ctrl+Shift+{idx}"), self)
            sc.activated.connect(
                lambda _=False, n=name: self._apply_preset_with_notice(n))

    # ── Setup ──────────────────────────────────────────────────────────────

    def _get_workspace_dir(self) -> Path:
        try:
            from core.config import USER_DIR
            d = USER_DIR / "workspaces"
        except Exception:
            d = Path.home() / ".config" / "squelch" / "workspaces"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _build_docks(self):
        """Wrap every panel in a PanelDock and add to window."""
        theme_name = self.cfg.get("ui.theme", "Dark")
        areas = [
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
            Qt.DockWidgetArea.TopDockWidgetArea,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        ]
        for i, (pid, panel) in enumerate(self._panels.items()):
            dock = PanelDock(panel, self, theme_name)
            self._docks[pid] = dock
            area = areas[i % 2]   # alternate left/right by default
            self.addDockWidget(area, dock)
        # Stack left docks tabbed initially to avoid overcrowding
        left = [d for d in self._docks.values()
                if self.dockWidgetArea(d) ==
                Qt.DockWidgetArea.LeftDockWidgetArea]
        for i in range(1, len(left)):
            self.tabifyDockWidget(left[0], left[i])

    def _build_menus(self):
        mb = self.menuBar()

        # ── Panels menu ──────────────────────────────────────────────
        pm = mb.addMenu("&Panels")
        for pid, dock in self._docks.items():
            act = dock.toggleViewAction()
            act.setText(dock.windowTitle())
            pm.addAction(act)

        pm.addSeparator()
        show_all = pm.addAction("Show All")
        show_all.triggered.connect(self._show_all_panels)
        hide_all = pm.addAction("Hide All")
        hide_all.triggered.connect(self._hide_all_panels)

        # ── Workspaces menu ───────────────────────────────────────────
        wm = mb.addMenu("&Workspace")

        for name, meta in PRESETS.items():
            act = wm.addAction(name)
            act.setToolTip(meta["description"])
            act.triggered.connect(
                lambda _=False, n=name: self._apply_preset(n))

        wm.addSeparator()

        # User-saved workspaces
        self._user_ws_menu = wm.addMenu("Saved workspaces")
        self._refresh_user_workspaces()

        wm.addSeparator()
        wm.addAction("Save workspace…").triggered.connect(
            self._save_workspace_as)
        wm.addAction("Reset to default").triggered.connect(
            lambda: self._apply_preset("HF Ops"))

        # ── Snap Layout menu ──────────────────────────────────────────
        sl = wm.addMenu("Snap Layout")
        for layout_name in ("Left | Right", "Top | Bottom", "2×2 Grid"):
            act = sl.addAction(layout_name)
            act.triggered.connect(
                lambda _=False, n=layout_name: self._apply_snap_layout(n))

        # ── View menu ─────────────────────────────────────────────────
        vm = mb.addMenu("&View")
        back = vm.addAction("⬅  Back to tab mode")
        back.setToolTip(
            "Return to the standard tab layout.\n"
            "Your workspace arrangement is saved automatically.")
        back.triggered.connect(self._exit_workspace_mode)

    # ── Preset / workspace management ──────────────────────────────────────

    def _apply_preset(self, name: str):
        """Show only the panels listed in the preset, hide the rest."""
        preset = PRESETS.get(name)
        if not preset:
            return
        visible = set(preset["visible"])
        for pid, dock in self._docks.items():
            if pid in visible:
                dock.show()
            else:
                dock.hide()
        log.info(f"Workspace preset applied: {name}")

    def _apply_preset_with_notice(self, name: str):
        """Apply preset and show a 2-second status bar confirmation."""
        self._apply_preset(name)
        self.statusBar().showMessage(f"Preset: {name} applied", 2000)

    def _show_all_panels(self):
        for dock in self._docks.values():
            dock.show()

    def _hide_all_panels(self):
        for dock in self._docks.values():
            dock.hide()

    def _save_workspace_as(self):
        name, ok = QInputDialog.getText(
            self, "Save workspace", "Workspace name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        state = {
            "visible": [pid for pid, dock in self._docks.items()
                        if not dock.isHidden()],
            "locked":  [pid for pid, dock in self._docks.items()
                        if dock.is_locked],
            "geometry": self.saveState().toBase64().data().decode(),
            "window":   self.saveGeometry().toBase64().data().decode(),
        }
        path = self._workspace_dir / f"{name}.json"
        path.write_text(json.dumps(state, indent=2))
        self._refresh_user_workspaces()
        log.info(f"Workspace saved: {path}")

    def _refresh_user_workspaces(self):
        self._user_ws_menu.clear()
        for ws_file in sorted(self._workspace_dir.glob("*.json")):
            name = ws_file.stem
            act = self._user_ws_menu.addAction(name)
            act.triggered.connect(
                lambda _=False, p=ws_file: self._load_workspace_file(p))
        if not list(self._workspace_dir.glob("*.json")):
            self._user_ws_menu.addAction("(none saved yet)").setEnabled(False)

    def _load_workspace_file(self, path: Path):
        try:
            state = json.loads(path.read_text())
            visible = set(state.get("visible", []))
            locked  = set(state.get("locked", []))
            for pid, dock in self._docks.items():
                dock.setVisible(pid in visible)
                dock.restore_lock(pid in locked)
            if "geometry" in state:
                self.restoreState(
                    QByteArray.fromBase64(state["geometry"].encode()))
            if "window" in state:
                self.restoreGeometry(
                    QByteArray.fromBase64(state["window"].encode()))
            log.info(f"Workspace loaded: {path.stem}")
        except Exception as e:
            QMessageBox.warning(
                self, "Load failed", f"Could not load workspace:\n{e}")

    # ── Snap layouts ───────────────────────────────────────────────────────

    def _apply_snap_layout(self, layout: str):
        """Tile all visible panels into a named snap layout."""
        visible = [d for d in self._docks.values() if not d.isHidden()]
        if not visible:
            return
        if layout == "Left | Right":
            self._snap_lr(visible)
        elif layout == "Top | Bottom":
            self._snap_tb(visible)
        elif layout == "2×2 Grid":
            self._snap_grid(visible)
        log.info(f"Snap layout applied: {layout}")

    def _snap_lr(self, visible: list) -> None:
        """Split visible panels into left and right columns (tabbed within each)."""
        L = Qt.DockWidgetArea.LeftDockWidgetArea
        R = Qt.DockWidgetArea.RightDockWidgetArea
        mid = max(1, len(visible) // 2)
        left, right = visible[:mid], visible[mid:]
        for d in left:
            self.addDockWidget(L, d); d.show()
        for i in range(1, len(left)):
            self.tabifyDockWidget(left[0], left[i])
        for d in right:
            self.addDockWidget(R, d); d.show()
        for i in range(1, len(right)):
            self.tabifyDockWidget(right[0], right[i])
        if left and right:
            w = self.width()
            self.resizeDocks([left[0], right[0]], [w // 2, w // 2],
                             Qt.Orientation.Horizontal)

    def _snap_tb(self, visible: list) -> None:
        """Split visible panels into top and bottom rows (tabbed within each)."""
        T = Qt.DockWidgetArea.TopDockWidgetArea
        B = Qt.DockWidgetArea.BottomDockWidgetArea
        mid = max(1, len(visible) // 2)
        top, bot = visible[:mid], visible[mid:]
        for d in top:
            self.addDockWidget(T, d); d.show()
        for i in range(1, len(top)):
            self.tabifyDockWidget(top[0], top[i])
        for d in bot:
            self.addDockWidget(B, d); d.show()
        for i in range(1, len(bot)):
            self.tabifyDockWidget(bot[0], bot[i])
        if top and bot:
            h = self.height()
            self.resizeDocks([top[0], bot[0]], [h // 2, h // 2],
                             Qt.Orientation.Vertical)

    def _snap_grid(self, visible: list) -> None:
        """Tile up to 4 panels in a 2×2 grid; extras tabbed onto top-left."""
        vs = visible[:4]
        extra = visible[4:]
        L = Qt.DockWidgetArea.LeftDockWidgetArea
        H = Qt.Orientation.Horizontal
        V = Qt.Orientation.Vertical
        self.addDockWidget(L, vs[0]); vs[0].show()
        if len(vs) >= 2:
            self.splitDockWidget(vs[0], vs[1], H)
            vs[1].show()
        if len(vs) >= 3:
            self.splitDockWidget(vs[0], vs[2], V)
            vs[2].show()
        if len(vs) == 4:
            self.splitDockWidget(vs[1], vs[3], V)
            vs[3].show()
        w, h = self.width(), self.height()
        if len(vs) >= 2:
            self.resizeDocks([vs[0], vs[1]], [w // 2, w // 2], H)
        if len(vs) >= 3:
            self.resizeDocks([vs[0], vs[2]], [h // 2, h // 2], V)
        if len(vs) == 4:
            self.resizeDocks([vs[1], vs[3]], [h // 2, h // 2], V)
        for d in extra:
            self.tabifyDockWidget(vs[0], d)

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist(self):
        """Save dock arrangement, visible panels, and lock states to config."""
        try:
            geo = self.saveGeometry().toBase64().data().decode()
            state = self.saveState().toBase64().data().decode()
            visible = [pid for pid, dock in self._docks.items()
                       if not dock.isHidden()]
            locked = [pid for pid, dock in self._docks.items()
                      if dock.is_locked]
            self.cfg.set("workspace.window_geometry", geo)
            self.cfg.set("workspace.geometry", state)
            self.cfg.set("workspace.visible_panels", visible)
            self.cfg.set("workspace.locked_panels", locked)
            self.cfg.save()
        except Exception as e:
            log.debug(f"PanelShell persist: {e}")

    def _exit_workspace_mode(self):
        """Return panels to MainWindow tab mode."""
        self._persist()
        # Reparent panels back before hiding
        for pid, dock in self._docks.items():
            dock.setWidget(None)
            panel = self._panels[pid]
            panel.setParent(None)
        # Signal parent MainWindow to re-adopt panels
        if self.parent():
            try:
                self.parent().exit_workspace_mode()
            except AttributeError:
                pass
        self.hide()

    def closeEvent(self, event):
        self._persist()
        self._exit_workspace_mode()
        event.ignore()   # let MainWindow handle the actual close
