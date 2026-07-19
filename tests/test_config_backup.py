# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Config export/import for backup & transfer to another device."""

from pathlib import Path

from core.config import Config


def _cfg(tmp_path, name="config.json"):
    return Config(Path(tmp_path) / name)


def test_export_writes_json(tmp_path):
    c = _cfg(tmp_path)
    c.set("callsign", "N0CALL")
    c.set("sdr.sigid_db_path", "/some/db.json")
    out = tmp_path / "backup.json"
    assert c.export_to(out) is True
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["callsign"] == "N0CALL"


def test_export_import_round_trip(tmp_path):
    src = _cfg(tmp_path, "a.json")
    src.set("callsign", "W1AW")
    src.set("ui.theme", "Dark")
    backup = tmp_path / "b.json"
    assert src.export_to(backup)
    # a different device / fresh config imports it
    dst = _cfg(tmp_path / "sub", "c.json")
    assert dst.import_from(backup) is True
    assert dst.get("callsign") == "W1AW"
    assert dst.get("ui.theme") == "Dark"


def test_import_merge_keeps_local_keys(tmp_path):
    dst = _cfg(tmp_path, "d.json")
    dst.set("local_only", 42)
    backup = tmp_path / "e.json"
    src = _cfg(tmp_path, "f.json")
    src.set("callsign", "K1ABC")
    src.export_to(backup)
    assert dst.import_from(backup, merge=True)
    assert dst.get("callsign") == "K1ABC"     # from file
    assert dst.get("local_only") == 42        # preserved


def test_import_bad_file_safe(tmp_path):
    c = _cfg(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid", encoding="utf-8")
    assert c.import_from(bad) is False        # no raise
    missing = tmp_path / "nope.json"
    assert c.import_from(missing) is False


def test_export_omits_internal_keys(tmp_path):
    c = _cfg(tmp_path)
    c._data["_comment"] = "internal"
    c.set("callsign", "N0CALL")
    out = tmp_path / "x.json"
    c.export_to(out)
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "_comment" not in data
