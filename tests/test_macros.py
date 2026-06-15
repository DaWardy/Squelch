"""Tests for core/macros.py — F-key TX macro manager."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def _mock_cfg(**overrides):
    cfg = MagicMock()
    store = {
        "macros.f1.label": None,
        "macros.f1.text": None,
        "guest.active": False,
        "session.dx_callsign": "K1ABC",
        "session.vfo_a_mhz": "14.074",
        "session.mode": "FT8",
        "operator.name": "",
        "session.serial": 7,
        **overrides,
    }
    cfg.get.side_effect = lambda k, default=None: store.get(k, default)
    cfg.callsign = "W1AW"
    return cfg


def test_defaults_returned_when_not_configured():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    m = mgr.get("f1")
    assert m["label"] == "CQ"
    assert "{mycall}" in m["text"]


def test_expand_replaces_mycall():
    from core.macros import MacroManager
    cfg = _mock_cfg()
    mgr = MacroManager(cfg)
    result = mgr.expand("CQ DE {mycall} K")
    assert "W1AW" in result
    assert "{mycall}" not in result


def test_expand_replaces_theircall():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    result = mgr.expand("{theircall} DE {mycall}")
    assert "K1ABC" in result


def test_expand_replaces_serial():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    result = mgr.expand("599 {serial}")
    assert "7" in result


def test_expand_leaves_unknown_vars():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    result = mgr.expand("hello {unknownvar} world")
    assert "{unknownvar}" in result


def test_set_persists_and_get_returns_saved():
    from core.macros import MacroManager
    store: dict = {}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, default=None: store.get(k, default)
    cfg.set.side_effect = lambda k, v: store.update({k: v})
    cfg.callsign = "W1AW"
    mgr = MacroManager(cfg)
    mgr.set("f3", "MyTU", "TU 73 {mycall}")
    assert mgr.get("f3")["label"] == "MyTU"
    assert "TU 73" in mgr.get("f3")["text"]


def test_all_macros_returns_eight_entries():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    macros = mgr.all_macros()
    assert len(macros) == 8
    assert macros[0][0] == "f1"
    assert macros[7][0] == "f8"


def test_context_override_in_expand():
    from core.macros import MacroManager
    mgr = MacroManager(_mock_cfg())
    result = mgr.expand("{theircall} QSL", context={"theircall": "VE3XYZ"})
    assert "VE3XYZ" in result


def test_serial_auto_increments_on_send():
    from core.macros import MacroManager
    store = {"session.serial": 5}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: store.get(k, d)
    cfg.set.side_effect = lambda k, v: store.update({k: v})
    cfg.save = MagicMock()
    cfg.callsign = "W1AW"
    mgr = MacroManager(cfg)
    r1 = mgr.expand("{mycall} 599 {serial}", auto_increment_serial=True)
    assert "5" in r1
    assert store["session.serial"] == 6, "serial not incremented"
    r2 = mgr.expand("{mycall} 599 {serial}", auto_increment_serial=True)
    assert "6" in r2
    assert store["session.serial"] == 7


def test_serial_not_incremented_on_preview():
    from core.macros import MacroManager
    store = {"session.serial": 3}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: store.get(k, d)
    cfg.set.side_effect = lambda k, v: store.update({k: v})
    cfg.save = MagicMock()
    cfg.callsign = "W1AW"
    mgr = MacroManager(cfg)
    mgr.expand("{serial}", auto_increment_serial=False)
    assert store.get("session.serial") == 3, "serial changed on preview"


def test_expand_uses_guest_callsign_in_guest_mode():
    """When guest mode is active, {mycall} must expand to the guest callsign."""
    from core.macros import MacroManager
    cfg = _mock_cfg(**{
        "guest.active":   True,
        "guest.callsign": "KE2XYZ",
    })
    mgr = MacroManager(cfg)
    result = mgr.expand("CQ DE {mycall} K")
    assert "KE2XYZ" in result
    assert "W1AW" not in result
