from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/flowgraph_tab.py
Visual flowgraph / signal processing pipeline editor.
Advanced mode — build custom DSP chains like GNU Radio.
"""

import logging
import json
from core.themes import get_theme as _fg_get_theme
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QLabel, QPushButton, QComboBox,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QScrollArea, QFrame, QFileDialog,
    QMessageBox, QTextEdit, QLineEdit,
    QFormLayout, QDialog, QDialogButtonBox,
    QTabWidget, QStatusBar, QDoubleSpinBox,
    QSpinBox, QCheckBox, QSizePolicy)
from PyQt6.QtCore import (
    Qt, QTimer, QPointF, QRectF, pyqtSignal)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
    QLinearGradient, QMouseEvent)

log = logging.getLogger(__name__)

PORT_TYPE_COLOR = {
    "CF32": "#4488ff",
    "F32":  "#44cc44",
    "F32S": "#44ccaa",
    "U8":   "#cc8844",
}

CATEGORY_ICONS = {
    "Sources":       "📡",
    "Processing":    "⚙",
    "Demodulators":  "📻",
    "Sinks":         "🔊",
    "Other":         "•",
}


# (block_key, params, [x, y]) chains for each built-in template
_FLOWGRAPH_TEMPLATES: "dict[str, list]" = {
    "FM Broadcast Receiver": [
        ("soapy_source", {"freq_hz": 96_500_000, "sample_rate": 2_048_000}, [0, 0]),
        ("wfm_demod",    {"decimation": 10},                                 [280, 0]),
        ("audio_sink",   {"sample_rate": 48000},                             [560, 0]),
    ],
    "NFM Voice Scanner": [
        ("soapy_source", {"freq_hz": 146_520_000, "sample_rate": 2_048_000}, [0, 0]),
        ("fir_filter",   {"cutoff": 0.02},                                   [280, 0]),
        ("nfm_demod",    {"decimation": 8},                                  [560, 0]),
        ("audio_sink",   {"sample_rate": 48000},                             [840, 0]),
    ],
    "APRS Receiver": [
        ("soapy_source", {"freq_hz": 144_390_000, "sample_rate": 2_048_000}, [0, 0]),
        ("fir_filter",   {"cutoff": 0.025, "taps": 64},                      [280, 0]),
        ("nfm_demod",    {"decimation": 5, "deviation": 3500},               [560, 0]),
        ("audio_sink",   {"sample_rate": 48000},                             [840, 0]),
    ],
    "AM Receiver": [
        ("soapy_source", {"freq_hz": 1_000_000, "sample_rate": 2_048_000},  [0, 0]),
        ("am_demod",     {"decimation": 40},                                 [280, 0]),
        ("audio_sink",   {"sample_rate": 48000},                             [560, 0]),
    ],
    "IQ Recording": [
        ("soapy_source", {"freq_hz": 144_390_000, "sample_rate": 2_048_000}, [0, 0]),
        ("iq_file_sink", {"filename": "aprs_record.iq", "format": "CF32"},  [280, 0]),
    ],
    "Spectrum Monitor": [
        ("soapy_source",  {"freq_hz": 144_000_000, "sample_rate": 2_048_000}, [0, 0]),
        ("fft",           {"fft_size": 2048, "avg": 8},                       [280, 0]),
        ("waterfall_sink", {},                                                 [560, 0]),
    ],
}


class FlowgraphTab(QWidget):
    """
    Advanced DSP flowgraph editor.
    Build signal processing pipelines visually.
    Works like GNU Radio Companion but integrated
    into Squelch with access to the SDR hardware.
    """

    def __init__(self, config, sdr_tab=None,
                 parent=None):
        super().__init__(parent)
        self.cfg     = config
        self._sdr    = sdr_tab
        self._fg     = None
        self._canvas = None
        self._build()
        self._new_graph()

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────
        tb = self._build_toolbar()
        root.addWidget(tb)

        # ── Main area: block browser + canvas + props ────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;}")

        splitter.addWidget(self._build_block_browser())
        splitter.addWidget(self._build_canvas_area())
        splitter.addWidget(self._build_props_panel())
        splitter.setSizes([200, 600, 220])
        root.addWidget(splitter, 1)

        # ── Status bar ───────────────────────────────────────
        self._status = QLabel(
            "New flowgraph — drag blocks from the left panel")
        self._status.setFixedHeight(22)
        self._status.setContentsMargins(8, 0, 0, 0)
        self._status.setStyleSheet(
            "background:#0a0a0a;"
            "font-family:'Courier New';"
            "border-top:1px solid #1a1a1a;")
        root.addWidget(self._status)

    @staticmethod
    def _tb_btn(label: str, tip: str, slot, color: str = "") -> "QPushButton":
        b = QPushButton(label)
        b.setFixedHeight(28)
        b.setToolTip(tip)
        b.clicked.connect(slot)
        if color:
            b.setStyleSheet(f"background:{color};border-radius:3px;")
        return b

    def _build_toolbar_file_buttons(self, l: "QHBoxLayout") -> None:
        self._run_btn = self._tb_btn(
            "▶  Run", "Start the flowgraph", self._toggle_run, "#1a3a1a")
        l.addWidget(self._run_btn)
        l.addWidget(self._tb_btn("New",  "New flowgraph (Ctrl+N)", self._new_graph))
        l.addWidget(self._tb_btn("Open", "Open flowgraph file",    self._open_graph))
        l.addWidget(self._tb_btn("Save", "Save flowgraph",         self._save_graph))
        l.addWidget(self._tb_btn(
            "Import GRC", "Import a GNU Radio Companion .grc file",
            self._import_grc))

    def _build_toolbar_template_selector(self, l: "QHBoxLayout") -> None:
        l.addSpacing(8)
        l.addWidget(QLabel("Template:"))
        self._template_combo = QComboBox()
        self._template_combo.addItems([
            "— select —", "FM Broadcast Receiver", "NFM Voice Scanner",
            "APRS Receiver", "AM Receiver", "IQ Recording", "Spectrum Monitor",
        ])
        self._template_combo.setToolTip("Load a preconfigured flowgraph template")
        self._template_combo.currentTextChanged.connect(self._load_template)
        l.addWidget(self._template_combo)

    def _build_toolbar(self) -> "QFrame":
        _t = _fg_get_theme(self.cfg.get("ui.theme", "Dark"))
        tb = QFrame()
        tb.setFixedHeight(38)
        tb.setStyleSheet(
            f"background:{_t.bg_secondary};border-bottom:1px solid {_t.border};")
        l = QHBoxLayout(tb)
        l.setContentsMargins(6, 4, 6, 4)
        l.setSpacing(4)
        self._build_toolbar_file_buttons(l)
        self._build_toolbar_template_selector(l)
        l.addStretch()
        self._uptime_lbl = QLabel("")
        self._uptime_lbl.setStyleSheet("font-family:'Courier New';")
        l.addWidget(self._uptime_lbl)
        return tb

    def _build_block_browser(self) -> QWidget:
        """Left panel: available blocks grouped by category."""
        panel = QWidget()
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(280)
        l = QVBoxLayout(panel)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(4)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Search blocks…")
        self._search.textChanged.connect(
            self._filter_blocks)
        l.addWidget(self._search)

        # Block tree
        self._block_tree = QTreeWidget()
        self._block_tree.setHeaderLabel("Blocks")
        self._block_tree.setStyleSheet(
            "QTreeWidget{background:#080808;"
            ""
            "border:1px solid #1a1a1a;}"
            "QTreeWidgetItem{padding:2px;}"
            "QTreeWidget::item:selected{"
            "background:#1a2a1a;color:#3fbe6f;}")
        self._block_tree.setDragEnabled(True)
        self._block_tree.itemDoubleClicked.connect(
            self._add_block_from_tree)
        l.addWidget(self._block_tree, 1)

        # "Add to canvas" button
        add_btn = QPushButton("➕ Add Selected")
        add_btn.setToolTip(
            "Add selected block to canvas\\n"
            "Or double-click a block")
        add_btn.clicked.connect(
            lambda: self._add_block_from_tree(
                self._block_tree.currentItem(), 0))
        l.addWidget(add_btn)

        self._populate_block_tree()
        return panel

    def _populate_block_tree(self, query: str = ""):
        self._block_tree.clear()
        try:
            from dsp.registry import get_registry
            registry = get_registry()
            by_cat = registry.by_category()
        except Exception as e:
            log.debug(f"Block registry: {e}")
            return

        for cat, blocks in sorted(by_cat.items()):
            icon = CATEGORY_ICONS.get(cat, "•")
            cat_item = QTreeWidgetItem(
                [f"{icon}  {cat}"])
            cat_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled)
            cat_item.setForeground(
                0, QColor("#3fbe6f"))

            filtered = [b for b in blocks
                        if not query or
                        query.lower() in b.name.lower() or
                        query.lower() in getattr(
                            b, "description", "").lower()]
            for blk_cls in sorted(
                    filtered, key=lambda b: b.name):
                blk_item = QTreeWidgetItem(
                    [blk_cls.name])
                blk_item.setData(
                    0, Qt.ItemDataRole.UserRole,
                    blk_cls.key)
                blk_item.setToolTip(
                    0, getattr(blk_cls,
                                "description", ""))
                cat_item.addChild(blk_item)

            if cat_item.childCount() > 0:
                self._block_tree.addTopLevelItem(
                    cat_item)
                cat_item.setExpanded(True)

    def _filter_blocks(self, query: str):
        self._populate_block_tree(query)

    def _build_canvas_area(self) -> QWidget:
        """Center panel: node editor canvas."""
        outer = QWidget()
        l = QVBoxLayout(outer)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)

        self._canvas = FlowgraphCanvas(self)
        self._canvas.node_selected.connect(
            self._on_node_selected)
        self._canvas.status_msg.connect(
            self._set_status)
        l.addWidget(self._canvas, 1)

        # Mini toolbar under canvas
        mini = QFrame()
        mini.setFixedHeight(28)
        mini.setStyleSheet(
            "background:#080808;"
            "border-top:1px solid #1a1a1a;")
        ml = QHBoxLayout(mini)
        ml.setContentsMargins(4, 2, 4, 2)
        ml.setSpacing(4)

        for label, tip, slot in [
            ("Clear",    "Remove all blocks",
             lambda: self._canvas.clear_all()),
            ("Auto-layout","Arrange blocks neatly",
             lambda: self._canvas.auto_layout()),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            ml.addWidget(b)

        ml.addStretch()
        self._node_count_lbl = QLabel("0 blocks")
        self._node_count_lbl.setStyleSheet(
            "")
        ml.addWidget(self._node_count_lbl)
        l.addWidget(mini)

        return outer

    def _build_props_panel(self) -> QWidget:
        """Right panel: block properties."""
        panel = QWidget()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(300)
        l = QVBoxLayout(panel)
        l.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Properties")
        header.setStyleSheet(
            "color:#3fbe6f;"
            "font-weight:bold;")
        l.addWidget(header)

        self._props_widget = QScrollArea()
        self._props_widget.setWidgetResizable(True)
        self._props_widget.setFrameShape(
            QFrame.Shape.NoFrame)
        self._props_inner = QWidget()
        self._props_layout = QFormLayout(
            self._props_inner)
        self._props_layout.setSpacing(6)
        self._props_widget.setWidget(
            self._props_inner)
        l.addWidget(self._props_widget, 1)

        # Delete selected
        del_btn = QPushButton("🗑 Delete Block")
        del_btn.setToolTip("Remove selected block (Del)")
        del_btn.clicked.connect(
            lambda: self._canvas.delete_selected())
        l.addWidget(del_btn)

        return panel

    # ── Graph operations ──────────────────────────────────────

    def _new_graph(self):
        from dsp.flowgraph import FlowGraph
        if self._fg and self._fg.is_running:
            self._fg.stop()
        self._fg = FlowGraph()
        if self._canvas:
            self._canvas.clear_all()
        self._set_status("New flowgraph")

    def _toggle_run(self):
        if self._fg is None:
            return
        if self._fg.is_running:
            self._fg.stop()
            self._run_btn.setText("▶  Run")
            self._run_btn.setStyleSheet(
                "background:#1a3a1a;border-radius:3px;")
            self._set_status("Stopped")
            self._uptime_lbl.setText("")
        else:
            # Build graph from canvas
            self._sync_canvas_to_graph()
            if not self._fg._blocks:
                QMessageBox.information(
                    self, "No Blocks",
                    "Add blocks to the canvas first.\\n\\n"
                    "Drag from the block browser on the left.")
                return
            ok = self._fg.start()
            if ok:
                self._run_btn.setText("⏹  Stop")
                self._run_btn.setStyleSheet(
                    "background:#3a1a1a;border-radius:3px;")
                self._set_status("Running…")
                # Start uptime timer
                QTimer.singleShot(
                    1000, self._update_uptime)
            else:
                QMessageBox.warning(
                    self, "Start Failed",
                    "Flowgraph failed to start.\\n"
                    "Check block configurations.")

    def _update_uptime(self):
        if self._fg and self._fg.is_running:
            t = self._fg.uptime
            self._uptime_lbl.setText(
                f"⏱ {t:.0f}s  "
                f"ticks:{self._fg.stats['ticks']}")
            QTimer.singleShot(1000, self._update_uptime)

    def _sync_canvas_to_graph(self):
        """Build FlowGraph from canvas node positions."""
        from dsp.flowgraph import FlowGraph
        from dsp.registry import get_registry
        registry = get_registry()

        self._fg = FlowGraph()
        nodes    = self._canvas.nodes

        id_to_block = {}
        for node in nodes:
            cls = registry.get(node.block_key)
            if not cls:
                continue
            blk = cls()
            for k, v in node.param_values.items():
                try:
                    blk.set(k, v)
                except Exception:
                    pass
            id_to_block[node.node_id] = blk
            self._fg.add(blk)

        for conn in self._canvas.connections:
            src = id_to_block.get(conn["src_id"])
            dst = id_to_block.get(conn["dst_id"])
            if src and dst:
                self._fg.connect(
                    src, conn["src_port"],
                    dst, conn["dst_port"])

    def _open_graph(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Flowgraph",
            str(Path.home()),
            "Squelch Flowgraph (*.sqfg);All (*)")
        if path:
            self._new_graph()
            ok = self._fg.load(path)
            if ok:
                self._canvas.load_from_graph(self._fg)
                self._set_status(f"Opened: {path}")
            else:
                QMessageBox.warning(
                    self, "Open Failed",
                    f"Could not open: {path}")

    def _save_graph(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Flowgraph",
            "flowgraph.sqfg",
            "Squelch Flowgraph (*.sqfg);All (*)")
        if path:
            self._sync_canvas_to_graph()
            self._fg.save(path)
            self._set_status(f"Saved: {path}")

    def _import_grc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import GNU Radio Companion File",
            str(Path.home()),
            "GRC Files (*.grc);JSON (*.json)"
            "All Files (*)")
        if not path:
            return
        from dsp.gnuradio_compat import import_grc
        result = import_grc(path)
        if result is None:
            QMessageBox.warning(
                self, "Import Failed",
                f"Could not parse: {path}")
            return
        summary = result.summary()
        log.info(summary)

        if result.errors:
            QMessageBox.warning(
                self, "Import Errors", summary)
            return

        fg = result.to_flowgraph()
        if fg:
            self._fg = fg
            self._canvas.load_from_graph(fg)
            msg = (f"Imported {result.supported_count} blocks")
            if result.unsupported_count:
                msg += (f" ({result.unsupported_count} "
                        f"unsupported — shown in red)")
            if result.warnings:
                msg += f"\\n{len(result.warnings)} warnings"
            QMessageBox.information(
                self, "GRC Import", msg)
            self._set_status(msg)

    def _load_template(self, name: str):
        if name.startswith("—") or name not in _FLOWGRAPH_TEMPLATES:
            return
        self._canvas.clear_all()
        from dsp.registry import get_registry
        registry = get_registry()

        nodes_created = []
        for key, params, pos in _FLOWGRAPH_TEMPLATES[name]:
            cls = registry.get(key)
            if cls:
                node = self._canvas.add_node_at(key, cls.name, pos)
                if node:
                    node.param_values.update(params)
                    nodes_created.append(node)

        for i in range(len(nodes_created) - 1):
            src = nodes_created[i]
            dst = nodes_created[i + 1]
            if src.outputs and dst.inputs:
                self._canvas.connections.append({
                    "src_id":   src.node_id,
                    "src_port": src.outputs[0],
                    "dst_id":   dst.node_id,
                    "dst_port": dst.inputs[0],
                })

        self._canvas.update()
        self._set_status(f"Template loaded: {name}")
        self._template_combo.setCurrentIndex(0)

    def _add_block_from_tree(self, item, col):
        if item is None:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self._canvas.add_node_at(key, item.text(0))

    def _on_node_selected(self, node):
        """Show block properties in the right panel."""
        # Clear existing
        while self._props_layout.rowCount():
            self._props_layout.removeRow(0)

        if node is None:
            return

        # Block name header
        header = QLabel(node.block_name)
        header.setStyleSheet(
            "font-weight:bold;"
            "")
        self._props_layout.addRow(header)

        # Description
        try:
            from dsp.registry import get_registry
            cls = get_registry().get(node.block_key)
            if cls and cls.description:
                desc = QLabel(cls.description)
                desc.setWordWrap(True)
                desc.setStyleSheet(
                    "")
                self._props_layout.addRow(desc)
        except Exception:
            pass

        # Parameters
        try:
            from dsp.registry import get_registry
            cls = get_registry().get(node.block_key)
            if cls:
                for p in cls.params:
                    self._add_param_row(
                        node, p)
        except Exception as e:
            log.debug(f"Props: {e}")

    @staticmethod
    def _make_param_widget(param, node, val):
        """Build and connect the appropriate editor widget for a block param."""
        k, n = param.name, node
        setter = lambda v, _k=k, _n=n: _n.param_values.__setitem__(_k, v)  # noqa: E731
        if param.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(setter)
        elif param.type == "choice":
            w = QComboBox()
            w.addItems([str(c) for c in param.choices])
            w.setCurrentText(str(val))
            w.currentTextChanged.connect(setter)
        elif param.type == "float":
            w = QDoubleSpinBox()
            w.setDecimals(3)
            if param.min_val is not None: w.setMinimum(param.min_val)
            if param.max_val is not None: w.setMaximum(param.max_val)
            w.setValue(float(val or 0))
            if param.units: w.setSuffix(f" {param.units}")
            w.valueChanged.connect(setter)
        elif param.type == "int":
            w = QSpinBox()
            w.setMinimum(int(param.min_val) if param.min_val is not None else -2_000_000_000)
            w.setMaximum(int(param.max_val) if param.max_val is not None else  2_000_000_000)
            w.setValue(int(val or 0))
            if param.units: w.setSuffix(f" {param.units}")
            w.valueChanged.connect(setter)
        else:
            w = QLineEdit()
            w.setText(str(val or ""))
            w.textChanged.connect(setter)
        return w

    def _add_param_row(self, node, param):
        """Add a parameter editing row."""
        val   = node.param_values.get(param.name, param.default)
        label = QLabel(f"{param.label}:")
        label.setToolTip(param.help or "")
        w = self._make_param_widget(param, node, val)
        self._props_layout.addRow(label, w)

    def _set_status(self, msg: str):
        self._status.setText(msg)

    def _update_node_count(self):
        n = len(self._canvas.nodes)
        self._node_count_lbl.setText(
            f"{n} block{'s' if n != 1 else ''}")


# ── Canvas widget ─────────────────────────────────────────────────────────

class GraphNode:
    """A single block node on the canvas."""

    def __init__(self, node_id: int, key: str,
                 name: str, pos: list):
        self.node_id     = node_id
        self.block_key   = key
        self.block_name  = name
        self.x           = float(pos[0])
        self.y           = float(pos[1])
        self.w           = 160.0
        self.h           = 60.0
        self.selected    = False
        self.param_values: dict = {}
        self.color       = "#2a2a2a"
        self.inputs:  list[str] = []
        self.outputs: list[str] = []
        self._load_ports()

    def _load_ports(self):
        try:
            from dsp.registry import get_registry
            cls = get_registry().get(self.block_key)
            if cls:
                self.inputs  = [p.name
                                 for p in cls.inputs]
                self.outputs = [p.name
                                 for p in cls.outputs]
                self.color   = getattr(
                    cls, "color", "#2a2a2a")
                self.param_values = {
                    p.name: p.default
                    for p in cls.params}
        except Exception:
            pass

    def contains(self, x: float, y: float) -> bool:
        return (self.x <= x <= self.x + self.w and
                self.y <= y <= self.y + self.h)

    def port_pos(self, port: str,
                  is_input: bool) -> tuple[float, float]:
        """Get canvas position of a port circle."""
        if is_input:
            idx = self.inputs.index(port) \
                if port in self.inputs else 0
            n   = len(self.inputs)
        else:
            idx = self.outputs.index(port) \
                if port in self.outputs else 0
            n   = len(self.outputs)
        step = self.h / (n + 1)
        px   = self.x if is_input else self.x + self.w
        py   = self.y + step * (idx + 1)
        return px, py


class FlowgraphCanvas(QWidget):
    """
    Interactive node editor canvas.
    Supports drag-and-drop blocks, drawing connections,
    and keyboard delete.
    """

    node_selected = pyqtSignal(object)
    status_msg    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes:       list[GraphNode] = []
        self.connections: list[dict]      = []
        self._next_id     = 0
        self._selected:   GraphNode | None = None
        self._dragging:   GraphNode | None = None
        self._drag_offset = (0.0, 0.0)
        self._connecting  = None   # {node, port, is_output}
        self._hover_port  = None

        self.setMinimumSize(400, 300)
        self.setStyleSheet("background:#0a0a0a;")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # ── Drawing ───────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background grid
        p.setPen(QPen(QColor("#111111"), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)

        # Connections
        for conn in self.connections:
            self._draw_connection(p, conn)

        # Nodes
        for node in self.nodes:
            self._draw_node(p, node)

        # Active connection being drawn
        if self._connecting:
            # Draw rubber band
            pass

        p.end()

    def _draw_node(self, p: QPainter, node: GraphNode):
        # Shadow
        shadow = QColor(0, 0, 0, 80)
        p.fillRect(
            QRectF(node.x + 3, node.y + 3,
                   node.w, node.h), shadow)

        # Body
        color = QColor(node.color)
        p.fillRect(
            QRectF(node.x, node.y, node.w, node.h),
            color)

        # Border
        border_col = (QColor("#3fbe6f")
                      if node.selected
                      else QColor("#2a2a2a"))
        p.setPen(QPen(border_col, 2 if node.selected else 1))
        p.drawRect(
            QRectF(node.x, node.y, node.w, node.h))

        # Title bar
        title_rect = QRectF(
            node.x, node.y, node.w, 22)
        title_color = QColor(node.color).lighter(120)
        p.fillRect(title_rect, title_color)
        p.setPen(QPen(QColor("#ddd")))
        p.setFont(QFont("Courier New", 10,
                         QFont.Weight.Bold))
        p.drawText(
            title_rect.adjusted(6, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter |
            Qt.AlignmentFlag.AlignLeft,
            node.block_name[:20])

        self._draw_node_ports(p, node)

    def _draw_node_ports(self, p: QPainter, node: GraphNode):
        p.setFont(QFont("Courier New", 9))
        for port in node.inputs:
            px, py = node.port_pos(port, True)
            p.setBrush(QBrush(QColor("#4488ff")))
            p.setPen(QPen(QColor("#111"), 1))
            p.drawEllipse(QRectF(px - 5, py - 5, 10, 10))
            p.setPen(QPen(QColor("#888")))
            p.drawText(QRectF(px + 7, py - 8, 50, 16),
                       Qt.AlignmentFlag.AlignVCenter, port)
        for port in node.outputs:
            px, py = node.port_pos(port, False)
            p.setBrush(QBrush(QColor("#44cc44")))
            p.setPen(QPen(QColor("#111"), 1))
            p.drawEllipse(QRectF(px - 5, py - 5, 10, 10))
            p.setPen(QPen(QColor("#888")))
            p.drawText(QRectF(px - 60, py - 8, 54, 16),
                       Qt.AlignmentFlag.AlignVCenter |
                       Qt.AlignmentFlag.AlignRight, port)

    def _draw_connection(self, p: QPainter,
                          conn: dict):
        src = self._node_by_id(conn["src_id"])
        dst = self._node_by_id(conn["dst_id"])
        if not src or not dst:
            return
        x1, y1 = src.port_pos(
            conn["src_port"], False)
        x2, y2 = dst.port_pos(
            conn["dst_port"], True)
        # Bezier curve
        cx = (x1 + x2) / 2
        p.setPen(QPen(QColor("#3fbe6f"), 2))
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(x1, y1)
        path.cubicTo(cx, y1, cx, y2, x2, y2)
        p.drawPath(path)

    # ── Interaction ───────────────────────────────────────────

    def _try_start_connection(self, x: float, y: float) -> bool:
        """If click lands on an output port, begin a connection drag. Returns True if handled."""
        for node in self.nodes:
            for port in node.outputs:
                px, py = node.port_pos(port, False)
                if abs(px - x) < 8 and abs(py - y) < 8:
                    self._connecting = {"node": node, "port": port}
                    return True
        return False

    def _try_complete_or_select_node(self, x: float, y: float) -> bool:
        """Handle a click that may land on a node body. Returns True if handled."""
        for node in reversed(self.nodes):
            if not node.contains(x, y):
                continue
            if self._connecting:
                for inp in node.inputs:
                    px, py = node.port_pos(inp, True)
                    if abs(px - x) < 12 and abs(py - y) < 12:
                        self.connections.append({
                            "src_id":   self._connecting["node"].node_id,
                            "src_port": self._connecting["port"],
                            "dst_id":   node.node_id,
                            "dst_port": inp,
                        })
                        self._connecting = None
                        self.update()
                        return True
                self._connecting = None
                return True
            if self._selected:
                self._selected.selected = False
            node.selected = True
            self._selected = node
            self.node_selected.emit(node)
            self._dragging    = node
            self._drag_offset = (x - node.x, y - node.y)
            self.update()
            return True
        return False

    def mousePressEvent(self, event: QMouseEvent):
        x, y = event.position().x(), event.position().y()
        if self._try_start_connection(x, y):
            return
        if self._try_complete_or_select_node(x, y):
            return
        # Click on empty → deselect
        self._connecting = None
        if self._selected:
            self._selected.selected = False
            self._selected = None
            self.node_selected.emit(None)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            x, y = (event.position().x(),
                     event.position().y())
            self._dragging.x = (
                x - self._drag_offset[0])
            self._dragging.y = (
                y - self._drag_offset[1])
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
        elif event.key() == Qt.Key.Key_Escape:
            self._connecting = None
            self.update()

    # ── Node management ───────────────────────────────────────

    def add_node_at(self, key: str, name: str,
                     pos: list | None = None
                     ) -> GraphNode | None:
        if pos is None:
            # Stagger new nodes
            n   = len(self.nodes)
            pos = [40 + (n % 5) * 170,
                   40 + (n // 5) * 120]
        node = GraphNode(
            self._next_id, key, name, pos)
        self._next_id += 1
        self.nodes.append(node)
        self.update()
        self.status_msg.emit(
            f"Added: {name}")
        return node

    def delete_selected(self):
        if not self._selected:
            return
        nid = self._selected.node_id
        self.nodes = [n for n in self.nodes
                      if n is not self._selected]
        self.connections = [
            c for c in self.connections
            if c["src_id"] != nid and
               c["dst_id"] != nid]
        self._selected = None
        self.node_selected.emit(None)
        self.update()

    def clear_all(self):
        self.nodes.clear()
        self.connections.clear()
        self._selected = None
        self._connecting = None
        self.node_selected.emit(None)
        self._next_id = 0
        self.update()

    def auto_layout(self):
        """Arrange nodes in a left-to-right flow."""
        if not self.nodes:
            return
        x, y = 40.0, 40.0
        for i, node in enumerate(self.nodes):
            node.x = x
            node.y = y + (i % 3) * 120
            x += node.w + 80
        self.update()

    def load_from_graph(self, fg):
        """Populate canvas from a loaded FlowGraph."""
        self.clear_all()
        for block in fg._blocks:
            pos = getattr(block, "_canvas_pos", [0, 0])
            node = self.add_node_at(
                block.key, block.name, pos)
            if node:
                node.param_values.update(
                    dict(block._params))
        self.update()

    def _node_by_id(self, nid: int
                    ) -> GraphNode | None:
        for n in self.nodes:
            if n.node_id == nid:
                return n
        return None
