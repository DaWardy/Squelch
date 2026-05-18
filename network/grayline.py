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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/grayline.py
Gray line (solar terminator) computation.
The gray line is the boundary between day and night.
Signals propagate exceptionally well along the gray line
because the ionosphere is in a transitional state.

No external dependencies — pure math using UTC time
and solar declination. Updates every 60 seconds.

Used by:
  - Local RF map overlay
  - Log map overlay
  - Band conditions tab (golden hour indicator)
"""

import math
import time
from datetime import datetime, timezone
from typing import NamedTuple


class SolarPosition(NamedTuple):
    """Solar position at a given UTC time."""
    declination_deg:  float   # solar declination (-23.5 to +23.5)
    equation_of_time: float   # minutes offset from mean solar time
    utc_timestamp:    float   # when computed


class GrayLineInfo(NamedTuple):
    """Gray line state for a given location and time."""
    is_day:           bool    # True if sun is up
    is_gray_line:     bool    # True if within gray line zone
    sun_elevation:    float   # degrees above/below horizon
    minutes_to_rise:  float   # minutes until next sunrise
    minutes_to_set:   float   # minutes until next sunset
    golden_hour:      bool    # within 30min of sunrise/sunset


# Gray line zone width — signals propagate well within this
GRAY_LINE_WIDTH_DEG = 6.0    # degrees either side of terminator


def solar_position(utc_dt: datetime = None) -> SolarPosition:
    """
    Compute solar declination and equation of time for UTC datetime.
    Uses Spencer's Fourier series approximation — accurate to ~0.01°.
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    # Day of year
    doy = utc_dt.timetuple().tm_yday
    B   = math.radians((360 / 365) * (doy - 81))

    # Solar declination (Spencer 1971)
    decl = 23.45 * math.sin(B)

    # Equation of time in minutes
    eot = (9.87 * math.sin(2 * B) -
           7.53 * math.cos(B) -
           1.5  * math.sin(B))

    return SolarPosition(
        declination_deg  = decl,
        equation_of_time = eot,
        utc_timestamp    = utc_dt.timestamp())


def sun_elevation(lat: float, lon: float,
                  utc_dt: datetime = None) -> float:
    """
    Compute sun elevation angle in degrees for lat/lon at UTC time.
    Positive = above horizon (day), negative = below (night).
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    sol = solar_position(utc_dt)
    decl_rad = math.radians(sol.declination_deg)

    # Local solar time
    utc_hours = (utc_dt.hour +
                 utc_dt.minute / 60 +
                 utc_dt.second / 3600)
    lst = utc_hours + lon / 15 + sol.equation_of_time / 60

    # Hour angle
    hour_angle = math.radians(15 * (lst - 12))

    lat_rad = math.radians(lat)

    # Solar elevation
    sin_elev = (math.sin(lat_rad) * math.sin(decl_rad) +
                math.cos(lat_rad) * math.cos(decl_rad) *
                math.cos(hour_angle))

    return math.degrees(math.asin(max(-1, min(1, sin_elev))))


def gray_line_info(lat: float, lon: float,
                   utc_dt: datetime = None) -> GrayLineInfo:
    """
    Get gray line state for a given location and time.
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    elev = sun_elevation(lat, lon, utc_dt)

    is_day      = elev > 0
    is_gray     = abs(elev) <= GRAY_LINE_WIDTH_DEG
    golden      = abs(elev) <= 30  # within 30° = golden hour zone

    # Estimate time to next sunrise/sunset
    # Simple scan — check every 5 minutes for next crossing
    mins_rise = _find_crossing(lat, lon, utc_dt, to_sunrise=True)
    mins_set  = _find_crossing(lat, lon, utc_dt, to_sunrise=False)

    return GrayLineInfo(
        is_day          = is_day,
        is_gray_line    = is_gray,
        sun_elevation   = round(elev, 2),
        minutes_to_rise = round(mins_rise, 1),
        minutes_to_set  = round(mins_set, 1),
        golden_hour     = golden and not is_day)


