from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for DSP block framework (offline — no hardware)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

class TestBlockBase:
    def test_block_key_and_name(self):
        from dsp.block import Block
        class MyBlock(Block):
            key  = "my_test_block"
            name = "My Test Block"
        b = MyBlock()
        assert b.key  == "my_test_block"
        assert b.name == "My Test Block"

    def test_param_set_and_get(self):
        from dsp.block import Block, ParamDef
        class MyBlock(Block):
            key    = "test_params"
            name   = "Test"
            params = [ParamDef("gain", "Gain",
                                "float", 1.0)]
        b = MyBlock()
        assert b.get("gain") == 1.0
        b.set("gain", 2.5)
        assert b.get("gain") == 2.5

    def test_param_int_coercion(self):
        from dsp.block import Block, ParamDef
        class MyBlock(Block):
            key    = "test_int"
            name   = "Test"
            params = [ParamDef("taps","Taps","int",64)]
        b = MyBlock()
        b.set("taps", "128")
        assert b.get("taps") == 128
        assert isinstance(b.get("taps"), int)

    def test_param_min_max_clamp(self):
        from dsp.block import Block, ParamDef
        class MyBlock(Block):
            key    = "test_clamp"
            name   = "Test"
            params = [ParamDef("val","Val","int",0,
                                min_val=0, max_val=10)]
        b = MyBlock()
        b.set("val", 999)
        assert b.get("val") == 10
        b.set("val", -5)
        assert b.get("val") == 0

    def test_to_dict_and_back(self):
        from dsp.block import Block, ParamDef
        class MyBlock(Block):
            key    = "test_serial"
            name   = "Test"
            params = [ParamDef("x","X","float",1.5)]
        b = MyBlock()
        b.set("x", 3.14)
        d = b.to_dict()
        assert d["key"] == "test_serial"
        assert d["params"]["x"] == 3.14

    def test_not_running_by_default(self):
        from dsp.block import Block
        class MyBlock(Block):
            key = "test_run"; name = "Test"
        b = MyBlock()
        assert not b.is_running()


class TestSyncBlock:
    def test_passthrough(self):
        from dsp.block import SyncBlock, PortDef, PortType
        class PassBlock(SyncBlock):
            key     = "pass"
            name    = "Pass"
            inputs  = [PortDef("in",  PortType.CF32)]
            outputs = [PortDef("out", PortType.CF32)]
        b = PassBlock()
        try:
            import numpy as np
            x = np.ones(16, dtype=np.complex64)
            result = {}
            b.work({"in": x}, result)
            assert "out" in result
        except ImportError:
            pytest.skip("numpy not installed")


class TestRegistry:
    def test_get_registry(self):
        from dsp.registry import get_registry
        r = get_registry()
        assert r is not None

    def test_block_count(self):
        from dsp.registry import get_registry
        r = get_registry()
        # Should have at least the builtin blocks
        assert len(r) >= 10

    def test_find_soapy_source(self):
        from dsp.registry import get_registry
        r   = get_registry()
        cls = r.get("soapy_source")
        assert cls is not None
        assert cls.name == "SDR Source (SoapySDR)"

    def test_find_wfm_demod(self):
        from dsp.registry import get_registry
        r   = get_registry()
        cls = r.get("wfm_demod")
        assert cls is not None

    def test_by_category(self):
        from dsp.registry import get_registry
        by_cat = get_registry().by_category()
        assert "Sources"      in by_cat
        assert "Processing"   in by_cat
        assert "Demodulators" in by_cat
        assert "Sinks"        in by_cat

    def test_search(self):
        from dsp.registry import get_registry
        results = get_registry().search("fm")
        assert len(results) >= 2   # WFM + NFM at least

    def test_all_blocks_instantiate(self):
        from dsp.registry import get_registry
        for cls in get_registry().all_blocks():
            b = cls()
            assert b is not None


class TestFlowGraph:
    def test_empty_graph(self):
        from dsp.flowgraph import FlowGraph
        fg = FlowGraph()
        assert not fg.is_running
        assert fg.uptime == 0.0

    def test_add_blocks(self):
        from dsp.flowgraph import FlowGraph
        from dsp.registry import get_registry
        fg = FlowGraph()
        src = get_registry().get("tone_source")()
        snk = get_registry().get("null_sink")()
        fg.add(src)
        fg.add(snk)
        assert len(fg._blocks) == 2

    def test_connect(self):
        from dsp.flowgraph import FlowGraph
        from dsp.registry import get_registry
        fg  = FlowGraph()
        src = get_registry().get("tone_source")()
        snk = get_registry().get("null_sink")()
        fg.connect(src, "out", snk, "in")
        assert len(fg._connections) == 1

    def test_topo_sort_order(self):
        from dsp.flowgraph import FlowGraph
        from dsp.registry import get_registry
        fg  = FlowGraph()
        src = get_registry().get("tone_source")()
        mul = get_registry().get("multiply_const")()
        snk = get_registry().get("null_sink")()
        fg.connect(src, "out", mul, "in")
        fg.connect(mul, "out", snk, "in")
        order = fg._topo_sort()
        # Source must come before multiply, multiply before sink
        assert order.index(src) < order.index(mul)
        assert order.index(mul) < order.index(snk)

    def test_save_load(self, tmp_path):
        from dsp.flowgraph import FlowGraph
        from dsp.registry import get_registry
        fg1 = FlowGraph()
        src = get_registry().get("tone_source")()
        snk = get_registry().get("null_sink")()
        fg1.connect(src, "out", snk, "in")
        path = tmp_path / "test.sqfg"
        fg1.save(path)
        fg2 = FlowGraph()
        ok  = fg2.load(path)
        assert ok
        assert len(fg2._blocks) == 2


class TestGNURadioCompat:
    def test_gr_block_map_exists(self):
        from dsp.gnuradio_compat import GR_TO_SQUELCH
        assert "osmosdr.source"    in GR_TO_SQUELCH
        assert "analog.wfm_rcv"   in GR_TO_SQUELCH
        assert "analog.nbfm_rx"   in GR_TO_SQUELCH
        assert "audio.sink"       in GR_TO_SQUELCH
        assert "blocks.null_sink" in GR_TO_SQUELCH

    def test_import_result_class(self):
        from dsp.gnuradio_compat import ImportResult
        r = ImportResult()
        assert r.success
        assert r.supported_count == 0

    def test_nonexistent_file(self):
        from dsp.gnuradio_compat import import_grc
        result = import_grc("/nonexistent/file.grc")
        assert result is None
