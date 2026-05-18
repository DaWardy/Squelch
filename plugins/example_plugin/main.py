from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations
# Example Squelch plugin
# Copy this folder, rename it, and modify main.py to create your own plugin.

import logging
from core.plugins import ApexPlugin

log = logging.getLogger(__name__)


class ExamplePlugin(ApexPlugin):
    """
    Example plugin demonstrating the Squelch plugin API.
    """
    NAME        = "Example Plugin"
    VERSION     = "1.0.0"
    DESCRIPTION = "Logs frequency changes and decodes to console"

    def on_load(self):
        try:
            freq = self.api.get_frequency() if self.api else 0
            log.info(
                f"Example plugin loaded. "
                f"Current frequency: "
                f"{freq / 1e6:.3f} MHz")
        except Exception:
            log.info("Example plugin loaded.")

    def on_frequency_change(self, freq_hz: int, band: str):
        log.debug(f"Frequency: {freq_hz / 1e6:.4f} MHz  Band: {band}")

    def on_decode(self, callsign: str, freq_hz: int,
                  mode: str, snr: int, message: str):
        log.info(f"Decoded: {callsign:12s} "
                 f"{freq_hz/1e6:.3f}MHz  "
                 f"{mode}  SNR={snr:+d}dB")

    def on_unload(self):
        log.info("Example plugin unloaded")
