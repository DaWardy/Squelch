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
import html
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

# Canonical map overlay layers. The in-map Leaflet layer control is the single
# source of truth for layer visibility (the redundant Qt toolbar checkboxes
# were removed). This dict gives the default on/off state; MapTab persists the
# user's choices across sessions and passes the live dict in as visible_layers.
# Keys are the JS layer keys; values are the default visibility.
DEFAULT_LAYER_VISIBLE = {
    "grayline":    True,
    "mygrid":      True,
    "workedgrids": True,
    "qsopaths":    True,
    "heard":       True,
    "pskreporter": True,
    "aprs":        True,
    "winlink":     True,
    "repeaters":   False,   # off by default — can clutter when many loaded
    "aircraft":    True,
    "satellites":  True,
    "wspr":        True,
    "dxspots":     True,
}

# Maps the Leaflet layer-control display name to its JS key, used by the
# overlayadd/overlayremove handlers that persist toggles back to Qt.
_LAYER_NAME_TO_KEY = {
    "Gray Line":      "grayline",
    "My Grid":        "mygrid",
    "Worked Grids":   "workedgrids",
    "QSO Paths":      "qsopaths",
    "Heard (decode)": "heard",
    "PSKReporter":    "pskreporter",
    "APRS":           "aprs",
    "Winlink RMS":    "winlink",
    "Repeaters":      "repeaters",
    "Aircraft":       "aircraft",
    "Satellites":     "satellites",
    "WSPR spots":     "wspr",
    "DX Spots":       "dxspots",
}


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
        for q in log_db.recent_qsos(limit=1000):
            my_pt, their_pt = qso_to_map_points(q)
            if my_pt and their_pt:
                paths.append({
                    "from":    [my_pt["lat"], my_pt["lon"]],
                    "to":      [their_pt["lat"], their_pt["lon"]],
                    "call":    q.call,   "band": q.band,
                    "mode":    q.mode,   "time": q.datetime_on[:16],
                    "my_grid": q.my_grid, "grid": q.grid,
                    "dist_km": round(
                        getattr(q, "dist_km", 0.0) or 0.0),
                    "lotw":    getattr(q, "lotw_status", "") or "",
                })
    except Exception as e:
        log.debug(f"QSO paths: {e}")
    return paths


def _worked_grids_data(log_db) -> list[dict]:
    """Return all distinct 4-char grid squares worked, with coords."""
    if not log_db:
        return []
    grids: dict[str, dict] = {}
    try:
        for q in log_db.recent_qsos(limit=99999):
            g = (q.grid or "").strip()
            if len(g) >= 4:
                g4 = g[:4].upper()
                if g4 not in grids:
                    try:
                        lat, lon = _grid_to_latlon(g4)
                        grids[g4] = {"grid": g4, "lat": lat, "lon": lon}
                    except Exception:
                        pass
    except Exception as e:
        log.debug(f"Worked grids: {e}")
    return list(grids.values())


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
                   winlink_gateways: list | None = None,
                   satellites: list | None = None,
                   wspr_spots: list | None = None,
                   dx_spots: list | None = None,
                   show_aprs_labels: bool = False,
                   visible_layers: dict | None = None,
                   ) -> str:
    """Build self-contained Leaflet map HTML for QWebEngineView.

    visible_layers maps JS layer keys to their on/off state; the in-map Leaflet
    layer control toggles them and persists choices via the squelch:// bridge.
    Missing keys fall back to DEFAULT_LAYER_VISIBLE.
    """
    vis = dict(DEFAULT_LAYER_VISIBLE)
    if isinstance(visible_layers, dict):
        vis.update({k: bool(v) for k, v in visible_layers.items()
                    if k in DEFAULT_LAYER_VISIBLE})
    now_utc = datetime.now(timezone.utc)

    grid, my_lat, my_lon, my_call = _station_location(config)
    grayline_json, grayline_status = _grayline_data(
        now_utc, my_lat, my_lon, show_grayline)

    center = [my_lat, my_lon] if (center_on_station and (my_lat or my_lon)) else [20, 0]
    zoom   = 6 if (center_on_station and (my_lat or my_lon)) else 2

    return _render_html(
        center              = center,
        zoom                = zoom,
        my_lat              = my_lat,
        my_lon              = my_lon,
        my_call             = my_call,
        my_grid             = grid,
        grayline_json       = grayline_json,
        grayline_status     = grayline_status,
        qso_paths           = _qso_path_data(log_db, show_qso_paths),
        aprs_stations       = aprs_stations or [],
        aircraft            = _fetch_adsb() if show_adsb else [],
        repeaters           = _repeater_marker_data(repeaters),
        grid_squares        = _grid_square_data(grid, my_lat, my_lon),
        worked_grids        = _worked_grids_data(log_db),
        utc_str             = now_utc.strftime("%H:%M UTC"),
        heard_stations      = _resolve_station_coords(heard_stations or {}),
        hearing_me          = _resolve_station_coords(hearing_me or {}),
        winlink_gateways    = _winlink_gateway_data(winlink_gateways),
        satellites          = satellites or [],
        wspr_spots          = wspr_spots or [],
        dx_spots            = _resolve_dx_spot_locs(dx_spots or []),
        show_aprs_labels    = bool(show_aprs_labels),
        visible_layers      = vis,
    )


