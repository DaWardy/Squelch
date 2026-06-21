"""Tests for core/voice_keyer.py — 8-slot SSB/phone voice macro manager."""
from __future__ import annotations
import os
import sys
import tempfile
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


def _mock_cfg(**overrides):
    """Return a MagicMock cfg whose .get() reads from a simple dict."""
    store = {"advanced.log_dir": "", **overrides}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, default=None: store.get(k, default)
    cfg.set.side_effect = lambda k, v: store.update({k: v})
    return cfg


def _make_wav(path: str, duration_s: float = 0.1, rate: int = 44100) -> None:
    """Write a minimal valid WAV file for playback tests."""
    n_frames = int(duration_s * rate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * n_frames)


# ── VoiceKeyer logic tests ────────────────────────────────────────────────


class TestVoiceKeyerSlots:
    def test_keys_count(self):
        from core.voice_keyer import VoiceKeyer
        assert len(VoiceKeyer.KEYS) == 8

    def test_keys_naming(self):
        from core.voice_keyer import VoiceKeyer
        assert VoiceKeyer.KEYS == ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"]

    def test_all_clips_returns_eight(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        clips = vk.all_clips()
        assert len(clips) == 8

    def test_all_clips_keys_match(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        keys = [k for k, _ in vk.all_clips()]
        assert keys == VoiceKeyer.KEYS


class TestVoiceKeyerDefaults:
    def test_default_labels_are_strings(self):
        from core.voice_keyer import VoiceKeyer, _DEFAULT_LABELS
        assert len(_DEFAULT_LABELS) == 8
        assert all(isinstance(s, str) and s for s in _DEFAULT_LABELS)

    def test_default_labels_unique(self):
        from core.voice_keyer import _DEFAULT_LABELS
        assert len(set(_DEFAULT_LABELS)) == 8

    def test_get_clip_returns_default_label(self):
        from core.voice_keyer import VoiceKeyer, _DEFAULT_LABELS
        vk = VoiceKeyer(_mock_cfg())
        for i, key in enumerate(VoiceKeyer.KEYS):
            clip = vk.get_clip(key)
            assert clip["label"] == _DEFAULT_LABELS[i]

    def test_get_clip_path_empty_by_default(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        for key in VoiceKeyer.KEYS:
            assert vk.get_clip(key)["path"] == ""

    def test_initial_not_playing(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        assert not vk.is_playing

    def test_initial_not_recording(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        assert not vk.is_recording


class TestVoiceKeyerSetGet:
    def test_set_clip_persists_label(self):
        from core.voice_keyer import VoiceKeyer
        cfg = _mock_cfg()
        vk = VoiceKeyer(cfg)
        vk.set_clip("v1", "My CQ", "/tmp/cq.wav")
        assert vk.get_clip("v1")["label"] == "My CQ"

    def test_set_clip_persists_path(self):
        from core.voice_keyer import VoiceKeyer
        cfg = _mock_cfg()
        vk = VoiceKeyer(cfg)
        vk.set_clip("v3", "Report", "/audio/report.wav")
        assert vk.get_clip("v3")["path"] == "/audio/report.wav"

    def test_set_clip_does_not_affect_other_slots(self):
        from core.voice_keyer import VoiceKeyer
        cfg = _mock_cfg()
        vk = VoiceKeyer(cfg)
        vk.set_clip("v2", "TX Test", "/audio/test.wav")
        assert vk.get_clip("v1")["path"] == ""
        assert vk.get_clip("v3")["path"] == ""

    def test_set_clip_strips_label_whitespace(self):
        from core.voice_keyer import VoiceKeyer
        cfg = _mock_cfg()
        vk = VoiceKeyer(cfg)
        vk.set_clip("v4", "  73  ", "/audio/73.wav")
        assert vk.get_clip("v4")["label"] == "73"


class TestVoiceKeyerPlay:
    def test_play_empty_path_returns_false(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        assert vk.play("v1") is False

    def test_play_missing_file_returns_false(self):
        from core.voice_keyer import VoiceKeyer
        cfg = _mock_cfg()
        vk = VoiceKeyer(cfg)
        vk.set_clip("v1", "CQ", "/nonexistent/path/cq.wav")
        assert vk.play("v1") is False

    def test_play_without_sounddevice_returns_false(self):
        from core.voice_keyer import VoiceKeyer
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            _make_wav(wav_path)
            cfg = _mock_cfg()
            vk = VoiceKeyer(cfg)
            vk.set_clip("v1", "CQ", wav_path)
            import builtins
            real_import = builtins.__import__
            def _no_sounddevice(name, *args, **kwargs):
                if name == "sounddevice":
                    raise ImportError("mocked absence")
                return real_import(name, *args, **kwargs)
            with patch("builtins.__import__", side_effect=_no_sounddevice):
                result = vk.play("v1")
            assert result is False
        finally:
            os.unlink(wav_path)


class TestVoiceKeyerStop:
    def test_stop_safe_when_not_playing(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        # Must not raise even without sounddevice
        vk.stop()

    def test_stop_resets_playing_flag(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        vk._playing = True
        vk.stop()
        assert not vk.is_playing

    def test_stop_resets_recording_flag(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        vk._recording = True
        vk.stop()
        assert not vk.is_recording


class TestVoiceKeyerRecord:
    def test_record_without_sounddevice_returns_false(self):
        from core.voice_keyer import VoiceKeyer
        vk = VoiceKeyer(_mock_cfg())
        import builtins
        real_import = builtins.__import__
        def _no_sd(name, *args, **kwargs):
            if name == "sounddevice":
                raise ImportError("mocked absence")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=_no_sd):
            result = vk.record("v1")
        assert result is False


class TestClipDir:
    def test_clip_dir_created(self):
        from core.voice_keyer import _clip_dir
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _mock_cfg(**{"advanced.log_dir": tmp})
            d = _clip_dir(cfg)
            assert d.exists()
            assert d.name == "voice_clips"

    def test_clip_dir_falls_back_to_home(self):
        from core.voice_keyer import _clip_dir
        cfg = _mock_cfg(**{"advanced.log_dir": ""})
        d = _clip_dir(cfg)
        assert d.name == "voice_clips"
