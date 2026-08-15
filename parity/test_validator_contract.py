#!/usr/bin/env python3
"""App-free regressions for validator contracts mirrored from upstream."""

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.compiler import compile_dsl  # noqa: E402


class ValidatorContractTests(unittest.TestCase):
    def test_text_style_accepts_a_quoted_css_string(self):
        graph = compile_dsl(
            'search synth, filter\n'
            'solid().text(style: "font-weight: bold").write(o0)\n'
            'render(o0)\n'
        )

        self.assertEqual(graph["renderSurface"], "o0")
        text_pass = next(
            render_pass
            for render_pass in graph["passes"]
            if render_pass["effectKey"] == "filter.text"
        )
        self.assertEqual(text_pass["uniforms"]["style"], "font-weight: bold")


if __name__ == "__main__":
    unittest.main()
