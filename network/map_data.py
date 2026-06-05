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
Squelch -- network/map_data.py
Aggregates all map data for the Leaflet map view:
  - Station location marker
  - QSO log great circle paths
  - Gray line terminator
  - APRS stations
  - ADS-B aircraft (from dump1090)
  - Repeaters from Local RF tab

Generates self-contained HTML with embedded Leaflet.
QWebEngineView renders it inside Squelch.
"""

import json
import logging
from core.constants import PORT_DUMP1090_HTTP
import time
from datetime import datetime, timezone

from network.grayline import (
    day_night_geojson, gray_line_info,
    format_gray_line_status, sun_elevation)
from core.location import (
    _grid_to_latlon, _valid_grid,
    qso_to_map_points)

log = logging.getLogger(__name__)

# Leaflet CDN — offline fallback uses bundled version if available
LEAFLET_CSS = (
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css")
LEAFLET_JS  = (
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js")


def _station_location(config) -> tuple[str, float, float, str]:
    """Return (grid, lat, lon, callsign) from config, resolving grid→coords if needed."""
    grid    = config.get("location.grid", "") or config.grid or ""
    my_lat  = float(config.get("location.lat", 0.0) or 0.0)
    my_lon  = float(config.get("location.lon", 0.0) or 0.0)
    my_call = config.callsign or "Station"
    if not (my_lat or my_lon) and _valid_grid(grid):
        try:
            my_lat, my_lon = _grid_to_latlon(grid)
        except Exception:
            pass
    return grid, my_lat, my_lon, my_call


def _grayline_data(now_utc, my_lat: float, my_lon: float,
                   show: bool) -> tuple[str, str]:
    """Return (grayline_json, grayline_status) strings."""
    if not show:
        return "null", ""
    try:
        gl = day_night_geojson(now_utc)
        gj = json.dumps(gl)
        status = ""
        if my_lat or my_lon:
            status = format_gray_line_status(
                gray_line_info(my_lat, my_lon, now_utc))
        return gj, status
    except Exception as e:
        log.debug(f"Gray line: {e}")
        return "null", ""


def _qso_path_data(log_db, show: bool) -> list[dict]:
    """Return list of QSO path dicts for map rendering."""
    if not (show and log_db):
        return []
    paths = []
    try:
        for q in log_db.recent_qsos(limit=200):
            my_pt, their_pt = qso_to_map_points(q)
            if my_pt and their_pt:
                paths.append({
                    "from":    [my_pt["lat"], my_pt["lon"]],
                    "to":      [their_pt["lat"], their_pt["lon"]],
                    "call":    q.call,   "band": q.band,
                    "mode":    q.mode,   "time": q.datetime_on[:16],
                    "my_grid": q.my_grid, "grid": q.grid,
                })
    except Exception as e:
        log.debug(f"QSO paths: {e}")
    return paths


def _repeater_marker_data(repeaters) -> list[dict]:
    """Return list of repeater marker dicts for map rendering."""
    if not repeaters:
        return []
    return [{"lat": r.lat, "lon": r.lon, "call": r.callsign,
             "freq": r.output_str, "tone": r.tone_str,
             "mode": r.mode, "city": r.city, "dist_km": r.distance_km}
            for r in repeaters[:50]]


def _grid_square_data(grid: str, my_lat: float, my_lon: float) -> list[dict]:
    """Return list of grid square overlay dicts for map rendering."""
    if not (_valid_grid(grid) and my_lat and my_lon):
        return []
    squares = []
    try:
        g4_lat, g4_lon = _grid_to_latlon(grid[:4])
        squares.append({"label": grid[:4], "lat": g4_lat, "lon": g4_lon,
                         "size": "4char", "dlat": 1.0, "dlon": 2.0})
    except Exception:
        pass
    if len(grid) >= 6:
        try:
            g6_lat, g6_lon = _grid_to_latlon(grid)
            squares.append({"label": grid[:6], "lat": g6_lat, "lon": g6_lon,
                             "size": "6char", "dlat": 1/24, "dlon": 2/24})
        except Exception:
            pass
    return squares


def build_map_html(config,
                   log_db=None,
                   repeaters=None,
                   aprs_stations=None,
                   show_grayline: bool = True,
                   show_qso_paths: bool = True,
                   show_adsb: bool = True,
                   show_aprs: bool = True,
                   center_on_station: bool = True,
                   heard_stations: dict | None = None,
                   hearing_me: dict | None = None,
                   ) -> str:
    """Build self-contained Leaflet map HTML for QWebEngineView."""
    now_utc = datetime.now(timezone.utc)

    grid, my_lat, my_lon, my_call = _station_location(config)
    grayline_json, grayline_status = _grayline_data(
        now_utc, my_lat, my_lon, show_grayline)

    center = [my_lat, my_lon] if (center_on_station and (my_lat or my_lon)) else [20, 0]
    zoom   = 6 if (center_on_station and (my_lat or my_lon)) else 2

    return _render_html(
        center          = center,
        zoom            = zoom,
        my_lat          = my_lat,
        my_lon          = my_lon,
        my_call         = my_call,
        my_grid         = grid,
        grayline_json   = grayline_json,
        grayline_status = grayline_status,
        qso_paths       = _qso_path_data(log_db, show_qso_paths),
        aprs_stations   = aprs_stations or [],
        aircraft        = _fetch_adsb() if show_adsb else [],
        repeaters       = _repeater_marker_data(repeaters),
        grid_squares    = _grid_square_data(grid, my_lat, my_lon),
        utc_str         = now_utc.strftime("%H:%M UTC"),
        heard_stations  = _resolve_station_coords(heard_stations or {}),
        hearing_me      = _resolve_station_coords(hearing_me or {}),
    )


def _resolve_station_coords(stations: dict) -> list[dict]:
    """Resolve grid squares to lat/lon for stations missing coordinates.
    Returns a list of dicts with lat/lon guaranteed non-zero (skips failures).
    """
    out = []
    for sta in stations.values():
        lat = sta.get("lat", 0.0)
        lon = sta.get("lon", 0.0)
        if not (lat or lon):
            grid = sta.get("grid", "")
            if not grid:
                continue
            try:
                lat, lon = _grid_to_latlon(grid.upper())
            except Exception:
                continue
        if lat or lon:
            out.append({**sta, "lat": lat, "lon": lon})
    return out


def _fetch_adsb() -> list[dict]:
    """Fetch aircraft from dump1090-fa JSON feed."""
    try:
        import urllib.request
        with urllib.request.urlopen(   # nosec B310
                f"http://localhost:{PORT_DUMP1090_HTTP}/data/aircraft.json",
                timeout=1) as resp:
            data = json.loads(resp.read(500_000))
            aircraft = []
            for a in data.get("aircraft", [])[:100]:
                if "lat" not in a or "lon" not in a:
                    continue
                aircraft.append({
                    "lat":    float(a["lat"]),
                    "lon":    float(a["lon"]),
                    "icao":   str(a.get("hex", ""))[:6],
                    "flight": str(a.get("flight",
                               "")).strip()[:8],
                    "alt":    int(a.get("alt_baro", 0)),
                    "speed":  int(a.get("gs", 0)),
                    "track":  int(a.get("track", 0)),
                })
            return aircraft
    except Exception:
        return []


def _render_html(**ctx) -> str:
    """Render the Leaflet map HTML."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Squelch Map</title>
