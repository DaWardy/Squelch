"""Tests for signal ID panel bookmark and annotation logic (no Qt required)."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_match(name="WSPR", modulation="USB", bw=200, cat="Amateur",
                conf=0.85, url="https://sigidwiki.com/wiki/WSPR"):
    from network.signal_id import SignalMatch
    return SignalMatch(
        name=name, modulation=modulation, bandwidth_hz=bw,
        category=cat, confidence=conf, url=url,
    )


def _make_mixin(tmp_path):
    """Build a minimal _SDRSignalIDMixin instance without Qt."""
    from ui.tabs.sdr_signal_id import _SDRSignalIDMixin

    class _Stub(_SDRSignalIDMixin):
        def __init__(self):
            self.cfg = MagicMock()
            self.cfg.get.return_value = "Dark"
            self._last_id_freq_hz = 14_097_000
            self._last_id_bw_hz = 200
            self._sigid_panel = None
            self._sigid_annotations = []
            self._spec_plot = None
            self._wf_plot = None

    return _Stub()


# ---------------------------------------------------------------------------
# Bookmark persistence
# ---------------------------------------------------------------------------

def test_bookmark_creates_file(tmp_path, monkeypatch):
    import ui.tabs.sdr_signal_id as mod
    bm_file = tmp_path / "bookmarks.json"
    monkeypatch.setattr(mod, "_BOOKMARK_FILE", bm_file)

    mixin = _make_mixin(tmp_path)
    match = _make_match()
    mixin._bookmark_signal(match)

    assert bm_file.exists(), "bookmark file not created"
    data = json.loads(bm_file.read_text())
    assert len(data) == 1
    assert data[0]["name"] == "WSPR"
    assert data[0]["freq_hz"] == 14_097_000
    assert data[0]["modulation"] == "USB"


def test_bookmark_prepends_newest(tmp_path, monkeypatch):
    import ui.tabs.sdr_signal_id as mod
    bm_file = tmp_path / "bookmarks.json"
    monkeypatch.setattr(mod, "_BOOKMARK_FILE", bm_file)

    mixin = _make_mixin(tmp_path)
    mixin._bookmark_signal(_make_match(name="First"))
    mixin._bookmark_signal(_make_match(name="Second"))

    data = json.loads(bm_file.read_text())
    assert data[0]["name"] == "Second"
    assert data[1]["name"] == "First"


def test_bookmark_caps_at_200(tmp_path, monkeypatch):
    import ui.tabs.sdr_signal_id as mod
    bm_file = tmp_path / "bookmarks.json"
    monkeypatch.setattr(mod, "_BOOKMARK_FILE", bm_file)

    mixin = _make_mixin(tmp_path)
    for i in range(210):
        mixin._bookmark_signal(_make_match(name=f"Sig{i}"))

    data = json.loads(bm_file.read_text())
    assert len(data) == 200


def test_bookmark_handles_corrupt_file(tmp_path, monkeypatch):
    import ui.tabs.sdr_signal_id as mod
    bm_file = tmp_path / "bookmarks.json"
    bm_file.write_text("NOT JSON")
    monkeypatch.setattr(mod, "_BOOKMARK_FILE", bm_file)

    mixin = _make_mixin(tmp_path)
    mixin._bookmark_signal(_make_match())  # should not raise

    data = json.loads(bm_file.read_text())
    assert len(data) == 1


# ---------------------------------------------------------------------------
# Annotation cleanup
# ---------------------------------------------------------------------------

def test_clear_annotations_removes_all(tmp_path):
    mixin = _make_mixin(tmp_path)
    fake_ann = MagicMock()
    fake_label = MagicMock()
    mixin._sigid_annotations = [
        (14_097_000, fake_ann, fake_label, None),
        (14_200_000, fake_ann, fake_label, None),
    ]
    mixin._clear_sigid_annotations()
    assert mixin._sigid_annotations == []


def test_clear_annotations_by_freq(tmp_path):
    mixin = _make_mixin(tmp_path)
    ann_a = MagicMock()
    ann_b = MagicMock()
    mixin._sigid_annotations = [
        (14_097_000, ann_a, MagicMock(), None),
        (14_200_000, ann_b, MagicMock(), None),
    ]
    mixin._clear_sigid_annotations(freq_hz=14_097_000)
    assert len(mixin._sigid_annotations) == 1
    assert mixin._sigid_annotations[0][0] == 14_200_000


# ---------------------------------------------------------------------------
# Category annotation colour lookup
# ---------------------------------------------------------------------------

def test_category_colors_defined():
    from ui.tabs.sdr_signal_id import _CATEGORY_ANNOTATION_COLOR
    for cat in ("amateur", "aviation", "marine", "military", "utility"):
        assert cat in _CATEGORY_ANNOTATION_COLOR
        r, g, b, a = _CATEGORY_ANNOTATION_COLOR[cat]
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255


def test_default_annotation_color_exists():
    from ui.tabs.sdr_signal_id import _DEFAULT_ANNOTATION_COLOR
    assert len(_DEFAULT_ANNOTATION_COLOR) == 4
