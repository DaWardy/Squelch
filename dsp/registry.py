from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/registry.py
Block registry — discovers and catalogs all available DSP blocks.
Blocks register themselves via @register decorator or auto-discovery.
"""

import logging
from typing import Type, Optional

log = logging.getLogger(__name__)


class BlockRegistry:
    """
    Central registry of all available DSP blocks.
    Used by the flowgraph UI to populate the block browser
    and by the flowgraph loader to instantiate blocks by key.
    """

    def __init__(self):
        self._blocks: dict[str, type] = {}

    def register(self, cls: type) -> type:
        """
        Register a block class. Use as decorator:
            @registry.register
            class MyBlock(SyncBlock): ...
        Or call directly: registry.register(MyBlock)
        """
        key = cls.key
        if key in self._blocks:
            log.debug(
                f"Registry: overwriting {key}")
        self._blocks[key] = cls
        return cls

    def get(self, key: str) -> Optional[type]:
        return self._blocks.get(key)

    def all_blocks(self) -> list[type]:
        return list(self._blocks.values())

    def by_category(self) -> dict[str, list[type]]:
        result: dict[str, list[type]] = {}
        for cls in self._blocks.values():
            cat = getattr(cls, "category", "Other")
            result.setdefault(cat, []).append(cls)
        return result

    def search(self, query: str) -> list[type]:
        q = query.lower()
        return [
            cls for cls in self._blocks.values()
            if q in cls.name.lower() or
               q in getattr(cls, "description", "").lower() or
               q in cls.key.lower()]

    def load_all(self):
        """Import all built-in block modules to trigger registration."""
        modules = [
            "dsp.blocks.sources",
            "dsp.blocks.processing",
            "dsp.blocks.demodulators",
            "dsp.blocks.sinks",
        ]
        for mod in modules:
            try:
                __import__(mod)
                log.debug(f"Loaded block module: {mod}")
            except ImportError as e:
                log.debug(f"Block module {mod}: {e}")
            except Exception as e:
                log.warning(
                    f"Block module {mod} error: {e}")

    def __len__(self) -> int:
        return len(self._blocks)


# Global singleton
_registry: BlockRegistry | None = None


def get_registry() -> BlockRegistry:
    global _registry
    if _registry is None:
        _registry = BlockRegistry()
        _registry.load_all()
    return _registry


def register(cls: type) -> type:
    """Module-level decorator to register a block globally."""
    return get_registry().register(cls)
