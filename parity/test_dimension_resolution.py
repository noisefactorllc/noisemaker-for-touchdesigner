#!/usr/bin/env python3
"""Dimension resolution and engine-global regressions.

Mirrors the reference engine's own `Pipeline - Func texture dimensions` test
(introduced with the nonnumeric-dimension guard, upstream 8ad2bf56): Func
wrappers and other nonnumeric authored values in texture-spec dimensions must
never execute a callback or allocate a NaN size — the runtime falls back to the
spec's numeric default (or paramDefault with its transforms).

The engine-global checks pin `aspectInv`/`invFullResolution` (reference/04
§10.1), the CPU-computed reciprocals shaders multiply by instead of dividing.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.runtime.dim import resolve_dimension  # noqa: E402
from noisemaker.runtime.engine_uniforms import engine_uniforms  # noqa: E402


class FuncWrapper:
    """A Func value like the reference's `{fn, min, max}` UI wrapper."""

    def __init__(self):
        self.fn = lambda: (_ for _ in ()).throw(
            AssertionError("Texture allocation must not execute Func callbacks"))
        self.min = 1
        self.max = 64


class ResolveDimensionTests(unittest.TestCase):
    def test_func_values_fall_back_to_authored_numeric_defaults(self):
        wrapper = FuncWrapper()
        cases = [
            ({'screenDivide': 'zoom_chain_0', 'default': 32},
             {'zoom_chain_0': wrapper}, 8),
            ({'param': 'stateSize_node_1', 'default': 256},
             {'stateSize_node_1': wrapper}, 256),
            ({'param': 'volumeSize_chain_0', 'default': 64},
             {'volumeSize_chain_0': wrapper}, 64),
            ({'param': 'volumeSize_chain_0', 'power': 2, 'default': 4096},
             {'volumeSize_chain_0': wrapper}, 4096),
            ({'param': 'size', 'paramDefault': 3, 'multiply': 2, 'power': 2},
             {'size': wrapper}, 36),
            ({'screenDivide': 'zoom_chain_0', 'default': 32},
             {'zoom_chain_0': 16}, 16),
            ({'param': 'stateSize_node_1', 'default': 256},
             {'stateSize_node_1': 128}, 128),
            ({'param': 'volumeSize_chain_0', 'power': 2, 'default': 4096},
             {'volumeSize_chain_0': 16}, 256),
        ]
        for spec, uniforms, expected in cases:
            self.assertEqual(resolve_dimension(spec, 256, uniforms), expected,
                             msg=f"spec={spec}")

    def test_numeric_values_still_resolve_exactly(self):
        self.assertEqual(resolve_dimension(64, 256), 64)
        self.assertEqual(resolve_dimension('screen', 256), 256)
        self.assertEqual(resolve_dimension('6.25%', 256), 16)
        self.assertEqual(resolve_dimension({'scale': 0.5}, 256), 128)


class EngineUniformReciprocalsTests(unittest.TestCase):
    def test_reciprocals_default_to_the_resolution(self):
        g = engine_uniforms(256, 192, 0.25)
        self.assertEqual(g['aspect'], 256 / 192)
        self.assertEqual(g['aspectInv'], 192 / 256)
        self.assertEqual(g['invFullResolution'], [1.0 / 256.0, 1.0 / 192.0])

    def test_reciprocals_follow_full_resolution_when_tiling(self):
        g = engine_uniforms(256, 256, 0.25, full_resolution=(1024, 512))
        self.assertEqual(g['fullResolution'], [1024.0, 512.0])
        self.assertEqual(g['aspect'], 2.0)
        self.assertEqual(g['aspectInv'], 0.5)
        self.assertEqual(g['invFullResolution'], [1.0 / 1024.0, 1.0 / 512.0])

    def test_names_register_the_reciprocals_as_engine_supplied(self):
        from noisemaker.runtime.engine_uniforms import ENGINE_UNIFORM_NAMES
        self.assertIn('aspectInv', ENGINE_UNIFORM_NAMES)
        self.assertIn('invFullResolution', ENGINE_UNIFORM_NAMES)


if __name__ == '__main__':
    unittest.main()
