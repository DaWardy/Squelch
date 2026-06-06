from __future__ import annotations
"""Terrain elevation for the propagation side-view.

Two backends behind a single elevation_profile() API:

  online  — OpenTopoData SRTM-30m (free, no key, 100 pts/request,
            1 req/s limit; documented at opentopodata.org)

  offline — Amazon open terrain tiles: NASA SRTM3 HGT format,
            https://elevation-tiles-prod.s3.amazonaws.com/skadi/
            No authentication, free. Downloaded 1°×1° tiles on first
            use, cached in {data_dir}/terrain/srtm/.

Both return a list of elevation values (metres) along the path.
Returns None if unavailable (network error, tile not yet downloaded).
"""
import gzip
import logging
import math
import struct
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Tile cache directory ──────────────────────────────────────────────────
def _cache_dir() -> Path:
    try:
        from core.config import USER_DIR
        d = USER_DIR / "terrain" / "srtm"
    except Exception:
        d = Path.home() / ".config" / "squelch" / "terrain" / "srtm"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Great-circle path sampling ────────────────────────────────────────────
def gc_profile(lat1: float, lon1: float,
               lat2: float, lon2: float,
               n: int = 60) -> list[tuple[float, float]]:
    """Sample n+1 evenly-spaced points along the great circle."""
    la1, lo1 = math.radians(lat1), math.radians(lon1)
    la2, lo2 = math.radians(lat2), math.radians(lon2)
    d = 2 * math.asin(math.sqrt(
        math.sin((la2 - la1) / 2) ** 2 +
        math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    if d < 1e-9:
        return [(lat1, lon1)] * (n + 1)
    pts = []
    for i in range(n + 1):
        t = i / n
        A = math.sin((1 - t) * d) / math.sin(d)
        B = math.sin(t * d) / math.sin(d)
        x = A * math.cos(la1) * math.cos(lo1) + B * math.cos(la2) * math.cos(lo2)
        y = A * math.cos(la1) * math.sin(lo1) + B * math.cos(la2) * math.sin(lo2)
        z = A * math.sin(la1) + B * math.sin(la2)
        pts.append((
            math.degrees(math.atan2(z, math.sqrt(x ** 2 + y ** 2))),
            math.degrees(math.atan2(y, x))))
    return pts


# ── SRTM HGT tile reader ──────────────────────────────────────────────────
_HGT_SAMPLES = 1201          # SRTM3: 1201×1201 16-bit big-endian ints
_HGT_SIZE    = _HGT_SAMPLES ** 2 * 2   # bytes


def _tile_key(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def _tile_url(lat: int, lon: int) -> str:
    key = _tile_key(lat, lon)
    ns_dir = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    return (f"https://elevation-tiles-prod.s3.amazonaws.com/skadi/"
            f"{ns_dir}/{key}.hgt.gz")


def _tile_path(lat: int, lon: int) -> Path:
    return _cache_dir() / f"{_tile_key(lat, lon)}.hgt"


def _download_tile(lat: int, lon: int) -> bool:
    """Download and cache an SRTM HGT tile. Returns True on success."""
    path = _tile_path(lat, lon)
    if path.exists() and path.stat().st_size == _HGT_SIZE:
        return True
    url = _tile_url(lat, lon)
    log.info(f"Terrain: downloading tile {_tile_key(lat, lon)} …")
    try:
        import requests
        resp = requests.get(url, timeout=30, stream=True)
        if resp.status_code == 404:
            # Ocean tiles don't exist — create a zero-elevation placeholder
            log.debug(f"Terrain: {_tile_key(lat, lon)} is ocean (404)")
            path.write_bytes(b"\x00\x00" * (_HGT_SAMPLES ** 2))
            return True
        if resp.status_code != 200:
            log.warning(f"Terrain tile HTTP {resp.status_code}: {url}")
            return False
        data = gzip.decompress(resp.content)
        if len(data) != _HGT_SIZE:
            log.warning(f"Terrain tile wrong size: {len(data)} != {_HGT_SIZE}")
            return False
        path.write_bytes(data)
        log.info(f"Terrain: tile {_tile_key(lat, lon)} cached at {path}")
        return True
    except Exception as e:
        log.debug(f"Terrain download failed ({_tile_key(lat, lon)}): {e}")
        return False


@lru_cache(maxsize=12)
def _read_tile(lat: int, lon: int) -> Optional[bytes]:
    """Read cached tile data (LRU-cached in memory for paint speed)."""
    path = _tile_path(lat, lon)
    if not path.exists():
        return None
    data = path.read_bytes()
    if len(data) != _HGT_SIZE:
        return None
    return data


def _elevation_from_tile(lat: float, lon: float) -> Optional[float]:
    """Bilinear-interpolated elevation at (lat, lon) from cached SRTM tile."""
    tile_lat = math.floor(lat)
    tile_lon = math.floor(lon)
    data = _read_tile(tile_lat, tile_lon)
    if data is None:
        return None
    # Sub-tile fractional position
    frac_lat = lat - tile_lat   # 0=south, 1=north
    frac_lon = lon - tile_lon   # 0=west,  1=east
    # SRTM3: row 0 = northernmost → row index increases southward
    row  = (_HGT_SAMPLES - 1) * (1 - frac_lat)
    col  = (_HGT_SAMPLES - 1) * frac_lon
    r0, c0 = int(row), int(col)
    r1, c1 = min(r0 + 1, _HGT_SAMPLES - 1), min(c0 + 1, _HGT_SAMPLES - 1)
    dr, dc = row - r0, col - c0

    def px(r: int, c: int) -> float:
        offset = (r * _HGT_SAMPLES + c) * 2
        val = struct.unpack_from(">h", data, offset)[0]
        return float(val if val != -32768 else 0)   # void value → sea level

    # Bilinear interpolation
    return (px(r0, c0) * (1 - dr) * (1 - dc) +
            px(r0, c1) * (1 - dr) *      dc  +
            px(r1, c0) *      dr  * (1 - dc) +
            px(r1, c1) *      dr  *      dc)


# ── Online backend: OpenTopoData ──────────────────────────────────────────
_ONLINE_URL     = "https://api.opentopodata.org/v1/srtm30m"
_ONLINE_LIMIT   = 100    # max points per request
_online_last    = 0.0    # last request timestamp (rate-limit 1/s)
_online_lock    = threading.Lock()


def _fetch_online(points: list[tuple[float, float]]) -> Optional[list[float]]:
    """Fetch elevations via OpenTopoData. Returns list[metres] or None."""
    global _online_last
    try:
        import requests
    except ImportError:
        return None
    # Chunk to respect the 100-point limit
    result: list[float] = []
    for i in range(0, len(points), _ONLINE_LIMIT):
        chunk = points[i: i + _ONLINE_LIMIT]
        locs  = "|".join(f"{lat:.5f},{lon:.5f}" for lat, lon in chunk)
        with _online_lock:
            wait = 1.0 - (time.time() - _online_last)
            if wait > 0:
                time.sleep(wait)
            _online_last = time.time()
        try:
            r = requests.get(_ONLINE_URL, params={"locations": locs},
                             timeout=15)
            if r.status_code != 200:
                log.debug(f"OpenTopoData HTTP {r.status_code}")
                return None
            for res in r.json()["results"]:
                result.append(float(res.get("elevation") or 0))
        except Exception as e:
            log.debug(f"OpenTopoData fetch: {e}")
            return None
    return result


# ── Offline backend ───────────────────────────────────────────────────────
def tiles_needed(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """Return the unique 1°×1° tile keys needed for a point list."""
    seen: set[tuple[int, int]] = set()
    for lat, lon in points:
        key = (math.floor(lat), math.floor(lon))
        if key not in seen:
            seen.add(key)
    return sorted(seen)


def download_tiles(points: list[tuple[float, float]],
                   progress_cb=None) -> tuple[int, int]:
    """Download all tiles needed for the given path. Returns (ok, total).
    progress_cb(done, total) is called after each tile if supplied."""
    needed = tiles_needed(points)
    ok = 0
    for i, (lat, lon) in enumerate(needed):
        if _download_tile(lat, lon):
            _read_tile.cache_clear()  # invalidate LRU after download
            ok += 1
        if progress_cb:
            progress_cb(i + 1, len(needed))
    return ok, len(needed)


def _fetch_offline(points: list[tuple[float, float]]) -> Optional[list[float]]:
    """Fetch elevations from locally-cached tiles. None if any tile missing."""
    result: list[float] = []
    for lat, lon in points:
        elev = _elevation_from_tile(lat, lon)
        if elev is None:
            return None    # tile not downloaded yet
        result.append(elev)
    return result


# ── Public API ────────────────────────────────────────────────────────────
def elevation_profile(lat1: float, lon1: float,
                      lat2: float, lon2: float,
                      n: int = 60,
                      mode: str = "online") -> Optional[list[float]]:
    """Return n+1 elevation samples (metres) along the great circle,
    or None if unavailable.

    mode: "online"  → OpenTopoData API (requires internet)
          "offline" → locally-cached SRTM tiles (download first via
                      download_tiles())
    """
    if lat1 == 0 and lon1 == 0:
        return None
    pts = gc_profile(lat1, lon1, lat2, lon2, n)
    if mode == "offline":
        return _fetch_offline(pts)
    return _fetch_online(pts)


def tiles_download_size_mb(lat1: float, lon1: float,
                           lat2: float, lon2: float,
                           n: int = 60) -> float:
    """Estimate download size in MB for a given path (offline mode)."""
    pts = gc_profile(lat1, lon1, lat2, lon2, n)
    needed = tiles_needed(pts)
    # ~400 KB per tile compressed (real average for continental US)
    already = sum(1 for la, lo in needed
                  if _tile_path(la, lo).exists()
                  and _tile_path(la, lo).stat().st_size == _HGT_SIZE)
    return (len(needed) - already) * 0.4


# Public alias used by band_conditions_tab
estimated_download_mb = tiles_download_size_mb