def _find_crossing(lat: float, lon: float,
                   utc_dt: datetime,
                   to_sunrise: bool,
                   max_hours: int = 24) -> float:
    """Find minutes until next sunrise or sunset."""
    from datetime import timedelta
    step_min = 5
    for i in range(1, max_hours * 60 // step_min):
        check = utc_dt + timedelta(minutes=i * step_min)
        elev  = sun_elevation(lat, lon, check)
        if to_sunrise and elev > 0:
            return i * step_min
        if not to_sunrise and elev <= 0:
            return i * step_min
    return max_hours * 60.0


def terminator_points(utc_dt: datetime = None,
                      steps: int = 180) -> list[tuple[float, float]]:
    """
    Generate lat/lon points along the solar terminator (gray line).
    Returns a list of (lat, lon) tuples forming the terminator path.
    Used by Leaflet to draw the gray line on the map.
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    sol = solar_position(utc_dt)
    decl_rad = math.radians(sol.declination_deg)

    # Subsolar point longitude
    utc_hours = (utc_dt.hour +
                 utc_dt.minute / 60 +
                 utc_dt.second / 3600)
    subsolar_lon = -15 * (utc_hours - 12 +
                          sol.equation_of_time / 60)
    subsolar_lon = ((subsolar_lon + 180) % 360) - 180

    # Terminator is 90° from the subsolar point
    # Generate points around the terminator circle
    points = []
    for i in range(steps + 1):
        angle = math.radians(i * 360 / steps)

        # Rotate from subsolar reference frame
        lat = math.degrees(
            math.asin(
                math.sin(decl_rad) * math.cos(math.pi / 2) +
                math.cos(decl_rad) * math.sin(math.pi / 2) *
                math.cos(angle)))
        dlon = math.atan2(
            math.sin(angle) * math.sin(math.pi / 2) *
            math.cos(decl_rad),
            math.cos(math.pi / 2) - math.sin(decl_rad) *
            math.sin(math.radians(lat)))
        lon = (subsolar_lon + math.degrees(dlon) + 180) % 360 - 180

        points.append((round(lat, 4), round(lon, 4)))

    return points


def day_night_geojson(utc_dt: datetime = None) -> dict:
    """
    Generate GeoJSON polygon for the night-side of the Earth.
    Pass to Leaflet as a layer for the gray line visualization.
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    pts = terminator_points(utc_dt)
    sol = solar_position(utc_dt)

    # Determine if north or south pole is in night
    north_in_night = sol.declination_deg > 0

    # Build polygon — terminator + pole
    if north_in_night:
        pole_lat = 90
    else:
        pole_lat = -90

    coordinates = [[lon, lat] for lat, lon in pts]
    # Close the polygon through the pole
    coordinates.append([180, pole_lat])
    coordinates.append([-180, pole_lat])
    coordinates.append(coordinates[0])

    return {
        "type": "Feature",
        "properties": {
            "description": "Night side",
            "declination": round(sol.declination_deg, 2),
            "computed_utc": utc_dt.strftime("%Y-%m-%d %H:%M UTC"),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates],
        }
    }


def format_gray_line_status(info: GrayLineInfo) -> str:
    """Human-readable gray line status for display."""
    if info.is_gray_line:
        if info.is_day:
            return (f"☀️ Gray line — sunset in "
                    f"{info.minutes_to_set:.0f} min  "
                    f"[excellent propagation]")
        else:
            return (f"🌅 Gray line — sunrise in "
                    f"{info.minutes_to_rise:.0f} min  "
                    f"[excellent propagation]")
    elif info.is_day:
        return (f"☀️ Daytime  "
                f"Sun: +{info.sun_elevation:.1f}°  "
                f"Sunset in {info.minutes_to_set:.0f} min")
    else:
        return (f"🌙 Nighttime  "
                f"Sun: {info.sun_elevation:.1f}°  "
                f"Sunrise in {info.minutes_to_rise:.0f} min")
