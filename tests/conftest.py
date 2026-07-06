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
# Squelch test configuration
import os
import sys
from pathlib import Path

import pytest

# Ensure squelch root is on the path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent))

# Run Qt fully headless by default (no display needed).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _set_defaults(fn, defaults) -> bool:
    """Best-effort set of a function's __defaults__ (used to redirect a bare
    Config()/SignalStore() to a temp path during the test session)."""
    try:
        fn.__defaults__ = defaults
    except Exception:
        return False
    return True


@pytest.fixture(scope="session", autouse=True)
def _guard_user_config_writes():
    """Never let the test suite WRITE the real user config
    (%APPDATA%/Squelch/config.json). A settings test builds `Config()` and
    saves a (Munich) GPS fix through it — running the suite on a user's machine
    was overwriting their saved station location.

    We can't globally redirect `Config()` (an unconfigured temp config makes
    MainWindow-building tests block on the first-run / legal-ack modals), so
    instead we make `Config.save()` a no-op *only* when it would write the real
    user config path. Tests that save to an explicit temp path are unaffected.
    """
    try:
        import core.config as cfgmod
    except Exception:
        yield
        return
    real = cfgmod.CONFIG_PATH
    orig_save = cfgmod.Config.save

    def _guarded_save(self, *a, **kw):
        try:
            is_real = Path(self._path).resolve() == Path(real).resolve()
        except Exception:
            is_real = False
        if is_real:
            return None                # refuse to clobber the real user config
        return orig_save(self, *a, **kw)

    cfgmod.Config.save = _guarded_save
    yield
    cfgmod.Config.save = orig_save


@pytest.fixture(scope="session", autouse=True)
def _isolate_signal_store():
    """Never let the test suite write the real signal DB (LOG_DIR/signals.db).

    A signal-ID panel test bookmarks 200+ signals through get_signal_store(),
    which accumulated hundreds of phantom rows in users' real signals.db across
    qa_check runs (same class of bug as the config one above). Point the
    process-wide store at an in-memory DB for the whole run, and default any
    bare SignalStore() to :memory: too.
    """
    try:
        import core.signal_model as sm
    except Exception:
        yield
        return
    orig_instance = sm._instance
    orig_defaults = sm.SignalStore.__init__.__defaults__
    sm._instance = sm.SignalStore(":memory:")
    _set_defaults(sm.SignalStore.__init__, (":memory:",))
    yield
    sm._instance = orig_instance
    _set_defaults(sm.SignalStore.__init__, orig_defaults)


@pytest.fixture(scope="session", autouse=True)
def _ensure_qapplication():
    """Guarantee a single QApplication exists for the whole test session.

    Constructing any QWidget without a live QApplication is undefined behaviour
    and segfaults under the offscreen platform (it took down the entire run when
    a widget-building test executed with no app). This autouse session fixture
    makes every test safe; it is a no-op when PyQt6 is absent (those tests skip).
    """
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        yield None
        return
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
