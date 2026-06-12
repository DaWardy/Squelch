from __future__ import annotations
"""SettingsDialog advanced tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt

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



class _SettingsAdvancedTab:
    """Mixed into SettingsDialog."""

    def _build_advanced_logging_section(self, f: "QFormLayout") -> None:
        _section(f, "Logging")
        self._log_level = QComboBox()
        self._log_level.addItems([
            "INFO (normal)",
            "DEBUG (verbose — for troubleshooting)",
            "WARNING (quiet)",
        ])
        f.addRow("Log Level:", self._log_level)
        self._log_max_size = QSpinBox()
        self._log_max_size.setRange(1, 100)
        self._log_max_size.setValue(5)
        self._log_max_size.setSuffix(" MB")
        f.addRow("Max Log Size:", self._log_max_size)

    def _build_advanced_network_section(self, f: "QFormLayout") -> None:
        _section(f, "Network")
        self._api_timeout = QSpinBox()
        self._api_timeout.setRange(3, 60)
        self._api_timeout.setValue(10)
        self._api_timeout.setSuffix(" seconds")
        f.addRow("API Timeout:", self._api_timeout)
        self._grayline_interval = QSpinBox()
        self._grayline_interval.setRange(10, 300)
        self._grayline_interval.setValue(60)
        self._grayline_interval.setSuffix(" seconds")
        self._grayline_interval.setToolTip(
            "How often to update the gray line on the map")
        f.addRow("Gray Line Update:", self._grayline_interval)

    def _build_advanced_data_section(self, f: "QFormLayout") -> None:
        _section(f, "Data")
        self._data_dir_lbl = QLabel(str(self.cfg._path.parent))
        self._data_dir_lbl.setStyleSheet("font-family:'Courier New';")
        f.addRow("Data Directory:", self._data_dir_lbl)
        open_btn = QPushButton("Open in Explorer")
        open_btn.setFixedWidth(140)
        open_btn.clicked.connect(self._open_data_dir)
        f.addRow("", open_btn)
        _section(f, "Privacy")
        self._share_spotting = QCheckBox(
            "Allow Squelch to appear in PSKReporter spots")
        f.addRow("", self._share_spotting)
        self._anon_telemetry = QCheckBox(
            "Send anonymous crash reports to help improve Squelch")
        self._anon_telemetry.setChecked(False)
        f.addRow("", self._anon_telemetry)

    def _tab_advanced(self) -> "QWidget":
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w = QWidget()
        scroll.setWidget(w)
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)
        self._build_advanced_logging_section(f)
        self._build_advanced_network_section(f)
        self._build_advanced_data_section(f)
        return scroll

