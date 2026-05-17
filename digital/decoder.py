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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- digital/decoder.py
Digital voice decode bridge.
DSD+ (Windows) and OP25 (Linux) subprocess management.
Routes decoded audio from SDR/rig to output device.
Stub — implemented in Chunk 7 (v0.7.0).
"""
# DSD+ launched via subprocess
# OP25 launched via subprocess (Linux)
# Audio routing: SDR IQ → demodulate → DSD+/OP25 → speaker
# Signal types: P25 Phase 1/2, DMR, NXDN, YSF, D-STAR
