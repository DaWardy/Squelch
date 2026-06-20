from __future__ import annotations
"""SettingsDialog apis tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from core.themes import get_theme as _api_get_theme

def _scrolled() -> QWidget:
    """Return a plain widget (most tabs don't need scrolling)."""
    return QWidget()


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("margin:4px 0;")
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



class _SettingsApisTab:
    """Mixed into SettingsDialog."""

    def _tab_apis(self) -> QWidget:
        # APIs tab needs scrolling — many credential fields.
        # IMPORTANT: return scroll (not w). Returning w lets QScrollArea
        # get GC'd, deleting w's C++ object → "wrapped C/C++ object deleted".
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
        note = QLabel(
            "API credentials are stored securely in the OS keyring "
            "(Windows Credential Manager) — never in config files.")
        note.setWordWrap(True)
        note.setStyleSheet("")
        f.addRow("", note)
        self._apis_add_qrz_section(f)
        self._apis_add_hamqth_section(f)
        self._apis_add_hamalert_section(f)
        self._apis_add_radioreference_section(f)
        self._apis_add_lotw_section(f)
        self._apis_add_clublog_section(f)
        self._apis_add_eqsl_section(f)
        self._apis_add_hrdlog_section(f)
        self._apis_add_repeaterbook_section(f)
        self._apis_add_aprs_beacon_section(f)
        return scroll

    def _apis_add_aprs_beacon_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "APRS Beacon")
        note = QLabel(
            "APRS position beacon is sent via the APRS-IS connection.\n"
            "Toggle from the Map tab toolbar  (⚑ Beacon button).")
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;")
        f.addRow("", note)
        self._aprs_beacon_comment = QLineEdit()
        self._aprs_beacon_comment.setMaxLength(43)
        self._aprs_beacon_comment.setPlaceholderText("e.g. Squelch SDR")
        self._aprs_beacon_comment.setToolTip(
            "Comment appended to the APRS position packet (max 43 chars).\n"
            "Grid square is included automatically.")
        f.addRow("Comment:", self._aprs_beacon_comment)
        self._aprs_beacon_interval = QSpinBox()
        self._aprs_beacon_interval.setRange(120, 3600)
        self._aprs_beacon_interval.setValue(600)
        self._aprs_beacon_interval.setSuffix(" s")
        self._aprs_beacon_interval.setToolTip(
            "How often to send the beacon (seconds). Minimum 120 s.")
        f.addRow("Interval:", self._aprs_beacon_interval)
        self._aprs_beacon_symbol = QComboBox()
        for sym in ("house", "portable", "car", "walker", "bicycle", "emergency"):
            self._aprs_beacon_symbol.addItem(sym.title(), sym)
        self._aprs_beacon_symbol.setToolTip(
            "APRS symbol shown on the map for your station.")
        f.addRow("Symbol:", self._aprs_beacon_symbol)

    def _apis_add_qrz_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "QRZ.com")
        self._qrz_user = QLineEdit()
        self._qrz_user.setPlaceholderText("QRZ username / callsign")
        f.addRow("Username:", self._qrz_user)
        self._qrz_pass = QLineEdit()
        self._qrz_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._qrz_pass.setPlaceholderText("QRZ password")
        f.addRow("Password:", self._qrz_pass)
        note = QLabel(
            "QRZ XML API requires a QRZ subscription. "
            "Used for callsign lookup during FT8 operation.")
        note.setStyleSheet("")
        note.setWordWrap(True)
        f.addRow("", note)
        self._qrz_logbook_key = QLineEdit()
        self._qrz_logbook_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._qrz_logbook_key.setPlaceholderText("QRZ logbook API key")
        self._qrz_logbook_key.setToolTip(
            "Get this from qrz.com → Logbook → Settings → Enable API.\n"
            "Free — does not require a QRZ subscription.")
        f.addRow("Logbook API Key:", self._qrz_logbook_key)
        lb_note = QLabel(
            "Logbook API key is free — get it from qrz.com → Logbook → Settings.")
        lb_note.setWordWrap(True)
        lb_note.setStyleSheet("")
        f.addRow("", lb_note)

    def _apis_add_hamqth_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "HamQTH (free alternative to QRZ)")
        self._hamqth_user = QLineEdit()
        self._hamqth_user.setPlaceholderText("HamQTH callsign")
        f.addRow("Callsign:", self._hamqth_user)
        self._hamqth_pass = QLineEdit()
        self._hamqth_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._hamqth_pass.setPlaceholderText("HamQTH password")
        f.addRow("Password:", self._hamqth_pass)

    def _apis_add_hamalert_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "HamAlert")
        ha_note = QLabel(
            "HamAlert has no general-purpose API key.\n"
            "Telnet uses your full account login (stored in keyring).\n"
            "URL callbacks: append ?key=<secret> to your endpoint URL.\n"
            "SMS alerts: requires a TextAnywhere (Clockwork) API token.")
        ha_note.setWordWrap(True)
        _t = _api_get_theme(self.cfg.get("ui.theme", "Dark"))
        ha_note.setStyleSheet(f"color:{_t.fg_secondary};")
        f.addRow("", ha_note)
        self._hamalert_user = QLineEdit()
        self._hamalert_user.setPlaceholderText("HamAlert callsign/username")
        f.addRow("Username:", self._hamalert_user)
        self._hamalert_key = QLineEdit()
        self._hamalert_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._hamalert_key.setPlaceholderText("HamAlert password (stored in keyring)")
        f.addRow("Password:", self._hamalert_key)
        self._hamalert_url_secret = QLineEdit()
        self._hamalert_url_secret.setPlaceholderText(
            "URL callback secret (e.g. abc123 → ?key=abc123)")
        self._hamalert_url_secret.setToolTip(
            "Append this value as ?key=<secret> to your HamAlert URL notification endpoint.\n"
            "Your receiver script can validate incoming alerts by checking this shared secret.")
        f.addRow("URL Secret:", self._hamalert_url_secret)
        self._hamalert_sms_token = QLineEdit()
        self._hamalert_sms_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._hamalert_sms_token.setPlaceholderText(
            "TextAnywhere (Clockwork) API token for SMS alerts")
        self._hamalert_sms_token.setToolTip(
            "Generate at textanywhere.net → Account Settings → API Keys.\n"
            "Required only if you use HamAlert SMS notifications.")
        f.addRow("SMS Token:", self._hamalert_sms_token)

    def _apis_add_radioreference_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "RadioReference Premium")
        self._rr_user = QLineEdit()
        self._rr_user.setPlaceholderText("RadioReference username")
        f.addRow("Username:", self._rr_user)
        self._rr_key = QLineEdit()
        self._rr_key.setPlaceholderText("RadioReference API key")
        f.addRow("API Key:", self._rr_key)

    def _apis_add_lotw_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "LoTW (ARRL Logbook of the World)")
        self._lotw_user = QLineEdit()
        self._lotw_user.setPlaceholderText("LoTW callsign")
        f.addRow("Callsign:", self._lotw_user)
        self._lotw_pass = QLineEdit()
        self._lotw_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._lotw_pass.setPlaceholderText("LoTW password")
        f.addRow("Password:", self._lotw_pass)
        self._auto_upload_lotw = QCheckBox("Auto-upload QSOs to LoTW after logging")
        f.addRow("", self._auto_upload_lotw)

    def _apis_add_clublog_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "ClubLog")
        self._clublog_email = QLineEdit()
        self._clublog_email.setPlaceholderText("ClubLog email")
        f.addRow("Email:", self._clublog_email)
        self._clublog_pass = QLineEdit()
        self._clublog_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._clublog_pass.setPlaceholderText("ClubLog password")
        f.addRow("Password:", self._clublog_pass)

    def _apis_add_eqsl_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "eQSL.cc (Electronic QSL)")
        self._eqsl_user = QLineEdit()
        self._eqsl_user.setPlaceholderText("eQSL username / callsign")
        f.addRow("Username:", self._eqsl_user)
        self._eqsl_pass = QLineEdit()
        self._eqsl_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._eqsl_pass.setPlaceholderText("eQSL password")
        f.addRow("Password:", self._eqsl_pass)
        note = QLabel("Free account at eqsl.cc. Uploads full log as ADIF.")
        note.setWordWrap(True)
        note.setStyleSheet("")
        f.addRow("", note)

    def _apis_add_hrdlog_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "HRDLog.net")
        self._hrdlog_callsign = QLineEdit()
        self._hrdlog_callsign.setPlaceholderText("Your callsign")
        f.addRow("Callsign:", self._hrdlog_callsign)
        self._hrdlog_key = QLineEdit()
        self._hrdlog_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._hrdlog_key.setPlaceholderText("HRDLog API key")
        self._hrdlog_key.setToolTip(
            "Get from hrdlog.net → Settings → API Key.\n"
            "Free account required.")
        f.addRow("API Key:", self._hrdlog_key)
        note = QLabel(
            "Free account at hrdlog.net. Uploads full log as ADIF.")
        note.setWordWrap(True)
        note.setStyleSheet("")
        f.addRow("", note)

    def _apis_add_repeaterbook_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "RepeaterBook (Local RF)")
        self._rb_token = QLineEdit()
        self._rb_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._rb_token.setPlaceholderText("RepeaterBook API token")
        f.addRow("API token:", self._rb_token)
        note = QLabel(
            "As of March 2026 RepeaterBook requires an approved API token. "
            "Apply (free for non-commercial use) at "
            "repeaterbook.com/api/token_request.php, then paste the token "
            "here. Without it, Local RF can still be populated by importing a "
            "CHIRP CSV export (Local RF tab → Import CHIRP CSV).")
        note.setWordWrap(True)
        f.addRow("", note)