def _resolve_dx_spot_locs(spots: list) -> list[dict]:
    """Add lat/lon to DX spots using CTY.DAT; drops spots without location."""
    if not spots:
        return []
    try:
        from network.cty_data import get_cty
        cty = get_cty()
    except Exception:
        return []
    out = []
    for s in spots[:200]:  # cap to avoid oversized HTML
        call = s.get("callsign", "")
        try:
            ent = cty.lookup(call) if cty else None
        except Exception:
            ent = None
        if not ent or not (ent.lat or ent.lon):
            continue
        out.append({
            "callsign": call,
            "lat":      ent.lat,
            "lon":      ent.lon,
            "band":     s.get("band", ""),
            "freq_mhz": s.get("freq_hz", 0) / 1e6,
            "mode":     s.get("mode", ""),
            "snr":      s.get("snr", 0),
            "country":  ent.name,
            "age_min":  s.get("age_min", 0),
        })
    return out


def _winlink_gateway_data(gateways: list | None) -> list[dict]:
    """Return slim dicts for Winlink gateway map markers."""
    if not gateways:
        return []
    return [
        {"callsign": g.get("callsign", ""),
         "lat":      g.get("lat", 0.0),
         "lon":      g.get("lon", 0.0),
         "freq":     g.get("frequency", "—"),
         "mode":     g.get("mode", ""),
         "dist":     g.get("distance", "—"),
         "grid":     g.get("grid", "")}
        for g in gateways
        if g.get("lat") and g.get("lon")
    ]


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


# ctx keys whose string values are concatenated into popup/label HTML by the
# Leaflet JS. Their values can originate from untrusted RF/network input (APRS
# comments, DX-cluster callsigns, etc.), so every string inside them is
# HTML-escaped before embedding to prevent script/markup injection (XSS) in the
# QWebEngine view. NOTE: deliberately excludes pre-serialized fields such as
# 'grayline_json' (raw JSON) and numeric fields (my_lat/my_lon).
_HTML_DATA_KEYS = frozenset({
    "my_call", "my_grid", "grayline_status", "utc_str",
    "qso_paths", "aprs_stations", "aircraft", "repeaters",
    "grid_squares", "worked_grids", "heard_stations", "hearing_me",
    "winlink_gateways", "satellites", "wspr_spots", "dx_spots",
})


def _esc_deep(obj):
    """Recursively HTML-escape every string in a JSON-able structure."""
    if isinstance(obj, str):
        return html.escape(obj, quote=True)
    if isinstance(obj, list):
        return [_esc_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _esc_deep(v) for k, v in obj.items()}
    return obj