<link rel="stylesheet" href="{LEAFLET_CSS}">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body,#map {{ width:100%; height:100%; }}
  body {{ background:#0a0a0a; }}
  .gl-status {{
    position:absolute; bottom:10px; left:50%;
    transform:translateX(-50%);
    background:rgba(0,0,0,0.75);
    color:#3fbe6f; font-size:12px;
    padding:6px 14px; border-radius:4px;
    border:1px solid #3fbe6f; z-index:1000;
    font-family:'Courier New',monospace;
  }}
  .qso-popup {{
    font-family:'Courier New',monospace;
    font-size:11px; color:#aaa;
  }}
  .qso-popup b {{ color:#3fbe6f; }}
  .grid-label {{
    background:transparent; border:none;
    color:#3fbe6f; font-size:10px;
    font-family:'Courier New',monospace;
    text-shadow: 1px 1px 2px #000;
  }}
</style>
</head>
<body>
<div id="map"></div>
{"<div class='gl-status'>" + ctx['grayline_status'] + "</div>" if ctx['grayline_status'] else ""}
<script src="{LEAFLET_JS}"></script>
<script>
// ── Data ────────────────────────────────────────────────────
var MY_LAT     = {ctx['my_lat']};
var MY_LON     = {ctx['my_lon']};
var MY_CALL    = {json.dumps(ctx['my_call'])};
var MY_GRID    = {json.dumps(ctx['my_grid'])};
var UTC_STR    = {json.dumps(ctx['utc_str'])};
var QSO_PATHS  = {json.dumps(ctx['qso_paths'])};
var APRS       = {json.dumps(ctx['aprs_stations'])};
var AIRCRAFT   = {json.dumps(ctx['aircraft'])};
var REPEATERS  = {json.dumps(ctx['repeaters'])};
var GRIDS      = {json.dumps(ctx['grid_squares'])};
var GRAYLINE   = {ctx['grayline_json']};
var HEARD      = {json.dumps(ctx['heard_stations'])};
var HEARING_ME = {json.dumps(ctx['hearing_me'])};

// ── Map init ─────────────────────────────────────────────────
var map = L.map('map', {{
  center: {json.dumps(ctx['center'])},
  zoom: {ctx['zoom']},
  zoomControl: true,
}});

// Dark tile layer
L.tileLayer(
  'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{attribution: '© OpenStreetMap © CARTO',
    maxZoom: 19, subdomains:'abcd'}}
).addTo(map);

// ── Gray line ─────────────────────────────────────────────────
if (GRAYLINE) {{
  L.geoJSON(GRAYLINE, {{
    style: {{
      fillColor: '#000033',
      fillOpacity: 0.45,
      color: '#3355aa',
      weight: 1.5,
      opacity: 0.8,
    }}
  }}).addTo(map);
}}

// ── Station marker ────────────────────────────────────────────
if (MY_LAT || MY_LON) {{
  var stIcon = L.divIcon({{
    html: '<div style="background:#3fbe6f;width:12px;height:12px;'
         +'border-radius:50%;border:2px solid #fff;'
         +'box-shadow:0 0 8px #3fbe6f;"></div>',
    className: '', iconSize:[12,12], iconAnchor:[6,6]
  }});
  L.marker([MY_LAT, MY_LON], {{icon:stIcon}})
    .bindPopup('<b style="color:#3fbe6f">' + MY_CALL + '</b><br>'
               + MY_GRID + '<br>' + UTC_STR)
    .addTo(map);
}}

// ── Grid square overlays ──────────────────────────────────────
GRIDS.forEach(function(g) {{
  var color = g.size === '4char' ? '#3fbe6f' : '#44aaff';
  var opacity = g.size === '4char' ? 0.3 : 0.5;
  var bounds = [
    [g.lat - g.dlat/2, g.lon - g.dlon/2],
    [g.lat + g.dlat/2, g.lon + g.dlon/2]
  ];
  L.rectangle(bounds, {{
    color: color, weight: 1,
    fillOpacity: 0.05, opacity: opacity
  }}).addTo(map);
  L.marker([g.lat, g.lon], {{
    icon: L.divIcon({{
      html: '<span class="grid-label">' + g.label + '</span>',
      className:'', iconSize:[60,16], iconAnchor:[30,8]
    }})
  }}).addTo(map);
}});

// ── QSO paths ─────────────────────────────────────────────────
var modeColors = {{
  FT8:'#44aaff', FT4:'#44aaff', WSPR:'#8844ff',
  SSB:'#3fbe6f', CW:'#ffaa22', DMR:'#ff6644',
  DEFAULT:'#558855'
}};
QSO_PATHS.forEach(function(q) {{
  var col = modeColors[q.mode] || modeColors.DEFAULT;
  var line = L.polyline([q.from, q.to], {{
    color: col, weight: 1, opacity: 0.5,
    dashArray: '4 4'
  }}).addTo(map);
  line.bindPopup(
    '<div class="qso-popup">'
    +'<b>'+q.call+'</b> via '+q.mode+'<br>'
    +q.band+'  '+q.grid+'<br>'
    +q.time
    +'</div>');
  // DX marker
  var dxIcon = L.divIcon({{
    html: '<div style="background:' + col
         +';width:6px;height:6px;border-radius:50%;'
         +'border:1px solid #fff;opacity:0.8;"></div>',
    className:'', iconSize:[6,6], iconAnchor:[3,3]
  }});
  L.marker(q.to, {{icon:dxIcon}})
    .bindPopup('<div class="qso-popup"><b>'+q.call+'</b><br>'
              +q.grid+'<br>'+q.mode+'  '+q.band+'</div>')
    .addTo(map);
}});

// ── Repeaters ─────────────────────────────────────────────────
REPEATERS.forEach(function(r) {{
  var modeColor = r.mode==='DMR'?'#44aaff':
                  r.mode==='P25'?'#ffaa22':'#3fbe6f';
  var repIcon = L.divIcon({{
    html: '<div style="background:' + modeColor
         +';width:8px;height:8px;'
         +'border:1px solid #fff;opacity:0.9;'
         +'transform:rotate(45deg);"></div>',
    className:'', iconSize:[8,8], iconAnchor:[4,4]
  }});
  L.marker([r.lat, r.lon], {{icon:repIcon}})
    .bindPopup('<div class="qso-popup">'
      +'<b>'+r.call+'</b><br>'
      +r.freq+' MHz  '+r.mode+'<br>'
      +(r.tone?r.tone+'<br>':'')
      +r.city+'  ('+r.dist_km.toFixed(1)+' km)'
      +'</div>')
    .addTo(map);
}});

// ── APRS stations ─────────────────────────────────────────────
APRS.forEach(function(a) {{
  L.circleMarker([a.lat, a.lon], {{
    radius:5, color:'#ff8844', fillColor:'#ff8844',
    fillOpacity:0.7, weight:1
  }}).bindPopup('<div class="qso-popup"><b>'+a.call+'</b><br>'
    +a.comment+'</div>').addTo(map);
}});

// ── ADS-B aircraft ────────────────────────────────────────────
AIRCRAFT.forEach(function(a) {{
  var icon = L.divIcon({{
    html: '<div style="color:#aaaaff;font-size:16px;'
         +'transform:rotate('+a.track+'deg);'
         +'text-shadow:0 0 3px #000;">✈</div>',
    className:'', iconSize:[16,16], iconAnchor:[8,8]
  }});
  L.marker([a.lat, a.lon], {{icon:icon}})
    .bindPopup('<div class="qso-popup">'
      +(a.flight||a.icao)+'<br>'
      +'Alt: '+a.alt.toLocaleString()+' ft<br>'
      +'Speed: '+a.speed+' kts'
      +'</div>')
    .addTo(map);
}});

// ── Heard stations (FT8/FT4/decode) — green dots ─────────────
HEARD.forEach(function(s) {{
  var icon = L.divIcon({{
    html: '<div style="background:#3fbe6f;width:8px;height:8px;'
         +'border-radius:50%;border:1px solid #fff;opacity:0.85;"></div>',
    className:'', iconSize:[8,8], iconAnchor:[4,4]
  }});
  L.marker([s.lat, s.lon], {{icon:icon}})
    .bindPopup('<div class="qso-popup">'
      +'<b style="color:#3fbe6f">'+s.callsign+'</b><br>'
      +(s.grid||'')+'<br>'
      +(s.freq_mhz?(s.freq_mhz.toFixed(4)+' MHz  '):'')
      +(s.source||'decode')
      +(s.snr_db?'<br>SNR '+s.snr_db+' dB':'')
      +'</div>')
    .addTo(map);
}});

// ── PSKReporter — stations that heard us — orange triangles ───
HEARING_ME.forEach(function(s) {{
  var icon = L.divIcon({{
    html: '<div style="width:0;height:0;'
         +'border-left:6px solid transparent;'
         +'border-right:6px solid transparent;'
         +'border-bottom:11px solid #ff8800;'
         +'opacity:0.9;"></div>',
    className:'', iconSize:[12,11], iconAnchor:[6,11]
  }});
  var freq_mhz = s.freq_hz ? (s.freq_hz/1e6).toFixed(4)+' MHz' : '';
  L.marker([s.lat, s.lon], {{icon:icon}})
    .bindPopup('<div class="qso-popup">'
      +'<b style="color:#ff8800">'+s.callsign+'</b> heard us<br>'
      +(s.grid||'')+'<br>'
      +(freq_mhz?freq_mhz+'  ':'')+(s.mode||'')
      +(s.snr?'<br>SNR '+s.snr+' dB':'')
      +'</div>')
    .addTo(map);
}});
</script>
</body>
</html>"""
