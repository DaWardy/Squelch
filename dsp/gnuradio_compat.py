from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/gnuradio_compat.py
GNU Radio flowgraph compatibility layer.
Imports .grc (GNU Radio Companion) flowgraph files
and maps their blocks to Squelch DSP blocks where possible.

GNU Radio blocks that map to Squelch blocks:
  blocks.multiply_const_cc  → multiply_const
  freq_xlating_fir_filter_ccc → fir_filter + freq_shift
  rational_resampler_xxx    → decimator
  analog.wfm_rcv            → wfm_demod
  analog.nbfm_rx            → nfm_demod
  analog.am_demod_cf        → am_demod
  audio.sink                → audio_sink
  blocks.file_sink          → iq_file_sink
  blocks.file_source        → iq_file_source
  osmosdr.source            → soapy_source
  blocks.null_sink          → null_sink

Unmapped blocks will be shown as "unsupported" nodes in the UI
but won't break import of the rest of the graph.
"""

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Mapping of GNU Radio block IDs → Squelch block keys
GR_TO_SQUELCH: dict[str, str] = {
    # Sources
    "osmosdr.source":              "soapy_source",
    "osmosdr_source":              "soapy_source",
    "blocks.file_source":          "iq_file_source",
    "blocks_file_source":          "iq_file_source",

    # Processing
    "blocks.multiply_const_cc":    "multiply_const",
    "blocks_multiply_const_cc":    "multiply_const",
    "blocks.multiply_const_vcc":   "multiply_const",
    "freq_xlating_fir_filter_ccc": "fir_filter",
    "rational_resampler_xxx":      "decimator",
    "rational_resampler_ccc":      "decimator",
    "blocks.nlog10_ff":            "fft",

    # Demodulators
    "analog.wfm_rcv":              "wfm_demod",
    "analog_wfm_rcv":              "wfm_demod",
    "analog.nbfm_rx":              "nfm_demod",
    "analog_nbfm_rx":              "nfm_demod",
    "analog.am_demod_cf":          "am_demod",
    "analog_am_demod_cf":          "am_demod",

    # Sinks
    "audio.sink":                  "audio_sink",
    "audio_sink":                  "audio_sink",
    "blocks.file_sink":            "iq_file_sink",
    "blocks_file_sink":            "iq_file_sink",
    "blocks.null_sink":            "null_sink",
    "blocks_null_sink":            "null_sink",
    "qtgui.sink_c":                "waterfall_sink",
    "qtgui.freq_sink_c":           "waterfall_sink",
    "wxgui.fftsink2":              "waterfall_sink",
}

# Parameter name mappings per block type
# (GR param name → Squelch param name)
GR_PARAM_MAP: dict[str, dict[str, str]] = {
    "soapy_source": {
        "center_freq": "freq_hz",
        "freq":        "freq_hz",
        "samp_rate":   "sample_rate",
        "rf_gain":     "gain",
        "corr":        "ppm",
    },
    "fir_filter": {
        "cutoff_freq":  "cutoff",
        "decimation":   "factor",
    },
    "decimator": {
        "decimation":   "factor",
        "decim":        "factor",
    },
    "wfm_demod": {
        "quad_rate":    "sample_rate",
        "audio_decimation": "decimation",
    },
    "nfm_demod": {
        "quad_rate":    "sample_rate",
        "audio_decimation": "decimation",
        "max_dev":      "deviation",
    },
    "audio_sink": {
        "samp_rate":    "sample_rate",
        "rate":         "sample_rate",
    },
    "iq_file_source": {
        "file":         "filename",
        "repeat":       "loop",
    },
    "iq_file_sink": {
        "file":         "filename",
    },
}


def import_grc(path: str) -> Optional["ImportResult"]:
    """
    Import a GNU Radio Companion .grc file.
    Returns an ImportResult with blocks, connections, warnings.
    Returns None if the file cannot be parsed.
    """
    p = Path(path)
    if not p.exists():
        log.error(f"GRC file not found: {path}")
        return None

    try:
        if p.suffix == ".grc":
            return _import_yaml_grc(p)
        elif p.suffix == ".json":
            return _import_json_grc(p)
        else:
            log.warning(
                f"Unknown GRC format: {p.suffix}")
            return None
    except Exception as e:
        log.error(f"GRC import: {e}")
        return None


def _parse_grc_block(block_data: dict, result: "ImportResult") -> None:
    """Parse one GRC block entry into *result*."""
    btype = block_data.get("id", "")
    squelch_key = GR_TO_SQUELCH.get(
        btype, GR_TO_SQUELCH.get(btype.replace(".", "_"), None))
    bid = block_data.get("name",
                         block_data.get("id", str(len(result.blocks))))
    pos = block_data.get("states", {}).get("coordinate", [0, 0])

    if squelch_key:
        param_map = GR_PARAM_MAP.get(squelch_key, {})
        params: dict = {}
        for p in block_data.get("parameters", []):
            pname = p.get("id", "")
            pval  = p.get("value", "")
            squelch_pname = param_map.get(pname, pname)
            try:
                pval = float(pval)
                if pval == int(pval):
                    pval = int(pval)
            except (ValueError, TypeError):
                pass
            params[squelch_pname] = pval
        result.blocks[bid] = {
            "key": squelch_key, "params": params,
            "pos": pos, "gr_id": btype}
    else:
        result.warnings.append(
            f"Unsupported block: {btype} ({bid}) — shown as placeholder")
        result.unsupported.append(btype)
        result.blocks[bid] = {
            "key": "_unsupported", "params": {"gr_type": btype},
            "pos": pos, "gr_id": btype}


def _parse_grc_connections(data: dict, result: "ImportResult") -> None:
    """Parse connection list from *data* into *result*."""
    for conn in data.get("connections", []):
        if isinstance(conn, list) and len(conn) == 4:
            src, src_port, dst, dst_port = conn
            result.connections.append({
                "src": src, "src_port": str(src_port),
                "dst": dst, "dst_port": str(dst_port)})


def _import_yaml_grc(path: Path) -> "ImportResult":
    """Import YAML-format .grc file (GNU Radio 3.8+)."""
    result = ImportResult()
    try:
        import yaml
        data = yaml.safe_load(path.read_text())
    except ImportError:
        result.warnings.append(
            "PyYAML not installed — basic GRC parsing "
            "may miss some blocks. pip install pyyaml")
        data = _parse_grc_basic(path.read_text())
    except Exception as e:
        result.errors.append(f"YAML parse: {e}")
        return result

    for block_data in data.get("blocks", []):
        _parse_grc_block(block_data, result)
    _parse_grc_connections(data, result)

    result.source_file = str(path)
    result.gr_version  = data.get(
        "metadata", {}).get("file_format", "unknown")
    return result


def _import_json_grc(path: Path) -> "ImportResult":
    """Import JSON-format flowgraph."""
    data   = json.loads(path.read_text())
    result = ImportResult()
    result.source_file = str(path)

    for block in data.get("blocks", []):
        btype = block.get("id", "")
        squelch_key = GR_TO_SQUELCH.get(btype)
        bid   = block.get("name", str(len(result.blocks)))
        if squelch_key:
            result.blocks[bid] = {
                "key":    squelch_key,
                "params": block.get("params", {}),
                "pos":    block.get("pos", [0, 0]),
                "gr_id":  btype,
            }
        else:
            result.warnings.append(
                f"Unsupported: {btype}")
            result.unsupported.append(btype)

    for c in data.get("connections", []):
        result.connections.append(c)

    return result


def _parse_grc_basic(text: str) -> dict:
    """Very basic GRC YAML parser (no PyYAML)."""
    # Just extract block IDs for a warning
    import re
    blocks = []
    for m in re.finditer(r"id:\s*(\S+)", text):
        blocks.append({"id": m.group(1), "parameters": []})
    return {"blocks": blocks, "connections": []}


class ImportResult:
    """Result of a GRC import."""

    def __init__(self):
        self.blocks:      dict[str, dict] = {}
        self.connections: list[dict]      = []
        self.warnings:    list[str]       = []
        self.errors:      list[str]       = []
        self.unsupported: list[str]       = []
        self.source_file: str             = ""
        self.gr_version:  str             = ""

    @property
    def success(self) -> bool:
        return not self.errors

    @property
    def supported_count(self) -> int:
        return len([b for b in self.blocks.values()
                    if b["key"] != "_unsupported"])

    @property
    def unsupported_count(self) -> int:
        return len([b for b in self.blocks.values()
                    if b["key"] == "_unsupported"])

    def to_flowgraph(self,
                     registry=None) -> Optional["FlowGraph"]:
        """Convert import result to a live FlowGraph."""
        from dsp.flowgraph import FlowGraph
        if registry is None:
            from dsp.registry import get_registry
            registry = get_registry()

        fg        = FlowGraph()
        id_to_blk = {}

        for bid, bdata in self.blocks.items():
            key = bdata["key"]
            if key == "_unsupported":
                continue
            cls = registry.get(key)
            if cls is None:
                self.warnings.append(
                    f"Block not in registry: {key}")
                continue
            blk = cls()
            for pname, pval in bdata.get(
                    "params", {}).items():
                try:
                    blk.set(pname, pval)
                except Exception:
                    pass
            blk._canvas_pos = bdata.get("pos", [0, 0])
            id_to_blk[bid]  = blk
            fg.add(blk)

        for c in self.connections:
            src = id_to_blk.get(c.get("src"))
            dst = id_to_blk.get(c.get("dst"))
            if src and dst:
                fg.connect(
                    src, c.get("src_port", "out"),
                    dst, c.get("dst_port", "in"))

        return fg

    def summary(self) -> str:
        lines = [
            f"GRC import: {self.source_file}",
            f"  Blocks: {self.supported_count} supported, "
            f"{self.unsupported_count} unsupported",
            f"  Connections: {len(self.connections)}",
        ]
        if self.warnings:
            lines.append(
                f"  Warnings ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"    • {w}")
        if self.unsupported:
            uniq = sorted(set(self.unsupported))
            lines.append(
                "  Unsupported block types:")
            for u in uniq[:8]:
                lines.append(f"    • {u}")
        return "\n".join(lines)
