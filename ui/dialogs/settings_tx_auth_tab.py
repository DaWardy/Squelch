from __future__ import annotations
"""SettingsDialog TX Authorization tab (ROADMAP Phase 5, AUTH-LAYER).

The operator-facing half of the transmit authorization gate. Transmit is
**default-deny**: nothing keys until the operator (1) accepts the legal-use
acknowledgment and (2) opts specific bands in. A buried **unrestricted
override** sits at the bottom behind disclaimers.

This tab only reads/writes the three `tx.auth.*` config keys that
`core.authorization.AuthorizationProfile` consumes — it renders the decision
core's inputs; it does not itself decide anything.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QGroupBox, QGridLayout, QScrollArea, QFrame, QPushButton)
from PyQt6.QtCore import Qt


class _SettingsTxAuthTab:
    """Mixed into SettingsDialog."""

    def _tab_tx_auth(self) -> "QWidget":
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setSpacing(12)
        v.setContentsMargins(16, 16, 16, 16)
        self._build_tx_ack_section(v)
        self._build_tx_bands_section(v)
        self._build_tx_unrestricted_section(v)
        v.addStretch()
        return scroll

    # ── legal acknowledgment ──────────────────────────────────────────────
    def _build_tx_ack_section(self, v: "QVBoxLayout") -> None:
        gb = QGroupBox("Transmit — legal acknowledgment")
        gl = QVBoxLayout(gb)
        warn = QLabel(
            "Squelch can drive TX-capable radios and SDRs. Transmitting is "
            "your responsibility: you must be licensed and authorized for "
            "each frequency you key. Transmit stays fully disabled until you "
            "accept below and enable specific bands.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#ffcc00;")
        gl.addWidget(warn)
        self._tx_ack = QCheckBox(
            "I acknowledge I am responsible for the legality of every "
            "transmission I make with Squelch.")
        self._tx_ack.setToolTip(
            "Required before any band can be enabled for transmit.")
        self._tx_ack.toggled.connect(self._on_tx_ack_toggled)
        gl.addWidget(self._tx_ack)
        v.addWidget(gb)

    # ── per-band opt-in ───────────────────────────────────────────────────
    def _build_tx_bands_section(self, v: "QVBoxLayout") -> None:
        gb = QGroupBox("Authorized transmit bands (default: none)")
        outer = QVBoxLayout(gb)
        hint = QLabel(
            "Enable only the bands you are licensed and authorized to "
            "transmit on. A frequency outside every enabled band is denied.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a8f98;")
        outer.addWidget(hint)
        self._tx_band_checks: dict[str, QCheckBox] = {}
        outer.addLayout(self._build_band_grid())
        row = QHBoxLayout()
        sel = QPushButton("Select all")
        clr = QPushButton("Clear all")
        sel.clicked.connect(lambda: self._set_all_tx_bands(True))
        clr.clicked.connect(lambda: self._set_all_tx_bands(False))
        row.addWidget(sel); row.addWidget(clr); row.addStretch()
        outer.addLayout(row)
        v.addWidget(gb)

    def _build_band_grid(self) -> "QGridLayout":
        from core.band_plan import BANDS, SERVICE_BANDS
        grid = QGridLayout()
        col_count = 4
        i = 0
        for band in list(BANDS) + list(SERVICE_BANDS):
            chk = QCheckBox(band.name)
            chk.setToolTip(
                f"{band.category}: "
                f"{band.freq_lo/1e6:.3f}–{band.freq_hi/1e6:.3f} MHz")
            self._tx_band_checks[band.name] = chk
            grid.addWidget(chk, i // col_count, i % col_count)
            i += 1
        return grid

    def _set_all_tx_bands(self, on: bool) -> None:
        for chk in getattr(self, "_tx_band_checks", {}).values():
            chk.setChecked(bool(on))

    def _on_tx_ack_toggled(self, on: bool) -> None:
        """Bands and the override are meaningless without the acknowledgment;
        disable (but never silently clear) them when it is off."""
        for chk in getattr(self, "_tx_band_checks", {}).values():
            chk.setEnabled(bool(on))
        if hasattr(self, "_tx_unrestricted"):
            self._tx_unrestricted.setEnabled(bool(on))

    # ── buried unrestricted override ──────────────────────────────────────
    def _build_tx_unrestricted_section(self, v: "QVBoxLayout") -> None:
        gb = QGroupBox("Advanced — unrestricted override")
        gl = QVBoxLayout(gb)
        warn = QLabel(
            "⚠ DANGER: this removes the per-band allow-list and permits "
            "transmit on ANY frequency the hardware supports, including bands "
            "you may not be licensed for. Intended only for emergency use or "
            "operators holding spectrum-wide authorization. Every keying is "
            "logged. Leave OFF unless you understand and accept the legal "
            "consequences.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#ff5555;font-weight:bold;")
        gl.addWidget(warn)
        self._tx_unrestricted = QCheckBox(
            "Enable unrestricted transmit override (I accept full legal "
            "responsibility)")
        gl.addWidget(self._tx_unrestricted)
        v.addWidget(gb)

    # ── load / save (tx.auth.* keys — see core.authorization) ─────────────
    def _load_tx_auth(self, cfg) -> None:
        ack = bool(cfg.get("tx.auth.acknowledged", False))
        allowed = set(cfg.get("tx.auth.allowed_bands", []) or [])
        self._tx_ack.setChecked(ack)
        for name, chk in self._tx_band_checks.items():
            chk.setChecked(name in allowed)
        self._tx_unrestricted.setChecked(
            bool(cfg.get("tx.auth.unrestricted", False)))
        self._on_tx_ack_toggled(ack)

    def _save_tx_auth(self, cfg) -> None:
        cfg.set("tx.auth.acknowledged", self._tx_ack.isChecked())
        bands = sorted(name for name, chk in self._tx_band_checks.items()
                       if chk.isChecked())
        cfg.set("tx.auth.allowed_bands", bands)
        cfg.set("tx.auth.unrestricted", self._tx_unrestricted.isChecked())
