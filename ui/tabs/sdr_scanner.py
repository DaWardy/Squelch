from __future__ import annotations
"""Squelch -- ui/tabs/sdr_scanner.py
_SDRScannerMixin: frequency-sweep scanner methods extracted from SDRTab.
"""

from PyQt6.QtWidgets import QMessageBox

# Matches SDR_STEP_SIZES in sdr_tab.py — keep in sync if ever changed.
_SDR_STEP_SIZES = [
    100, 1_000, 5_000, 10_000, 12_500,
    25_000, 100_000, 500_000, 1_000_000
]


class _SDRScannerMixin:
    """Frequency-sweep scanner for SDRTab."""

    def _start_scan(self):
        try:
            lo = int(float(self._scan_from.text()) * 1_000_000)
            hi = int(float(self._scan_to.text()) * 1_000_000)
        except ValueError:
            QMessageBox.warning(self, self.tr("Scanner"),
                                self.tr("Invalid frequency range."))
            return
        self._scan_lo  = lo
        self._scan_hi  = hi
        self._scan_cur = lo
        self._scan_running = True
        interval = int(self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)

    def _stop_scan(self):
        self._scan_running = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)

    def _scan_step(self):
        if not self._scan_running:
            return
        step = _SDR_STEP_SIZES[self._step_idx]
        self._scan_cur += step
        if self._scan_cur > self._scan_hi:
            self._scan_cur = self._scan_lo
        self._set_freq(self._scan_cur)
