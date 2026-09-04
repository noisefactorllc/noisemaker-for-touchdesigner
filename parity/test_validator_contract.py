#!/usr/bin/env python3
"""App-free regressions for validator contracts mirrored from upstream."""

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.compiler import compile_dsl  # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402
from noisemaker.compiler.lang.lexer import lex  # noqa: E402
from noisemaker.compiler.lang.parser import parse  # noqa: E402
from noisemaker.compiler.lang.validator import validate  # noqa: E402


def validate_dsl(source):
    registry = EffectRegistry.load_from_directory()
    return validate(parse(lex(source), registry), registry)


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

    def test_nested_automation_and_selected_inputs_compile_to_runtime_descriptors(self):
        graph = compile_dsl(
            'search synth\n'
            'let rate = audio(audioBand.raw, 0.25, 0.75, channel: 2, '
            'name: "Interface", id: "device")\n'
            'let carrier = osc(type: oscKind.saw, speed: rate)\n'
            'solid(alpha: midi(1, midiMode.velocity, carrier, 1, 0.5, '
            'name: "Controller", id: "port")).write(o0)\n'
            'render(o0)\n'
        )

        descriptor = next(
            render_pass["uniforms"]["alpha"]
            for render_pass in graph["passes"]
            if "alpha" in render_pass["uniforms"]
        )
        self.assertEqual("Midi", descriptor["type"])
        self.assertEqual("port", descriptor["id"])
        self.assertEqual("Oscillator", descriptor["min"]["type"])
        self.assertEqual("carrier", descriptor["min"]["_varRef"])
        self.assertEqual("Audio", descriptor["min"]["speed"]["type"])
        self.assertEqual("rate", descriptor["min"]["speed"]["_varRef"])
        self.assertEqual(4, descriptor["min"]["speed"]["band"])

    def test_automation_cycle_is_reported(self):
        graph = validate_dsl(
            'search synth\n'
            'let first = osc(type: oscKind.sine, speed: second)\n'
            'let second = osc(type: oscKind.tri, speed: first)\n'
            'noise(scaleX: first).write(o0)\n'
            'render(o0)\n'
        )

        messages = "\n".join(item["message"] for item in graph["diagnostics"])
        self.assertRegex(messages, r"(?i)automation cycle")

    def test_automation_nesting_beyond_eight_levels_is_rejected(self):
        lets = ['let rate9 = osc(type: oscKind.sine)']
        for level in range(8, 0, -1):
            lets.append(
                'let rate%d = osc(type: oscKind.sine, speed: rate%d)'
                % (level, level + 1)
            )
        lets.append('let carrier = osc(type: oscKind.saw, speed: rate1)')
        graph = validate_dsl(
            'search synth\n%s\nnoise(scaleX: carrier).write(o0)\nrender(o0)\n'
            % "\n".join(lets)
        )

        messages = "\n".join(item["message"] for item in graph["diagnostics"])
        self.assertIn("maximum depth of 8", messages)

    def test_single_quoted_external_identity_decodes_the_accepted_escape_set(self):
        cases = (
            (
                "solid(alpha: midi(1, name: 'Keys \"Left\" Controller\\'s "
                "\\\\ Main')).write(o0)",
                "alpha",
            ),
            (
                "noise(scaleX: audio(audioBand.low, channel: 1, "
                "name: 'Keys \"Left\" Controller\\'s \\\\ Main')).write(o0)",
                "scaleX",
            ),
        )

        for call, uniform in cases:
            with self.subTest(call=call):
                graph = compile_dsl("search synth\n%s\nrender(o0)\n" % call)
                descriptor = next(
                    render_pass["uniforms"][uniform]
                    for render_pass in graph["passes"]
                    if uniform in render_pass["uniforms"]
                )
                self.assertEqual(r'''Keys "Left" Controller's \ Main''', descriptor["name"])


if __name__ == "__main__":
    unittest.main()
