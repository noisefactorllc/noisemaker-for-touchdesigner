#!/usr/bin/env python3
"""App-free regressions for TouchDesigner runtime helpers."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.runtime import td_backend  # noqa: E402


class BoolDefineScanTests(unittest.TestCase):
    def test_block_comment_boolean_patterns_do_not_classify_numeric_define(self):
        source = (
            "/* legacy: #define COUNT true\n"
            "void old_main() { if (COUNT) {} } */\n"
            "#define COUNT 5\n"
            "void main() { int n = COUNT; }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_line_comment_boolean_patterns_do_not_classify_numeric_define(self):
        source = (
            "// legacy: #define COUNT false\n"
            "// void old_main() { if (COUNT) {} }\n"
            "#define COUNT 5\n"
            "void main() { int n = COUNT; }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_live_fallback_and_bare_if_are_still_detected(self):
        source = (
            "#ifndef RIDGES\n"
            "#define RIDGES true\n"
            "#endif\n"
            "void main() { if (RIDGES) {} if (!INVERT) {} }\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), {"RIDGES", "INVERT"})

    def test_arithmetic_comparison_and_loop_bound_uses_stay_numeric(self):
        source = (
            "#define COUNT 5\n"
            "void main() {\n"
            "  int doubled = COUNT * 2;\n"
            "  if (COUNT == 1) {}\n"
            "  for (int i = 0; i < COUNT; ++i) {}\n"
            "}\n"
        )

        self.assertEqual(td_backend._bool_define_keys(source), set())

    def test_effect_assembly_preserves_commented_source_byte_for_byte(self):
        source = "/* #define COUNT true */\n#define COUNT 5\nvoid main() {}\n"

        assembled = td_backend._assemble_effect_source(source, {"COUNT": 5})

        self.assertTrue(assembled.endswith(source))
        self.assertEqual("#define COUNT 5\n" + source, assembled)


class MrtStorageFormatTests(unittest.TestCase):
    @staticmethod
    def graph(formats):
        specs = {name: SimpleNamespace(fmt=fmt) for name, fmt in formats.items()}
        return SimpleNamespace(spec_for=lambda tex_id: specs.get(tex_id))

    def test_three_buffer_particle_state_uses_half_float_under_32_byte_budget(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba",
        })
        graph = self.graph({"xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba16float")

    def test_default_native_budget_preserves_full_float_particle_state(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba",
        })
        graph = self.graph({"xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph), "rgba32float")

    def test_two_full_float_buffers_fit_the_same_budget(self):
        pass_ = SimpleNamespace(outputs={"outA": "a", "outB": "b"})
        graph = self.graph({"a": "rgba32f", "b": "rgba32float"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba32float")

    def test_larger_budget_preserves_three_full_float_buffers(self):
        pass_ = SimpleNamespace(outputs={"outA": "a", "outB": "b", "outC": "c"})
        graph = self.graph({"a": "rgba32f", "b": "rgba32f", "c": "rgba8"})

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 64), "rgba32float")

    def test_four_buffer_life_state_fits_exactly_at_half_float(self):
        pass_ = SimpleNamespace(outputs={
            "outXYZ": "xyz", "outVel": "vel", "outRGBA": "rgba", "outState": "state",
        }, draw_buffers=4)
        graph = self.graph({
            "xyz": "rgba32f", "vel": "rgba32f", "rgba": "rgba8", "state": "rgba16f",
        })

        self.assertEqual(td_backend._mrt_storage_format(pass_, graph, 32), "rgba16float")

    def test_render_select_converts_storage_back_to_logical_attachment_format(self):
        class FakeParent:
            def create(self, _operator_type, name):
                return SimpleNamespace(name=name, par=SimpleNamespace())

        backend = td_backend.TDBackend(FakeParent(), "/unused")
        spec = SimpleNamespace(fmt="rgba8")
        with mock.patch.object(td_backend, "_td", return_value="renderselectTOP"):
            select = backend._register_mrt_buffer(object(), 2, "rgba", "points", spec)

        self.assertEqual(select.par.format, "rgba8fixed")


if __name__ == "__main__":
    unittest.main()
