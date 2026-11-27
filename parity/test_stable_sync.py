"""Stable compiler contracts exercised through parsing and validation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'td'))

from noisemaker.compiler import compile_dsl
from noisemaker.compiler.lang.effect_registry import EffectRegistry
from noisemaker.compiler.lang.lexer import lex
from noisemaker.compiler.lang.parser import parse
from noisemaker.compiler.lang.validator import validate
from noisemaker.compiler.lang.dsl_syntax_error import DslSyntaxError


class StableSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = EffectRegistry.load_from_directory()

    def parse_source(self, source):
        try:
            return parse(lex(source), self.registry)
        except Exception as error:
            self.fail('Stable source must parse: %s' % error)

    def compile_source(self, source):
        return validate(self.parse_source(source), self.registry)

    def test_comments_inside_calls_and_arrays_do_not_change_values(self):
        tree = self.parse_source(
            'search synth\nnoise(/* before */ scaleX: /* value */ 2 + 3 * 4, '
            'scaleY: [1, /* member */ 2, /* end */], /* end */).write(o0)')
        args = tree['plans'][0]['chain'][0]['kwargs']
        self.assertEqual(14, args['scaleX']['value'])
        self.assertEqual([1, 2], [x['value'] for x in args['scaleY']['elements']])

    def test_call_and_folded_literal_keep_source_locations(self):
        tree = self.parse_source('search synth\nnoise(scaleX: -2 + 3 * 4).write(o0)')
        call = tree['plans'][0]['chain'][0]
        self.assertEqual({'line': 2, 'col': 1}, call.get('loc'))
        self.assertEqual({'line': 2, 'col': 16}, call['kwargs']['scaleX'].get('loc'))
        self.assertEqual(10, call['kwargs']['scaleX']['value'])

    def test_literal_diagnostics_keep_the_written_location(self):
        result = self.compile_source('search synth\nnoise(scaleX: "bad").write(o0)')
        diagnostic = next(d for d in result['diagnostics'] if d['code'] == 'S001')
        self.assertEqual({'line': 2, 'column': 15}, diagnostic.get('location'))

    def test_element_ids_survive_effect_read_and_write_validation(self):
        result = self.compile_source(
            'search synth\nnoise(_id: "seed").write(o0, _id: "out")\n'
            'read(tex: o0, _id: "copy").write(o1)')
        self.assertEqual([], result['diagnostics'])
        self.assertEqual(['seed', 'out', 'copy', None], [
            step['args'].get('_id') for plan in result['plans'] for step in plan['chain']])

    def test_element_ids_survive_volume_read_and_write_validation(self):
        result = self.compile_source(
            'search synth3d\nnoise3d(_id: "volume").write3d(vol0, geo0, _id: "store")\n'
            'read3d(tex3d: vol0, geo: geo0, _id: "readVolume").write3d(vol1, geo1)')
        self.assertEqual([], result['diagnostics'])
        self.assertEqual(['volume', 'store', 'readVolume', None], [
            step['args'].get('_id') for plan in result['plans'] for step in plan['chain']])

    def test_element_ids_do_not_become_shader_uniforms(self):
        graph = compile_dsl('search synth\nnoise(_id: "seed").write(o0)', self.registry)
        self.assertTrue(graph['passes'])
        for pass_ in graph['passes']:
            self.assertNotIn('_id', pass_['uniforms'])

    def test_invalid_or_variable_element_ids_are_ignored_without_diagnostics(self):
        for value in ('"1bad"', '"bad-id"', '""', '42', 'true', 'saved'):
            with self.subTest(value=value):
                result = self.compile_source(
                    'search synth\nlet saved = "Valid"\nnoise(_id: %s).write(o0)' % value)
                self.assertEqual([], result['diagnostics'])
                self.assertNotIn('_id', result['plans'][0]['chain'][0]['args'])

    def test_excess_positionals_warn_without_changing_bound_values(self):
        result = self.compile_source('search synth\nsolid(#804020, 0.5, 99).write(o0)')
        self.assertEqual(['S009'], [d['code'] for d in result['diagnostics']])
        self.assertEqual('warning', result['diagnostics'][0]['severity'])
        self.assertEqual({'line': 2, 'column': 21}, result['diagnostics'][0]['location'])
        args = result['plans'][0]['chain'][0]['args']
        self.assertEqual([128 / 255, 64 / 255, 32 / 255, 1], args['color'])
        self.assertEqual(0.5, args['alpha'])

    def test_let_alias_keeps_call_site_for_unknown_effect_diagnostic(self):
        result = self.compile_source('search synth\nlet alias = nonexistent()\nalias().write(o0)')
        diagnostic = next(d for d in result['diagnostics'] if d['code'] == 'S001')
        self.assertEqual({'line': 3, 'column': 1}, diagnostic.get('location'))

    def test_experimental_grammar_remains_rejected(self):
        for source in ('noise(1, scaleX: 2)', 'noise(scaleX: {x: 2})'):
            with self.subTest(source=source):
                with self.assertRaises(DslSyntaxError):
                    parse(lex('search synth\n' + source + '.write(o0)'), self.registry)

    def test_let_bound_hex_color_keeps_components_when_one_is_overridden(self):
        registry = EffectRegistry()
        registry.register({
            'name': 'RGB', 'namespace': 'test', 'func': 'rgb',
            'globals': {key: {'type': 'float', 'default': 1}
                        for key in ('r', 'g', 'b', 'alpha')},
            'passes': [{'program': 'rgb', 'inputs': {}, 'outputs': {'color': 'outputTex'}}],
        })
        source = 'search test\nlet color = rgb(#804020)\ncolor(r: 0.25).write(o0)'
        result = validate(parse(lex(source), registry), registry)
        self.assertEqual([], result['diagnostics'])
        self.assertEqual({'r': 0.25, 'g': 64 / 255, 'b': 32 / 255, 'alpha': 1},
                         result['plans'][0]['chain'][0]['args'])

    def test_chain_argument_with_read_reports_error_instead_of_expanding(self):
        registry = EffectRegistry()
        registry.register({
            'name': 'Input', 'namespace': 'test', 'func': 'image',
            'globals': {'tex': {'type': 'surface', 'default': 'inputTex'}},
            'passes': [{'program': 'image', 'inputs': {'tex': 'tex'},
                        'outputs': {'color': 'outputTex'}}],
        })
        source = 'search test\nimage(tex: read(o1).image()).write(o0)'
        result = validate(parse(lex(source), registry), registry)
        self.assertEqual(['S001'], [d['code'] for d in result['diagnostics']])
        self.assertEqual({'line': 2, 'column': 12}, result['diagnostics'][0]['location'])
        self.assertIsNone(result['plans'][0]['chain'][0]['args']['tex'])

    def test_particle_outputs_reach_reader_in_each_emitter_scope(self):
        registry = EffectRegistry.load_from_directory()
        registry.register({
            'name': 'Reader', 'namespace': 'test', 'func': 'reader', 'globals': {},
            'passes': [{'program': 'reader',
                        'inputs': {'xyzTex': 'inputXyz', 'velTex': 'inputVel',
                                   'rgbaTex': 'inputRgba'},
                        'outputs': {'color': 'outputTex'}}],
        })
        graph = compile_dsl(
            'search synth, render, points, test\n'
            'noise().pointsEmit().attractor().reader()'
            '.pointsEmit().attractor().reader().write(o0)', registry)
        producers = [p for p in graph['passes']
                     if p.get('func') == 'attractor' and 'outXYZ' in p['outputs']]
        readers = [p for p in graph['passes'] if p.get('func') == 'reader']
        self.assertEqual(len(producers), 2)
        self.assertEqual(len(readers), 2)
        for producer, reader in zip(producers, readers):
            for input_name, output_name in (('xyzTex', 'outXYZ'),
                                            ('velTex', 'outVel'),
                                            ('rgbaTex', 'outRGBA')):
                self.assertEqual(reader['inputs'][input_name], producer['outputs'][output_name])
                self.assertIn(reader['inputs'][input_name], graph['textures'])
        self.assertNotEqual(readers[0]['inputs'], readers[1]['inputs'])


if __name__ == '__main__':
    unittest.main()
