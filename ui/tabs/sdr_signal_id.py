from __future__ import annotations
"""Squelch -- ui/tabs/sdr_signal_id.py
_SDRSignalIDMixin: signal identification, ADS-B, TX IQ, and
public-API methods extracted from SDRTab.
"""

import threading
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialogButtonBox, QFileDialog, QMessageBox,
)

from network.signal_id import get_identifier
from ui.tabs.sdr_recording import _safe_recordings_path


class _SDRSignalIDMixin:
    """Signal ID, ADS-B, TX IQ, and decoder routing for SDRTab."""

    # ── TX ────────────────────────────────────────────────────────────────

    def _tx_iq_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select IQ File"),
            str(_safe_recordings_path(self.cfg)),
            "SigMF Data (*.sigmf-data);All (*)")
        if path:
            QMessageBox.information(
                self, self.tr("TX IQ"),
                self.tr(
                    "IQ file TX will be available in "
                    "a future update.\n"
                    "File selected: " + Path(path).name))

    # ── Signal routing to Digital tab ────────────────────────────────────

    def set_decoder_callback(self, cb):
        """Set callback for routed IQ samples."""
        self._decoder_cb_fn = cb

    # ── Signal identification ─────────────────────────────────────────────

    def _identify_signal(self, bandwidth_hz: int, freq_hz: int):
        """Identify signal at clicked frequency (async via Artemis DB)."""
        def _done(matches):
            QTimer.singleShot(
                0, lambda m=matches: self._show_signal_id_dialog(
                    m, bandwidth_hz, freq_hz))
        get_identifier().identify_async(bandwidth_hz, freq_hz, _done)

    def _show_signal_id_dialog(self, matches, bandwidth_hz: int,
                                freq_hz: int) -> None:
        """Show Artemis signal-ID results in a dialog (main thread only)."""
        bw_k = bandwidth_hz / 1e3
        fq_m = freq_hz / 1e6
        if not matches:
            QMessageBox.information(
                self, self.tr("Signal ID"),
                f"No match found for {bw_k:.1f} kHz bandwidth "
                f"at {fq_m:.3f} MHz.\n\n"
                "Try adjusting bandwidth selection.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Signal Identification"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lbl = QLabel(
            f"Bandwidth: {bw_k:.1f} kHz  Frequency: {fq_m:.3f} MHz\n"
            f"Top {len(matches)} matches from Artemis database:")
        lay.addWidget(lbl)
        tbl = QTableWidget(len(matches), 4)
        tbl.setHorizontalHeaderLabels(
            ["Signal", "Modulation", "Bandwidth", "Confidence"])
        tbl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setStyleSheet("font-family:'Courier New';")
        for row, match in enumerate(matches):
            tbl.setItem(row, 0, QTableWidgetItem(match.name))
            tbl.setItem(row, 1, QTableWidgetItem(match.modulation))
            tbl.setItem(row, 2, QTableWidgetItem(
                f"{match.bandwidth_hz/1e3:.1f} kHz"))
            tbl.setItem(row, 3, QTableWidgetItem(
                f"{match.confidence*100:.0f}%"))
        lay.addWidget(tbl)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

    # ── ADS-B ─────────────────────────────────────────────────────────────

    def _open_adsb_map(self):
        """Open dump1090 aircraft map in browser."""
        if self.cfg:
            try:
                self.location_mgr.write_dump1090_receiver_json()
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl("http://localhost:8080"))

    def _check_dump1090_status(self):
        """Check if dump1090 is running; update button on main thread."""
        def _check():
            running = False
            try:
                import urllib.request
                urllib.request.urlopen(  # nosec B310
                    "http://localhost:8080/data/aircraft.json", timeout=1)
                running = True
            except Exception:
                pass
            QTimer.singleShot(
                0, lambda r=running: self._update_dump1090_btn(r))
        threading.Thread(target=_check, daemon=True).start()

    def _update_dump1090_btn(self, running: bool):
        if not hasattr(self, '_adsb_map_btn'):
            return
        if running:
            self._adsb_map_btn.setText("🗺  Open ADS-B Aircraft Map  ●")
            self._adsb_map_btn.setEnabled(True)
            self._adsb_map_btn.setToolTip(
                "dump1090-fa is running\n"
                "Your station marker is shown on the map.\n"
                "Opens http://localhost:8080")
        else:
            self._adsb_map_btn.setText(
                "🗺  Open ADS-B Map (dump1090 not running)")
            self._adsb_map_btn.setEnabled(False)
            self._adsb_map_btn.setToolTip(
                "dump1090-fa is not running.\n"
                "Configure path in Settings → Paths & Executables\n"
                "then launch from the Paths dialog.")

    # ── SDR guide ─────────────────────────────────────────────────────────

    def _open_sdr_guide(self):
        QDesktopServices.openUrl(QUrl(
            "https://github.com/dawardy/squelch"
            "/blob/main/README.md#sdr-setup"))

    # ── Public API ────────────────────────────────────────────────────────

    def _decoder_cb(self, text: str):
        """Called by the audio decoder with a decoded line of text."""
        try:
            self._decode_log.append(text.strip())
        except RuntimeError:
            pass

    def set_center_freq_from_rig(self, hz: int):
        """Called by rig tab when VFO changes."""
        if self._current:
            self._set_freq(hz)
