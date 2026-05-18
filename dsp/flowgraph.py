from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/flowgraph.py
FlowGraph: connects Blocks and drives the execution loop.

Topology is a directed acyclic graph (DAG):
  SourceBlock → ProcessBlock → ... → SinkBlock

Execution:
  1. Topological sort of blocks
  2. Sources generate samples each tick
  3. Each downstream block pulls from upstream and calls work()
  4. Sinks consume final output
  5. Runs at ~1000 Hz, limited by hardware source rate
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class Connection:
    """A wired connection: src_block.port → dst_block.port."""
    __slots__ = ("src", "src_port", "dst", "dst_port")

    def __init__(self, src, src_port: str,
                 dst, dst_port: str):
        self.src      = src
        self.src_port = src_port
        self.dst      = dst
        self.dst_port = dst_port

    def to_dict(self) -> dict:
        return {
            "src":      id(self.src),
            "src_port": self.src_port,
            "dst":      id(self.dst),
            "dst_port": self.dst_port,
        }


class FlowGraph:
    """
    Container for a signal processing flowgraph.
    Manages blocks, connections, and the execution thread.
    """

    def __init__(self):
        self._blocks:      list           = []
        self._connections: list[Connection] = []
        self._running:     bool           = False
        self._thread:      threading.Thread | None = None
        self._lock         = threading.Lock()
        self._on_error:    Callable | None = None
        self._on_status:   Callable | None = None
        self._tick_hz:     float          = 20.0  # work() calls/sec
        self._stats = {
            "ticks":        0,
            "dropped":      0,
            "error_count":  0,
            "started_at":   0.0,
        }

    # ── Block management ──────────────────────────────────────────────────

    def add(self, block) -> "FlowGraph":
        """Add a block to the flowgraph."""
        if block not in self._blocks:
            self._blocks.append(block)
        return self

    def remove(self, block):
        """Remove a block and all its connections."""
        self._blocks = [b for b in self._blocks
                        if b is not block]
        self._connections = [
            c for c in self._connections
            if c.src is not block and c.dst is not block]

    def connect(self, src, src_port: str,
                dst, dst_port: str) -> "FlowGraph":
        """
        Wire src.src_port → dst.dst_port.
        Fluent: fg.connect(a, "out", b, "in")
        """
        # Auto-add blocks if not present
        self.add(src)
        self.add(dst)

        # Remove existing connection to dst_port
        self._connections = [
            c for c in self._connections
            if not (c.dst is dst and
                    c.dst_port == dst_port)]

        self._connections.append(
            Connection(src, src_port, dst, dst_port))
        return self

    def disconnect(self, src=None, dst=None):
        self._connections = [
            c for c in self._connections
            if not (
                (src is None or c.src is src) and
                (dst is None or c.dst is dst))]

    def clear(self):
        self._blocks.clear()
        self._connections.clear()

    # ── Topology ──────────────────────────────────────────────────────────

    def _topo_sort(self) -> list:
        """
        Kahn's algorithm — topological sort.
        Returns blocks in execution order (sources first).
        """
        in_degree = {b: 0 for b in self._blocks}
        adj: dict = {b: [] for b in self._blocks}

        for c in self._connections:
            if c.src in adj and c.dst in in_degree:
                adj[c.src].append(c.dst)
                in_degree[c.dst] += 1

        queue = [b for b, deg in in_degree.items()
                 if deg == 0]
        order = []
        while queue:
            b = queue.pop(0)
            order.append(b)
            for nxt in adj[b]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(order) != len(self._blocks):
            log.warning("Flowgraph has cycles — "
                        "running partial order")
        return order

    def _build_input_map(self, block) -> dict:
        """Gather all input arrays for a block."""
        inputs = {}
        for c in self._connections:
            if c.dst is block:
                data = c.src.get_output(c.src_port)
                if data is not None:
                    inputs[c.dst_port] = data
        return inputs

    # ── Execution ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start the flowgraph execution thread."""
        if self._running:
            return True
        if not self._blocks:
            return False

        # Start all blocks
        for block in self._blocks:
            try:
                if not block.start():
                    log.error(
                        f"Block {block.name} refused to start")
                    return False
            except Exception as e:
                log.error(f"Block {block.name} start: {e}")
                return False

        self._stats["started_at"] = time.time()
        self._stats["ticks"]      = 0
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_loop,
            daemon=True, name="FlowGraph")
        self._thread.start()
        self._notify_status("running")
        log.info(
            f"FlowGraph started: "
            f"{len(self._blocks)} blocks")
        return True

    def stop(self):
        """Stop the flowgraph."""
        self._running = False
        for block in self._blocks:
            try:
                block.stop()
            except Exception:
                pass
        self._notify_status("stopped")
        log.info("FlowGraph stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def uptime(self) -> float:
        if not self._stats["started_at"]:
            return 0.0
        return time.time() - self._stats["started_at"]

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def _run_loop(self):
        """Main execution loop — topo-sorted work() calls."""
        order    = self._topo_sort()
        interval = 1.0 / self._tick_hz

        while self._running:
            t0 = time.time()
            try:
                self._tick(order)
                self._stats["ticks"] += 1
            except Exception as e:
                self._stats["error_count"] += 1
                log.warning(f"FlowGraph tick: {e}")
                if self._on_error:
                    try:
                        self._on_error(str(e))
                    except Exception:
                        pass
            elapsed = time.time() - t0
            sleep   = interval - elapsed
            if sleep > 0:
                time.sleep(sleep)

        self._running = False

    def _tick(self, order: list):
        """One execution tick — drive each block once."""
        from dsp.block import SourceBlock, SinkBlock

        for block in order:
            if isinstance(block, SourceBlock):
                # Source generates samples
                outputs = {}
                try:
                    outputs = block.generate(block.CHUNK)
                except Exception as e:
                    log.debug(
                        f"{block.name} generate: {e}")
                for port, data in outputs.items():
                    block.push_output(port, data)

            elif isinstance(block, SinkBlock):
                # Sink consumes from upstream
                inputs = self._build_input_map(block)
                if inputs:
                    try:
                        block.consume(inputs)
                    except Exception as e:
                        log.debug(
                            f"{block.name} consume: {e}")

            else:
                # Processing block
                inputs = self._build_input_map(block)
                if inputs:
                    outputs = {}
                    try:
                        block.work(inputs, outputs)
                    except Exception as e:
                        log.debug(
                            f"{block.name} work: {e}")
                    for port, data in outputs.items():
                        block.push_output(port, data)

    # ── Serialization ─────────────────────────────────────────────────────

    def save(self, path: Path):
        """Save flowgraph to JSON."""
        block_ids = {id(b): i
                     for i, b in enumerate(self._blocks)}
        data = {
            "version":  "1.0",
            "blocks":   [
                {"id":    block_ids[id(b)],
                 "key":   b.key,
                 "params": dict(b._params),
                 "pos":   getattr(b, "_canvas_pos", [0, 0])}
                for b in self._blocks],
            "connections": [
                {"src":      block_ids.get(id(c.src), -1),
                 "src_port": c.src_port,
                 "dst":      block_ids.get(id(c.dst), -1),
                 "dst_port": c.dst_port}
                for c in self._connections],
        }
        Path(path).write_text(
            json.dumps(data, indent=2))
        log.info(f"FlowGraph saved: {path}")

    def load(self, path: Path,
             registry=None) -> bool:
        """Load flowgraph from JSON."""
        try:
            data = json.loads(Path(path).read_text())
        except Exception as e:
            log.error(f"FlowGraph load: {e}")
            return False

        if registry is None:
            from dsp.registry import get_registry
            registry = get_registry()

        self.clear()
        id_to_block = {}

        for bd in data.get("blocks", []):
            key = bd.get("key", "")
            cls = registry.get(key)
            if cls is None:
                log.warning(
                    f"Unknown block: {key}")
                continue
            block = cls()
            for k, v in bd.get("params", {}).items():
                block.set(k, v)
            block._canvas_pos = bd.get("pos", [0, 0])
            id_to_block[bd["id"]] = block
            self._blocks.append(block)

        for cd in data.get("connections", []):
            src = id_to_block.get(cd["src"])
            dst = id_to_block.get(cd["dst"])
            if src and dst:
                self.connect(
                    src, cd["src_port"],
                    dst, cd["dst_port"])

        log.info(
            f"FlowGraph loaded: "
            f"{len(self._blocks)} blocks, "
            f"{len(self._connections)} connections")
        return True

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_error(self, cb: Callable):
        self._on_error = cb

    def on_status(self, cb: Callable):
        self._on_status = cb

    def _notify_status(self, status: str):
        if self._on_status:
            try:
                self._on_status(status)
            except Exception:
                pass
