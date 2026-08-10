#!/usr/bin/env python3
"""App-free regressions for TouchDesigner runtime helpers."""

import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
