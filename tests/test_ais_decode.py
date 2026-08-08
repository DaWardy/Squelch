# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/ais_decode — validated against published AIVDM sentences."""

from core.ais_decode import decode_ais_nmea, parse_ais_fields, _armored_to_bits


def test_type1_sf_bay():
    # !AIVDM,1,1,,A,15M67FC000G?ufbE`FepT@3n00Sa,0*5C  (published test vector)
    m = decode_ais_nmea("15M67FC000G?ufbE`FepT@3n00Sa", 0)
    assert m.type == 1 and m.valid
    assert m.mmsi == 366053209
    assert abs(m.lat - 37.8021) < 0.001
    assert abs(m.lon - (-122.3416)) < 0.001
    assert m.has_position


def test_type1_seattle():
    m = decode_ais_nmea("177KQJ5000G?tO`K>RA1wUbN0TKH", 0)
    assert m.type == 1 and m.mmsi == 477553000
    assert abs(m.lat - 47.5828) < 0.001
    assert abs(m.lon - (-122.3458)) < 0.001


def test_parse_fields_matches_nmea():
    bits = _armored_to_bits("15M67FC000G?ufbE`FepT@3n00Sa")
    m = parse_ais_fields(bits)
    assert m.mmsi == 366053209


def test_short_payload_safe():
    m = decode_ais_nmea("15M", 0)
    assert m.valid is False and "short" in m.note


def test_garbage_never_raises():
    assert decode_ais_nmea("", 0).valid is False
    assert decode_ais_nmea("!!!!", 0).type in range(64)
