"""Host COMP extension — the public Noisemaker API for a TouchDesigner component.

Attach as an extension on the `noisemaker` Base COMP (the .tox). It owns a Pipeline and exposes
a small host-facing surface. Mirrors `NMRenderer` (Unity) / `nm_renderer.gd` (Godot).

Public API:
    nm.set_graph(path)         build the network from a golden graph JSON (offline producer)
    nm.set_graph_dict(d)       build from an in-memory normalized graph dict
    nm.set_dsl(src)            Phase 6 — compile DSL live in-engine, then build
    nm.resize(w, h)            change render resolution (rebuilds)
    nm.set_time(time)          resolve animated uniforms at normalized time
    nm.set_midi_state(state)   provide the current legacy/selected MIDI snapshot
    nm.set_audio_state(state)  provide the current legacy/selected audio snapshot
    nm.get_audio_input_requirements() describe captures required by the active graph
    nm.Output                  the presented TOP (renderSurface) — wire to a Null/Out for display
    nm.add_sink(sink)          register an output sink for explicitly submitted frames
    nm.submit_frame(timestamp) cook and submit the current TOP to registered sinks
    nm.create_frame_export_queue(...)  create a delayed GPU-download queue
    nm.render_to(path, time)   deterministic single-frame render (parity / export)

Touches the TouchDesigner Python API — only runs inside a TD process.
"""
import os

from .graph_loader import load_graph, load_graph_str
from .render_graph import RenderGraph
from .pipeline import Pipeline


class NMRenderer:
    def __init__(self, owner_comp, *, shaders_root=None, width=256, height=256, time=0.25):
        self.owner = owner_comp
        # default: shaders ship beside this package at ../shaders/effects
        self.shaders_root = shaders_root or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shaders', 'effects')
        self.width = width
        self.height = height
        self.time = time
        self.pipeline = None
        self._graph = None
        self._midi_state = None
        self._audio_state = None

    # -- build paths -------------------------------------------------------
    def set_graph(self, path):
        return self._build(load_graph(path))

    def set_graph_dict(self, d):
        return self._build(RenderGraph.from_dict(d))

    def set_graph_str(self, text):
        return self._build(load_graph_str(text))

    def set_dsl(self, src):
        """Compile the Polymorphic DSL live in-engine to a normalized graph, then build the
        network. The compiler (`compiler/`, ports of reference/01–04) is graph-parity-clean vs
        the offline `tools/export-graph.mjs` oracle (parity/compiler/check_graph.py), so this
        live path produces the same network the offline set_graph path renders 72/72."""
        from ..compiler import compile_dsl
        return self.set_graph_dict(compile_dsl(src))

    # -- host controls -----------------------------------------------------
    def resize(self, width, height):
        self.width = int(width)
        self.height = int(height)
        if self._graph is not None:
            self._build(self._graph)

    def render_to(self, path, time=0.25):
        if self.pipeline is None:
            return None
        self.time = float(time)
        return self.pipeline.render_to(path, time=time)

    def set_time(self, time):
        self.time = float(time)
        if self.pipeline is not None:
            self.pipeline.set_time(self.time)

    def add_sink(self, sink):
        if self.pipeline is None:
            raise RuntimeError('NMRenderer has no active pipeline; build before adding a sink')
        return self.pipeline.add_sink(sink)

    def submit_frame(self, timestamp=None):
        if self.pipeline is None:
            return False
        return self.pipeline.submit_frame(timestamp)

    def create_frame_export_queue(self, *, slots=3, on_error=None):
        if self.pipeline is None:
            raise RuntimeError(
                'NMRenderer has no active pipeline; build before creating a frame export queue'
            )
        return self.pipeline.create_frame_export_queue(slots=slots, on_error=on_error)

    def set_midi_state(self, state):
        self._midi_state = state
        if self.pipeline is not None:
            self.pipeline.set_midi_state(state)

    def set_audio_state(self, state):
        self._audio_state = state
        if self.pipeline is not None:
            self.pipeline.set_audio_state(state)

    def get_audio_input_requirements(self):
        if self.pipeline is None:
            return {'needsLegacy': False, 'needsLegacyRaw': False, 'selected': []}
        return self.pipeline.get_audio_input_requirements()

    @property
    def Output(self):
        return self.pipeline.output if self.pipeline else None

    # -- internal ----------------------------------------------------------
    def _build(self, graph):
        if self.pipeline is not None:
            self.pipeline.teardown()
        self._graph = graph
        self.pipeline = Pipeline(self.owner, self.shaders_root, width=self.width, height=self.height,
                                 time=self.time, midi_state=self._midi_state,
                                 audio_state=self._audio_state)
        return self.pipeline.build(graph)
