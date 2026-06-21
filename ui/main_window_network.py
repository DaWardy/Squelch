from __future__ import annotations
"""MainWindow network mixin — extracted from main_window.py."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

import logging
log = logging.getLogger(__name__)
from PyQt6.QtCore import QTimer


class _MainWindowNetworkMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _init_aprs(self):
        """
        Initialize APRS-IS client as app-level singleton.
        Auto-connects if APRS was running last session.
        """
        from network.aprs_anomaly import APRSAnomalyDetector
        self._aprs_anomaly = APRSAnomalyDetector()
        try:
            from aprs.aprs_client import APRSClient
            from aprs.beacon     import APRSBeacon
            self._aprs_client = APRSClient(self.cfg)
            self._aprs_beacon = APRSBeacon(
                self.cfg, self._aprs_client)
            # Auto-connect in background so startup does not block
            if self.cfg.get("aprs.auto_connect", False):
                import threading
                threading.Thread(
                    target=self._aprs_client.connect,
                    daemon=True, name="APRSAutoConnect").start()
            # Update map when packets arrive
            self._aprs_client.on_packet(
                self._on_aprs_packet)
            log.info("APRS client initialized")
        except Exception as e:
            log.debug(f"APRS init: {e}")
            self._aprs_client = None
            self._aprs_beacon = None


    def _init_satellites(self):
        """Initialize satellite tracker (background thread)."""
        try:
            from network.satellites import SatTracker
            self._sat_tracker = SatTracker(self.cfg)
            self._sat_tracker.on_update(
                self._on_sat_update)
            self._sat_tracker.start()
            log.info("Satellite tracker started")
        except Exception as e:
            log.debug(f"Satellite tracker: {e}")
            self._sat_tracker = None


    def _on_sat_update(self, positions: list):
        """Push satellite positions to map."""
        try:
            map_tab = self._tab_map.get("map")
            if map_tab and hasattr(
                    map_tab, "set_satellite_positions"):
                from PyQt6.QtCore import QTimer
                def _pass_dict(sp):
                    if sp is None:
                        return None
                    return {
                        "aos": sp.aos_utc.strftime("%H:%M UTC"),
                        "los": sp.los_utc.strftime("%H:%M UTC"),
                        "max_el": sp.max_el_deg,
                        "aos_az": sp.aos_az_deg,
                    }
                sats = [{"name":       p.name,
                         "lat":        p.lat,
                         "lon":        p.lon,
                         "alt_km":     p.alt_km,
                         "el_deg":     p.el_deg,
                         "az_deg":     p.az_deg,
                         "doppler_hz": p.doppler_hz,
                         "visible":    p.is_visible,
                         "next_pass":  _pass_dict(p.next_pass)}
                        for p in positions]
                QTimer.singleShot(0,
                    lambda s=sats:
                        map_tab.set_satellite_positions(s))
                # Route to rig_tab for rotor auto-track
                rig_tab = self._tab_map.get("rig")
                if rig_tab and hasattr(rig_tab, "update_from_sat_position"):
                    QTimer.singleShot(0,
                        lambda s=sats:
                            rig_tab.update_from_sat_position(s))
        except Exception:
            pass


    def _init_pskreporter(self):
        """
        Start PSKReporter submission if enabled.
        FT8 decodes from WSJT-X are forwarded here.
        """
        try:
            if not self.cfg.get(
                    "spotting.pskreporter_enabled",
                    True):
                self._pskreporter = None
                return
            from network.pskreporter import PSKReporter
            self._pskreporter = PSKReporter(self.cfg)
            self._pskreporter.start()
            log.info("PSKReporter submission started")
        except Exception as e:
            log.debug(f"PSKReporter init: {e}")
            self._pskreporter = None

    def _load_cty_background(self) -> None:
        """Load CTY.DAT in a background thread so DXCC lookup is accurate."""
        import threading
        def _worker():
            try:
                from network.cty_data import get_cty
                cty = get_cty()
                if cty.is_loaded:
                    log.info(
                        f"CTY.DAT ready: {cty.entity_count} DXCC entities")
                else:
                    log.warning("CTY.DAT could not be loaded")
            except Exception as e:
                log.debug(f"CTY.DAT load failed: {e}")
        threading.Thread(
            target=_worker, daemon=True, name="CTYLoader").start()

    def _update_cty_dat(self) -> None:
        """Help → Update DXCC Data: download latest CTY.DAT from country-files.com."""
        from PyQt6.QtWidgets import QProgressDialog, QMessageBox
        from PyQt6.QtCore import Qt, QTimer
        prog = QProgressDialog(
            "Downloading CTY.dat from country-files.com…", None,
            0, 0, self)
        prog.setWindowTitle("Updating DXCC Data")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        import threading
        def _worker():
            try:
                from network.cty_data import CTYData
                cty = CTYData()
                ok = cty.update()
                if ok:
                    from network import cty_data as _mod
                    _mod._cty = cty
                QTimer.singleShot(0,
                    lambda: self._cty_update_done(ok, cty, prog))
            except Exception as exc:
                QTimer.singleShot(0,
                    lambda e=exc: self._cty_update_done(False, None, prog, str(e)))
        threading.Thread(target=_worker, daemon=True,
                         name="CTYUpdate").start()

    def _cty_update_done(self, ok: bool, cty, prog,
                         error: str = "") -> None:
        from PyQt6.QtWidgets import QMessageBox
        prog.close()
        if ok and cty:
            QMessageBox.information(
                self, "DXCC Data Updated",
                f"CTY.dat updated successfully.\n"
                f"{cty.entity_count} DXCC entities loaded.\n\n"
                "DXCC tracking will use the new data immediately.")
        else:
            QMessageBox.warning(
                self, "DXCC Update Failed",
                f"Could not download CTY.dat.\n{error}\n\n"
                "Check your internet connection and try again.\n"
                "The existing data file (if any) is unchanged.")

    def _on_aprs_packet(self, packet):
        """Update map tab, run anomaly detection, push to RF Lab decode monitor."""
        try:
            map_tab = self._tab_map.get("map")
            if map_tab and hasattr(map_tab, "set_aprs_stations"):
                stations = self._aprs_client.stations_on_map()
                QTimer.singleShot(0,
                    lambda s=stations:
                        map_tab.set_aprs_stations(s))
        except Exception:
            pass
        try:
            alerts = self._aprs_anomaly.feed(packet)
            for alert in alerts:
                log.warning("APRS anomaly: %s", alert)
                self._aprs_anomaly_alert(alert)
        except Exception:
            pass
        try:
            rf_lab = self._tab_map.get("rf_lab")
            if rf_lab and hasattr(rf_lab, "append_decode") and packet:
                rf_lab.append_decode(
                    "APRS", 144_390_000,
                    callsign=packet.call_ssid,
                    message=(packet.comment or "")[:80],
                )
        except Exception:
            pass
        # Mirror into the unified Signal store (best-effort, thread-safe).
        try:
            if packet:
                from core.signal_ingest import ingest, signal_from_aprs
                ingest(signal_from_aprs(packet))
        except Exception:
            pass
        # Route APRS message packets to the map message log
        try:
            if packet:
                msg_data = packet.parse_message()
                if msg_data:
                    to_call, message, _msg_id = msg_data
                    map_tab = self._tab_map.get("map")
                    if map_tab and hasattr(map_tab, "add_aprs_message"):
                        from core.guest_op import operating_callsign
                        my_call = (operating_callsign(self.cfg) or "").upper()
                        directed = to_call.upper() == my_call
                        QTimer.singleShot(0, lambda f=packet.call_ssid,
                                          t=to_call, m=message, d=directed:
                                          map_tab.add_aprs_message(f, t, m, d))
        except Exception:
            pass

    def _aprs_anomaly_alert(self, alert) -> None:
        """Surface an anomaly alert to the user (status bar + optional tab)."""
        try:
            sb = getattr(self, "statusBar", None)
            if callable(sb):
                sb().showMessage(f"⚠ APRS {alert.rule}: {alert.callsign} — "
                                 f"{alert.description}", 8000)
        except Exception:
            pass
        try:
            # Push to the APRS/map tab if it has an anomaly log widget
            map_tab = self._tab_map.get("map")
            if map_tab and hasattr(map_tab, "add_aprs_alert"):
                map_tab.add_aprs_alert(alert)
        except Exception:
            pass

