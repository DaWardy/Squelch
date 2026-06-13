"""
Squelch -- core/macros.py
F-key TX macro manager.

Macros are keyed F1-F8. Each macro is a dict with:
  label   : str  — button label (e.g. "CQ", "59", "TU")
  text    : str  — template text with substitution vars

Substitution variables:
  {mycall}    — operating callsign (from operating_callsign())
  {theircall} — last-logged or manually set DX callsign
  {freq}      — VFO A frequency in MHz (e.g. 14.074)
  {mode}      — active mode (e.g. FT8, SSB)
  {serial}    — QSO serial number; incremented when expand(auto_increment_serial=True)
  {name}      — operator name from config, or blank

Macros persist to config under the key "macros.fX" where X is 1-8.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Config

_NUM_MACROS = 8

DEFAULTS: dict[str, dict] = {
    "f1": {"label": "CQ",   "text": "CQ CQ CQ DE {mycall} {mycall} K"},
    "f2": {"label": "Exch", "text": "{mycall} 599 001"},
    "f3": {"label": "TU",   "text": "TU {mycall} K"},
    "f4": {"label": "QSL",  "text": "QSL TU 73 DE {mycall} SK"},
    "f5": {"label": "AGN",  "text": "AGN? {theircall} DE {mycall}"},
    "f6": {"label": "QRZ?", "text": "QRZ? DE {mycall}"},
    "f7": {"label": "73",   "text": "73 DE {mycall} SK"},
    "f8": {"label": "Free", "text": ""},
}

_VAR_RE = re.compile(r"\{(\w+)\}")


class MacroManager:
    """Load, edit, and expand F-key macros from config."""

    def __init__(self, cfg: "Config"):
        self._cfg = cfg

    def get(self, key: str) -> dict:
        """Return macro dict for key 'f1'..'f8'. Falls back to default."""
        key = key.lower()
        saved_label = self._cfg.get(f"macros.{key}.label", None)
        saved_text  = self._cfg.get(f"macros.{key}.text",  None)
        default = DEFAULTS.get(key, {"label": key.upper(), "text": ""})
        return {
            "label": saved_label if saved_label is not None else default["label"],
            "text":  saved_text  if saved_text  is not None else default["text"],
        }

    def set(self, key: str, label: str, text: str) -> None:
        """Persist a macro."""
        key = key.lower()
        self._cfg.set(f"macros.{key}.label", label.strip())
        self._cfg.set(f"macros.{key}.text",  text)
        self._cfg.save()

    def expand(self, text: str, context: dict | None = None,
               auto_increment_serial: bool = False) -> str:
        """Substitute {vars} in text using context dict + config fallbacks.

        If auto_increment_serial is True and the text contains {serial},
        the serial counter is incremented in config after substitution.
        Pass True from TX send paths; False for previews.
        """
        ctx = self._build_context(context)
        serial_used = "{serial}" in text.lower() or "serial" in (context or {})

        def _sub(m: re.Match) -> str:
            var = m.group(1).lower()
            return str(ctx.get(var, m.group(0)))  # leave unknown vars as-is

        result = _VAR_RE.sub(_sub, text)
        if auto_increment_serial and serial_used:
            next_serial = int(ctx.get("serial", 1)) + 1
            self._cfg.set("session.serial", next_serial)
            self._cfg.save()
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_context(self, extra: dict | None) -> dict:
        from core.guest_op import operating_callsign
        ctx: dict = {
            "mycall":    operating_callsign(self._cfg),
            "theircall": self._cfg.get("session.dx_callsign", ""),
            "freq":      self._cfg.get("session.vfo_a_mhz", ""),
            "mode":      self._cfg.get("session.mode", ""),
            "name":      self._cfg.get("operator.name", ""),
            "serial":    str(self._cfg.get("session.serial", 1)),
        }
        if extra:
            ctx.update({k.lower(): v for k, v in extra.items()})
        return ctx

    def all_macros(self) -> list[tuple[str, dict]]:
        """Return [(key, macro_dict), ...] for f1..f8 in order."""
        return [(f"f{i}", self.get(f"f{i}")) for i in range(1, _NUM_MACROS + 1)]
