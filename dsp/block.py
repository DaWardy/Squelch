from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/block.py
Signal processing block base class.
Every block in the flowgraph inherits from Block.
Blocks connect to each other through typed Ports.
Data flows as numpy arrays between blocks.

Port types:
  CF32   — complex float32 (IQ samples)     → shape (N,)
  F32    — float32 (audio, magnitude)       → shape (N,)
  F32S   — float32 stereo (L+R interleaved) → shape (2N,)
  U8     — uint8 bytes (raw bytes)          → shape (N,)

Similar to GNU Radio's block hierarchy:
  Block          → gr::block
  SyncBlock      → gr::sync_block  (1 input = 1 output sample)
  DecimBlock     → gr::sync_decimator
  InterpBlock    → gr::sync_interpolator
  SourceBlock    → gr::source
  SinkBlock      → gr::sink
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional
import queue

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── Port types ────────────────────────────────────────────────────────────

class PortType(Enum):
    CF32 = auto()   # complex IQ samples
    F32  = auto()   # real float (audio, power)
    F32S = auto()   # stereo float (interleaved L+R)
    U8   = auto()   # raw bytes

PORT_DTYPE = {
    PortType.CF32: "complex64",
    PortType.F32:  "float32",
    PortType.F32S: "float32",
    PortType.U8:   "uint8",
}

PORT_LABEL = {
    PortType.CF32: "IQ",
    PortType.F32:  "Float",
    PortType.F32S: "Stereo",
    PortType.U8:   "Bytes",
}

PORT_COLOR = {
    PortType.CF32: "#4488ff",
    PortType.F32:  "#44cc44",
    PortType.F32S: "#44ccaa",
    PortType.U8:   "#cc8844",
}


@dataclass
class PortDef:
    """Definition of an input or output port."""
    name:     str
    type:     PortType
    optional: bool = False
    help:     str  = ""


@dataclass
class ParamDef:
    """Definition of a block parameter."""
    name:     str
    label:    str
    type:     str      # "int" / "float" / "str" / "bool" / "choice"
    default:  Any      = None
    choices:  list     = field(default_factory=list)
    units:    str      = ""
    help:     str      = ""
    min_val:  Any      = None
    max_val:  Any      = None


# ── Block base class ──────────────────────────────────────────────────────

class Block:
    """
    Base class for all signal processing blocks.

    Subclasses must implement work():
      def work(self, inputs: dict, outputs: dict):
          iq = inputs["in"]       # CF32 array
          outputs["out"] = iq * self.gain

    Block metadata:
      key:         unique string identifier
      name:        human-readable name
      category:    "Sources" / "Processing" / "Demodulators" / "Sinks"
      description: one-line description for the block browser
      inputs:      list[PortDef]
      outputs:     list[PortDef]
      params:      list[ParamDef]
    """

    # ── Override in subclass ──────────────────────────────
    key:         str         = "block"
    name:        str         = "Block"
    category:    str         = "Processing"
    description: str         = ""
    color:       str         = "#2a2a2a"

    inputs:  list[PortDef]   = []
    outputs: list[PortDef]   = []
    params:  list[ParamDef]  = []

    CHUNK = 4096   # default samples per work() call

    def __init__(self):
        self._params:  dict[str, Any]   = {}
        self._running: bool             = False
        self._error:   str              = ""

        # Initialize params from defaults
        for p in self.params:
            self._params[p.name] = p.default

        # Output queues (one per output port)
        self._out_queues: dict[str, queue.Queue] = {}
        for p in self.outputs:
            self._out_queues[p.name] = queue.Queue(
                maxsize=16)

        # Input connections: port_name → upstream Block
        self._connections: dict[str, tuple["Block", str]] = {}

    # ── Param access ──────────────────────────────────────

    def get(self, name: str, default: Any = None) -> Any:
        return self._params.get(name, default)

    def set(self, name: str, value: Any):
        """Set a parameter. Validates type."""
        for p in self.params:
            if p.name == name:
                if p.type == "int":
                    value = int(value)
                elif p.type == "float":
                    value = float(value)
                elif p.type == "bool":
                    value = bool(value)
                if p.min_val is not None:
                    value = max(p.min_val, value)
                if p.max_val is not None:
                    value = min(p.max_val, value)
                break
        self._params[name] = value
        self.on_param_change(name, value)

    def on_param_change(self, name: str, value: Any):
        """Called when a parameter changes. Override to react."""
        pass

    # ── Lifecycle ─────────────────────────────────────────

    def start(self) -> bool:
        """Called when flowgraph starts. Return False to abort."""
        self._running = True
        self._error   = ""
        return True

    def stop(self):
        """Called when flowgraph stops."""
        self._running = False

    def is_running(self) -> bool:
        return self._running

    @property
    def error(self) -> str:
        return self._error

    # ── Data flow ─────────────────────────────────────────

    def work(self, inputs: dict, outputs: dict):
        """
        Process one chunk of samples.
        inputs:  {port_name: np.ndarray}
        outputs: {port_name: np.ndarray}  ← fill these

        Example (passthrough):
            outputs["out"] = inputs["in"]
        """
        raise NotImplementedError(
            f"{self.name}.work() not implemented")

    def get_output(self, port: str,
                   timeout: float = 0.1):
        """Called by downstream blocks to pull samples."""
        q = self._out_queues.get(port)
        if q is None:
            return None
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def push_output(self, port: str, data):
        """Push processed samples to output queue."""
        q = self._out_queues.get(port)
        if q:
            try:
                q.put_nowait(data)
            except queue.Full:
                try:
                    q.get_nowait()   # drop oldest
                    q.put_nowait(data)
                except Exception:
                    pass

    # ── Serialization ─────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "key":    self.key,
            "params": dict(self._params),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        b = cls()
        for k, v in d.get("params", {}).items():
            b.set(k, v)
        return b

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._params})"


class SourceBlock(Block):
    """Block with outputs only. Generates samples from hardware or files."""
    inputs   = []
    category = "Sources"

    def generate(self, n_samples: int) -> dict:
        """
        Generate n_samples worth of data.
        Returns dict of {port_name: np.ndarray}.
        Override this instead of work().
        """
        raise NotImplementedError


class SinkBlock(Block):
    """Block with inputs only. Consumes samples (audio out, file write)."""
    outputs  = []
    category = "Sinks"

    def consume(self, inputs: dict):
        """
        Consume a chunk of samples.
        Override this instead of work().
        """
        raise NotImplementedError


class SyncBlock(Block):
    """
    1-in / 1-out block. Output length equals input length.
    Override process() with your DSP:
        def process(self, x: np.ndarray) -> np.ndarray:
    """
    category = "Processing"

    def process(self, x):
        return x

    def work(self, inputs, outputs):
        for out_port in self.outputs:
            in_port = self.inputs[0].name \
                if self.inputs else None
            if in_port and in_port in inputs:
                outputs[out_port.name] = self.process(
                    inputs[in_port])


class DecimBlock(SyncBlock):
    """Sync block with integer decimation (output < input)."""
    decimation: int = 1

    def work(self, inputs, outputs):
        for out_port in self.outputs:
            in_port = self.inputs[0].name \
                if self.inputs else None
            if in_port and in_port in inputs:
                x = inputs[in_port]
                outputs[out_port.name] = self.process(x)
