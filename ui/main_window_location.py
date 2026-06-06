"""MainWindow location/grid/callsign mixin — extracted from main_window.py."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

import logging
log = logging.getLogger(__name__)


class _MainWindowLocationMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _on_loc(self, loc, _rr_refresh):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda l=loc: self._apply_loc(l))

    def _apply_loc(self, loc):
        disp = loc.display if loc.is_valid else "—"
        self._loc_lbl.setText(disp)
        self._sb_loc.setText(f"Location: {disp}")
        if loc.is_valid:
            import threading
            threading.Thread(
                target=self.location.write_dump1090_receiver_json,
                daemon=True).start()
        if loc.grid:
            self._grid_lbl.setText(loc.grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;font-family:'Courier New';")
        elif loc.is_valid:
            from core.location import _latlon_to_grid
            try:
                grid = _latlon_to_grid(loc.lat, loc.lon)
                self._grid_lbl.setText(grid)
                self._grid_lbl.setStyleSheet(
                    "color:#3fbe6f;font-family:'Courier New';")
            except Exception:
                pass

    def _on_callsign_edit(self, val: str):
        """Save inline callsign edit to cfg AND active profile."""
        self.cfg.callsign = val
        self.cfg.save()
        try:
            from core.profiles import get_profile_manager
            pm = get_profile_manager()
            cur = pm.current
            if cur:
                cur.callsign = val
                pm.save()
        except Exception:
            pass
        try:
            self._cs_lbl.setText(val)
        except Exception:
            pass
        log.info(f"Callsign updated to: {val}")

    def _on_location_found(self, grid: str, display: str,
                            lat: float, lon: float):
        """Slot — always called on main thread via signal."""
        if not grid:
            return
        grid = grid.upper()
        self._grid_lbl.setText(grid)
        self._grid_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';")
        if display and hasattr(self, "_loc_lbl"):
            self._loc_lbl.setText(display)
        self.cfg.grid = grid
        if lat:
            self.cfg.set("location.lat", lat)
            self.cfg.set("location.lon", lon)
        self.cfg.save()
        for tab in self._tab_map.values():
            if hasattr(tab, "on_location_change"):
                try:
                    tab.on_location_change(self.location)
                except Exception:
                    pass

    def _on_location_failed(self, msg: str):
        self._grid_lbl.setText(msg)
        self._grid_lbl.setStyleSheet(
            "color:#cc6644;font-family:'Courier New';")

    def _on_grid_edit(self, val: str):
        """Handle grid/ZIP/city/MGRS entry from top bar."""
        from core.location import _valid_grid, _latlon_to_grid
        import threading

        val = val.strip()
        if not val:
            return

        def _set_grid(grid: str, display: str = "",
                      lat: float = 0.0, lon: float = 0.0):
            if not grid:
                return
            grid = grid.upper()
            self._grid_lbl.setText(grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;font-family:'Courier New';")
            if display:
                if hasattr(self, "_loc_lbl"):
                    self._loc_lbl.setText(display)
                if hasattr(self, "_sb_loc"):
                    self._sb_loc.setText(f"Location: {display}")
            self.cfg.grid = grid
            if lat:
                self.cfg.set("location.lat", lat)
                self.cfg.set("location.lon", lon)
            self.cfg.save()
            for key, tab in self._tab_map.items():
                if hasattr(tab, "on_location_change"):
                    try:
                        tab.on_location_change(self.location)
                    except Exception:
                        pass

        if _valid_grid(val):
            self.location.set_from_grid(val.upper())
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda g=val.upper(): _set_grid(g))
        else:
            self._grid_lbl.setText("Searching…")
            self._grid_lbl.setStyleSheet("font-family:'Courier New';")

            def _search(q=val):
                try:
                    loc = self.location.search(q)
                    if loc and loc.is_valid:
                        grid = loc.grid or ""
                        if not grid and loc.lat:
                            try:
                                grid = _latlon_to_grid(loc.lat, loc.lon)
                            except Exception:
                                pass
                        if grid:
                            self.location.apply(loc)
                            city  = getattr(loc, "city",  "") or ""
                            state = getattr(loc, "state", "") or ""
                            disp  = ", ".join(filter(None, [city, state]))
                            lat_v = float(getattr(loc, "lat", 0.0) or 0.0)
                            lon_v = float(getattr(loc, "lon", 0.0) or 0.0)
                            self._location_found.emit(grid, disp, lat_v, lon_v)
                        else:
                            self._location_failed.emit(
                                "Not found — try grid square")
                    else:
                        self._location_failed.emit("Not found")
                except Exception as e:
                    log.debug(f"Location search: {e}")
                    self._location_failed.emit("Search failed")

            threading.Thread(target=_search, daemon=True).start()

    def _restore_location(self):
        """Show previously saved location on startup."""
        grid = (self.cfg.get("location.grid_square", "")
                or self.cfg.grid or "")
        if grid:
            self._grid_lbl.setText(grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;font-family:'Courier New';")
            city  = self.cfg.get("location.city", "")
            state = self.cfg.get("location.state", "")
            if city and state:
                disp = f"{grid}  |  {city}, {state}"
            elif city:
                disp = f"{grid}  |  {city}"
            else:
                disp = grid
            self._loc_lbl.setText(disp)
            self._sb_loc.setText(f"Location: {disp}")
        elif self.cfg.get("callsign"):
            self._loc_lbl.setText("No location set — click grid to set")
            self._loc_lbl.setStyleSheet("")
