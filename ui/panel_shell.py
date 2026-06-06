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
    QInputDialog, QApplication, QHBoxLayout, QLabel, QToolButton,
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


_TITLE_BAR_QSS = """
    background:#2a2a2a;
    border-bottom:1px solid #1a1a1a;
"""
_BTN_QSS = """
    QToolButton {
        background:#3a3a3a; color:#e0e0e0;
        border:1px solid #555; border-radius:3px;
        padding:1px 4px; font-size:11px;
        min-width:20px; min-height:20px;
    }
    QToolButton:hover { background:#505050; }
    QToolButton:pressed { background:#222; }
"""
_CLOSE_QSS = _BTN_QSS.replace("QToolButton:hover { background:#505050; }",
                               "QToolButton:hover { background:#a04040; }")
_FLOAT_QSS = _BTN_QSS.replace("QToolButton:hover { background:#505050; }",
                               "QToolButton:hover { background:#404080; }")


class _PanelTitleBar(QWidget):
    """Custom title bar for PanelDock that embeds panel_actions() as buttons.

    Replaces the default QDockWidget title bar so we can add per-panel
    toolbar actions while keeping float/close controls.
    """

    def __init__(self, dock: "PanelDock", title: str, actions: list):
        super().__init__(dock)
        self.setStyleSheet(_TITLE_BAR_QSS)
        self.setFixedHeight(28)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 4, 0)
        lay.setSpacing(3)

        lbl = QLabel(title)
        lbl.setStyleSheet("color:#f0f0f0;font-weight:bold;font-size:12px;")
        lay.addWidget(lbl, 1)

        # Per-panel action buttons
        for action in actions:
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setStyleSheet(_BTN_QSS)
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                if action.icon() and not action.icon().isNull()
                else Qt.ToolButtonStyle.ToolButtonTextOnly)
            lay.addWidget(btn)

        # Separator between panel actions and window controls
        if actions:
            sep = QWidget()
            sep.setFixedWidth(1)
            sep.setStyleSheet("background:#555;")
            lay.addWidget(sep)

        # Float button
        float_btn = QToolButton()
        float_btn.setText("⧉")
        float_btn.setToolTip("Float / re-dock this panel")
        float_btn.setStyleSheet(_FLOAT_QSS)
        float_btn.clicked.connect(
            lambda: dock.setFloating(not dock.isFloating()))
        lay.addWidget(float_btn)

        # Close (hide) button
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setToolTip("Hide panel")
        close_btn.setStyleSheet(_CLOSE_QSS)
        close_btn.clicked.connect(dock.hide)
        lay.addWidget(close_btn)


class PanelDock(QDockWidget):
    """QDockWidget wrapper for a SquelchPanel.

    Adds close-to-hide behaviour (panel is hidden, not destroyed),
    exposes the panel_id for workspace serialisation, and installs a
    custom title bar that renders the panel's panel_actions() as buttons.
    """

    def __init__(self, panel: SquelchPanel, parent: QMainWindow):
        title = getattr(panel, "panel_title", "") or type(panel).__name__
        super().__init__(title, parent)
        self._panel = panel
        self._panel_id = getattr(panel, "panel_id", "")
        self.setWidget(panel)
        self.setObjectName(f"dock_{self._panel_id}")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        actions = panel.panel_actions() if hasattr(panel, "panel_actions") else []
        self.setTitleBarWidget(_PanelTitleBar(self, title, actions))

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
        areas = [
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
            Qt.DockWidgetArea.TopDockWidgetArea,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        ]
        for i, (pid, panel) in enumerate(self._panels.items()):
            dock = PanelDock(panel, self)
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
            for pid, dock in self._docks.items():
                dock.setVisible(pid in visible)
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

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist(self):
        """Save dock arrangement and visible panels to config."""
        try:
            geo = self.saveGeometry().toBase64().data().decode()
            state = self.saveState().toBase64().data().decode()
            visible = [pid for pid, dock in self._docks.items()
                       if not dock.isHidden()]
            self.cfg.set("workspace.window_geometry", geo)
            self.cfg.set("workspace.geometry", state)
            self.cfg.set("workspace.visible_panels", visible)
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
