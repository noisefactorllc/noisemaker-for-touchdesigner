#!/usr/bin/env python3
"""allocate_resources releases a texture read under two names in one pass once.

Ported from reference `shaders/tests/test_resource_pooling.js` (upstream 8e583593). lighting
reads the same texture as inputTex and heightMap; releasing it once per name put its slot on the
free list twice, so two textures live at the same time were both given that slot.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "td"))

from noisemaker.compiler.graph.resources import allocate_resources  # noqa: E402


class AllocateResourcesTests(unittest.TestCase):
    def test_a_texture_read_under_two_names_in_one_pass_is_released_once(self):
        allocations = allocate_resources([
            {"outputs": {"out": "A"}},
            {"inputs": {"inputTex": "A", "heightMap": "A"}, "outputs": {"out": "B"}},
            {"inputs": {"inputTex": "B"}, "outputs": {"out": "C"}},
            {"inputs": {"inputTex": "B"}, "outputs": {"out": "D"}},
            {"inputs": {"a": "C", "b": "D"}, "outputs": {"out": "E"}},
        ])
        self.assertEqual(allocations["C"], allocations["A"], "C reuses the slot A released")
        self.assertNotEqual(allocations["D"], allocations["C"],
                            "C and D are live together and must not share a slot")


if __name__ == "__main__":
    unittest.main()
