"""Tests for digital/rfdf.py — RF direction finding math (DF-GRADIENT)."""
from __future__ import annotations
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── bearing_from_rssi_sweep ──────────────────────────────────────────────────


class TestBearingSweep:
    def test_peak_north(self):
        from digital.rfdf import bearing_from_rssi_sweep
        # Strong at 0°, weak elsewhere → bearing ≈ 0
        samples = [(0, -40), (90, -80), (180, -90), (270, -80)]
        b = bearing_from_rssi_sweep(samples)
        assert b is not None
        assert abs(b.bearing_deg - 0.0) < 5 or abs(b.bearing_deg - 360.0) < 5

    def test_peak_east(self):
        from digital.rfdf import bearing_from_rssi_sweep
        samples = [(0, -80), (90, -40), (180, -80), (270, -90)]
        b = bearing_from_rssi_sweep(samples)
        assert abs(b.bearing_deg - 90.0) < 5

    def test_peak_southwest(self):
        from digital.rfdf import bearing_from_rssi_sweep
        samples = [(225, -35), (45, -85), (0, -88), (180, -80), (270, -78)]
        b = bearing_from_rssi_sweep(samples)
        assert abs(b.bearing_deg - 225.0) < 12

    def test_confidence_higher_when_directional(self):
        from digital.rfdf import bearing_from_rssi_sweep
        sharp = bearing_from_rssi_sweep([(0, -30), (90, -90), (180, -95), (270, -90)])
        flat  = bearing_from_rssi_sweep([(0, -60), (90, -60), (180, -60), (270, -60)])
        assert sharp.confidence > flat.confidence

    def test_flat_low_confidence(self):
        from digital.rfdf import bearing_from_rssi_sweep
        b = bearing_from_rssi_sweep([(0, -60), (90, -60), (180, -60), (270, -60)])
        assert b.confidence < 0.1

    def test_peak_rssi_and_count(self):
        from digital.rfdf import bearing_from_rssi_sweep
        b = bearing_from_rssi_sweep([(0, -40), (90, -80), (180, -77)])
        assert b.peak_rssi == -40
        assert b.n_samples == 3

    def test_empty_returns_none(self):
        from digital.rfdf import bearing_from_rssi_sweep
        assert bearing_from_rssi_sweep([]) is None

    def test_heading_wraps(self):
        from digital.rfdf import bearing_from_rssi_sweep
        # 360 should behave like 0
        b = bearing_from_rssi_sweep([(360, -40), (90, -80), (270, -80)])
        assert 0 <= b.bearing_deg < 360


# ── triangulate ──────────────────────────────────────────────────────────────


class TestTriangulate:
    def test_two_bearings_cross(self):
        from digital.rfdf import triangulate, DFFix
        # Observer A south of TX looking N (0°); observer B west looking E (90°).
        # TX should be near A's lon and B's lat.
        a = DFFix(lat=40.0, lon=-75.0, bearing_deg=0.0)    # looks north
        b = DFFix(lat=40.1, lon=-75.2, bearing_deg=90.0)   # looks east
        est = triangulate([a, b])
        assert est is not None
        assert est.method == "triangulate"
        # Intersection ≈ (lat of A's meridian going north) x (B's parallel going east)
        assert abs(est.lat - 40.1) < 0.05
        assert abs(est.lon - (-75.0)) < 0.05

    def test_known_intersection_recovered(self):
        from digital.rfdf import triangulate, DFFix
        import math as _m
        # Place a TX, compute true bearings from two observers, recover it.
        tx = (41.0, -74.0)
        obs = [(40.0, -74.0), (40.0, -75.0)]
        fixes = []
        for la, lo in obs:
            de = (tx[1] - lo) * _m.cos(_m.radians(la))
            dn = (tx[0] - la)
            brg = _m.degrees(_m.atan2(de, dn)) % 360
            fixes.append(DFFix(la, lo, brg))
        est = triangulate(fixes)
        assert abs(est.lat - 41.0) < 0.05
        assert abs(est.lon - (-74.0)) < 0.05

    def test_tuples_accepted(self):
        from digital.rfdf import triangulate
        est = triangulate([(40.0, -75.0, 0.0), (40.1, -75.2, 90.0)])
        assert est is not None

    def test_single_fix_returns_none(self):
        from digital.rfdf import triangulate, DFFix
        assert triangulate([DFFix(40.0, -75.0, 10.0)]) is None

    def test_parallel_bearings_return_none(self):
        from digital.rfdf import triangulate, DFFix
        a = DFFix(40.0, -75.0, 45.0)
        b = DFFix(40.1, -75.1, 45.0)   # same bearing → parallel
        assert triangulate([a, b]) is None

    def test_confidence_higher_for_orthogonal(self):
        from digital.rfdf import triangulate, DFFix
        ortho = triangulate([DFFix(40.0, -75.0, 0.0), DFFix(40.1, -75.2, 90.0)])
        shallow = triangulate([DFFix(40.0, -75.0, 10.0), DFFix(40.1, -75.2, 30.0)])
        assert ortho.confidence > shallow.confidence


# ── estimate_location_rssi ───────────────────────────────────────────────────


class TestRssiCentroid:
    def test_centroid_pulled_to_strong_sample(self):
        from digital.rfdf import estimate_location_rssi
        samples = [
            (40.0, -75.0, -30),    # strong
            (41.0, -74.0, -90),    # weak
            (39.0, -76.0, -90),    # weak
        ]
        est = estimate_location_rssi(samples)
        assert est is not None
        assert est.method == "rssi-centroid"
        # Should sit very close to the strong sample
        assert abs(est.lat - 40.0) < 0.2
        assert abs(est.lon - (-75.0)) < 0.2

    def test_equal_weights_average(self):
        from digital.rfdf import estimate_location_rssi
        est = estimate_location_rssi([(40.0, -75.0, -50), (42.0, -75.0, -50)])
        assert abs(est.lat - 41.0) < 0.01

    def test_confidence_grows_with_samples(self):
        from digital.rfdf import estimate_location_rssi
        few  = estimate_location_rssi([(40.0, -75.0, -50)])
        many = estimate_location_rssi([(40.0, -75.0, -50)] * 12)
        assert many.confidence > few.confidence

    def test_empty_returns_none(self):
        from digital.rfdf import estimate_location_rssi
        assert estimate_location_rssi([]) is None


# ── helpers ──────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_norm_deg(self):
        from digital.rfdf import _norm_deg
        assert _norm_deg(370) == 10
        assert _norm_deg(-10) == 350

    def test_enu_roundtrip(self):
        from digital.rfdf import _enu, _enu_to_latlon
        e, n = _enu(41.0, -74.0, 40.0, -75.0)
        lat, lon = _enu_to_latlon(e, n, 40.0, -75.0)
        assert abs(lat - 41.0) < 1e-6
        assert abs(lon - (-74.0)) < 1e-6

    def test_dbm_to_linear_monotonic(self):
        from digital.rfdf import _dbm_to_linear
        assert _dbm_to_linear(-30) > _dbm_to_linear(-90)

    def test_dbm_to_linear_clamps(self):
        from digital.rfdf import _dbm_to_linear
        # Must not overflow/raise on absurd input
        assert _dbm_to_linear(1e9) > 0
        assert _dbm_to_linear(-1e9) >= 0
