from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_device_connect.py

SDR device enumeration + connection management for the SDR tab, extracted from
sdr_tab.py (HOUSE-CS complexity split): background device scan, combo
population (incl. the RTL-TCP fallback), driver-type label, device-select
dispatch to the hardware-specific settings panel, and connect / disconnect.

`_SDRDeviceConnectMixin` is mixed into `SDRTab`. Every cross-reference is a
call via self, so the streaming/plot core and the per-device panel builders
stay where they are:
  * self._on_samples                         — stream callback (host core)
  * self._update_axes / self._draw_band_segments  — plot core (host)
  * self._hackrf_panel / _usrp_panel / _rtlsdr_panel / _sdrplay_panel
                                             — _SDRDevicePanelsMixin
  * self._manager / self._devices / self._dev_combo / self._connect_btn /
    self._sdr_status / self._tx_grp / self._tx_indicator / self._dev_panel /
    self._controls_layout / self._rtltcp_dev / self._current / self._span_hz

HAS_RTLTCP / rtltcp_is_running / RTLTCPDevice come from ui.tabs.sdr_tab (which
resolves them with a graceful fallback) — imported lazily to avoid a cycle.
"""

import logging
import threading

from PyQt6.QtCore import QTimer

from sdr.soapy_device import SoapyManager, HAS_SOAPY

log = logging.getLogger(__name__)

# Sentinel for the always-available synthetic source (like the RTL-TCP None
# sentinel). Lets a no-hardware user bring the whole SDR stack alive.
SIM_DEVICE = "__SIM__"


class _SDRDeviceConnectMixin:
    """Enumerate, select, and connect/disconnect SDR hardware."""

    def _enumerate_devices(self):
        """Enumerate SDR devices in background; always calls _populate_devices."""
        def _do():
            if not HAS_SOAPY:
                QTimer.singleShot(0, lambda: self._populate_devices([]))
                return
            try:
                log.info("SDR: enumerating devices via SoapySDR")
                devs = SoapyManager.enumerate()
                log.info(f"SDR: found {len(devs)} device(s)")
            except Exception as e:
                log.warning(f"SDR: enumerate failed: {e}")
                devs = []
            QTimer.singleShot(0, lambda d=devs: self._populate_devices(d))
        # Update status so user can see a scan is in progress
        if hasattr(self, "_dev_combo"):
            self._dev_combo.clear()
            self._dev_combo.addItem(self.tr("— Scanning… —"))
        threading.Thread(target=_do, daemon=True, name="SDREnum").start()

    def _populate_devices(self, devices: list):
        from ui.tabs.sdr_tab import HAS_RTLTCP, rtltcp_is_running
        self._devices = list(devices)
        self._dev_combo.clear()
        if hasattr(self, "_dev_type_lbl"):
            self._dev_type_lbl.setText("")
        # Fallback: RTL-TCP running but SoapySDR can't claim the device
        rtltcp_up = HAS_RTLTCP and rtltcp_is_running()
        if not devices:
            log.info("SDR: 0 SoapySDR devices — HAS_RTLTCP=%s rtltcp_running=%s",
                     HAS_RTLTCP, rtltcp_up)
        if not devices and rtltcp_up:
            self._dev_combo.addItem(
                self.tr("RTL-TCP server  (127.0.0.1:1234)"))
            self._devices = [None]
            if hasattr(self, "_dev_type_lbl"):
                self._dev_type_lbl.setText("RTL-TCP")
            log.info("SDR: SoapySDR found 0 devices, rtl_tcp running — using RTL-TCP")
        elif not devices:
            # Surface *why* nothing was found (e.g. missing rtlsdr module) as a
            # tooltip on the device combo, and log it to the console. The
            # Simulated source below is always offered as a no-hardware option.
            try:
                from sdr.soapy_device import SoapyManager
                hint = SoapyManager.diagnostics().get("hint", "")
                if hint:
                    self._dev_combo.setToolTip(hint)
                    log.info("SDR: no devices — %s", hint.replace("\n", " "))
            except Exception as exc:
                log.debug("device diagnostics hint failed: %s", exc)
        else:
            for dev in devices:
                self._dev_combo.addItem(dev.display_name)
            self._update_dev_type_label(0)
        # Always offer the simulated source last — a no-hardware user can bring
        # the whole SDR stack (waterfall, survey, history, alerts) alive.
        self._dev_combo.addItem(self.tr("Simulated signal (no hardware)"))
        self._devices.append(SIM_DEVICE)
        if self._dev_combo.currentIndex() < 0:
            self._dev_combo.setCurrentIndex(0)
        self._update_dev_type_label(self._dev_combo.currentIndex())

    def _update_dev_type_label(self, index: int) -> None:
        """Show driver/hardware type for selected device."""
        if not hasattr(self, "_dev_type_lbl"):
            return
        if not self._devices or index < 0 or index >= len(self._devices):
            self._dev_type_lbl.setText("")
            return
        dev = self._devices[index]
        if dev == SIM_DEVICE:
            self._dev_type_lbl.setText("Simulated")
            return
        if dev is None:
            self._dev_type_lbl.setText("RTL-TCP")
            return
        # SDRDevice has a 'driver' or 'hardware' attribute from SoapySDR
        driver = (getattr(dev, "driver", "")
                  or getattr(dev, "hardware", "")
                  or "").upper()
        # Map common driver keys to friendly names
        _DRIVER_NAMES = {
            "RTL":    "RTL-SDR",
            "RTLSDR": "RTL-SDR",
            "AIRSPY": "Airspy",
            "SDRPLAY": "SDRplay RSP",
            "RSP": "SDRplay RSP",
            "UHD": "USRP (UHD)",
            "HACKRF": "HackRF",
            "LIME": "LimeSDR",
            "XTRX": "XTRX",
            "AUDIO": "Audio IQ",
            "REMOTE": "SoapyRemote",
        }
        label = next((v for k, v in _DRIVER_NAMES.items()
                      if k in driver), driver or "Unknown")
        self._dev_type_lbl.setText(label)

    def _on_device_select(self, idx: int):
        self._update_dev_type_label(idx)
        if 0 <= idx < len(self._devices):
            dev = self._devices[idx]
            if dev is None:
                return   # RTL-TCP sentinel — no SoapySDR device object
            if dev == SIM_DEVICE:
                # Synthetic source — no TX, no hardware panel.
                self._tx_grp.setVisible(False)
                self._tx_indicator.setVisible(False)
                return
            # Show TX controls only for TX hardware
            self._tx_grp.setVisible(getattr(dev, "can_tx", False))
            self._tx_indicator.setVisible(getattr(dev, "can_tx", False))
            # Adjust span to hardware limits
            if hasattr(dev, "recommended_span"):
                self._span_hz = dev.recommended_span
                self._manager.set_sample_rate(dev.recommended_span)
            # Show device-specific settings panel
            self._build_device_panel(dev)

    def _build_device_panel(self, dev):
        """
        Show hardware-specific controls for the selected device.
        HackRF: amp, bias-tee, LNA/VGA split
        USRP B200/B210: clock source, subdev, channel
        RTL-SDR: direct sampling, bias-tee
        """
        from sdr.soapy_device import DEVICE_PROFILES
        profile = DEVICE_PROFILES.get(
            dev.driver.lower(), {})

        # Clear old panel
        if hasattr(self, "_dev_panel") and                 self._dev_panel:
            self._dev_panel.setVisible(False)
            self._dev_panel.deleteLater()
            self._dev_panel = None

        driver = dev.driver.lower()

        if driver == "hackrf":
            self._dev_panel = self._hackrf_panel()
        elif driver == "uhd":
            self._dev_panel = self._usrp_panel()
        elif driver == "rtlsdr":
            self._dev_panel = self._rtlsdr_panel()
        elif driver == "sdrplay":
            # Detect exact RSP model from device label
            from sdr.soapy_device import detect_rsp_model
            model = detect_rsp_model(dev.label)
            self._dev_panel = self._sdrplay_panel(model)
        else:
            self._dev_panel = None
            return

        # Insert into the controls layout
        if hasattr(self, "_controls_layout"):
            self._controls_layout.addWidget(
                self._dev_panel)

    def _connect_sdr(self):
        idx = self._dev_combo.currentIndex()
        if not self._devices or idx >= len(self._devices):
            return
        if self._connect_btn.text() == self.tr("Disconnect"):
            sim = getattr(self, "_sim_source", None)
            if sim is not None and sim.is_running:
                sim.stop()
            else:
                self._manager.stop_rx()
                self._manager.close()
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Disconnected")
            self._sdr_status.setStyleSheet(
                ""
                "font-family:'Courier New';")
            return

        dev = self._devices[idx]
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText(self.tr("Connecting…"))

        # Synthetic source — bring the whole stack alive with no hardware.
        if dev == SIM_DEVICE:
            self._start_sim_source()
            return

        # Sentinel from _populate_devices: connect to the local rtl_tcp
        # server instead of opening a SoapySDR device.
        if dev is None:
            def _do_rtltcp():
                from ui.tabs.sdr_tab import RTLTCPDevice
                ok = False
                try:
                    if not self._rtltcp_dev:
                        self._rtltcp_dev = RTLTCPDevice()
                    if self._rtltcp_dev.open():
                        self._rtltcp_dev.on_samples(self._on_samples)
                        self._rtltcp_dev.start_rx()
                        ok = True
                except Exception as e:
                    log.error(f"RTL-TCP connect failed: {e}")
                from types import SimpleNamespace
                fake = SimpleNamespace(
                    display_name="RTL-TCP @ 127.0.0.1:1234")
                QTimer.singleShot(0,
                    lambda o=ok, d=fake: self._on_connected(o, d))
            threading.Thread(target=_do_rtltcp, daemon=True).start()
            return

        def _do():
            ok = self._manager.open(dev)
            QTimer.singleShot(0,
                lambda o=ok, d=dev: self._on_connected(o, d))
        threading.Thread(target=_do, daemon=True).start()

    def _start_sim_source(self):
        """Start the synthetic source feeding the stream path, and show the
        connected state (no SoapySDR device / manager RX involved)."""
        try:
            from sdr.sim_source import SimSource
            if getattr(self, "_sim_source", None) is None:
                self._sim_source = SimSource(
                    sample_rate=int(self._sample_rate),
                    get_center=lambda: int(self._center_hz))
            self._sim_source.on_samples(self._on_samples)
            self._sim_source.start()
            ok = True
        except Exception as exc:
            log.error("sim source start failed: %s", exc)
            ok = False
        self._connect_btn.setEnabled(True)
        if ok:
            self._connect_btn.setText(self.tr("Disconnect"))
            self._sdr_status.setText("● Simulated signal")
            self._sdr_status.setStyleSheet(
                "color:#3fbe6f;font-family:'Courier New';")
            from types import SimpleNamespace
            self._current = SimpleNamespace(display_name="Simulated signal")
            self._update_axes()
            self._draw_band_segments()
        else:
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Error")
            self._sdr_status.setStyleSheet(
                "color:#cc4444;font-family:'Courier New';")

    def _on_connected(self, ok: bool, dev: "SDRDevice"):
        self._connect_btn.setEnabled(True)
        if ok:
            self._connect_btn.setText(
                self.tr("Disconnect"))
            self._sdr_status.setText(
                f"● {dev.display_name}")
            self._sdr_status.setStyleSheet(
                "color:#3fbe6f;"
                "font-family:'Courier New';")
            self._current = dev
            self._manager.start_rx()
            self._update_axes()
            self._draw_band_segments()
        else:
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Error")
            self._sdr_status.setStyleSheet(
                "color:#cc4444;"
                "font-family:'Courier New';")
