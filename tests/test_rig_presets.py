from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
# Squelch tests — core/rig_presets.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.rig_presets import PRESETS, preset_names


class TestPresets:
    def test_has_icom_7100(self):
        assert "ICOM IC-7100" in PRESETS

    def test_ic7100_hamlib_model(self):
        p = PRESETS["ICOM IC-7100"]
        assert p.hamlib_model == 370

    def test_ic7100_baud(self):
        p = PRESETS["ICOM IC-7100"]
        assert p.baud == 19200

    def test_has_yaesu(self):
        assert any("Yaesu" in k for k in PRESETS)

    def test_has_kenwood(self):
        assert any("Kenwood" in k for k in PRESETS)

    def test_has_elecraft(self):
        assert any("Elecraft" in k for k in PRESETS)

    def test_has_signalink(self):
        assert "SignaLink USB" in PRESETS

    def test_signalink_no_cat(self):
        p = PRESETS["SignaLink USB"]
        assert p.supports_cat is False

    def test_signalink_vox_or_rts(self):
        p = PRESETS["SignaLink USB"]
        assert p.ptt_method in ("VOX", "RTS")

    def test_qrz1_no_cat(self):
        p = PRESETS.get("Explorer QRZ-1")
        if p:
            assert p.supports_cat is False

    def test_all_have_name(self):
        for key, p in PRESETS.items():
            assert p.name, f"{key} has no name"

    def test_all_have_category(self):
        for key, p in PRESETS.items():
            assert p.category, f"{key} has no category"

    def test_cat_rigs_have_hamlib(self):
        """CAT-capable rigs should have a hamlib model."""
        for key, p in PRESETS.items():
            if p.supports_cat and "Manual" not in key and "Other" not in key:
                assert p.hamlib_model is not None, \
                    f"{key} supports_cat but no hamlib_model"


class TestPresetNames:
    def test_returns_list(self):
        names = preset_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_icom_first(self):
        """ICOM rigs should appear before Yaesu."""
        names = preset_names()
        icom_idx = next(
            (i for i, n in enumerate(names)
             if "ICOM" in n), None)
        yaesu_idx = next(
            (i for i, n in enumerate(names)
             if "Yaesu" in n), None)
        if icom_idx and yaesu_idx:
            assert icom_idx < yaesu_idx

    def test_no_duplicates(self):
        names = preset_names()
        assert len(names) == len(set(names))

    def test_manual_present(self):
        names = preset_names()
        assert any("Manual" in n for n in names)