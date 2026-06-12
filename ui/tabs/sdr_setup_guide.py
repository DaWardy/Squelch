from __future__ import annotations
"""SDR setup-guide mixin."""
import subprocess, sys, webbrowser
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QFrame)
from core.themes import get_theme as _sg_get_theme

class _SDRSetupGuideMixin:
    def _build_rtltcp(self, outer):
        _t = _sg_get_theme(
            self.cfg.get("ui.theme", "Dark") if getattr(self, "cfg", None) else "Dark")
        w = QWidget(); vl = QVBoxLayout(w)
        vl.setContentsMargins(20,20,20,20)
        h = QLabel("RTL-TCP Mode — rtl_tcp running on 127.0.0.1:1234")
        h.setStyleSheet(f"font-size:14px;font-weight:bold;color:{_t.accent};")
        vl.addWidget(h)
        vl.addWidget(QLabel("SoapySDR not installed — using RTL-TCP as sample source.\nSelect RTL-TCP server from the Device dropdown above."))
        b = QPushButton("Install SoapySDR for full support")
        b.clicked.connect(lambda: self._open_url("https://github.com/pothosware/SoapySDR/wiki"))
        vl.addWidget(b); vl.addStretch(); outer.addWidget(w)

    def _detect_connected_hardware(self) -> list:
        found = []
        try:
            cmd = ["pnputil","/enum-devices","/class","USB"] if sys.platform=="win32" else ["lsusb"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            t = r.stdout.lower()
            if "0bda" in t and ("2832" in t or "2838" in t): found.append("RTL-SDR")
            if "1d50" in t and "6089" in t: found.append("HackRF One")
            if "2500" in t and ("0020" in t or "0021" in t): found.append("USRP B200/B210")
            if "1df7" in t: found.append("SDRplay RSP")
        except Exception: pass
        return found

    def _build_no_soapy(self, layout):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); vl = QVBoxLayout(inner)
        vl.setContentsMargins(20,20,20,20); vl.setSpacing(16)
        scroll.setWidget(inner)
        _t = _sg_get_theme(
            self.cfg.get("ui.theme", "Dark") if getattr(self, "cfg", None) else "Dark")
        h = QLabel("SDR Setup — SoapySDR not installed")
        h.setStyleSheet(f"font-size:16px;font-weight:bold;color:{_t.accent};")
        vl.addWidget(h)
        det = self._detect_connected_hardware()
        if det:
            vl.addWidget(QLabel("Detected: " + ", ".join(det)))
        self._setup_path(vl, "Windows — miniforge/conda (recommended)", "#0a1a0a", "#3fbe6f", [
            ("No CMake, no Visual Studio. Works with any RTL-SDR.", None, None, None),
            ("Step 1 — Install miniforge3", "conda-forge.org", "https://github.com/conda-forge/miniforge/releases/latest", "Download miniforge3"),
            ("Step 2 — Miniforge Prompt", "conda install -c conda-forge soapysdr soapysdr-module-rtlsdr soapysdr-module-hackrf", None, None),
            ("Step 3 — Install Zadig (RTL-SDR only)", "Run Zadig → RTL2832U → Install WinUSB", "https://zadig.akeo.ie", "Download Zadig"),
            ("Step 4 — Restart Squelch", "Squelch auto-detects conda.", None, None),
        ])
        self._setup_path(vl, "pip (Squelch venv)", "#0a0a1a", "#6090ff", [
            ("venv\\Scripts\\pip install soapysdr", None, None, None),
            ("Then: conda install -c conda-forge soapysdr-module-rtlsdr", None, None, None),
        ])
        self._setup_path(vl, "Linux", "#1a0a0a", "#ff8060", [
            ("sudo apt install python3-soapysdr soapysdr-module-rtlsdr", None, None, None),
            ("sudo usermod -aG plugdev $USER  # then reboot", None, None, None),
        ])
        vl.addStretch(); layout.addWidget(scroll)

    def _setup_path(self, parent, title, bg, fg, steps):
        frame = QFrame()
        frame.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {fg}44;border-radius:6px;padding:4px;}}")
        gl = QVBoxLayout(frame); gl.setSpacing(6)
        tl = QLabel(title); tl.setStyleSheet(f"color:{fg};font-weight:bold;"); gl.addWidget(tl)
        for step in steps:
            st_title = step[0] if len(step)>0 else ""
            detail   = step[1] if len(step)>1 else None
            url      = step[2] if len(step)>2 else None
            btn_lbl  = step[3] if len(step)>3 else None
            rl = QHBoxLayout()
            st = QLabel(f"<b>{st_title}</b>"); st.setWordWrap(True); rl.addWidget(st, 1)
            if url and btn_lbl:
                b = QPushButton(btn_lbl); b.setFixedWidth(200)
                b.clicked.connect(lambda _=False, u=url: self._open_url(u))
                rl.addWidget(b)
            gl.addLayout(rl)
            if detail:
                dl = QLabel(detail); dl.setWordWrap(True)
                _t2 = _sg_get_theme(
                    self.cfg.get("ui.theme","Dark") if getattr(self,"cfg",None) else "Dark")
                dl.setStyleSheet(
                    f"font-family:'Courier New';font-size:10px;"
                    f"color:{_t2.fg_muted};margin-left:8px;")
                gl.addWidget(dl)
        parent.addWidget(frame)

    def _open_url(self, url: str):
        try: webbrowser.open(url)
        except Exception: pass

    def _build_no_pyqtgraph(self, layout):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(20,20,20,20)
        _t = _sg_get_theme(
            self.cfg.get("ui.theme", "Dark") if getattr(self, "cfg", None) else "Dark")
        h = QLabel("Spectrum display unavailable — pyqtgraph not installed")
        h.setStyleSheet(f"font-size:14px;font-weight:bold;color:{_t.warn_color};")
        vl.addWidget(h)
        vl.addWidget(QLabel("Install: pip install pyqtgraph\n   or:  conda install -c conda-forge pyqtgraph"))
        b = QPushButton("pyqtgraph docs"); b.clicked.connect(lambda: self._open_url("https://pyqtgraph.readthedocs.io/"))
        vl.addWidget(b); vl.addStretch(); layout.addWidget(w)
