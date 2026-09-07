"""Queued MIDI-expression and default-audio-channel contract regressions."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'td'))
from noisemaker.compiler.lang.effect_registry import EffectRegistry
from noisemaker.compiler.lang.lexer import lex
from noisemaker.compiler.lang.parser import parse
from noisemaker.compiler.lang.validator import validate
from noisemaker.runtime.automation import resolve_uniform_value, get_audio_input_requirements


def compile_expression(expression):
    registry = EffectRegistry.load_from_directory()
    source = 'search synth\nsolid(alpha: ' + expression + ').write(o0)\nrender(o0)'
    result = validate(parse(lex(source), registry), registry)
    return result['plans'][0]['chain'][0]['args']['alpha'], result['diagnostics']


class MidiExpressionTests(unittest.TestCase):
    def test_named_modes_compile(self):
        for mode, name in enumerate(('cc', 'cc14', 'nrpn', 'pitchBend', 'pressure', 'polyPressure'), 5):
            with self.subTest(name=name):
                value, diagnostics = compile_expression('midi(2, midiMode.%s, nrpn: 42)' % name)
                self.assertEqual([], diagnostics)
                self.assertEqual(mode, value['mode'])

    def test_zone_and_static_selector_guards(self):
        value, diagnostics = compile_expression('midi(zone: midiZone.upper, members: 3, mode: midiMode.pressure)')
        self.assertEqual([], diagnostics)
        self.assertEqual(1, value['zone'])
        self.assertNotIn('channel', value)
        for expression in ('midi(17, midiMode.cc)', 'midi(1, midiMode.cc14, cc: 32)',
                           'midi(1, midiMode.nrpn)', 'midi(zone: midiZone.lower, members: 0)'):
            with self.subTest(expression=expression):
                value, diagnostics = compile_expression(expression)
                self.assertTrue(value['_invalid'])
                self.assertTrue(diagnostics)

    def test_expression_runtime_and_mpe(self):
        channel = dict(key=60, gate=1, cc={1:64}, cc14={1:8193}, nrpn={42:12000},
                       pitchBend=4096, pressure=90, polyPressure={60:80})
        midi = SimpleNamespace(get_channel=lambda number: channel,
                               get_zone_voice=lambda config: dict(key=60, channel=channel))
        expected = (64/127, 8193/16383, 12000/16383, 4096/16383, 90/127, 80/127)
        for mode, raw in enumerate(expected, 5):
            value = dict(type='Midi', channel=2, mode=mode, min=0.2, max=0.8, nrpn=42)
            self.assertAlmostEqual(0.2+raw*0.6, resolve_uniform_value(value, 0, external_state={'midi':midi}))
            value.pop('channel'); value['zone'] = 0
            self.assertAlmostEqual(0.2+raw*0.6, resolve_uniform_value(value, 0, external_state={'midi':midi}))
            value['members'] = 0
            self.assertEqual(0.2, resolve_uniform_value(value, 0, external_state={'midi':midi}))

    def test_compiled_selectors_read_string_keyed_snapshots(self):
        for mode, selector, field, maximum in (('cc', 'cc:31', 'cc', 127),
                                                ('cc14', 'cc:31', 'cc14', 16383),
                                                ('nrpn', 'nrpn:31', 'nrpn', 16383)):
            value, diagnostics = compile_expression('midi(2, midiMode.%s, %s)' % (mode, selector))
            self.assertEqual([], diagnostics)
            state = {'channels': {'2': {field: {'31': maximum}}}}
            self.assertEqual(1, resolve_uniform_value(value, 0, external_state={'midi': state}))

    def test_default_audio_channel_and_requirements(self):
        audio, diagnostics = compile_expression('audio(audioBand.raw, channel: 32)')
        self.assertEqual([], diagnostics)
        state = SimpleNamespace(get_device_channel_state=lambda config: dict(raw=-0.5, rawReady=True))
        self.assertEqual(0.25, resolve_uniform_value(audio, 0, external_state={'audio':state}))
        graph = SimpleNamespace(passes=[SimpleNamespace(uniforms={'alpha':audio}, effect_key='synth.solid')])
        requirements = get_audio_input_requirements(graph, Path(__file__).resolve().parents[1]/'td/noisemaker/effects')
        self.assertFalse(requirements['needsLegacy'])
        self.assertEqual([dict(id=None,name=None,channel=32,needsRaw=True)], requirements['selected'])
        audio, diagnostics = compile_expression('audio(audioBand.raw, channel: 33)')
        self.assertTrue(audio['_invalid'])
        self.assertEqual(0, resolve_uniform_value(audio, 0, external_state={'audio':state}))


if __name__ == '__main__':
    unittest.main()
