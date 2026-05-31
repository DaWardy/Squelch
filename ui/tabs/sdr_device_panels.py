"""SDR device-specific control panels — mixin for SDRTab."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QCheckBox, QComboBox, QSlider, QSpinBox, QPushButton, QLineEdit)

class _SDRDevicePanelsMixin:

    def _hackrf_panel(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w)
        grp = QGroupBox("HackRF One"); gl = QVBoxLayout(grp)

        amp_cb = QCheckBox("RF Amp (+14 dB)")
        amp_cb.setChecked(self.cfg.get("sdr.hackrf.amp", False))
        amp_cb.toggled.connect(self._on_hackrf_amp)
        gl.addWidget(amp_cb); self._hackrf_amp_cb = amp_cb

        bias_cb = QCheckBox("Bias Tee (3.3 V)")
        bias_cb.setChecked(self.cfg.get("sdr.hackrf.bias", False))
        bias_cb.toggled.connect(self._on_hackrf_bias)
        gl.addWidget(bias_cb); self._hackrf_bias_cb = bias_cb

        rl = QHBoxLayout(); rl.addWidget(QLabel("LNA gain:"))
        lna = QComboBox()
        lna.addItems([f"{v} dB" for v in range(0, 41, 8)])
        lna.setCurrentText(f"{self.cfg.get('sdr.hackrf.lna', 16)} dB")
        lna.currentTextChanged.connect(self._on_hackrf_lna)
        rl.addWidget(lna); gl.addLayout(rl); self._hackrf_lna = lna

        rl2 = QHBoxLayout(); rl2.addWidget(QLabel("VGA gain:"))
        vga = QSpinBox(); vga.setRange(0, 62); vga.setSingleStep(2)
        vga.setSuffix(" dB"); vga.setValue(self.cfg.get("sdr.hackrf.vga", 20))
        vga.valueChanged.connect(self._on_hackrf_vga)
        rl2.addWidget(vga); gl.addLayout(rl2); self._hackrf_vga = vga

        vl.addWidget(grp); return w

    def _usrp_panel(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w)
        grp = QGroupBox("USRP B200/B210"); gl = QVBoxLayout(grp)

        rl = QHBoxLayout(); rl.addWidget(QLabel("Clock source:"))
        clk = QComboBox(); clk.addItems(["internal", "external", "gpsdo"])
        clk.setCurrentText(self.cfg.get("sdr.usrp.clock_source", "internal"))
        clk.currentTextChanged.connect(self._on_usrp_clock)
        rl.addWidget(clk); gl.addLayout(rl); self._usrp_clock = clk

        rl2 = QHBoxLayout(); rl2.addWidget(QLabel("Subdev:"))
        sub = QLineEdit(self.cfg.get("sdr.usrp.subdev", "A:A"))
        sub.setPlaceholderText("A:A  or  A:A A:B (B210)")
        sub.editingFinished.connect(lambda: self._on_usrp_subdev(sub.text()))
        rl2.addWidget(sub); gl.addLayout(rl2); self._usrp_subdev = sub

        rl3 = QHBoxLayout(); rl3.addWidget(QLabel("Antenna:"))
        ant = QComboBox(); ant.addItems(["TX/RX", "RX2"])
        ant.setCurrentText(self.cfg.get("sdr.usrp.antenna", "TX/RX"))
        ant.currentTextChanged.connect(self._on_usrp_ant)
        rl3.addWidget(ant); gl.addLayout(rl3); self._usrp_ant = ant

        vl.addWidget(grp); return w

    def _rtlsdr_panel(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w)
        grp = QGroupBox("RTL-SDR"); gl = QVBoxLayout(grp)

        rl = QHBoxLayout(); rl.addWidget(QLabel("Direct sampling:"))
        ds = QComboBox()
        ds.addItems(["Off (normal)", "I-branch (Q1)", "Q-branch (Q2)"])
        ds.setCurrentIndex(self.cfg.get("sdr.rtl.direct_sampling", 0))
        ds.currentIndexChanged.connect(self._on_rtl_direct_sampling)
        ds.setToolTip("Direct sampling enables HF reception below 24 MHz.\n"
                      "Q-branch works on most RTL-SDR Blog V3/V4 dongles.")
        rl.addWidget(ds); gl.addLayout(rl); self._rtl_ds = ds

        bias_cb = QCheckBox("Bias Tee (4.5 V)")
        bias_cb.setChecked(self.cfg.get("sdr.rtl.bias", False))
        bias_cb.toggled.connect(self._on_rtl_bias)
        bias_cb.setToolTip("Powers active antennas and LNAs via the coax.")
        gl.addWidget(bias_cb); self._rtl_bias_cb = bias_cb

        vl.addWidget(grp); return w

    def _sdrplay_panel(self, model: str) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w)
        grp = QGroupBox(f"SDRplay {model}"); gl = QVBoxLayout(grp)

        # Antenna selection (varies by model)
        ants = {"RSP1A": ["ANT A"], "RSP2": ["ANT A", "ANT B", "Hi-Z"],
                "RSPdx": ["ANT A", "ANT B", "ANT C"],
                "RSP1":  ["ANT A"], "RSPduo": ["Tuner 1", "Tuner 2"]}
        ant_opts = ants.get(model, ["ANT A"])
        rl = QHBoxLayout(); rl.addWidget(QLabel("Antenna:"))
        ant = QComboBox(); ant.addItems(ant_opts)
        ant.setCurrentText(self.cfg.get(f"sdr.rsp.{model}.antenna", ant_opts[0]))
        ant.currentTextChanged.connect(self._on_rsp_antenna)
        rl.addWidget(ant); gl.addLayout(rl); self._rsp_ant = ant

        # Bandwidth
        rl2 = QHBoxLayout(); rl2.addWidget(QLabel("IF bandwidth:"))
        bw = QComboBox()
        bw.addItems(["200 kHz","300 kHz","600 kHz","1.536 MHz","5 MHz","6 MHz","7 MHz","8 MHz"])
        bw.setCurrentText(self.cfg.get(f"sdr.rsp.{model}.bandwidth", "1.536 MHz"))
        bw.currentIndexChanged.connect(self._on_rsp_bandwidth)
        rl2.addWidget(bw); gl.addLayout(rl2); self._rsp_bw = bw

        # Notch filters
        if model in ("RSP1A", "RSPdx"):
            notch = QCheckBox("AM/FM notch filter")
            notch.setChecked(self.cfg.get(f"sdr.rsp.{model}.notch", False))
            notch.toggled.connect(self._on_rsp_notch)
            gl.addWidget(notch); self._rsp_notch = notch

            dab = QCheckBox("DAB notch filter")
            dab.setChecked(self.cfg.get(f"sdr.rsp.{model}.dab_notch", False))
            dab.toggled.connect(self._on_rsp_dab_notch)
            gl.addWidget(dab); self._rsp_dab = dab

        # Bias tee
        if model in ("RSP1A", "RSP2", "RSPdx", "RSPduo"):
            bias = QCheckBox("Bias Tee")
            bias.setChecked(self.cfg.get(f"sdr.rsp.{model}.bias", False))
            bias.toggled.connect(self._on_rsp_bias)
            gl.addWidget(bias); self._rsp_bias = bias

        # AGC / IF gain reduction
        agc = QCheckBox("Hardware AGC")
        agc.setChecked(self.cfg.get(f"sdr.rsp.{model}.agc", True))
        agc.toggled.connect(self._on_rsp_agc)
        gl.addWidget(agc); self._rsp_agc = agc

        rl3 = QHBoxLayout(); rl3.addWidget(QLabel("IF gain reduction:"))
        ifgr = QSpinBox(); ifgr.setRange(20, 59); ifgr.setSuffix(" dB")
        ifgr.setValue(self.cfg.get(f"sdr.rsp.{model}.ifgr", 40))
        ifgr.valueChanged.connect(self._on_rsp_ifgr)
        rl3.addWidget(ifgr); gl.addLayout(rl3); self._rsp_ifgr = ifgr

        # IQ correction
        iq = QCheckBox("IQ correction")
        iq.setChecked(self.cfg.get(f"sdr.rsp.{model}.iq_correction", True))
        iq.toggled.connect(self._on_rsp_iq)
        gl.addWidget(iq); self._rsp_iq = iq

        vl.addWidget(grp); return w

    # ── RSP callbacks ─────────────────────────────────────────────────

    def _rsp_write(self, key: str, val):
        self.cfg.set(key, val); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param(key, val)
            except Exception: pass

    def _on_rsp_antenna(self, ant: str):
        self._rsp_write("sdr.rsp.antenna", ant)

    def _on_rsp_bandwidth(self, idx: int):
        self._rsp_write("sdr.rsp.bandwidth_idx", idx)

    def _on_rsp_notch(self, enabled: bool):
        self._rsp_write("sdr.rsp.notch", enabled)

    def _on_rsp_dab_notch(self, enabled: bool):
        self._rsp_write("sdr.rsp.dab_notch", enabled)

    def _on_rsp_bias(self, enabled: bool):
        self._rsp_write("sdr.rsp.bias", enabled)

    def _on_rsp_agc(self, enabled: bool):
        self._rsp_write("sdr.rsp.agc", enabled)
        if hasattr(self, "_rsp_ifgr"):
            self._rsp_ifgr.setEnabled(not enabled)

    def _on_rsp_ifgr(self, db: int):
        self._rsp_write("sdr.rsp.ifgr", db)
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_gain(db)
            except Exception: pass

    def _on_rsp_iq(self, enabled: bool):
        self._rsp_write("sdr.rsp.iq_correction", enabled)

    # ── HackRF callbacks ──────────────────────────────────────────────

    def _on_hackrf_amp(self, enabled: bool):
        self.cfg.set("sdr.hackrf.amp", enabled); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("amp_enable", enabled)
            except Exception: pass

    def _on_hackrf_bias(self, enabled: bool):
        self.cfg.set("sdr.hackrf.bias", enabled); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("bias", enabled)
            except Exception: pass

    def _on_hackrf_lna(self, text: str):
        db = int(text.replace(" dB", ""))
        self.cfg.set("sdr.hackrf.lna", db); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("lna", db)
            except Exception: pass

    def _on_hackrf_vga(self, db: int):
        self.cfg.set("sdr.hackrf.vga", db); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("vga", db)
            except Exception: pass

    # ── USRP callbacks ────────────────────────────────────────────────

    def _on_usrp_clock(self, source: str):
        self.cfg.set("sdr.usrp.clock_source", source); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("clock_source", source)
            except Exception: pass

    def _on_usrp_subdev(self, spec: str):
        self.cfg.set("sdr.usrp.subdev", spec); self.cfg.save()

    def _on_usrp_ant(self, ant: str):
        self.cfg.set("sdr.usrp.antenna", ant); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("antenna", ant)
            except Exception: pass

    # ── RTL-SDR callbacks ─────────────────────────────────────────────

    def _on_rtl_direct_sampling(self, idx: int):
        self.cfg.set("sdr.rtl.direct_sampling", idx); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("direct_samp", idx)
            except Exception: pass

    def _on_rtl_bias(self, enabled: bool):
        self.cfg.set("sdr.rtl.bias", enabled); self.cfg.save()
        if hasattr(self, "_manager") and self._manager:
            try: self._manager.set_device_param("bias", enabled)
            except Exception: pass
