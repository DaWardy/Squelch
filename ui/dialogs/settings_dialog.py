from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/dialogs/settings_dialog.py
Full in-app settings editor.
Organized into tabbed sections:
  Station, Audio, Digital Modes, APIs,
  Appearance, Paths, Advanced
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QDialogButtonBox, QGroupBox,
    QScrollArea, QFrame, QSlider, QFileDialog,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

log = logging.getLogger(__name__)


from ui.dialogs.settings_station_tab import _SettingsStationTab
from ui.dialogs.settings_audio_tab import _SettingsAudioTab
from ui.dialogs.settings_modes_tab import _SettingsModesTab
from ui.dialogs.settings_apis_tab import _SettingsApisTab
from ui.dialogs.settings_appearance_tab import _SettingsAppearanceTab
from ui.dialogs.settings_advanced_tab import _SettingsAdvancedTab
from ui.dialogs.settings_sdr_tab import _SettingsSdrTab


class SettingsDialog(_SettingsStationTab, _SettingsAudioTab, _SettingsModesTab, _SettingsApisTab, _SettingsAppearanceTab, _SettingsAdvancedTab, _SettingsSdrTab, QDialog):
    """
    Full settings editor — all user-configurable options
    in one organized dialog. Changes applied on OK.
    """

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self._dirty = False
        self.setWindowTitle("Settings — Squelch")
        self.setMinimumSize(640, 520)
        self.resize(720, 580)
        self._build()
        self._load_all()

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabBar::tab{padding:6px 14px;}"
            "QTabBar::tab:selected{color:#3fbe6f;}")

        self._tabs.addTab(self._tab_station(),   "🎙  Station")
        self._tabs.addTab(self._tab_audio(),     "🔊  Audio")
        self._tabs.addTab(self._tab_modes(),     "📡  Digital Modes")
        self._tabs.addTab(self._tab_apis(),      "🔑  APIs")
        self._tabs.addTab(self._tab_appearance(),"🎨  Appearance")
        self._tabs.addTab(self._tab_advanced(),  "⚙  Advanced")
        self._tabs.addTab(self._tab_sdr_drivers(),"📻  SDR Hardware")

        root.addWidget(self._tabs, 1)

        # Reset / OK / Cancel
        btn_row = QHBoxLayout()
        reset = QPushButton("Reset to Defaults")
        reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset)
        btn_row.addStretch()
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply)
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(
            QDialogButtonBox.StandardButton.Apply
        ).clicked.connect(self._apply)
        btn_row.addWidget(btns)
        root.addLayout(btn_row)

    # ── Tab: Station ──────────────────────────────────────────


    # ── Tab: Audio ────────────────────────────────────────────


    # ── Tab: Digital Modes ────────────────────────────────────


    # ── Tab: APIs ─────────────────────────────────────────────


    # ── Tab: Appearance ───────────────────────────────────────


    # ── Tab: Advanced ─────────────────────────────────────────


    # ── Load / Save ───────────────────────────────────────────

    # ── Settings load helpers (one per tab section) ──────────────────────

    def _load_station(self, cfg):
        region_map = {"1": 1, "2": 0, "3": 2}
        lic_map    = {"technician": 0, "general": 1, "extra": 2, "other": 3}
        self._daily_goal.setValue(cfg.get("log.daily_goal", 0))
        self._callsign.setText(cfg.callsign or "")
        self._op_name.setText(cfg.get("station.op_name", ""))
        self._grid.setText(cfg.grid or "")
        self._itu_region.setCurrentIndex(
            region_map.get(str(cfg.get("station.itu_region", "2")), 0))
        self._license.setCurrentIndex(
            lic_map.get(cfg.get("station.license", "").lower(), 1))
        self._station_call.setText(cfg.get("station.station_callsign", ""))
        self._contest_exchange.setText(cfg.get("station.contest_exchange", ""))

    def _load_modes(self, cfg):
        self._auto_launch_wsjtx.setChecked(cfg.get("modes.auto_launch_wsjtx", True))
        self._auto_log_ft8.setChecked(cfg.get("modes.auto_log_ft8", True))
        self._wsjtx_udp_port.setValue(cfg.get("modes.wsjtx_udp_port", 2237))
        self._cq_timeout_cycles.setValue(cfg.get("modes.cq_timeout_cycles", 2))
        self._ptt_timeout.setValue(cfg.get("safety.ptt_timeout_s", 180))
        self._tx_inhibit.setChecked(cfg.get("safety.tx_inhibit", False))
        self._log_dupes.setChecked(cfg.get("log.warn_dupes", True))

    def _load_appearance(self, cfg):
        font_sizes = [10, 11, 13, 15, 18]
        saved_fs   = cfg.get("ui.font_size", 11)
        self._font_size.setCurrentIndex(
            font_sizes.index(saved_fs) if saved_fs in font_sizes else 1)
        ui_idx = self._units.findData(cfg.get("ui.units", "metric"))
        if ui_idx >= 0:
            self._units.setCurrentIndex(ui_idx)
        self._layout_locked.setChecked(cfg.get("ui.layout_locked", False))
        self._clock_utc.setChecked(cfg.get("ui.clock_utc", True))
        from ui.dialogs.settings_appearance_tab import _CUSTOM_COLORS
        for key, _label, default in _CUSTOM_COLORS:
            btn = getattr(self, "_color_btns", {}).get(key)
            if btn:
                h = cfg.get(f"theme.custom.{key}", default) or default
                btn.setProperty("hex_color", h)
                btn.setStyleSheet(
                    f"background:{h};border:1px solid #555;"
                    f"border-radius:2px;")

    def _load_advanced(self, cfg):
        level_map = {"INFO": 0, "DEBUG": 1, "WARNING": 2}
        self._log_level.setCurrentIndex(
            level_map.get(cfg.get("advanced.log_level", "INFO"), 0))
        self._api_timeout.setValue(cfg.get("advanced.api_timeout_s", 10))
        self._grayline_interval.setValue(cfg.get("advanced.grayline_interval_s", 60))

    def _load_apis(self, cfg):
        try:
            from core.credentials import get_store
            store = get_store(cfg.get("profile.name", "default"))
            self._qrz_user.setText(cfg.get("apis.qrz_user", ""))
            self._qrz_logbook_key.setText(
                store.retrieve("qrz_logbook_key") or "")
            self._hamqth_user.setText(cfg.get("apis.hamqth_user", ""))
            self._rr_user.setText(cfg.get("apis.rr_user", ""))
            self._lotw_user.setText(cfg.get("apis.lotw_user", ""))
            self._clublog_email.setText(cfg.get("apis.clublog_email", ""))
            self._eqsl_user.setText(cfg.get("apis.eqsl_username", ""))
            self._eqsl_pass.setText(store.retrieve("eqsl_password") or "")
            self._hrdlog_callsign.setText(cfg.get("apis.hrdlog_callsign", ""))
            self._hrdlog_key.setText(store.retrieve("hrdlog_key") or "")
            self._rb_token.setText(store.retrieve("repeaterbook_token") or "")
            self._hamalert_user.setText(cfg.get("apis.hamalert_user", ""))
            self._hamalert_url_secret.setText(cfg.get("apis.hamalert_url_secret", ""))
            self._hamalert_key.setText(store.retrieve("hamalert_password") or "")
            self._hamalert_sms_token.setText(store.retrieve("hamalert_sms_token") or "")
        except Exception:
            pass

    def _load_all(self):
        """Populate all fields from config and keyring."""
        cfg = self.cfg
        self._load_station(cfg)
        self._load_modes(cfg)
        self._load_appearance(cfg)
        self._load_advanced(cfg)
        self._load_apis(cfg)


    def _conda_exe(self) -> str:
        import shutil
        from pathlib import Path as P
        for name in ["conda", "mamba", "micromamba"]:
            f = shutil.which(name)
            if f:
                return f
        for p in [
            P.home() / "miniforge3" / "Scripts" / "conda.exe",
            P.home() / "miniconda3"  / "Scripts" / "conda.exe",
            P("C:/miniforge3/Scripts/conda.exe"),
            P("C:/miniconda3/Scripts/conda.exe"),
        ]:
            if p.exists():
                return str(p)
        return ""

    def _sdr_log_append(self, text: str):
        try:
            self._sdr_log.append(text)
        except RuntimeError:
            pass

    def _check_sdr_status(self):
        import sys, subprocess, sysconfig
        from pathlib import Path as P

        lines = []
        vpy = sys.executable
        r = subprocess.run(
            [vpy, "-c",
             "import SoapySDR; d=SoapySDR.Device.enumerate();"
             "print(SoapySDR.getAPIVersion(), len(d), 'device(s)')"],
            capture_output=True, text=True)
        if r.returncode == 0:
            lines.append("SoapySDR core: OK  " + r.stdout.strip())
        else:
            lines.append("SoapySDR core: NOT INSTALLED")
            lines.append("  Run fix_soapysdr.bat or python installer.py")

        try:
            site = P(sysconfig.get_path("purelib"))
        except Exception:
            site = P(sys.prefix) / "Lib" / "site-packages"

        lines.append("")
        lines.append("Device plugins:")
        plugin_map = {
            "soapyrtlsdr":   ("SoapyRTLSDR",   "RTL-SDR"),
            "soapyhackrf":   ("SoapyHackRF",   "HackRF"),
            "soapysdrplay3": ("SoapySDRPlay",  "SDRplay RSP"),
            "soapyuhd":      ("SoapyUHD",      "USRP"),
            "soapyairspy":   ("SoapyAirspy",   "Airspy"),
            "limesuite":     ("SoapyLMS7",     "LimeSDR"),
        }
        from core.themes import get_theme as _gt
        _t = _gt(self.cfg.get("ui.theme", "Dark"))
        status_labels = getattr(self, "_sdr_status_labels", {})
        for pkg, (stem, hw) in plugin_map.items():
            found = list(site.glob(stem + "*.pyd"))
            if found:
                lines.append("  [installed]  " + hw + " - " + found[0].name)
                if pkg in self._sdr_checks:
                    self._sdr_checks[pkg].setChecked(False)
                    self._sdr_checks[pkg].setEnabled(False)
                if pkg in status_labels:
                    status_labels[pkg].setText("✓ Installed")
                    status_labels[pkg].setStyleSheet(
                        "color:#3fbe6f;font-size:11px;font-weight:bold;")
            else:
                lines.append("  [ missing ]  " + hw)
                if pkg in self._sdr_checks:
                    self._sdr_checks[pkg].setEnabled(True)
                if pkg in status_labels:
                    status_labels[pkg].setText("Not installed")
                    status_labels[pkg].setStyleSheet(
                        f"color:{_t.fg_muted};font-size:11px;")
        try:
            self._sdr_log.setPlainText("\n".join(lines))
        except RuntimeError:
            pass

    def _install_sdr_drivers(self):
        import threading
        selected = [p for p, cb in self._sdr_checks.items() if cb.isChecked()]
        if not selected:
            self._sdr_log.setPlainText(
                "No drivers selected. Check the boxes for your hardware first.")
            return
        conda = self._conda_exe()
        if not conda:
            self._sdr_log.setPlainText(
                "conda not found.\n\n"
                "Install miniforge3 from:\n"
                "  github.com/conda-forge/miniforge/releases\n\n"
                "Or run manually:\n"
                "  conda install -c conda-forge " + " ".join(selected))
            return
        self._sdr_install_btn.setEnabled(False)
        self._sdr_install_btn.setText("Installing...")
        self._sdr_log.setPlainText(
            "Running: conda install -c conda-forge "
            + " ".join(selected) + "\n\nPlease wait...")

        def _done(msg):
            try:
                self._sdr_log.setPlainText(msg)
                self._sdr_install_btn.setEnabled(True)
                self._sdr_install_btn.setText("Install Selected Drivers")
                self._check_sdr_status()
            except RuntimeError:
                pass

        def _run():
            from PyQt6.QtCore import QTimer
            msg = self._run_conda_install(conda, selected)
            QTimer.singleShot(0, lambda m=msg: _done(m))

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _find_conda_site_packages() -> "object":  # returns pathlib.Path or None
        """Return the first conda site-packages directory found, or None."""
        from pathlib import Path as P
        for root in [
            P.home() / "miniforge3" / "Lib" / "site-packages",
            P.home() / "miniconda3"  / "Lib" / "site-packages",
            P("C:/miniforge3/Lib/site-packages"),
            P("C:/miniconda3/Lib/site-packages"),
        ]:
            if root.exists():
                return root
        return None

    @staticmethod
    def _copy_soapy_plugins(conda_sp, selected, site) -> "list[str]":
        """Copy SoapySDR .pyd plugins from conda_sp into the venv site-packages."""
        import shutil
        STEM_MAP = {
            "soapyrtlsdr": "SoapyRTLSDR", "soapyhackrf": "SoapyHackRF",
            "soapysdrplay3": "SoapySDRPlay", "soapyuhd": "SoapyUHD",
            "soapyairspy": "SoapyAirspy", "limesuite": "SoapyLMS7",
        }
        copied = []
        for pkg in selected:
            stem = STEM_MAP.get(pkg, pkg)
            for pyd in conda_sp.glob(stem + "*.pyd"):
                try:
                    shutil.copy2(pyd, site / pyd.name)
                    copied.append(pyd.name)
                except Exception:
                    pass
        return copied

    def _run_conda_install(self, conda, selected) -> str:
        """Run conda install in a worker thread; return a result message."""
        import subprocess, sysconfig
        from pathlib import Path as P
        try:
            result = subprocess.run(
                [conda, "install", "-c", "conda-forge", "-y", "--quiet"] + selected,
                capture_output=True, text=True)
            if result.returncode != 0:
                return "conda install failed.\n\n" + (result.stderr or result.stdout)[:400]
            try:
                site = P(sysconfig.get_path("purelib"))
            except Exception:
                import sys
                site = P(sys.prefix) / "Lib" / "site-packages"
            conda_sp = self._find_conda_site_packages()
            copied = self._copy_soapy_plugins(conda_sp, selected, site) if conda_sp else []
            msg = "Installation complete.\n\n"
            if copied:
                msg += "Copied to venv:\n" + "\n".join("  " + f for f in copied)
                msg += "\n\nRestart Squelch to use new drivers."
            else:
                msg += "conda install succeeded but no .pyd files found to copy.\nRun fix_soapysdr.bat."
            return msg
        except Exception as exc:
            return "Error: " + str(exc)


    # ── Settings save helpers (one per tab section) ──────────────────────

    def _save_station(self, cfg):
        cs = self._callsign.text().strip().upper()
        if cs:
            cfg.callsign = cs
        cfg.set("station.op_name", self._op_name.text().strip())
        grid = self._grid.text().strip().upper()
        if grid:
            cfg.grid = grid
        region_map = {0: "2", 1: "1", 2: "3"}
        cfg.set("station.itu_region",
                region_map.get(self._itu_region.currentIndex(), "2"))
        lic_labels = ["technician", "general", "extra", "other"]
        cfg.set("station.license", lic_labels[self._license.currentIndex()])
        cfg.set("station.station_callsign",
                self._station_call.text().strip().upper())
        cfg.set("station.contest_exchange",
                self._contest_exchange.text().strip())
        cfg.set("log.daily_goal", self._daily_goal.value())

    def _save_audio(self, cfg):
        cfg.set("audio.input",          self._audio_input.currentText())
        cfg.set("audio.output",         self._audio_output.currentText())
        cfg.set("audio.digital_input",  self._digital_input.currentText())
        cfg.set("audio.digital_output", self._digital_output.currentText())

    def _save_modes(self, cfg):
        cfg.set("modes.auto_launch_wsjtx",  self._auto_launch_wsjtx.isChecked())
        cfg.set("modes.auto_log_ft8",       self._auto_log_ft8.isChecked())
        cfg.set("modes.wsjtx_udp_port",     self._wsjtx_udp_port.value())
        cfg.set("modes.cq_timeout_cycles",  self._cq_timeout_cycles.value())
        cfg.set("safety.ptt_timeout_s",     self._ptt_timeout.value())
        cfg.set("safety.tx_inhibit",        self._tx_inhibit.isChecked())
        cfg.set("log.warn_dupes",           self._log_dupes.isChecked())

    def _save_appearance(self, cfg):
        cfg.set("ui.font_size",      self._font_size.currentData())
        cfg.set("ui.units",          self._units.currentData() or "metric")
        cfg.set("ui.layout_locked",  self._layout_locked.isChecked())
        cfg.set("ui.clock_utc",      self._clock_utc.isChecked())
        for key, btn in getattr(self, "_color_btns", {}).items():
            h = btn.property("hex_color") or ""
            if h:
                cfg.set(f"theme.custom.{key}", h)

    def _save_advanced(self, cfg):
        levels = ["INFO", "DEBUG", "WARNING"]
        cfg.set("advanced.log_level",
                levels[self._log_level.currentIndex()])
        cfg.set("advanced.api_timeout_s",      self._api_timeout.value())
        cfg.set("advanced.grayline_interval_s", self._grayline_interval.value())

    def _save_apis(self, cfg):
        cfg.set("apis.qrz_user",           self._qrz_user.text().strip())
        cfg.set("apis.hamqth_user",        self._hamqth_user.text().strip())
        cfg.set("apis.rr_user",            self._rr_user.text().strip())
        cfg.set("apis.lotw_user",          self._lotw_user.text().strip())
        cfg.set("apis.clublog_email",      self._clublog_email.text().strip())
        cfg.set("apis.eqsl_username",      self._eqsl_user.text().strip())
        cfg.set("apis.hrdlog_callsign",    self._hrdlog_callsign.text().strip().upper())
        cfg.set("apis.hamalert_user",      self._hamalert_user.text().strip())
        cfg.set("apis.hamalert_url_secret", self._hamalert_url_secret.text().strip())
        try:
            from core.credentials import get_store
            store = get_store(cfg.get("profile.name", "default"))
            for attr, key in [
                (self._qrz_pass,          "qrz_password"),
                (self._qrz_logbook_key,   "qrz_logbook_key"),
                (self._hamqth_pass,       "hamqth_password"),
                (self._lotw_pass,         "lotw_password"),
                (self._clublog_pass,      "clublog_password"),
                (self._eqsl_pass,         "eqsl_password"),
                (self._hrdlog_key,        "hrdlog_key"),
                (self._rb_token,          "repeaterbook_token"),
                (self._hamalert_key,      "hamalert_password"),
                (self._hamalert_sms_token, "hamalert_sms_token"),
            ]:
                if attr.text():
                    store.store(key, attr.text())
        except Exception as e:
            log.warning(f"Keyring save: {e}")

    def _apply(self):
        """Save all settings without closing."""
        cfg = self.cfg
        self._save_station(cfg)
        self._save_audio(cfg)
        self._save_modes(cfg)
        self._save_appearance(cfg)
        self._save_advanced(cfg)
        self._save_apis(cfg)
        cfg.save()
        # Deferred so the dialog closes before the stylesheet rebuild
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_live)

    def _get_live_theme_settings(self):
        """Return (app, sip, theme, fs) guarded for sip safety, or None if unavailable."""
        try:
            from PyQt6.QtWidgets import QApplication
            try:
                from PyQt6 import sip
            except ImportError:
                import sip
            app = QApplication.instance()
            if not app or sip.isdeleted(self):
                return None
            if sip.isdeleted(self._font_size):
                return None
            theme = self.cfg.get("ui.theme", "Dark")
            fs    = self._font_size.currentData() or 11
            return app, sip, theme, fs
        except (RuntimeError, AttributeError):
            return None

    def _repolish_all_widgets(self, app, sip):
        """Unpolish/re-polish every widget so QSS changes take immediate effect."""
        for w in app.allWidgets():
            try:
                if sip.isdeleted(w):
                    continue
                st = w.style()
                st.unpolish(w)
                st.polish(w)
                w.update()
            except Exception:
                pass

    def _apply_live(self):
        """Apply theme and font immediately — called on Apply/OK."""
        try:
            from core.themes import get_stylesheet
            from PyQt6.QtGui import QFont
            result = self._get_live_theme_settings()
            if result is None:
                return
            app, sip, theme, fs = result
            app.setStyleSheet(get_stylesheet(theme, fs))
            f = QFont(); f.setPointSize(fs); app.setFont(f)
            self._repolish_all_widgets(app, sip)
            try:
                import main as _main
                for tlw in app.topLevelWidgets():
                    if not sip.isdeleted(tlw):
                        _main._apply_theme_fixes(tlw, theme)
            except Exception:
                pass
        except Exception as e:
            log.debug(f"Live apply: {e}")

    def _set_font_recursive(self, widget, font):
        """
        No longer used — font size is applied via QSS in _apply_live.
        Kept as stub to avoid AttributeError from any call sites.
        """
        pass

    def _save_and_accept(self):
        self._apply()
        self.accept()

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from core.config import Config
            defaults = Config._load_example(self.cfg)
            for key, val in _flatten(defaults).items():
                self.cfg.set(key, val)
            self._load_all()

    _COMMON_INPUTS  = ["Default", "CABLE Output (VB-Audio Virtual Cable)",
                        "USB Audio CODEC", "Microphone (USB)", "Stereo Mix"]
    _COMMON_OUTPUTS = ["Default", "CABLE Input (VB-Audio Virtual Cable)",
                        "Speakers (USB Audio CODEC)", "Speakers", "Headphones"]

    def _enumerate_audio_devices(self) -> tuple[list, list, bool]:
        """Return (in_devices, out_devices, detected) from sounddevice.
        Falls back to common-device lists if sounddevice is unavailable.
        """
        in_devices  = list(self._COMMON_INPUTS)
        out_devices = list(self._COMMON_OUTPUTS)
        try:
            import sounddevice as sd
            for d in sd.query_devices():
                name = d["name"]
                if d["max_input_channels"] > 0 and name not in in_devices:
                    in_devices.append(name)
                if d["max_output_channels"] > 0 and name not in out_devices:
                    out_devices.append(name)
            return in_devices, out_devices, True
        except Exception:
            return in_devices, out_devices, False

    def _populate_audio_combos(self, in_devices: list, out_devices: list):
        """Fill input/output combos, preserving current selection if still valid."""
        for combo, devices in [
            (self._audio_input,   in_devices),
            (self._digital_input, in_devices),
        ]:
            saved = combo.currentText()
            combo.clear()
            combo.addItems(devices)
            if saved in devices:
                combo.setCurrentText(saved)
        for combo, devices in [
            (self._audio_output,   out_devices),
            (self._digital_output, out_devices),
        ]:
            saved = combo.currentText()
            combo.clear()
            combo.addItems(devices)
            if saved in devices:
                combo.setCurrentText(saved)

    def _restore_audio_config_values(self, in_devices: list,
                                     out_devices: list, detected: bool):
        """Apply saved config audio values to combos; update the refresh button label."""
        cfg = self.cfg
        for combo, key in [
            (self._audio_input,    "audio.input"),
            (self._audio_output,   "audio.output"),
            (self._digital_input,  "audio.digital_input"),
            (self._digital_output, "audio.digital_output"),
        ]:
            val = cfg.get(key, "")
            if val:
                if combo.findText(val) < 0:
                    combo.addItem(val)
                combo.setCurrentText(val)
        if not detected:
            self._refresh_audio_btn.setText("↺ Refresh Device List")
            self._audio_status_lbl.setText(
                "sounddevice not installed — dropdowns show common names only.\n"
                "Install with: pip install sounddevice  (then restart Squelch)")
            self._audio_status_lbl.setStyleSheet("color:#ffcc00;")
        else:
            n_in  = len(in_devices)
            n_out = len(out_devices)
            self._refresh_audio_btn.setText("↺ Refresh Device List")
            self._audio_status_lbl.setText(
                f"{n_in} input device(s), {n_out} output device(s) found.")
            self._audio_status_lbl.setStyleSheet("color:#888;")
        self._refresh_audio_btn.setStyleSheet("")

    def _refresh_audio_devices(self):
        """Populate audio device dropdowns from sounddevice."""
        in_dev, out_dev, detected = self._enumerate_audio_devices()
        self._populate_audio_combos(in_dev, out_dev)
        self._restore_audio_config_values(in_dev, out_dev, detected)

    def _open_data_dir(self):
        import subprocess, sys
        path = str(self.cfg._path.parent)
        if sys.platform == "win32":
            subprocess.Popen(
                ["explorer", path], shell=False)  # nosec B603
        else:
            subprocess.Popen(
                ["xdg-open", path], shell=False)  # nosec B603


# ── Helpers ───────────────────────────────────────────────────────────────

def _scrolled() -> QWidget:
    """Return a plain widget (most tabs don't need scrolling)."""
    return QWidget()


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        "color:#1a1a1a;margin:4px 0;")
    return f


def _section(form: QFormLayout, title: str):
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "color:#3fbe6f;"
        "font-weight:bold;margin-top:8px;")
    form.addRow(lbl)


def _flatten(d: dict, prefix: str = "") -> dict:
    result = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = v
    return result
