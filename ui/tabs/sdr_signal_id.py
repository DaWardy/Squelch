from __future__ import annotations
"""Squelch -- ui/tabs/sdr_signal_id.py
_SDRSignalIDMixin: signal identification, ADS-B, TX IQ, and
public-API methods extracted from SDRTab.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from network.signal_id import get_identifier
from ui.tabs.sdr_paths import _safe_recordings_path

log = logging.getLogger(__name__)

_BOOKMARK_FILE = Path("assets/signal_bookmarks.json")


def _annotation_font():
    from PyQt6.QtGui import QFont
    f = QFont("Courier New", 8)
    f.setBold(True)
    return f

# Category → annotation colour on the waterfall
_CATEGORY_ANNOTATION_COLOR = {
    "amateur":   (63, 190, 111, 80),
    "aviation":  (68, 153, 255, 80),
    "marine":    (68, 204, 255, 80),
    "military":  (204, 68, 68, 80),
    "utility":   (255, 170, 68, 80),
    "broadcast": (204, 136, 255, 80),
}
_DEFAULT_ANNOTATION_COLOR = (136, 136, 136, 80)


class _SDRSignalIDMixin:
    """Signal ID, ADS-B, TX IQ, and decoder routing for SDRTab."""

    # ── TX ────────────────────────────────────────────────────────────────

    def _tx_iq_file(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
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

    def _ensure_sigid_panel(self):
        """Lazily create the SignalIDPanel and add it to the splitter."""
        if getattr(self, "_sigid_panel", None) is not None:
            return
        try:
            from ui.tabs.sdr_sigid_panel import SignalIDPanel
            panel = SignalIDPanel(
                on_annotate=self._annotate_waterfall,
                on_bookmark=self._bookmark_signal,
                cfg=self.cfg,
                parent=self,
            )
            panel.hide()
            # Insert before the right control panel (index 1) in the splitter
            splitter = getattr(self, "_main_splitter", None)
            if splitter is not None:
                splitter.addWidget(panel)
                splitter.setSizes([700, 280, 240])
            self._sigid_panel = panel
        except Exception as e:
            log.debug("SignalIDPanel init: %s", e)
            self._sigid_panel = None

    def _identify_signal(self, bandwidth_hz: int, freq_hz: int):
        """Identify signal at clicked frequency (async via Artemis DB)."""
        from PyQt6.QtCore import QTimer
        def _done(matches):
            QTimer.singleShot(
                0, lambda m=matches: self._on_signal_id_results(
                    m, bandwidth_hz, freq_hz))
        get_identifier().identify_async(bandwidth_hz, freq_hz, _done)

    def _on_signal_id_results(self, matches: list, bandwidth_hz: int,
                               freq_hz: int) -> None:
        """Route results to side panel (main thread only)."""
        self._ensure_sigid_panel()
        panel = getattr(self, "_sigid_panel", None)
        if panel is not None:
            panel.show_results(matches, bandwidth_hz, freq_hz)
            # Store for annotation
            self._last_id_freq_hz = freq_hz
            self._last_id_bw_hz = bandwidth_hz
        else:
            # Fallback: plain message if panel failed to build
            if not matches:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Signal ID",
                    f"No match for {bandwidth_hz/1e3:.1f} kHz at "
                    f"{freq_hz/1e6:.3f} MHz.")

    # ── Waterfall annotation ──────────────────────────────────────────────

    def _annotate_waterfall(self, match) -> None:
        """Paint a labelled LinearRegionItem on the spectrum for this match."""
        try:
            import pyqtgraph as pg
        except ImportError:
            return
        freq_hz = getattr(self, "_last_id_freq_hz", 0)
        bw_hz = match.bandwidth_hz or getattr(self, "_last_id_bw_hz", 0)
        if not freq_hz or not bw_hz:
            return

        spec = getattr(self, "_spec_plot", None)
        wf = getattr(self, "_wf_plot", None)
        if spec is None:
            return

        lo = freq_hz - bw_hz / 2
        hi = freq_hz + bw_hz / 2
        lo_mhz = lo / 1e6
        hi_mhz = hi / 1e6
        freq_mhz = freq_hz / 1e6

        cat = (match.category or "").lower().split("/")[0].strip()
        r, g, b, a = _CATEGORY_ANNOTATION_COLOR.get(
            cat, _DEFAULT_ANNOTATION_COLOR)

        # Remove previous annotation for this exact freq to avoid stacking
        self._clear_sigid_annotations(freq_hz)

        ann_spec = pg.LinearRegionItem(
            [lo_mhz, hi_mhz], movable=False,
            brush=pg.mkBrush(r, g, b, a),
            pen=pg.mkPen(r, g, b, 180, width=1))
        ann_spec.setZValue(10)
        spec.addItem(ann_spec)

        # Label at top of spectrum
        label = pg.TextItem(
            text=match.name[:30],
            color=(r, g, b),
            anchor=(0.5, 1.0))
        label.setPos(freq_mhz, spec.getViewBox().viewRange()[1][1])
        label.setFont(_annotation_font())
        spec.addItem(label)

        if wf is not None:
            ann_wf = pg.LinearRegionItem(
                [lo_mhz, hi_mhz], movable=False,
                brush=pg.mkBrush(r, g, b, 40),
                pen=pg.mkPen(r, g, b, 120, width=1),
                orientation="vertical")
            wf.addItem(ann_wf)
        else:
            ann_wf = None

        # Track for cleanup
        if not hasattr(self, "_sigid_annotations"):
            self._sigid_annotations = []
        self._sigid_annotations.append(
            (freq_hz, ann_spec, label, ann_wf))

    def _clear_sigid_annotations(self, freq_hz: int | None = None) -> None:
        """Remove annotations — all if freq_hz is None, or matching freq."""
        anns = getattr(self, "_sigid_annotations", [])
        spec = getattr(self, "_spec_plot", None)
        wf = getattr(self, "_wf_plot", None)
        remaining = []
        for entry in anns:
            f, ann_spec, label, ann_wf = entry
            if freq_hz is None or abs(f - freq_hz) < 1000:
                try:
                    if spec:
                        spec.removeItem(ann_spec)
                        spec.removeItem(label)
                    if wf and ann_wf:
                        wf.removeItem(ann_wf)
                except Exception:
                    pass
            else:
                remaining.append(entry)
        self._sigid_annotations = remaining

    # ── Bookmarking ───────────────────────────────────────────────────────

    def _bookmark_signal(self, match) -> None:
        """Save match + current freq to local JSON bookmark file."""
        freq_hz = getattr(self, "_last_id_freq_hz", 0)
        ts = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": ts,
            "freq_hz": freq_hz,
            "freq_mhz": round(freq_hz / 1e6, 6),
            "name": match.name,
            "modulation": match.modulation,
            "bandwidth_hz": match.bandwidth_hz,
            "category": match.category,
            "confidence": round(match.confidence, 3),
            "url": match.url,
        }
        try:
            _BOOKMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if _BOOKMARK_FILE.exists():
                try:
                    existing = json.loads(
                        _BOOKMARK_FILE.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.insert(0, entry)
            _BOOKMARK_FILE.write_text(
                json.dumps(existing[:200], indent=2), encoding="utf-8")
            log.info("Signal bookmarked: %s @ %.3f MHz",
                     match.name, freq_hz / 1e6)
        except Exception as e:
            log.warning("Bookmark save failed: %s", e)

        # Mirror into the unified Signal store (best-effort).
        try:
            from core.signal_ingest import ingest, signal_from_bookmark
            ingest(signal_from_bookmark(entry))
        except Exception:
            pass

        # Update panel bookmark log
        panel = getattr(self, "_sigid_panel", None)
        if panel is not None:
            panel.add_bookmark_entry(match, freq_hz)

    # ── Export to RF Lab ──────────────────────────────────────────────────

    def _export_to_rf_lab(self) -> None:
        """Export signal bookmarks from JSON to RF Lab frequency watchlist."""
        from PyQt6.QtWidgets import QMessageBox
        entries = []
        if _BOOKMARK_FILE.exists():
            try:
                bookmarks = json.loads(
                    _BOOKMARK_FILE.read_text(encoding="utf-8"))
                for b in bookmarks:
                    hz = int(b.get("freq_hz", 0))
                    name = str(b.get("name", "")).strip() or "Unknown"
                    desc = str(b.get("modulation", "") or "")
                    if hz > 0:
                        entries.append((hz, name, "SDR Bookmark", desc))
            except Exception as exc:
                log.warning("Bookmark read failed: %s", exc)
        if not entries:
            QMessageBox.information(
                self, self.tr("Export to RF Lab"),
                self.tr(
                    "No signal bookmarks found.\n\n"
                    "Right-click the spectrum or waterfall and choose\n"
                    "\"Identify Signal…\" to create bookmarks first."))
            return
        try:
            mw = self.window()
            if not (mw and hasattr(mw, "_tab_map")):
                raise RuntimeError("Main window not accessible")
            rf_lab = mw._tab_map.get("rf_lab")
            if not (rf_lab and hasattr(rf_lab, "add_custom_freqs_batch")):
                raise RuntimeError("RF Lab tab not available")
            added, skipped = rf_lab.add_custom_freqs_batch(entries)
            sb = getattr(mw, "statusBar", None)
            if callable(sb):
                msg = f"→ RF Lab: {added} bookmark(s) exported"
                if skipped:
                    msg += f", {skipped} skipped (already present)"
                sb().showMessage(msg, 5000)
        except Exception as exc:
            QMessageBox.warning(
                self, self.tr("Export to RF Lab"),
                self.tr(f"Could not export to RF Lab:\n{exc}"))

    # ── ADS-B ─────────────────────────────────────────────────────────────

    def _open_adsb_map(self):
        """Open dump1090 aircraft map in browser."""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if self.cfg:
            try:
                self.location_mgr.write_dump1090_receiver_json()
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl("http://localhost:8080"))

    def _check_dump1090_status(self):
        """Check if dump1090 is running; update button on main thread."""
        def _check():
            from PyQt6.QtCore import QTimer
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
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
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
