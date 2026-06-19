from __future__ import annotations
"""Path-specific HF band reliability helpers — no Qt dependency.

Used by BandConditionsTab and testable without a display.
"""

# HF bands shown in the reliability chart (name → nominal centre MHz)
CHART_BANDS: list[tuple[str, float]] = [
    ("160m",  1.900), ("80m",  3.750), ("60m",  5.357),
    ("40m",  7.150),  ("30m", 10.125), ("20m", 14.150),
    ("17m", 18.110),  ("15m", 21.250), ("12m", 24.940),
    ("10m", 28.300),
]


def band_reliability(freq_mhz: float, muf_mhz: float,
                     luf_mhz: float, path_km: float) -> tuple:
    """Return (reliability 0–1, status_str) for a band centre on a given path.

    Path-distance adjustments applied to MUF:
    - NVIS (<400 km): effective MUF capped to ~11 MHz (NVIS ceiling)
    - Multi-hop (>5000 km): effective MUF reduced by 15% (absorption penalty)
    - Otherwise: standard F2 MUF used as-is

    Reliability scale:
    - 0.0          → not viable (absorbed or above MUF)
    - 0.05–0.50    → marginal (between FOT and MUF)
    - 0.50–0.98    → good (below FOT, above LUF)
    """
    if muf_mhz <= 0:
        return 0.0, "No data"
    # Path-specific effective MUF
    if path_km < 400:
        eff_muf = min(muf_mhz, 11.0)    # NVIS ceiling
    elif path_km > 5000:
        eff_muf = muf_mhz * 0.85        # multi-hop absorption
    else:
        eff_muf = muf_mhz
    if freq_mhz < luf_mhz:
        return 0.0, "D-absorbed"
    if freq_mhz > eff_muf:
        return 0.0, "Above MUF"
    fot = 0.85 * eff_muf                # Frequency of Optimum Transmission
    if freq_mhz <= fot:
        span = max(fot - luf_mhz, 0.1)
        r = 0.50 + 0.48 * min(1.0, (freq_mhz - luf_mhz) / span)
        return round(min(0.98, r), 2), "Good"
    frac = (freq_mhz - fot) / max(eff_muf - fot, 0.1)
    return round(max(0.05, 0.70 * (1.0 - frac)), 2), "Marginal"
