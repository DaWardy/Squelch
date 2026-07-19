from __future__ import annotations
"""Squelch -- ui/tabs/sdr_recording.py
_SDRRecordingMixin: IQ recorder/player methods extracted from SDRTab.
Also owns _safe_recordings_path (used by SDRTab and _SDRSignalIDMixin).
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QInputDialog

from sdr.iq_recorder import list_recordings, Recording
from ui.tabs.sdr_paths import _safe_recordings_path  # noqa: F401 re-export

log = logging.getLogger(__name__)


class _SDRRecordingMixin:
    """IQ recorder and playback methods for SDRTab."""

    def _toggle_record(self):
        if self._recorder.is_recording:
            self._recorder.stop()
            self._rec_btn.setText("⏺ Record")
            self._rec_btn.setStyleSheet(
                "background:#3a1a1a;color:#cc4444;"
                "border:1px solid #cc4444;border-radius:4px;")
            self._rec_status.setText(self.tr("Recording saved"))
            self._rec_status.setStyleSheet(
                "color:#3fbe6f;font-family:'Courier New';")
            self._refresh_recordings()
        else:
            hw = (self._current.display_name if self._current else "")
            from core.guest_op import operating_callsign
            cs   = operating_callsign(self.cfg) or ""
            grid = self.cfg.grid or ""
            notes = (f"operator:{cs} grid:{grid}".strip()
                     if cs or grid else "")
            lat = self.cfg.get("location.lat", 0.0)
            lon = self.cfg.get("location.lon", 0.0)
            stem = self._recorder.start(
                self._center_hz, self._manager._sample_rate,
                hardware=hw, notes=notes, lat=lat, lon=lon)
            if stem:
                self._rec_btn.setText("■ Stop")
                self._rec_btn.setStyleSheet(
                    "background:#cc2222;color:#fff;"
                    "border:1px solid #ff4444;border-radius:4px;")

    def _on_audio_record_toggle(self, on: bool) -> None:
        """Start/stop recording the tuned VFO's demod audio to a WAV (§14.7)."""
        if on:
            mode = self._demod_combo.currentText()
            if mode == "Raw IQ":
                self._audio_rec_btn.setChecked(False)
                self._sdr_status_msg(self.tr(
                    "Pick a demod mode (AM/FM/SSB/CW) to record audio"))
                return
            from core.audio_record import AudioRecorder
            self._audio_rec = AudioRecorder(
                mode=mode, offset_hz=0.0,
                bandwidth_hz=float(getattr(self, "_bw_hz", 0) or 0))
            self._audio_rec.start()
            self._audio_rec_btn.setText(self.tr("■ Stop Audio"))
        else:
            self._audio_rec_btn.setText(self.tr("🎧 Rec Audio"))
            rec = getattr(self, "_audio_rec", None)
            if rec is None or not rec.is_recording:
                return
            from pathlib import Path
            from PyQt6.QtCore import QDateTime
            ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            out_dir = _safe_recordings_path(self.cfg)
            path = Path(out_dir) / f"audio_{ts}.wav"
            written = rec.stop(path)
            if written is not None:
                self._sdr_status_msg(self.tr(
                    f"Audio saved: {written.name}  ({rec.duration_s:.1f}s)"))
            else:
                self._sdr_status_msg(self.tr("No audio captured"))
            self._audio_rec = None

    def _sdr_status_msg(self, text: str) -> None:
        """Best-effort status message (window status bar, else the SDR label)."""
        try:
            self.window().statusBar().showMessage(text, 5000)
        except Exception:
            if hasattr(self, "_sdr_status"):
                self._sdr_status.setText(text)

    def _toggle_play(self):
        if self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("▶ Play")
        else:
            self._player.play()
            self._play_btn.setText("⏸ Pause")
            self._stop_btn.setEnabled(True)

    def _stop_playback(self):
        self._player.stop()
        self._play_btn.setText("▶ Play")
        self._stop_btn.setEnabled(False)
        self._play_bar.setValue(0)

    def _on_playback_reverse(self, on: bool) -> None:
        """Reverse toggle → play the capture backwards (live if playing)."""
        self._player.set_reverse(bool(on))

    def _on_playback_speed(self, text: str) -> None:
        """Speed combo ('2×') → set playback speed (live if playing)."""
        try:
            self._player.set_speed(float(text.replace("×", "").strip()))
        except (ValueError, AttributeError):
            pass

    def _load_recording(self):
        idx = self._rec_combo.currentIndex()
        recs = list_recordings(_safe_recordings_path(self.cfg))
        if 0 <= idx < len(recs):
            rec = recs[idx]
            if self._player.load(rec):
                self._player.on_samples(self._on_samples)
                self._player.on_progress(self._on_play_progress)
                self._player.on_end(
                    lambda: QTimer.singleShot(0, self._stop_playback))
                self._set_freq(rec.center_hz)
                self._rec_status.setText(f"Loaded: {rec.name}")
            else:
                QMessageBox.warning(self, self.tr("Load Failed"),
                                    self.tr("Recording file not found."))

    def _open_recording_file(self, p) -> "Recording | None":
        """Parse a recording file path; return Recording or None on error."""
        p = Path(p)
        if p.suffix == ".sigmf-meta":
            return Recording.from_meta_file(p)
        if p.suffix == ".sigmf-data":
            meta = p.with_suffix(".sigmf-meta")
            if meta.exists():
                return Recording.from_meta_file(meta)
            QMessageBox.warning(
                self, self.tr("Missing metadata"),
                self.tr("This .sigmf-data file has no sibling "
                        ".sigmf-meta — sample rate and center frequency are unknown."))
            return None
        if p.suffix.lower() in (".cf32", ".iq", ".bin"):
            sr, ok = QInputDialog.getInt(
                self, self.tr("Sample rate"),
                self.tr("Sample rate (Hz) — required for raw IQ files:"),
                2_400_000, 8_000, 100_000_000, 1)
            if not ok:
                return None
            # Raw files carry no format header — ask (unless the extension
            # already implies cf32). RTL-SDR dumps are cu8; HackRF ci8.
            dtype = "cf32_le"
            if p.suffix.lower() != ".cf32":
                choices = ["cf32_le (complex float32)",
                           "cu8 (RTL-SDR 8-bit)",
                           "ci8 (HackRF 8-bit)",
                           "ci16_le (16-bit)"]
                pick, ok2 = QInputDialog.getItem(
                    self, self.tr("Sample format"),
                    self.tr("IQ sample format:"), choices, 0, False)
                if not ok2:
                    return None
                dtype = pick.split()[0]
            from core.sigmf_io import bytes_per_sample
            try:
                duration = p.stat().st_size / bytes_per_sample(dtype) / sr
            except Exception:
                duration = 0.0
            return Recording(
                name=p.stem, data_path=p, meta_path=p,
                center_hz=getattr(self, "_center_hz", 0),
                sample_rate=sr, datatype=dtype,
                duration_s=duration, file_size=p.stat().st_size)
        QMessageBox.information(
            self, self.tr("Unsupported format"),
            self.tr(
                f"'{p.suffix}' files are not currently supported.\n"
                "Supported: .sigmf-meta, .sigmf-data, .cf32, .iq, .bin\n"
                "(SigMF carries its own format; raw .iq/.bin let you pick "
                "cf32 / cu8 / ci8 / ci16.)\n\n"
                "WAV audio is not IQ data — use Squelch's Record button "
                "or a SigMF-compliant capture tool."))
        return None

    def _browse_recording(self):
        """Open any SigMF / raw IQ file from anywhere on disk."""
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Open IQ recording"), "",
            "All supported (*.sigmf-meta *.sigmf-data *.cf32 *.iq *.bin);;"
            "SigMF metadata (*.sigmf-meta);;"
            "SigMF data (*.sigmf-data);;"
            "Raw complex64 IQ (*.cf32 *.iq *.bin);;"
            "All files (*)")
        if not path:
            return
        rec = self._open_recording_file(path)
        if not rec:
            return
        if not self._player.load(rec):
            QMessageBox.warning(self, self.tr("Load Failed"),
                                self.tr("Recording file not found or unreadable."))
            return
        self._player.on_samples(self._on_samples)
        self._player.on_progress(self._on_play_progress)
        self._player.on_end(lambda: QTimer.singleShot(0, self._stop_playback))
        self._set_freq(rec.center_hz)
        self._rec_status.setText(f"Loaded: {rec.name}")

    def _on_play_progress(self, pos_s: float, dur_s: float):
        if dur_s > 0:
            pct = int(pos_s / dur_s * 100)
            QTimer.singleShot(0, lambda p=pct: self._play_bar.setValue(p))

    def _refresh_recordings(self):
        recs = list_recordings(_safe_recordings_path(self.cfg))
        self._rec_combo.clear()
        for r in recs:
            self._rec_combo.addItem(r.display_name)
