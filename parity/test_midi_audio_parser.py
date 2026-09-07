#!/usr/bin/env python3
"""App-free regressions for MIDI/audio selector syntax mirrored from upstream."""

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "td"))

from noisemaker.compiler.lang.dsl_syntax_error import DslSyntaxError  # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402
from noisemaker.compiler.lang.enums import std  # noqa: E402
from noisemaker.compiler.lang.lexer import lex  # noqa: E402
from noisemaker.compiler.lang.parser import parse  # noqa: E402


def parse_expr(source):
    program = parse(lex("search synth\nlet input = " + source + "\n"), EffectRegistry())
    return program["vars"][0]["expr"]


class MidiAudioParserTests(unittest.TestCase):
    def test_midi_mixed_arguments_are_dense_and_preserve_identity(self):
        midi = parse_expr(
            'midi(channel: 2, midiMode.triggerNote, 0.25, 0.75, 0.5, '
            'name: "Controller", id: "port-a")'
        )

        self.assertEqual(midi["mode"]["path"], ["midiMode", "triggerNote"])
        self.assertEqual(midi["min"]["value"], 0.25)
        self.assertEqual(midi["max"]["value"], 0.75)
        self.assertEqual(midi["sensitivity"]["value"], 0.5)
        self.assertEqual(midi["name"]["value"], "Controller")
        self.assertEqual(midi["id"]["value"], "port-a")

    def test_audio_mixed_arguments_are_dense_and_preserve_selector(self):
        audio = parse_expr(
            'audio(band: audioBand.raw, 0.25, 0.75, channel: 2, '
            'name: "Interface", id: "device-b")'
        )

        self.assertEqual(audio["band"]["path"], ["audioBand", "raw"])
        self.assertEqual(audio["min"]["value"], 0.25)
        self.assertEqual(audio["max"]["value"], 0.75)
        self.assertEqual(audio["channel"]["value"], 2)
        self.assertEqual(audio["name"]["value"], "Interface")
        self.assertEqual(audio["id"]["value"], "device-b")

    def test_selector_invariants_reject_invalid_calls(self):
        invalid = (
            'midi(1, id: "port-a")',
            'midi(1, midiMode.velocity, 0, 1, 1, "Controller")',
            'midi(1, bogus: 1)',
            'midi(1, name: Controller)',
            'midi(1, name: "")',
            'audio(audioBand.low, name: "Interface")',
            'audio(audioBand.low, id: "device-b")',
            'audio(audioBand.low, 0, 1, 2)',
            'audio(audioBand.low, bogus: 1)',
            'audio(audioBand.low, channel: 1, name: Interface)',
            'audio(audioBand.low, channel: 1, name: "")',
        )

        for source in invalid:
            with self.subTest(source=source), self.assertRaises(DslSyntaxError):
                parse_expr(source)

    def test_unknown_keyword_diagnostic_uses_source_order(self):
        cases = (
            (
                'midi(1, zzz: 1, aaa: 2)',
                "midi() unknown parameter 'zzz' at line 2 col 13. Valid: "
                "channel, mode, min, max, sensitivity, name, id, cc, nrpn, zone, members",
            ),
            (
                'audio(audioBand.low, zzz: 1, aaa: 2)',
                "audio() unknown parameter 'zzz' at line 2 col 13. Valid: "
                "band, min, max, channel, name, id",
            ),
        )

        for source, expected in cases:
            with self.subTest(source=source), self.assertRaisesRegex(
                DslSyntaxError, "^" + expected.replace("(", r"\(").replace(")", r"\)") + "$"
            ):
                parse_expr(source)

    def test_audio_raw_enum_is_four(self):
        self.assertEqual(std()["audioBand"]["raw"]["value"], 4)


if __name__ == "__main__":
    unittest.main()
