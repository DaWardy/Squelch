from __future__ import annotations
"""MainWindow view/appearance mixin — extracted from main_window.py."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

import logging
log = logging.getLogger(__name__)


class _MainWindowViewMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _set_theme(self, name: str):
        from core.themes import get_stylesheet
        fs = max(8, min(20, self.cfg.get("ui.font_size", 11)))
        self.setStyleSheet(get_stylesheet(name, fs))
        self.cfg.set("ui.theme", name)
        self.cfg.save()
        # Re-patch inline dark QSS strings for Light/HC themes.
        # main._apply_theme_fixes walks all child widgets and substitutes
        # hardcoded dark hex values — must run after stylesheet is applied.
        try:
            import main as _m
            if hasattr(_m, "_apply_theme_fixes"):
                _m._apply_theme_fixes(self, name)
        except Exception:
            pass

    def _set_font_size(self, size: int):
        """Change application font size globally; persisted to config."""
        size = max(8, min(20, size))
        # Update global QSS (cascades theme + font together)
        try:
            from core.themes import get_stylesheet
            theme = self.cfg.get("ui.theme", "Dark")
            self.setStyleSheet(get_stylesheet(theme, size))
        except Exception:
            pass
        # Set QApplication default font so widgets without explicit fonts resize
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                f = app.font()
                f.setPointSize(size)
                app.setFont(f)
                app.setStyleSheet(
                    app.styleSheet() +
                    f"QToolTip{{font-size:{size}pt;"
                    f"padding:6px;border:1px solid #333;"
                    f"background:#1a1a1a;}}")
        except Exception:
            pass
        self.cfg.set("ui.font_size", size)
        self.cfg.save()
        log.info(f"Font size set to {size}pt")

    def _apply_saved_font_size(self):
        """Apply saved font size preference on startup."""
        size = self.cfg.get("ui.font_size", 0)
        if size and isinstance(size, int) and 8 <= size <= 24:
            self._set_font_size(size)

    def _update_spectrum_action(self, index: int = -1):
        """Enable the Spectrum/Waterfall toggle only on tabs that support it."""
        act = getattr(self, '_spectrum_action', None)
        if act is None:
            return
        widget = self.tabs.currentWidget()
        has_spectrum = widget is not None and (
            hasattr(widget, '_spectrum') or
            hasattr(widget, '_waterfall') or
            hasattr(widget, 'toggle_spectrum') or
            hasattr(widget, '_toggle_spectrum'))
        act.setEnabled(has_spectrum)
        act.setVisible(has_spectrum)

    def _toggle_spectrum(self):
        rig_tab = self._tab_map.get("rig")
        if rig_tab and hasattr(rig_tab, '_spectrum_widget'):
            sw = rig_tab._spectrum_widget
            if sw:
                visible = not sw.isVisible()
                sw.setVisible(visible)
                if hasattr(rig_tab, '_spec_toggle'):
                    rig_tab._spec_toggle.setChecked(visible)

    def _toggle_ui_lock(self, locked: bool):
        """Lock/unlock UI layout — prevent accidental tab moves."""
        self.cfg.set("ui.layout_locked", locked)
        self.cfg.save()
        self.tabs.tabBar().setMovable(not locked)
        try:
            from PyQt6.QtWidgets import QSplitter
            for splitter in self.findChildren(QSplitter):
                for i in range(splitter.count()):
                    splitter.handle(i).setEnabled(not locked)
        except Exception:
            pass
        icon = "🔒" if locked else "🔓"
        self._lock_action.setText(
            f"{icon} {'Lock' if not locked else 'Unlock'} UI Layout")
