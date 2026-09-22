#!/usr/bin/env python3
"""App-free regressions for validator contracts mirrored from upstream."""

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.compiler import compile_dsl  # noqa: E402
from noisemaker.compiler.lang.dsl_syntax_error import DslSyntaxError  # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402
from noisemaker.compiler.lang.lexer import lex  # noqa: E402
from noisemaker.compiler.lang.parser import parse  # noqa: E402
from noisemaker.compiler.lang.validator import validate  # noqa: E402
from noisemaker.compiler.lang import diagnostics as lang_diag  # noqa: E402


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

    def test_chained_variable_alias_compiles_to_terminal_write_blit(self):
        source = (
            'search synth, filter\n'
            'let gen = noise()\n'
            'let eff = rotate(1, 0.1)\n'
            'gen().eff().write(o0)\n'
            'render(o0)\n'
        )
        validated = validate_dsl(source)
        self.assertEqual(len(validated.get("plans", [])), 1)
        chain = validated["plans"][0]["chain"]
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0].get("op"), "synth.noise")
        self.assertEqual(chain[1].get("op"), "filter.rotate")
        self.assertEqual(chain[2].get("op"), "_write")

        graph = compile_dsl(source)
        self.assertEqual(len(graph["passes"]), 3)
        self.assertEqual(graph["passes"][0]["id"], "node_0_pass_0")
        self.assertEqual(graph["passes"][1]["id"], "node_1_pass_0")
        terminal_pass = graph["passes"][2]
        self.assertEqual(terminal_pass["id"], "node_2_write_blit")
        self.assertEqual(terminal_pass["program"], "blit")
        self.assertEqual(terminal_pass["passType"], "blit")
        self.assertEqual(terminal_pass["inputs"].get("src"), "node_1_out")
        self.assertEqual(terminal_pass["outputs"].get("color"), "global_o0")

    def test_filter_adjust_resolves_and_expired_effects_are_rejected(self):
        source = (
            'search synth, filter\n'
            'noise().adjust(rotation: 45).write(o0)\n'
            'render(o0)\n'
        )
        validated = validate_dsl(source)
        chain = validated["plans"][0]["chain"]
        self.assertEqual(chain[1].get("op"), "filter.adjust")

        graph = compile_dsl(source)
        self.assertTrue(any(p.get("effectKey") == "filter.adjust" for p in graph["passes"]))

        for expired in ("bc", "colorspace", "hs"):
            with self.subTest(expired=expired):
                bad_source = f"search synth, filter\nnoise().{expired}().write(o0)\nrender(o0)\n"
                bad_val = validate_dsl(bad_source)
                self.assertTrue(
                    any(d.get("code") == "S001" for d in bad_val.get("diagnostics", [])),
                    f"expected diagnostic S001 for expired effect {expired}"
                )

    def test_output_surface_range_enforcement(self):
        # valid boundaries
        toks = lex("o0 o7 s3 output0")
        self.assertEqual(len(toks), 5)
        self.assertEqual(toks[0].type, "OUTPUT_REF")
        self.assertEqual(toks[0].lexeme, "o0")
        self.assertEqual(toks[1].type, "OUTPUT_REF")
        self.assertEqual(toks[1].lexeme, "o7")
        self.assertEqual(toks[2].type, "SOURCE_REF")
        self.assertEqual(toks[2].lexeme, "s3")

        # invalid references throw DslSyntaxError
        cases = [
            ("render(o8)", "Output surface reference 'o8' is out of range; expected o0-o7 at line 1 col 8"),
            ("read(o99).write(o0)", "Output surface reference 'o99' is out of range; expected o0-o7 at line 1 col 6"),
            ("read(o0).write(o10)", "Output surface reference 'o10' is out of range; expected o0-o7 at line 1 col 16"),
        ]
        for src, expected_msg in cases:
            with self.subTest(src=src):
                with self.assertRaises(DslSyntaxError) as ctx:
                    lex(src)
                self.assertEqual(str(ctx.exception), expected_msg)

        # member segments foo.o8 and foo.o99 are allowed
        member_toks = lex("foo.o0 foo.o7 foo.o8 foo.o99")
        output_refs = [t for t in member_toks if t.type == "OUTPUT_REF"]
        self.assertEqual([t.lexeme for t in output_refs], ["o0", "o7", "o8", "o99"])

        # other surface reference families preserve multi-digit numbers
        other_toks = lex("s99 vol99 geo99 xyz99 vel99 rgba99 mesh99")
        ref_tokens = [(t.type, t.lexeme) for t in other_toks[:-1]]
        self.assertEqual(
            ref_tokens,
            [
                ("SOURCE_REF", "s99"),
                ("VOL_REF", "vol99"),
                ("GEO_REF", "geo99"),
                ("XYZ_REF", "xyz99"),
                ("VEL_REF", "vel99"),
                ("RGBA_REF", "rgba99"),
                ("MESH_REF", "mesh99"),
            ],
        )

    def test_diagnostic_source_columns_and_locations(self):
        result = validate_dsl('search synth\n  read(123).write(o0)')
        diagnostics = result.get('diagnostics', [])
        diag_summary = [(d.get('code'), d.get('line'), d.get('column'), d.get('location')) for d in diagnostics]
        self.assertEqual(
            diag_summary,
            [
                ('S001', 2, 3, {'line': 2, 'column': 3}),
                ('S005', 2, 13, {'line': 2, 'column': 13}),
            ],
        )

        # explicit column on caller-supplied AST locations takes precedence over col
        registry = EffectRegistry.load_from_directory()
        ast_tree = parse(lex('search synth\n  read(123).write(o0)'), registry)
        ast_tree['plans'][0]['chain'][0]['loc']['column'] = 9
        res2 = validate(ast_tree, registry)
        self.assertEqual(res2['diagnostics'][0].get('column'), 9)
        self.assertEqual(res2['diagnostics'][0].get('location'), {'line': 2, 'column': 9})

        # unlocated AST node does not invent location
        missing_res = validate_dsl('search synth\n  missing().write(o0)')
        missing_diag = next(d for d in missing_res.get('diagnostics', []) if d.get('identifier') == 'missing')
        self.assertEqual(missing_diag.get('code'), 'S001')
        self.assertNotIn('location', missing_diag)
        self.assertNotIn('line', missing_diag)
        self.assertNotIn('column', missing_diag)

        # diagnostics.make helper populates location when line and column are present
        diag_record = lang_diag.make('S001', line=3, column=5)
        self.assertEqual(diag_record.get('location'), {'line': 3, 'column': 5})
        self.assertEqual(diag_record.get('line'), 3)
        self.assertEqual(diag_record.get('column'), 5)


if __name__ == "__main__":
    unittest.main()

