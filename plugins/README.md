# Squelch Plugins

Place community plugins in subdirectories here.

## Plugin Structure

```
plugins/
└── my_plugin/
      ├── plugin.json   ← metadata
      └── main.py       ← implements ApexPlugin subclass
```

## plugin.json Format

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "W4XYZ",
  "description": "Does something useful",
  "squelch_min_version": "0.7.0",
  "hooks": ["on_decode", "on_frequency_change"]
}
```

## Available Hooks

| Hook | Called when |
|------|-------------|
| `on_load()` | Plugin is loaded |
| `on_unload()` | Plugin is unloaded |
| `on_frequency_change(hz, band)` | VFO frequency changes |
| `on_mode_change(mode)` | Operating mode changes |
| `on_decode(callsign, freq, mode, snr, msg)` | Digital signal decoded |
| `on_qso_complete(call, band, mode, rst_s, rst_r)` | QSO logged |
| `on_sdr_sample(iq, sample_rate, center_hz)` | IQ samples available |
| `on_spot(call, freq, mode, snr, source)` | DX spot received |
| `on_location_change(grid, lat, lon)` | Operator location changes |
| `get_tab()` | Return QWidget to add as a tab |
| `get_menu_items()` | Return menu items to add |

## Plugin API

```python
from core.plugins import ApexPlugin

class MyPlugin(ApexPlugin):
    NAME = "My Plugin"
    VERSION = "1.0.0"

    def on_load(self):
        print(f"Loaded at {self.api.get_frequency()} Hz")

    def on_decode(self, callsign, freq, mode, snr, msg):
        print(f"Decoded: {callsign} on {freq/1e6:.3f} MHz")

    def on_qso_complete(self, callsign, band, mode,
                        rst_sent, rst_rcvd):
        # Example: post to an external service
        pass

    def get_tab(self):
        from PyQt6.QtWidgets import QLabel
        return QLabel(f"Hello from {self.NAME}!")
```

## API Reference

The `self.api` object provides:

```python
# Rig control
self.api.get_frequency() -> int      # Hz
self.api.set_frequency(hz: int)
self.api.get_mode() -> str
self.api.set_ptt(tx: bool)

# Location
self.api.get_grid() -> str           # e.g. "DM79rr"
self.api.get_latlon() -> (float, float)

# Config
self.api.get_config(key, default=None)
self.api.set_config(key, value)

# Log
self.api.get_recent_qsos(limit=50) -> list
```

## Security Notice

Plugins run with full access to Squelch internals and
your filesystem. Only install plugins from sources you trust.

Future versions will add subprocess sandboxing.

## Example Plugins

See the `example_plugin/` directory for a working example.

## Frequency Hopping Plugin

Interested in implementing frequency hopping follow?
This is the ideal candidate for a community plugin.
The `on_sdr_sample` hook gives you raw IQ data.
Open an issue on GitHub to discuss implementation.
