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
    def test_unwritten_pipeline_input_alias_releases_the_upstream_texture(self):
        for name in ('inputColor', 'inputTex'):
            with self.subTest(name=name):
                allocations = allocate_resources([
                    {'nodeId': 'node_0', 'outputs': {'color': 'node_0_out'}},
                    {'nodeId': 'node_1', 'inputs': {'tex': 'node_1_' + name},
                     'outputs': {'color': 'node_1_out'}},
                    {'nodeId': 'node_2', 'inputs': {'tex': 'node_1_out'},
                     'outputs': {'color': 'node_2_out'}},
                ])
                self.assertEqual(allocations['node_0_out'], allocations['node_2_out'])
                self.assertNotEqual(allocations['node_0_out'], allocations['node_1_out'])

    def test_written_local_input_is_not_treated_as_a_pipeline_alias(self):
        allocations = allocate_resources([
            {'nodeId': 'node_0', 'outputs': {'color': 'node_0_out'}},
            {'nodeId': 'node_1', 'outputs': {'local': 'node_1_inputColor'}},
            {'nodeId': 'node_1', 'inputs': {'tex': 'node_1_inputColor'},
             'outputs': {'color': 'node_1_out'}},
            {'nodeId': 'node_2', 'inputs': {'tex': 'node_1_out'},
             'outputs': {'color': 'node_2_out'}},
            {'nodeId': 'node_3', 'inputs': {'tex': 'node_0_out'},
             'outputs': {'color': 'global_o0'}},
        ])
        self.assertEqual(allocations['node_1_inputColor'], allocations['node_2_out'])
        self.assertNotEqual(allocations['node_0_out'], allocations['node_2_out'])

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
