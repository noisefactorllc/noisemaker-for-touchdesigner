"""Build orchestration + deterministic time driving.

The reference runs an imperative per-frame loop (reference/04 §10). In TouchDesigner the built
network cooks itself; the pipeline's job each frame is only to (1) update the engine `time`
uniform (normalized 0..1) on every effect TOP and (2) request the output to cook. For parity we
pin `time` to a fixed value and render one frame.

Touches the TouchDesigner Python API — only runs inside a TD process.
"""
import os
import time as clock

from .automation import get_audio_input_requirements
from .sink import SinkManager
from .td_backend import TDBackend
from .surface_manager import SurfaceManager


class Pipeline:
    def __init__(self, parent_comp, shaders_root, *, width=256, height=256, time=0.25,
                 midi_state=None, audio_state=None):
        self.parent = parent_comp
        self.shaders_root = shaders_root
        self.width = width
        self.height = height
        self._time = time
        self._external_state = {'midi': midi_state, 'audio': audio_state}
        self._graph = None
        self.surfaces = SurfaceManager(parent_comp)
        self.backend = TDBackend(parent_comp, shaders_root, width=width, height=height,
                                 time=time, surface_manager=self.surfaces,
                                 external_state=self._external_state)
        self.output = None      # the TOP presented (renderSurface)
        self._effect_tops = []
        self.sink_manager = SinkManager()

    def build(self, graph):
        self._graph = graph
        self.output = self.backend.build(graph)
        self.surfaces.finalize()
        self._effect_tops = [g for g in self.backend.ops if _is_glsl_top(g)]
        self._configure_sinks()
        return self.output

    def _configure_sinks(self):
        self.sink_manager.configure({
            'width': self.width,
            'height': self.height,
            'format': 'rgba8unorm',
            'colorSpace': 'srgb',
            'alphaMode': 'straight',
            'fps': 60,
        })

    def add_sink(self, sink):
        """Register a sink for explicitly submitted completed output frames."""
        return self.sink_manager.add(sink)

    def create_frame_export_queue(self, *, slots=3, on_error=None):
        """Create a bounded queue backed by TouchDesigner's delayed TOP downloads."""
        return self.backend.create_frame_export_queue(slots=slots, on_error=on_error)

    def set_resolution(self, width, height):
        self.width = width
        self.height = height
        # full rebuild is simplest/safest for a resolution change (rare; parity is fixed-size).

    def set_time(self, t):
        """Stamp normalized time onto every effect TOP, preserving its per-effect uniforms.

        Re-binding engine-uniforms-ONLY would reset the Vectors slot count and wipe each effect's
        own uniforms (speed/dyeDecay/zoom/...). Instead we refresh the engine values WITHIN each
        TOP's full declared binding and re-bind the whole set (same slot count, stable order)."""
        self._time = float(t)
        self.backend.refresh_uniforms(self._time, self._external_state)

    def set_midi_state(self, state):
        self._external_state['midi'] = state
        self._refresh_external_state()

    def set_audio_state(self, state):
        self._external_state['audio'] = state
        self._refresh_external_state()

    def get_audio_input_requirements(self):
        effects_root = os.path.join(os.path.dirname(os.path.dirname(self.shaders_root)), 'effects')
        return get_audio_input_requirements(self._graph, effects_root) if self._graph else {
            'needsLegacy': False, 'needsLegacyRaw': False, 'selected': [],
        }

    def _refresh_external_state(self):
        self.backend.external_state = self._external_state
        if self._graph is None:
            return
        self.backend.refresh_uniforms(self._time, self._external_state)

    def render_to(self, filepath, *, time=None):
        """Deterministic one-shot render of the presented surface to an image file.
        Returns the save path (str) or None. Caller should ensure project.realTime=False."""
        if time is not None:
            self.set_time(time)
        if self.output is None:
            return None
        self.submit_frame()
        return str(self.output.save(filepath, createFolders=True))

    def submit_frame(self, timestamp=None):
        """Cook and submit the current output TOP to registered sinks."""
        if self.output is None:
            return False
        try:
            self.output.cook(force=True)
        except Exception:
            pass
        if timestamp is None:
            timestamp = clock.perf_counter() * 1000.0
        self.sink_manager.submit(self.output, timestamp)
        return True

    def teardown(self):
        first_error = None
        try:
            self.sink_manager.close()
        except Exception as error:
            first_error = error
        try:
            self.backend.teardown()
        except Exception as error:
            if first_error is None:
                first_error = error
        for o in self.surfaces.ops:
            try:
                o.destroy()
            except Exception:
                pass
        if first_error is not None:
            raise first_error


def _is_glsl_top(op):
    try:
        return op.type in ('glsl', 'glslmulti') or op.OPType in ('glslTOP', 'glslmultiTOP')
    except Exception:
        return False
