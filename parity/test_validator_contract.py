#!/usr/bin/env python3
"""App-free regressions for validator contracts mirrored from upstream."""

import math
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

    def test_lexer_structured_diagnostics(self):
        cases = [
            (
                '@noise()',
                'L001',
                "Unexpected character '@' at line 1 col 1",
                {'line': 1, 'column': 1},
                {'start': 0, 'end': 1},
            ),
            (
                'noise("unterminated)',
                'L002',
                'Unterminated string literal at line 1 col 7',
                {'line': 1, 'column': 7},
                {'start': 6, 'end': 20},
            ),
            (
                '"""unterminated triple',
                'L002',
                'Unterminated triple-quoted string at line 1 col 1',
                {'line': 1, 'column': 1},
                {'start': 0, 'end': 22},
            ),
            (
                '/* unclosed comment\nnoise()',
                'L003',
                'Unterminated comment at line 1 col 1',
                {'line': 1, 'column': 1},
                {'start': 0, 'end': 27},
            ),
            (
                'search synth\nnoise().write(o8)',
                'L004',
                "Output surface reference 'o8' is out of range; expected o0-o7 at line 2 col 15",
                {'line': 2, 'column': 15},
                {'start': 27, 'end': 29},
            ),
        ]

        for src, code, message, location, span in cases:
            with self.subTest(code=code, src=src):
                with self.assertRaises(DslSyntaxError) as ctx:
                    lex(src)
                err = ctx.exception
                self.assertEqual(str(err), message)
                diag = err.diagnostic
                self.assertIsNotNone(diag)
                self.assertEqual(diag['code'], code)
                self.assertEqual(diag['stage'], 'lexer')
                self.assertEqual(diag['severity'], 'error')
                self.assertEqual(diag['message'], message)
                self.assertEqual(diag['location'], location)
                self.assertEqual(diag['span'], span)

    def test_parser_structured_diagnostics(self):
        cases = [
            (
                "opening parenthesis",
                "search synth\nrender o0",
                "P001",
                "Expect '(' at line 2 col 8",
                2,
                8,
            ),
            (
                "closing parenthesis",
                "search synth\nrender(o0",
                "P002",
                "Expect ')' at line 2 col 10",
                2,
                10,
            ),
            (
                "identifier",
                "search synth\nlet = 1",
                "P001",
                "Expected identifier at line 2 col 5",
                2,
                5,
            ),
            (
                "assignment sign",
                "search synth\nlet x 1",
                "P001",
                "Expect '=' at line 2 col 7",
                2,
                7,
            ),
            (
                "block opening",
                "search synth\nif(true) return 1",
                "P001",
                "Expect '{' at line 2 col 10",
                2,
                10,
            ),
            (
                "end of input",
                "search synth\nrender(o0) xyz",
                "P001",
                "Expected end of input at line 2 col 12",
                2,
                12,
            ),
            (
                "call closing parenthesis",
                "search synth\nfoo(1",
                "P002",
                "Expect ')' at line 2 col 6",
                2,
                6,
            ),
            (
                "write3d separator",
                "search synth\nfoo().write3d(tex3d0 geo0)",
                "P001",
                "Expect ',' between tex3d and geo in write3d() at line 2 col 22",
                2,
                22,
            ),
            (
                "CRLF and tab offsets",
                "// 😀\r\nsearch synth\r\n\trender(o0",
                "P002",
                "Expect ')' at line 3 col 11",
                3,
                11,
            ),
            (
                "UTF-16 column",
                'search synth\nlet x = "😀"; render o0',
                "P001",
                "Expect '(' at line 2 col 22",
                2,
                22,
            ),
        ]

        for name, src, code, message, line, col in cases:
            with self.subTest(name=name, code=code):
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(lex(src))
                err = ctx.exception
                self.assertEqual(str(err), message)
                diag = err.diagnostic
                self.assertIsNotNone(diag)
                self.assertEqual(diag["code"], code)
                self.assertEqual(diag["stage"], "parser")
                self.assertEqual(diag["severity"], "error")
                self.assertEqual(diag["message"], message)
                self.assertEqual(diag["location"], {"line": line, "column": col})
                self.assertIsNone(diag["span"])

    def test_parser_diagnostic_explicit_unavailable_locations(self):
        cases = [
            ({}, "undefined", "undefined"),
            ({"line": 1}, "1", "undefined"),
            ({"line": 0, "col": 1}, "0", "1"),
            ({"line": 1, "col": float("nan")}, "1", "NaN"),
        ]

        for coordinates, line_str, col_str in cases:
            with self.subTest(coordinates=coordinates):
                tokens = lex("search synth\nrender o0")
                modified = []
                for t in tokens:
                    if t.type == "OUTPUT_REF":
                        d = {"type": t.type, "lexeme": t.lexeme}
                        d.update(coordinates)
                        modified.append(d)
                    else:
                        modified.append(t)

                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(modified)
                err = ctx.exception
                expected_msg = f"Expect '(' at line {line_str} col {col_str}"
                self.assertEqual(str(err), expected_msg)
                self.assertEqual(
                    err.diagnostic,
                    {
                        "code": "P001",
                        "stage": "parser",
                        "severity": "error",
                        "message": expected_msg,
                        "location": None,
                        "span": None,
                    },
                )

    def test_renderLandscape3d_filtering_define_choices(self):
        default_graph = compile_dsl(
            "search synth, synth3d, render\n"
            "heightmap3d(heightTex: read(o1), tex: read(o2)).renderLandscape3d().write(o0)\n"
            "render(o0)\n"
        )
        iso_graph = compile_dsl(
            "search synth, synth3d, render\n"
            "heightmap3d(heightTex: read(o1), tex: read(o2)).renderLandscape3d(filtering: isosurface).write(o0)\n"
            "render(o0)\n"
        )
        voxel_graph = compile_dsl(
            "search synth, synth3d, render\n"
            "heightmap3d(heightTex: read(o1), tex: read(o2)).renderLandscape3d(filtering: voxel).write(o0)\n"
            "render(o0)\n"
        )

        default_pass = next(
            p for p in default_graph["passes"] if p["effectKey"] == "render.renderLandscape3d"
        )
        iso_pass = next(
            p for p in iso_graph["passes"] if p["effectKey"] == "render.renderLandscape3d"
        )
        voxel_pass = next(
            p for p in voxel_graph["passes"] if p["effectKey"] == "render.renderLandscape3d"
        )

        self.assertEqual(default_pass["defines"]["FILTERING"], 1)
        self.assertEqual(iso_pass["defines"]["FILTERING"], 0)
        self.assertEqual(voxel_pass["defines"]["FILTERING"], 1)

    def test_parser_structured_diagnostics_p003_automation(self):
        cases = [
            ("osc(type: oscKind.sine, bogus: 1)", "osc() unknown parameter 'bogus' at line 2 col 1. Valid: type, min, max, speed, offset, seed"),
            ("midi(1, 2, 3, 4, 5, 6)", "midi() name, id, cc, nrpn, zone and members are keyword-only at line 2 col 1"),
            ("midi(channel: 1, bogus: 2)", "midi() unknown parameter 'bogus' at line 2 col 1. Valid: channel, mode, min, max, sensitivity, name, id, cc, nrpn, zone, members"),
            ("midi(1, 2, 3, 4, 5, channel: 6)", "midi() has an excess positional argument at line 2 col 1"),
            ("midi()", "midi() requires 'channel' or 'zone' argument at line 2 col 1"),
            ("midi(channel: 1, zone: 2)", "midi() 'channel' and 'zone' are mutually exclusive at line 2 col 1"),
            ("midi(channel: 1, members: 2)", "midi() 'members' requires 'zone' at line 2 col 1"),
            ("midi(channel: 1, id: \"pad\")", "midi() 'id' requires readable 'name' at line 2 col 1"),
            ("midi(channel: 1, name: 1)", "midi() 'name' requires a quoted string at line 2 col 1"),
            ("midi(channel: 1, name: \"\")", "midi() 'name' must not be empty at line 2 col 1"),
            ("midi(channel: 1, name: \"pad\", id: 1)", "midi() 'id' requires a quoted string at line 2 col 1"),
            ("midi(channel: 1, name: \"pad\", id: \"\")", "midi() 'id' must not be empty at line 2 col 1"),
            ("audio(1, 2, 3, 4)", "audio() channel, name and id are keyword-only at line 2 col 1"),
            ("audio(band: 1, bogus: 2)", "audio() unknown parameter 'bogus' at line 2 col 1. Valid: band, min, max, channel, name, id"),
            ("audio(1, 2, 3, band: 4)", "audio() has an excess positional argument at line 2 col 1"),
            ("audio()", "audio() requires 'band' argument at line 2 col 1"),
            ("audio(band: 1, id: \"mic\")", "audio() 'id' requires readable 'name' at line 2 col 1"),
            ("audio(band: 1, name: \"mic\")", "audio() selected device requires both 'name' and 'channel' at line 2 col 1"),
            ("audio(band: 1, channel: 1, name: 1)", "audio() 'name' requires a quoted string at line 2 col 1"),
            ("audio(band: 1, channel: 1, name: \"\")", "audio() 'name' must not be empty at line 2 col 1"),
            ("audio(band: 1, channel: 1, name: \"mic\", id: 1)", "audio() 'id' requires a quoted string at line 2 col 1"),
            ("audio(band: 1, channel: 1, name: \"mic\", id: \"\")", "audio() 'id' must not be empty at line 2 col 1"),
        ]
        registry = EffectRegistry.load_from_directory()
        for expr, expected_msg in cases:
            src = f"search synth\n{expr}"
            with self.subTest(expr=expr):
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(lex(src), registry)
                err = ctx.exception
                self.assertEqual(str(err), expected_msg)
                diag = err.diagnostic
                self.assertIsNotNone(diag)
                self.assertEqual(diag["code"], "P003")
                self.assertEqual(diag["stage"], "parser")
                self.assertEqual(diag["severity"], "error")
                self.assertEqual(diag["message"], expected_msg)
                self.assertEqual(diag["location"], {"line": 2, "column": 1})
                self.assertIsNone(diag["span"])

        # coordinates with CRLF, tab, and surrogate pairs
        utf_src = 'search synth\r\n\tlet x = "😀"; let y = midi()'
        with self.assertRaises(DslSyntaxError) as ctx:
            parse(lex(utf_src), registry)
        err = ctx.exception
        self.assertEqual(err.diagnostic["code"], "P003")
        self.assertEqual(err.diagnostic["location"], {"line": 2, "column": 24})

    def test_parser_structured_diagnostics_p004_search(self):
        missing_msg = (
            "Missing required 'search' directive. Every program must start with 'search <namespace>, ...' to specify namespace search order."
        )
        cases = [
            ("empty program", "", missing_msg, 1, 1),
            ("missing directive after statements", "let x = 1", missing_msg, 1, 10),
            ("duplicate search directive", "search synth\nsearch filter", "Only one search directive is allowed per program at line 2 col 1", 2, 1),
            ("misplaced search directive", "let x = 1\nsearch synth", "'search' directive must appear before other statements at line 2 col 1", 2, 1),
            ("nested search directive", "search synth\nif (true) {\n  search filter\n}", "'search' directive is only allowed at the start of the program at line 3 col 3", 3, 3),
            ("missing first namespace", "search", "Expected namespace identifier after search at line 1 col 7", 1, 7),
            ("missing trailing namespace", "search synth,", "Expected namespace identifier after comma at line 1 col 14", 1, 14),
            ("invalid namespace", "search bogus", "Invalid namespace 'bogus' at line 1 col 8. Valid namespaces: io, classicNoisedeck, synth, mixer, filter, render, points, synth3d, filter3d, user", 1, 8),
            ("CRLF offset", "search synth\r\nsearch filter", "Only one search directive is allowed per program at line 2 col 1", 2, 1),
            ("UTF-16 column offset", 'search synth\nlet x = "😀"; search filter', "'search' directive must appear before other statements at line 2 col 15", 2, 15),
        ]
        registry = EffectRegistry.load_from_directory()
        for name, src, expected_msg, line, col in cases:
            with self.subTest(name=name):
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(lex(src), registry)
                err = ctx.exception
                self.assertEqual(str(err), expected_msg)
                diag = err.diagnostic
                self.assertIsNotNone(diag)
                self.assertEqual(diag["code"], "P004")
                self.assertEqual(diag["stage"], "parser")
                self.assertEqual(diag["severity"], "error")
                self.assertEqual(diag["message"], expected_msg)
                self.assertEqual(diag["location"], {"line": line, "column": col})
                self.assertIsNone(diag["span"])

    def test_parser_automation_and_search_unavailable_locations(self):
        cases = [
            ({}, "undefined", "undefined"),
            ({"line": 1}, "1", "undefined"),
            ({"line": 0, "col": 1}, "0", "1"),
            ({"line": 1, "col": float("nan")}, "1", "NaN"),
        ]
        registry = EffectRegistry.load_from_directory()
        for coordinates, line_str, col_str in cases:
            with self.subTest(coordinates=coordinates):
                tokens = [
                    {"type": "SEARCH", "lexeme": "search", "line": 1, "col": 1},
                    {"type": "IDENT", "lexeme": "synth", "line": 1, "col": 8},
                    {"type": "IDENT", "lexeme": "midi", **coordinates},
                    {"type": "LPAREN", "lexeme": "(", "line": 2, "col": 5},
                    {"type": "RPAREN", "lexeme": ")", "line": 2, "col": 6},
                    {"type": "EOF", "lexeme": "", "line": 2, "col": 7},
                ]
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(tokens, registry)
                err = ctx.exception
                expected_msg = f"midi() requires 'channel' or 'zone' argument at line {line_str} col {col_str}"
                self.assertEqual(str(err), expected_msg)
                self.assertEqual(
                    err.diagnostic,
                    {
                        "code": "P003",
                        "stage": "parser",
                        "severity": "error",
                        "message": expected_msg,
                        "location": None,
                        "span": None,
                    },
                )

                eof_tokens = [{"type": "EOF", "lexeme": "", **coordinates}]
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(eof_tokens, registry)
                err = ctx.exception
                missing_msg = (
                    "Missing required 'search' directive. Every program must start with 'search <namespace>, ...' to specify namespace search order."
                )
                self.assertEqual(str(err), missing_msg)
                self.assertEqual(
                    err.diagnostic,
                    {
                        "code": "P004",
                        "stage": "parser",
                        "severity": "error",
                        "message": missing_msg,
                        "location": None,
                        "span": None,
                    },
                )

    def test_parser_structured_diagnostics_p005_output(self):
        output_failures = [
            ("invalid render target", "search synth\nrender(1)", "Expected output reference in render()", 2, 8),
            ("render target at EOF", "search synth\nrender(", "Expected output reference in render()", 2, 8),
            ("write in expression", "search synth\nlet x = diagProbe().write(o0)", "'.write()' is only allowed in statement context at line 2 col 21", 2, 21),
            ("write3d in expression", "search synth\nlet x = diagProbe().write3d(vol0, geo0)", "'.write()' is only allowed in statement context at line 2 col 21", 2, 21),
            ("missing write surface", "search synth\ndiagProbe().write()", "write() requires an explicit surface reference (e.g., o0, o1, xyz0, vel0, rgba0, mesh0, none) at line 2 col 19", 2, 19),
            ("write surface at EOF", "search synth\ndiagProbe().write(", "write() requires an explicit surface reference (e.g., o0, o1, xyz0, vel0, rgba0, mesh0, none) at line 2 col 19", 2, 19),
            ("invalid write surface", "search synth\ndiagProbe().write(1)", "write() requires an explicit surface reference (e.g., o0, o1, xyz0, vel0, rgba0, mesh0, none) at line 2 col 19", 2, 19),
            ("invalid write3d texture", "search synth\ndiagProbe().write3d(1, geo0)", "Expected tex3d reference in write3d() at line 2 col 21", 2, 21),
            ("write3d texture at EOF", "search synth\ndiagProbe().write3d(", "Expected tex3d reference in write3d() at line 2 col 21", 2, 21),
            ("invalid write3d geometry", "search synth\ndiagProbe().write3d(vol0, 1)", "Expected geo reference in write3d() at line 2 col 27", 2, 27),
            ("write3d geometry at EOF", "search synth\ndiagProbe().write3d(vol0,", "Expected geo reference in write3d() at line 2 col 26", 2, 26),
            ("CRLF and tab render target", "// 😀\r\nsearch synth\r\n\trender(\"😀\")", "Expected output reference in render()", 3, 9),
            ("UTF-16 render target column", 'search synth\nlet x = "😀"; render(none)', "Expected output reference in render()", 2, 22),
        ]
        registry = EffectRegistry.load_from_directory()
        for name, src, expected_msg, line, col in output_failures:
            with self.subTest(name=name):
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(lex(src), registry)
                err = ctx.exception
                self.assertEqual(str(err), expected_msg)
                diag = err.diagnostic
                self.assertIsNotNone(diag)
                self.assertEqual(diag["code"], "P005")
                self.assertEqual(diag["stage"], "parser")
                self.assertEqual(diag["severity"], "error")
                self.assertEqual(diag["message"], expected_msg)
                self.assertEqual(diag["location"], {"line": line, "column": col})
                self.assertIsNone(diag["span"])

    def test_parser_output_unavailable_locations(self):
        output_failures = [
            ("invalid render target", "search synth\nrender(1)"),
            ("render target at EOF", "search synth\nrender("),
            ("write in expression", "search synth\nlet x = diagProbe().write(o0)"),
            ("write3d in expression", "search synth\nlet x = diagProbe().write3d(vol0, geo0)"),
            ("missing write surface", "search synth\ndiagProbe().write()"),
            ("write surface at EOF", "search synth\ndiagProbe().write("),
            ("invalid write surface", "search synth\ndiagProbe().write(1)"),
            ("invalid write3d texture", "search synth\ndiagProbe().write3d(1, geo0)"),
            ("write3d texture at EOF", "search synth\ndiagProbe().write3d("),
            ("invalid write3d geometry", "search synth\ndiagProbe().write3d(vol0, 1)"),
            ("write3d geometry at EOF", "search synth\ndiagProbe().write3d(vol0,"),
            ("CRLF and tab render target", '// 😀\r\nsearch synth\r\n\trender("😀")'),
            ("UTF-16 render target column", 'search synth\nlet x = "😀"; render(none)'),
        ]
        cases = [
            ({}, "undefined", "undefined"),
            ({"line": 1}, "1", "undefined"),
            ({"line": 0, "col": 1}, "0", "1"),
            ({"line": 1, "col": float("nan")}, "1", "NaN"),
        ]
        registry = EffectRegistry.load_from_directory()
        for name, src in output_failures:
            for coordinates, _, _ in cases:
                with self.subTest(name=name, coordinates=coordinates):
                    tokens = [
                        {"type": t.type, "lexeme": t.lexeme, **coordinates}
                        for t in lex(src)
                    ]
                    with self.assertRaises(DslSyntaxError) as ctx:
                        parse(tokens, registry)
                    err = ctx.exception
                    self.assertIsNotNone(err.diagnostic)
                    self.assertEqual(err.diagnostic["code"], "P005")
                    self.assertEqual(err.diagnostic["stage"], "parser")
                    self.assertEqual(err.diagnostic["severity"], "error")
                    self.assertEqual(err.diagnostic["message"], str(err))
                    self.assertIsNone(err.diagnostic["location"])
                    self.assertIsNone(err.diagnostic["span"])

    def test_parser_output_syntax_preserves_expectation_precedence(self):
        cases = [
            ("search synth\nrender o0", "P001", "Expect '(' at line 2 col 8"),
            ("search synth\nrender(o0", "P002", "Expect ')' at line 2 col 10"),
            ("search synth\nrender(o0) render(o1)", "P001", "Expected end of input at line 2 col 12"),
            ("search synth\ndiagProbe().write(o0", "P002", "Expect ')' at line 2 col 21"),
            ("search synth\ndiagProbe().write3d(vol0 geo0)", "P001", "Expect ',' between tex3d and geo in write3d() at line 2 col 26"),
        ]
        registry = EffectRegistry.load_from_directory()
        for src, code, message in cases:
            with self.subTest(src=src):
                with self.assertRaises(DslSyntaxError) as ctx:
                    parse(lex(src), registry)
                err = ctx.exception
                self.assertEqual(str(err), message)
                self.assertIsNotNone(err.diagnostic)
                self.assertEqual(err.diagnostic["code"], code)

    def test_parser_valid_output_operations(self):
        registry = EffectRegistry.load_from_directory()
        for name, expected_type in [
            ("o0", "OutputRef"), ("xyz0", "XyzRef"), ("vel0", "VelRef"),
            ("rgba0", "RgbaRef"), ("mesh0", "MeshRef"), ("none", "OutputRef"),
        ]:
            ast_res = parse(lex(f"search synth\ndiagProbe().write({name})"), registry)
            self.assertEqual(
                ast_res["plans"][0]["chain"][1],
                {"type": "Write", "surface": {"type": expected_type, "name": name}, "loc": {"line": 2, "col": 13}},
            )
            self.assertEqual(ast_res["plans"][0]["write"], {"type": expected_type, "name": name})
            self.assertIsNone(ast_res["render"])

        for tex, tex_type, geo, geo_type in [
            ("vol0", "VolRef", "geo0", "GeoRef"),
            ("o0", "OutputRef", "o1", "OutputRef"),
            ("volume", "Ident", "geometry", "Ident"),
        ]:
            ast_res = parse(lex(f"search synth\ndiagProbe().write3d({tex}, {geo})"), registry)
            self.assertEqual(
                ast_res["plans"][0]["chain"][1],
                {
                    "type": "Write3D",
                    "tex3d": {"type": tex_type, "name": tex},
                    "geo": {"type": geo_type, "name": geo},
                    "loc": {"line": 2, "col": 13},
                },
            )


if __name__ == "__main__":
    unittest.main()

