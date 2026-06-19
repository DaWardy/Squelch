from __future__ import annotations
"""Frequency formatting helpers.

All storage is in Hz (int).  Display units are user-configurable via
cfg key ``display.freq_units`` (default "MHz").

Supported units:  "MHz"  "kHz"  "Hz"
"""

_VALID_UNITS = ("MHz", "kHz", "Hz")


def _units(cfg) -> str:
    """Read display.freq_units from config, falling back to 'MHz'."""
    if cfg is None:
        return "MHz"
    try:
        u = (cfg.get("display.freq_units", "MHz") or "MHz").strip()
        return u if u in _VALID_UNITS else "MHz"
    except Exception:
        return "MHz"


def format_freq(hz: int, units: str = "MHz", *, precision: int | None = None) -> str:
    """Format a frequency in Hz to a human-readable string.

    Args:
        hz:        Frequency in Hz.
        units:     Display unit — "MHz", "kHz", or "Hz".
        precision: Decimal places; defaults to 3 for MHz, 1 for kHz, 0 for Hz.

    Returns:
        String like "14.074 MHz", "14074.0 kHz", or "14074000 Hz".
    """
    if units == "MHz":
        p = precision if precision is not None else 3
        return f"{hz / 1_000_000:.{p}f} MHz"
    elif units == "kHz":
        p = precision if precision is not None else 1
        return f"{hz / 1_000:.{p}f} kHz"
    else:  # Hz
        p = precision if precision is not None else 0
        return f"{hz:.{p}f} Hz"


def format_freq_cfg(hz: int, cfg) -> str:
    """Format a frequency using the user's configured display units."""
    return format_freq(hz, _units(cfg))


def parse_freq_input(text: str, units: str = "MHz") -> int:
    """Parse a user-entered frequency string to Hz.

    Handles bare numbers (interpreted as the configured unit) and
    suffixed values ("14.074 MHz", "14074 kHz", "14074000 Hz",
    "14074000", "14.074").

    Returns 0 on parse failure.
    """
    text = text.strip().replace(",", "").replace(" ", "")
    if not text:
        return 0
    try:
        # Strip unit suffix if present
        upper = text.upper()
        if upper.endswith("MHZ"):
            return int(float(text[:-3]) * 1_000_000)
        elif upper.endswith("KHZ"):
            return int(float(text[:-3]) * 1_000)
        elif upper.endswith("HZ"):
            return int(float(text[:-2]))
        # No suffix — interpret as configured unit
        val = float(text)
        if units == "MHz":
            # Heuristic: bare values < 1000 → MHz; >= 1 000 000 → Hz; else kHz
            if val < 1_000:
                return int(val * 1_000_000)
            elif val >= 1_000_000:
                return int(val)
            else:
                return int(val * 1_000)
        elif units == "kHz":
            if val >= 1_000_000:
                return int(val)
            return int(val * 1_000)
        else:  # Hz
            return int(val)
    except (ValueError, OverflowError):
        return 0


def freq_label(units: str = "MHz") -> str:
    """Return a short label string for the configured units, e.g. 'Freq (MHz)'."""
    return f"Freq ({units})"


def freq_placeholder(units: str = "MHz") -> str:
    """Return a suitable placeholder text for a frequency input field."""
    if units == "MHz":
        return "e.g. 14.074"
    elif units == "kHz":
        return "e.g. 14074.0"
    else:
        return "e.g. 14074000"