def _render_html(**ctx) -> str:
    """Render the Leaflet map HTML with layer groups and layer control."""
    # Harden against XSS: escape untrusted RF/network strings that the JS
    # concatenates into popup HTML. Numbers and pre-serialized JSON untouched.
    for _k in _HTML_DATA_KEYS:
        if _k in ctx:
            ctx[_k] = _esc_deep(ctx[_k])
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
    font-size:11px; color:#aaa; min-width:130px;
  }}
  .qso-popup b {{ color:#3fbe6f; }}
  .aprs-label {{
    background: transparent; border: none; box-shadow: none;
    color: #ff9966; font-size: 10px; font-family: 'Courier New', monospace;
    white-space: nowrap; text-shadow: 0 0 3px #000, 0 0 3px #000;
    padding: 0;
  }}
  .qso-popup .lotw {{ color:#3fbe6f; }}
  .grid-label {{
    background:transparent; border:none;
    color:#3fbe6f; font-size:10px;
    font-family:'Courier New',monospace;
    text-shadow: 1px 1px 2px #000;
  }}
  .leaflet-control-layers {{
    background:rgba(15,15,15,0.92) !important;
    border:1px solid #333 !important;
    color:#ccc !important;
    font-family:'Courier New',monospace;
    font-size:11px;
  }}
  .leaflet-control-layers label {{ color:#ccc !important; }}
  .leaflet-control-layers-base,
  .leaflet-control-layers-overlays {{ color:#aaa !important; }}
  .leaflet-control-layers-separator {{
    border-top-color:#333 !important;
  }}
  .ruler-btn {{
    font-size:15px; text-align:center;
    line-height:26px; text-decoration:none;
  }}
  .map-legend {{
    background:rgba(10,10,10,0.85);
    border:1px solid #333; border-radius:5px;
    padding:8px 10px; font-size:11px;
    color:#ccc; font-family:'Courier New',monospace;
    line-height:1.7;
  }}
  .map-legend b {{ color:#aaa; font-size:10px; letter-spacing:1px; }}
  .leg-dot {{
    display:inline-block; width:9px; height:9px;
    border-radius:50%; border:1px solid #fff;
    vertical-align:middle; margin-right:5px;
  }}
  .leg-tri-up {{
    display:inline-block; width:0; height:0;
    border-left:5px solid transparent;
    border-right:5px solid transparent;
    vertical-align:middle; margin-right:5px;
  }}
  .leg-sq {{
    display:inline-block; width:8px; height:8px;
    transform:rotate(45deg);
    vertical-align:middle; margin-right:5px;
  }}
</style>
</head>
<body>
<div id="map"></div>
{"<div class='gl-status'>" + ctx['grayline_status'] + "</div>" if ctx['grayline_status'] else ""}
<script src="{LEAFLET_JS}"></script>
<script>
// ── Data ────────────────────────────────────────────────────
var MY_LAT       = {ctx['my_lat']};
var MY_LON       = {ctx['my_lon']};
var MY_CALL      = {json.dumps(ctx['my_call'])};
var MY_GRID      = {json.dumps(ctx['my_grid'])};
var UTC_STR      = {json.dumps(ctx['utc_str'])};
var QSO_PATHS    = {json.dumps(ctx['qso_paths'])};
var APRS         = {json.dumps(ctx['aprs_stations'])};
var AIRCRAFT     = {json.dumps(ctx['aircraft'])};
var REPEATERS    = {json.dumps(ctx['repeaters'])};
var GRIDS        = {json.dumps(ctx['grid_squares'])};
var WORKED_GRIDS = {json.dumps(ctx['worked_grids'])};
var GRAYLINE     = {ctx['grayline_json']};
var HEARD        = {json.dumps(ctx['heard_stations'])};
var HEARING_ME   = {json.dumps(ctx['hearing_me'])};
var WINLINK_GW   = {json.dumps(ctx['winlink_gateways'])};
var SATELLITES   = {json.dumps(ctx['satellites'])};
var WSPR_SPOTS   = {json.dumps(ctx['wspr_spots'])};
var DX_SPOTS     = {json.dumps(ctx['dx_spots'])};
var SHOW_APRS_LABELS = {'true' if ctx.get('show_aprs_labels') else 'false'};
var LAYER_VISIBLE = {json.dumps(ctx['visible_layers'])};
function _vis(k) {{ return LAYER_VISIBLE[k] !== false; }}

// ── Map init ─────────────────────────────────────────────────
var map = L.map('map', {{
  center: {json.dumps(ctx['center'])},
  zoom: {ctx['zoom']},
  zoomControl: true,
}});

// Base layers
var darkTiles = L.tileLayer(
  'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{attribution:'© OpenStreetMap © CARTO', maxZoom:19, subdomains:'abcd'}}
);
var streetTiles = L.tileLayer(
  'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution:'© OpenStreetMap contributors', maxZoom:19}}
);
darkTiles.addTo(map);

// Embedded-view fix + diagnostics for the "black map" case: force a size
// recalc after layout so Leaflet actually requests tiles, and surface tile
// load failures visibly (a black map is usually GPU compositing failing —
// mitigated by the --disable-gpu launch flag — or the tile CDN being blocked).
setTimeout(function() {{ try {{ map.invalidateSize(true); }} catch(e) {{}} }}, 300);
var _tileErrs = 0;
darkTiles.on('tileerror', function(e) {{
  _tileErrs++;
  if (_tileErrs === 3) {{
    var d = document.createElement('div');
    d.style.cssText = 'position:absolute;top:8px;left:50%;'
      + 'transform:translateX(-50%);z-index:9999;background:#3a1a1a;'
      + 'color:#ff8888;border:1px solid #cc4444;border-radius:4px;'
      + 'padding:6px 12px;font:12px monospace;';
    d.textContent = 'Map tiles failed to load — check network / tile-CDN access.';
    document.body.appendChild(d);
  }}
}});

// ── Layer groups ─────────────────────────────────────────────
// Each group is created, then added to the map only if its persisted
// visibility (LAYER_VISIBLE) is on. The Leaflet layer control toggles them
// after load; toggles are persisted back to Qt via the overlay handlers below.
var lyrGrayline    = L.layerGroup(); if (_vis('grayline'))    lyrGrayline.addTo(map);
var lyrWorkedGrids = L.layerGroup(); if (_vis('workedgrids')) lyrWorkedGrids.addTo(map);
var lyrMyGrid      = L.layerGroup(); if (_vis('mygrid'))      lyrMyGrid.addTo(map);
var lyrQsoPaths    = L.layerGroup(); if (_vis('qsopaths'))    lyrQsoPaths.addTo(map);
var lyrRepeaters   = L.layerGroup(); if (_vis('repeaters'))   lyrRepeaters.addTo(map);
var lyrAprs        = L.layerGroup(); if (_vis('aprs'))        lyrAprs.addTo(map);
var lyrAircraft    = L.layerGroup(); if (_vis('aircraft'))    lyrAircraft.addTo(map);
var lyrHeard       = L.layerGroup(); if (_vis('heard'))       lyrHeard.addTo(map);
var lyrHearingMe   = L.layerGroup(); if (_vis('pskreporter')) lyrHearingMe.addTo(map);
var lyrWinlink     = L.layerGroup(); if (_vis('winlink'))     lyrWinlink.addTo(map);
var lyrSatellites  = L.layerGroup(); if (_vis('satellites'))  lyrSatellites.addTo(map);
var lyrWspr        = L.layerGroup(); if (_vis('wspr'))        lyrWspr.addTo(map);
var lyrDxSpots     = L.layerGroup(); if (_vis('dxspots'))     lyrDxSpots.addTo(map);

// ── Gray line ─────────────────────────────────────────────────
if (GRAYLINE) {{
  L.geoJSON(GRAYLINE, {{
    style: {{fillColor:'#000033', fillOpacity:0.45,
             color:'#3355aa', weight:1.5, opacity:0.8}}
  }}).addTo(lyrGrayline);
}}

// ── Station marker ────────────────────────────────────────────
if (MY_LAT || MY_LON) {{
  var stIcon = L.divIcon({{
    html: '<div style="background:#3fbe6f;width:12px;height:12px;'
         +'border-radius:50%;border:2px solid #fff;'
         +'box-shadow:0 0 8px #3fbe6f;"></div>',
    className:'', iconSize:[12,12], iconAnchor:[6,6]
  }});
  L.marker([MY_LAT, MY_LON], {{icon:stIcon}})
    .bindPopup('<b style="color:#3fbe6f">' + MY_CALL + '</b><br>'
               + MY_GRID + '<br>' + UTC_STR)
    .addTo(lyrMyGrid);
}}

// ── Station grid square overlays ─────────────────────────────
GRIDS.forEach(function(g) {{
  var color = g.size === '4char' ? '#3fbe6f' : '#44aaff';
  var opacity = g.size === '4char' ? 0.3 : 0.5;
  var bounds = [
    [g.lat - g.dlat/2, g.lon - g.dlon/2],
    [g.lat + g.dlat/2, g.lon + g.dlon/2]
  ];
  L.rectangle(bounds, {{
    color:color, weight:1, fillOpacity:0.05, opacity:opacity
  }}).addTo(lyrMyGrid);
  L.marker([g.lat, g.lon], {{
    icon: L.divIcon({{
      html:'<span class="grid-label">'+g.label+'</span>',
      className:'', iconSize:[60,16], iconAnchor:[30,8]
    }})
  }}).addTo(lyrMyGrid);
}});

// ── Worked grids (all log contacts with a grid) ───────────────
WORKED_GRIDS.forEach(function(g) {{
  var bounds = [
    [g.lat - 0.5, g.lon - 1.0],
    [g.lat + 0.5, g.lon + 1.0]
  ];
  L.rectangle(bounds, {{
    color:'#44aaff', weight:0.5,
    fillColor:'#44aaff', fillOpacity:0.10, opacity:0.4
  }}).bindPopup(
    '<div class="qso-popup"><b style="color:#44aaff">'
    +g.grid+'</b> worked</div>'
  ).addTo(lyrWorkedGrids);
}});

// ── QSO paths ─────────────────────────────────────────────────
var modeColors = {{
  FT8:'#44aaff', FT4:'#44aaff', WSPR:'#8844ff',
  SSB:'#3fbe6f', CW:'#ffaa22', DMR:'#ff6644',
  DEFAULT:'#558855'
}};
QSO_PATHS.forEach(function(q) {{
  var col = modeColors[q.mode] || modeColors.DEFAULT;
  var dist_str = q.dist_km > 0
    ? '<br>' + q.dist_km.toLocaleString() + ' km' : '';
  var lotw_str = q.lotw === 'confirmed'
    ? '<span class="lotw"> ✓ LoTW</span>' : '';
  var popup =
    '<div class="qso-popup">'
    +'<b>'+q.call+'</b>'+lotw_str+' via '+q.mode+'<br>'
    +q.band+'  '+(q.grid||'')
    +dist_str+'<br>'+q.time
    +'</div>';
  L.polyline([q.from, q.to], {{
    color:col, weight:1, opacity:0.5, dashArray:'4 4'
  }}).bindPopup(popup).addTo(lyrQsoPaths);
  L.marker(q.to, {{
    icon: L.divIcon({{
      html: '<div style="background:'+col+';width:6px;height:6px;'
           +'border-radius:50%;border:1px solid #fff;opacity:0.8;"></div>',
      className:'', iconSize:[6,6], iconAnchor:[3,3]
    }})
  }}).bindPopup(popup).addTo(lyrQsoPaths);
}});

// ── Repeaters ─────────────────────────────────────────────────
REPEATERS.forEach(function(r) {{
  var mc = r.mode==='DMR'?'#44aaff': r.mode==='P25'?'#ffaa22':'#3fbe6f';
  L.marker([r.lat, r.lon], {{
    icon: L.divIcon({{
      html: '<div style="background:'+mc+';width:8px;height:8px;'
           +'border:1px solid #fff;opacity:0.9;transform:rotate(45deg);"></div>',
      className:'', iconSize:[8,8], iconAnchor:[4,4]
    }})
  }}).bindPopup(
    '<div class="qso-popup"><b>'+r.call+'</b><br>'
    +r.freq+' MHz  '+r.mode+'<br>'
    +(r.tone?r.tone+'<br>':'')
    +r.city+'  ('+r.dist_km.toFixed(1)+' km)</div>'
  ).addTo(lyrRepeaters);
}});

// ── APRS stations ─────────────────────────────────────────────
APRS.forEach(function(a) {{
  var m = L.circleMarker([a.lat, a.lon], {{
    radius:5, color:'#ff8844', fillColor:'#ff8844',
    fillOpacity:0.7, weight:1
  }}).bindPopup(
    '<div class="qso-popup"><b>'+a.call+'</b><br>'+a.comment+'</div>'
  );
  if (SHOW_APRS_LABELS) {{
    m.bindTooltip(a.call, {{
      permanent: true, direction: 'right',
      className: 'aprs-label',
      offset: [6, 0]
    }});
  }}
  m.addTo(lyrAprs);
}});

// ── ADS-B aircraft — altitude-coded colour ────────────────────
function _acColor(alt) {{
  if (alt > 35000) return '#ff88ff';   // high FL — magenta
  if (alt > 18000) return '#aaaaff';   // upper airspace — blue
  if (alt > 5000)  return '#88ccff';   // mid airspace — cyan
  return '#66ddaa';                    // low / VFR — green
}}
AIRCRAFT.forEach(function(a) {{
  var col = _acColor(a.alt);
  L.marker([a.lat, a.lon], {{
    icon: L.divIcon({{
      html: '<div style="color:'+col+';font-size:16px;'
           +'transform:rotate('+a.track+'deg);'
           +'text-shadow:0 0 4px #000,0 0 2px #000;cursor:pointer;">✈</div>',
      className:'', iconSize:[16,16], iconAnchor:[8,8]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:'+col+'">'+(a.flight||a.icao)+'</b><br>'
    +'Alt: <b>'+a.alt.toLocaleString()+'</b> ft<br>'
    +'Speed: '+a.speed+' kts  Hdg: '+a.track+'°'
    +'</div>'
  ).addTo(lyrAircraft);
}});

// ── WSPR heard stations — propagation path dots ───────────────
var WSPR_BAND_COLS = {{
  '2200m':'#cc88ff','630m':'#aa66cc','160m':'#ff8866',
  '80m':'#ffaa44','60m':'#ffcc44','40m':'#ffee22',
  '30m':'#ccee22','20m':'#88ee22','17m':'#44ee66',
  '15m':'#22eebb','12m':'#22ccff','10m':'#22aaff',
  '6m':'#6688ff','4m':'#aa66ff','2m':'#ff66ff'
}};
var WSPR_DEF = '#aaaaff';
WSPR_SPOTS.forEach(function(s) {{
  if (!s.lat || !s.lon) return;
  var col = WSPR_BAND_COLS[s.band] || WSPR_DEF;
  L.circleMarker([s.lat, s.lon], {{
    radius: 5, color: col, fillColor: col,
    fillOpacity: 0.7, weight: 1, opacity: 0.9
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:'+col+'">'+s.callsign+'</b><br>'
    +s.grid+'  '+s.band+'<br>'
    +'SNR: '+s.snr+' dB  '+s.power_dbm+' dBm<br>'
    +(s.dist_km ? s.dist_km.toLocaleString()+' km' : '')
    +'</div>'
  ).addTo(lyrWspr);
  // Draw faint great-circle line from station to reporter if we have MY position
  if (MY_LAT || MY_LON) {{
    L.polyline([[MY_LAT, MY_LON],[s.lat, s.lon]], {{
      color: col, weight: 0.8, opacity: 0.4, dashArray: '3 5'
    }}).addTo(lyrWspr);
  }}
}});

// ── DX cluster spots — star markers at DX station location ───
var DX_BAND_COLS = {{
  '160m':'#ff8866','80m':'#ffaa44','60m':'#ffcc44','40m':'#ffee22',
  '30m':'#ccee22','20m':'#88ee22','17m':'#44ee66','15m':'#22eebb',
  '12m':'#22ccff','10m':'#22aaff','6m':'#6688ff','2m':'#cc88ff'
}};
var DX_DEF = '#ffddaa';
DX_SPOTS.forEach(function(d) {{
  if (!d.lat || !d.lon) return;
  var col  = DX_BAND_COLS[d.band] || DX_DEF;
  var dim  = d.age_min && d.age_min > 15 ? 0.4 : 0.9;
  L.marker([d.lat, d.lon], {{
    icon: L.divIcon({{
      html: '<div style="color:'+col+';font-size:12px;'
           +'opacity:'+dim+';text-shadow:0 0 3px #000;">★</div>',
      className:'', iconSize:[12,12], iconAnchor:[6,6]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:'+col+'">'+d.callsign+'</b>  '+d.country+'<br>'
    +d.freq_mhz.toFixed(3)+' MHz  '+d.band+'  '+d.mode+'<br>'
    +(d.snr ? 'SNR '+d.snr+' dB' : '')
    +'</div>'
  ).addTo(lyrDxSpots);
}});

// ── Map right-click → propagation path analysis ───────────────
map.on('contextmenu', function(e) {{
  var lat = e.latlng.lat.toFixed(5);
  var lon = e.latlng.lng.toFixed(5);
  L.popup({{maxWidth: 240}})
    .setLatLng(e.latlng)
    .setContent(
      '<div class="qso-popup">'
      +'<b>'+lat+'°, '+lon+'°</b><br>'
      +'<a href="squelch://path-analysis?lat='+lat+'&lon='+lon
      +'" style="color:#3fbe6f;">→ Analyze propagation to this point</a>'
      +'</div>')
    .openOn(map);
}});

// ── Heard stations (FT8/FT4/decode) — mode-coloured dots ─────
var MCOLORS = {{
  'FT8':'#00aaff', 'FT4':'#0066cc', 'WSPR':'#ffcc00',
  'CW':'#ff8800', 'SSB':'#44cc44', 'AM':'#44cc44',
  'PSK31':'#cc66ff', 'PSK63':'#cc66ff', 'RTTY':'#ff66aa',
  'JS8':'#22dddd', 'SSTV':'#ff9933'
}};
var MC_DEFAULT = '#aaaaaa';
HEARD.forEach(function(s) {{
  var col = MCOLORS[s.source] || MC_DEFAULT;
  L.marker([s.lat, s.lon], {{
    icon: L.divIcon({{
      html: '<div style="background:'+col+';width:8px;height:8px;'
           +'border-radius:50%;border:1px solid #fff;opacity:0.85;"></div>',
      className:'', iconSize:[8,8], iconAnchor:[4,4]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:'+col+'">'+s.callsign+'</b><br>'
    +(s.grid||'')+'<br>'
    +(s.freq_mhz?(s.freq_mhz.toFixed(4)+' MHz  '):'')
    +(s.source||'decode')
    +(s.snr_db?'<br>SNR '+s.snr_db+' dB':'')
    +'</div>'
  ).addTo(lyrHeard);
}});

// ── Winlink RMS gateways — purple upward triangles ────────────
WINLINK_GW.forEach(function(g) {{
  L.marker([g.lat, g.lon], {{
    icon: L.divIcon({{
      html: '<div style="width:0;height:0;'
           +'border-left:7px solid transparent;'
           +'border-right:7px solid transparent;'
           +'border-bottom:13px solid #cc66ff;opacity:0.9;"></div>',
      className:'', iconSize:[14,13], iconAnchor:[7,13]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:#cc66ff">'+g.callsign+'</b> Winlink RMS<br>'
    +(g.grid||'')+(g.dist?' • '+g.dist:'')+'<br>'
    +g.freq+'  '+(g.mode||'')+'</div>'
  ).addTo(lyrWinlink);
}});

// ── PSKReporter — stations that heard us — orange triangles ───
HEARING_ME.forEach(function(s) {{
  var freq_mhz = s.freq_hz ? (s.freq_hz/1e6).toFixed(4)+' MHz' : '';
  L.marker([s.lat, s.lon], {{
    icon: L.divIcon({{
      html: '<div style="width:0;height:0;'
           +'border-left:6px solid transparent;'
           +'border-right:6px solid transparent;'
           +'border-bottom:11px solid #ff8800;opacity:0.9;"></div>',
      className:'', iconSize:[12,11], iconAnchor:[6,11]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:#ff8800">'+s.callsign+'</b> heard us<br>'
    +(s.grid||'')+'<br>'
    +(freq_mhz?freq_mhz+'  ':'')+(s.mode||'')
    +(s.snr?'<br>SNR '+s.snr+' dB':'')
    +'</div>'
  ).addTo(lyrHearingMe);
}});

// ── Satellites — ISS & ham satellites ────────────────────────
SATELLITES.forEach(function(s) {{
  var isISS = s.name && s.name.indexOf('ISS') >= 0;
  var isVisible = s.is_visible || s.visible;
  var col  = isISS ? '#ffd700' : (isVisible ? '#00ddff' : '#888888');
  var size = isISS ? 20 : 14;
  var emoji = isISS ? '🛰️' : '🛰';
  var opacity = isVisible ? 1.0 : 0.5;
  // Compute the next-pass popup fragment BEFORE the marker — these are plain
  // statements and cannot live inside the L.marker({{...}}) options object
  // literal (doing so is a JS syntax error that aborts the whole map script).
  var np = s.next_pass;
  var npHtml = np
    ? '<br><span style="color:#aaa;font-size:10px;">Next pass: AOS '
      +np.aos+' / LOS '+np.los
      +' / Max El '+np.max_el.toFixed(1)+'°'
      +' / Az '+np.aos_az.toFixed(0)+'°</span>'
    : '';
  L.marker([s.lat, s.lon], {{
    icon: L.divIcon({{
      html: '<div title="'+s.name+'" style="'
           +'font-size:'+(isISS?18:13)+'px;'
           +'line-height:1;opacity:'+opacity+';'
           +'filter:drop-shadow(0 0 4px '+col+');'
           +'cursor:pointer;"></div>',
      className:'', iconSize:[size,size], iconAnchor:[size/2,size/2]
    }})
  }}).bindPopup(
    '<div class="qso-popup">'
    +'<b style="color:'+col+'">'+s.name+'</b><br>'
    +'Alt: '+(s.alt_km?s.alt_km.toFixed(0)+' km':'—')
    +'  El: '+(s.el_deg!=null?s.el_deg.toFixed(1)+'°':'—')+'<br>'
    +(isVisible
      ? '<span style="color:#00ff88">● Above horizon</span>'
      : '<span style="color:#888">● Below horizon</span>')
    +npHtml
    +'</div>'
  ).addTo(lyrSatellites);
}});

// ── Layer control (top-right) — toggle overlays ───────────────
L.control.layers(
  {{"Dark": darkTiles, "Street Map": streetTiles}},
  {{
    "Gray Line":      lyrGrayline,
    "My Grid":        lyrMyGrid,
    "Worked Grids":   lyrWorkedGrids,
    "QSO Paths":      lyrQsoPaths,
    "Heard (decode)": lyrHeard,
    "PSKReporter":    lyrHearingMe,
    "APRS":           lyrAprs,
    "Winlink RMS":    lyrWinlink,
    "Repeaters":      lyrRepeaters,
    "Aircraft":       lyrAircraft,
    "Satellites":     lyrSatellites,
    "WSPR spots":     lyrWspr,
    "DX Spots":       lyrDxSpots
  }},
  {{position:'topright', collapsed:true}}
).addTo(map);

// ── Persist layer toggles back to Qt ─────────────────────────
// When the user toggles an overlay in the control, fire a squelch:// URL that
// _MapPage intercepts (and cancels) so the choice survives the next rebuild
// and across sessions. Handlers are attached AFTER the initial addTo() calls
// above so restoring the persisted state does not re-fire them.
var NAME2KEY = {json.dumps(_LAYER_NAME_TO_KEY)};
map.on('overlayadd', function(e) {{
  var k = NAME2KEY[e.name];
  if (k) {{ window.location.href = 'squelch://layer-toggle?name=' + k + '&on=1'; }}
}});
map.on('overlayremove', function(e) {{
  var k = NAME2KEY[e.name];
  if (k) {{ window.location.href = 'squelch://layer-toggle?name=' + k + '&on=0'; }}
}});

// ── Measure / ruler tool ─────────────────────────────────────
// Click the 📏 button to arm, then click two points for great-circle
// distance (km / mi) + initial bearing. A third click resets.
var rulerLayer = L.layerGroup().addTo(map);
var rulerPts = [];
var rulerOn = false;
function rulerClear() {{ rulerLayer.clearLayers(); rulerPts = []; }}
function rulerBearing(a, b) {{
  var la1 = a.lat * Math.PI / 180, la2 = b.lat * Math.PI / 180;
  var dlon = (b.lng - a.lng) * Math.PI / 180;
  var y = Math.sin(dlon) * Math.cos(la2);
  var x = Math.cos(la1) * Math.sin(la2)
        - Math.sin(la1) * Math.cos(la2) * Math.cos(dlon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}}
var RulerControl = L.Control.extend({{
  options: {{position: 'topleft'}},
  onAdd: function() {{
    var btn = L.DomUtil.create('a', 'leaflet-bar leaflet-control ruler-btn');
    btn.href = '#';
    btn.title = 'Measure distance + bearing (click two points)';
    btn.innerHTML = '📏';
    L.DomEvent.on(btn, 'click', function(ev) {{
      L.DomEvent.stop(ev);
      rulerOn = !rulerOn;
      btn.style.background = rulerOn ? '#3fbe6f' : '';
      L.DomUtil.removeClass(map._container, 'leaflet-grab');
      map._container.style.cursor = rulerOn ? 'crosshair' : '';
      if (!rulerOn) rulerClear();
    }});
    return btn;
  }}
}});
map.addControl(new RulerControl());
map.on('click', function(e) {{
  if (!rulerOn) return;
  if (rulerPts.length >= 2) rulerClear();
  rulerPts.push(e.latlng);
  L.circleMarker(e.latlng, {{radius: 4, color: '#3fbe6f',
    fillColor: '#3fbe6f', fillOpacity: 1, weight: 2}}).addTo(rulerLayer);
  if (rulerPts.length === 2) {{
    var a = rulerPts[0], b = rulerPts[1];
    var km = map.distance(a, b) / 1000;
    var mi = km * 0.621371;
    var brg = rulerBearing(a, b);
    L.polyline([a, b], {{color: '#3fbe6f', weight: 2,
      dashArray: '5,6', opacity: 0.9}}).addTo(rulerLayer);
    L.popup({{className: 'qso-popup'}})
      .setLatLng(b)
      .setContent('<b>Ruler</b><br>' + km.toFixed(1) + ' km / '
        + mi.toFixed(1) + ' mi<br>Bearing ' + brg.toFixed(0) + '&deg;')
      .openOn(map);
  }}
}});

// ── Legend control (bottom-right) ────────────────────────────
var legend = L.control({{position:'bottomright'}});
legend.onAdd = function() {{
  var d = L.DomUtil.create('div','map-legend');
  d.innerHTML =
    '<b>LEGEND</b><br>'
    +'<span class="leg-dot" style="background:#3fbe6f;"></span>My Station<br>'
    +'<span class="leg-sq" style="background:#44aaff;transform:none;width:10px;height:7px;border-radius:0;"></span>Worked Grid<br>'
    +'<span class="leg-dot" style="background:#00aaff;"></span>FT8 heard<br>'
    +'<span class="leg-dot" style="background:#ffcc00;"></span>WSPR heard<br>'
    +'<span class="leg-dot" style="background:#ff8800;"></span>CW heard<br>'
    +'<span class="leg-dot" style="background:#44cc44;"></span>SSB heard<br>'
    +'<span class="leg-tri-up" style="border-bottom:11px solid #ff8800;"></span>PSKReporter<br>'
    +'<span class="leg-dot" style="background:#ff8844;"></span>APRS<br>'
    +'<span class="leg-sq" style="background:#3fbe6f;"></span>Repeater<br>'
    +'<span class="leg-tri-up" style="border-bottom:13px solid #cc66ff;"></span>Winlink RMS<br>'
    +'<span style="color:#aaaaff;font-size:13px;vertical-align:middle;margin-right:4px;">✈</span>ADS-B<br>'
    +'<span style="color:#ffd700;font-size:11px;vertical-align:middle;margin-right:4px;">🛰</span>Satellite (visible)<br>'
    +'<span style="color:#888;font-size:11px;vertical-align:middle;margin-right:4px;">🛰</span>Satellite (below horizon)<br>'
    +'<span class="leg-dot" style="background:#ffee22;"></span>WSPR heard (20m)';
  return d;
}};
legend.addTo(map);
</script>
</body>
</html>"""
