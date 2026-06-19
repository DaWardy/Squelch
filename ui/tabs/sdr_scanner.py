from __future__ import annotations
"""Squelch -- ui/tabs/sdr_scanner.py
_SDRScannerMixin: frequency-sweep scanner with squelch-advance.

Two scan modes:
  • Sweep (default): advance every dwell period regardless of signal
  • Squelch-advance: pause on active signal (squelch open), advance when
    the channel goes quiet (squelch closes)
"""

from PyQt6.QtWidgets import QMessageBox

# Keep in sync with SDR_STEP_SIZES in sdr_tab.py
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
        if lo >= hi:
            QMessageBox.warning(self, self.tr("Scanner"),
                                self.tr("From must be less than To."))
            return
        self._scan_lo      = lo
        self._scan_hi      = hi
        self._scan_cur     = lo
        self._scan_running = True
        self._scan_held    = False   # True = paused on active signal
        interval = int(self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)
        self._set_freq(self._scan_cur)

    def _stop_scan(self):
        self._scan_running = False
        self._scan_held    = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)

    def _scan_step(self):
        """Called by _scan_timer on each dwell tick."""
        if not self._scan_running:
            return
        # Squelch-advance: if squelch is open (signal present) hold position
        use_sq_adv = (hasattr(self, "_scan_squelch_cb") and
                      self._scan_squelch_cb.isChecked())
        if use_sq_adv and self._squelch_open:
            self._scan_held = True
            return          # signal active — stay here until it clears

        # Advance to next frequency
        self._scan_held = False
        step = _SDR_STEP_SIZES[self._step_idx]
        self._scan_cur += step
        if self._scan_cur > self._scan_hi:
            self._scan_cur = self._scan_lo
        self._set_freq(self._scan_cur)
