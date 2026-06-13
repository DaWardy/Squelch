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
                sats = [{"name":   p.name,
                         "lat":    p.lat,
                         "lon":    p.lon,
                         "alt_km": p.alt_km,
                         "el_deg": p.el_deg,
                         "visible": p.is_visible}
                        for p in positions]
                QTimer.singleShot(0,
                    lambda s=sats:
                        map_tab.set_satellite_positions(s))
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


    def _on_aprs_packet(self, packet):
        """Update map tab with new APRS station and run anomaly detection."""
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

