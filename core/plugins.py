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

from __future__ import annotations
"""Squelch -- core/plugins.py
Plugin system. Discovers, loads, and manages community plugins
from the plugins/ directory.

Plugin structure:
  plugins/
  └── my_plugin/
        ├── plugin.json   metadata
        └── main.py       implements ApexPlugin interface

plugin.json format:
{
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "W4XYZ",
  "description": "Does something cool",
  "apex_min_version": "1.3",
  "hooks": ["on_decode", "on_frequency_change"]
}
"""

import json
import logging
import importlib.util
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

PLUGINS_DIR = Path("plugins")


@dataclass
class PluginMeta:
    name:             str
    version:          str
    author:           str
    description:      str
    apex_min_version: str
    hooks:            list[str]
    directory:        Path
    enabled:          bool = True
    loaded:           bool = False
    error:            str  = ""


class ApexPlugin:
    """
    Base class for Squelch plugins.
    Plugins subclass this and override the hooks they need.
    All hooks are optional — override only what you need.
    """

    # Plugin metadata — override in subclass
    NAME        = "Unnamed Plugin"
    VERSION     = "0.0.0"
    DESCRIPTION = ""

    def __init__(self, apex_api):
        """
        apex_api provides access to Squelch internals.
        See PluginAPI below for available methods.
        """
        self.api = apex_api

    # ── Available hooks ───────────────────────────────────────────────────

    def on_load(self):
        """Called when the plugin is loaded."""
        pass

    def on_unload(self):
        """Called when the plugin is unloaded."""
        pass

    def on_frequency_change(self, freq_hz: int, band: str):
        """Called when the VFO frequency changes."""
        pass

    def on_mode_change(self, mode: str):
        """Called when the operating mode changes."""
        pass

    def on_decode(self, callsign: str, freq_hz: int,
                  mode: str, snr: int, message: str):
        """Called for each decoded digital signal (FT8, PSK31 etc.)"""
        pass

    def on_qso_complete(self, callsign: str, band: str,
                         mode: str, rst_sent: str, rst_rcvd: str):
        """Called when a QSO is logged."""
        pass

    def on_sdr_sample(self, iq_data, sample_rate: int,
                       center_freq: int):
        """
        Called with raw IQ samples from SDR.
        WARNING: Called at high rate — keep processing minimal
        or offload to a thread.
        """
        pass

    def on_spot(self, callsign: str, freq_hz: int,
                 mode: str, snr: int, source: str):
        """Called when a new DX spot arrives."""
        pass

    def on_location_change(self, grid: str,
                            lat: float, lon: float):
        """Called when the operator location changes."""
        pass

    def get_tab(self):
        """
        Return a QWidget to add as a tab in Squelch.
        Return None to not add a tab.
        """
        return None

    def get_menu_items(self) -> list[dict]:
        """
        Return list of menu items to add.
        Format: [{"menu": "Tools", "label": "My Feature",
                   "callback": self.my_callback}]
        """
        return []


class PluginAPI:
    """
    API exposed to plugins for accessing Squelch internals.
    Provides a stable interface — internal implementation
    can change without breaking plugins.
    """

    def __init__(self, rig=None, config=None,
                 log_db=None, location=None):
        self._rig      = rig
        self._config   = config
        self._log_db   = log_db
        self._location = location

    # Rig access
    def get_frequency(self) -> int:
        return self._rig.state.freq_hz if self._rig else 0

    def set_frequency(self, hz: int):
        if self._rig and self._rig.is_connected:
            self._rig.set_freq(hz)

    def get_mode(self) -> str:
        return self._rig.state.mode if self._rig else ""

    def set_ptt(self, tx: bool):
        if self._rig and self._rig.is_connected:
            self._rig.set_ptt(tx)

    # Config access
    def get_config(self, key: str, default=None):
        return self._config.get(key, default) if self._config else default

    def set_config(self, key: str, value):
        if self._config:
            self._config.set(key, value)

    # Location
    def get_grid(self) -> str:
        return self._location.location.grid if self._location else ""

    def get_latlon(self) -> tuple:
        if self._location:
            return (self._location.location.lat,
                    self._location.location.lon)
        return (0.0, 0.0)

    # Log access (read only)
    def get_recent_qsos(self, limit: int = 50) -> list:
        if self._log_db:
            return self._log_db.recent_qsos(limit)
        return []


