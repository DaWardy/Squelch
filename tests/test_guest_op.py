# Squelch tests — guest operator support (students/visitors)
# Licensed under GNU GPL v3
from __future__ import annotations
"""Guest operator: callsign handling + contact script. TX is NOT blocked."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_phonetic_spelling():
    from core.guest_op import phonetic
    assert phonetic("W1AW") == "Whiskey One Alpha Whiskey"
    assert phonetic("KE2XYZ").startswith("Kilo Echo Two")

def test_script_includes_guest_call_phonetically():
    from core.guest_op import voice_contact_script
    s = voice_contact_script("KE2XYZ", "W1AW", "EM73", supervised=True)
    assert "Kilo Echo Two" in s          # guest call in phonetics
    assert "W1AW" in s                    # station call for ID
    assert "CQ" in s                      # has a calling-CQ section
    assert "73" in s                      # has an ending

def test_script_supervised_note():
    from core.guest_op import voice_contact_script
    sup = voice_contact_script("KE2XYZ", "W1AW", supervised=True)
    unsup = voice_contact_script("KE2XYZ", "W1AW", supervised=False)
    assert "control operator" in sup
    assert "control operator" not in unsup

def test_guest_mode_does_not_block_transmit():
    """Critical: guest operator mode must NOT disable TX (students transmit)."""
    from core.safety import SafetyManager
    s = SafetyManager()
    # Guest operating is a normal TX state — only Demo mode blocks TX.
    assert s.can_transmit() is True
    s.set_demo_mode(True)
    assert s.can_transmit() is False     # demo blocks
    s.set_demo_mode(False)
    assert s.can_transmit() is True


def test_operating_callsign_all_modes():
    """operating_callsign() is the single source of truth for every mode."""
    from core.guest_op import operating_callsign
    class Cfg:
        callsign = "W1AW"
        def __init__(self): self._d = {}
        def get(self, k, d=None): return self._d.get(k, d)
    cfg = Cfg()
    # No guest -> station call
    assert operating_callsign(cfg) == "W1AW"
    # Guest active -> guest call (applies to ALL modes, not just FT8)
    cfg._d["guest.active"] = True
    cfg._d["guest.callsign"] = "ke2xyz"
    assert operating_callsign(cfg) == "KE2XYZ"