class PluginManager:
    """
    Discovers and manages Squelch plugins.
    Security: plugins run in the same process — only install
    plugins from trusted sources. Future: sandbox via subprocess.
    """

    def __init__(self):
        self._plugins:  dict[str, ApexPlugin] = {}
        self._meta:     dict[str, PluginMeta] = {}
        self._api:      PluginAPI | None   = None
        self._hooks:    dict[str, list[Callable]] = {}

    def set_api(self, api: PluginAPI):
        self._api = api

    def discover(self) -> list[PluginMeta]:
        """Scan plugins/ directory and return metadata for all found plugins."""
        if not PLUGINS_DIR.exists():
            PLUGINS_DIR.mkdir(parents=True)
            self._create_readme()
            return []

        found = []
        for plugin_dir in PLUGINS_DIR.iterdir():
            if not plugin_dir.is_dir():
                continue
            meta_file = plugin_dir / "plugin.json"
            main_file = plugin_dir / "main.py"
            if not meta_file.exists() or not main_file.exists():
                continue
            try:
                meta_data = json.loads(
                    meta_file.read_text(encoding='utf-8'))
                meta = PluginMeta(
                    name             = str(meta_data.get("name", plugin_dir.name))[:50],
                    version          = str(meta_data.get("version", "0.0.0"))[:20],
                    author           = str(meta_data.get("author", "Unknown"))[:50],
                    description      = str(meta_data.get("description", ""))[:200],
                    apex_min_version = str(meta_data.get("apex_min_version", "1.0")),
                    hooks            = [str(h)[:50] for h in
                                        meta_data.get("hooks", [])[:20]],
                    directory        = plugin_dir,
                )
                self._meta[meta.name] = meta
                found.append(meta)
                log.info(f"Plugin found: {meta.name} v{meta.version}")
            except Exception as e:
                log.warning(f"Plugin metadata error in {plugin_dir}: {e}")

        return found

    def load(self, name: str) -> bool:
        """Load and initialize a plugin by name."""
        meta = self._meta.get(name)
        if not meta:
            return False
        if not meta.enabled:
            return False

        try:
            main_file = meta.directory / "main.py"
            spec = importlib.util.spec_from_file_location(
                f"apex_plugin_{name}", str(main_file))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find ApexPlugin subclass in module
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                        issubclass(attr, ApexPlugin) and
                        attr is not ApexPlugin):
                    plugin_class = attr
                    break

            if not plugin_class:
                raise ValueError("No ApexPlugin subclass found in main.py")

            instance = plugin_class(self._api)
            instance.on_load()
            self._plugins[name] = instance
            meta.loaded = True

            # Register hooks
            for hook in meta.hooks:
                if hook not in self._hooks:
                    self._hooks[hook] = []
                method = getattr(instance, hook, None)
                if method and callable(method):
                    self._hooks[hook].append(method)

            log.info(f"Plugin loaded: {name}")
            return True

        except Exception as e:
            meta.error = str(e)
            log.error(f"Plugin load failed '{name}': {e}")
            return False

    def unload(self, name: str):
        plugin = self._plugins.get(name)
        if plugin:
            try:
                plugin.on_unload()
            except Exception as e:
                log.warning(f"Plugin unload error '{name}': {e}")
            del self._plugins[name]
            meta = self._meta.get(name)
            if meta:
                meta.loaded = False
            # Remove hooks
            for hook_list in self._hooks.values():
                hook_list[:] = [
                    h for h in hook_list
                    if not hasattr(h, '__self__') or
                    h.__self__ is not plugin]
            log.info(f"Plugin unloaded: {name}")

    def load_all(self):
        """Load all discovered enabled plugins."""
        for meta in self.discover():
            if meta.enabled:
                self.load(meta.name)

    def fire(self, hook: str, *args, **kwargs):
        """Fire a hook to all loaded plugins that registered it."""
        for cb in self._hooks.get(hook, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                log.warning(f"Plugin hook '{hook}' error: {e}")

    def get_plugin_tabs(self) -> list[tuple[str, Any]]:
        """Return (name, widget) for all plugins that provide a tab."""
        tabs = []
        for name, plugin in self._plugins.items():
            try:
                widget = plugin.get_tab()
                if widget is not None:
                    tabs.append((name, widget))
            except Exception as e:
                log.warning(f"Plugin tab error '{name}': {e}")
        return tabs

    def get_menu_items(self) -> list[dict]:
        items = []
        for name, plugin in self._plugins.items():
            try:
                items.extend(plugin.get_menu_items())
            except Exception as e:
                log.warning(f"Plugin menu error '{name}': {e}")
        return items

    @property
    def loaded_plugins(self) -> dict[str, ApexPlugin]:
        return dict(self._plugins)

    @property
    def all_meta(self) -> dict[str, PluginMeta]:
        return dict(self._meta)

    def _create_readme(self):
        readme = PLUGINS_DIR / "README.md"
        readme.write_text(
            "# Squelch Plugins\n\n"
            "Place community plugins in subdirectories here.\n\n"
            "Each plugin needs:\n"
            "- `plugin.json` — metadata\n"
            "- `main.py` — implements `ApexPlugin` subclass\n\n"
            "See `core/plugins.py` for the full API reference.\n\n"
            "**Security note:** Plugins run with full access to\n"
            "Squelch internals. Only install plugins from trusted sources.\n",
            encoding='utf-8')


# Module-level singleton
_manager: PluginManager | None = None

def get_plugin_manager() -> PluginManager:
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager
