"""Contract tests for noisemaker.runtime.effect_validator (GAP-003 port).

Mirrors the reference suite `shaders/tests/test_effect_definition_validation.js`
(noise@9d3474dfdc6c): structure-only validation over the definition schema,
deterministic, side-effect-free, insertion-ordered errors. The Effect-instance
branches are JS-only (see the port's module docstring); the corpus test runs
against the converted `td/noisemaker/effects/**/*.json` inventory.
"""

import copy
import glob
import json
import os
import sys
import unittest

sys.path.insert(0, 'td')

from noisemaker.runtime.effect_validator import (  # noqa: E402
    resolve_std_enum,
    validate_effect_definition,
)

EFFECTS_ROOT = 'td/noisemaker/effects'


def valid_definition():
    """A complete, valid plain-object definition exercising the schema surface."""
    return {
        'name': 'Validator Probe',
        'namespace': 'synth',
        'func': 'validatorProbe',
        'description': 'Used by the definition-validator tests',
        'tags': ['noise', 'util'],
        'openCategories': ['general'],
        'defaultProgram': 'search synth\nvalidatorProbe().write(o0)',
        'hidden': False,
        'uniformLayout': {
            'resolution': {'slot': 0, 'components': 'xy'},
            'time': {'slot': 0, 'components': 'z'},
        },
        'uniformLayouts': {
            'alt': {'amount': {'slot': 0, 'components': 'x'}}
        },
        'paramAliases': {'amt': 'amount'},
        'textures': {
            'scratch': {'width': 64, 'height': '100%', 'format': 'rgba16f'},
            'scaled': {
                'width': {'param': 'volumeSize', 'power': 2, 'default': 1024},
                'height': {'screenDivide': 'zoom', 'default': 8},
            },
        },
        'globals': {
            'amount': {
                'type': 'float', 'default': 0.5, 'uniform': 'amount',
                'min': 0, 'max': 1, 'step': 0.01, 'zero': 0,
                'ui': {'label': 'amount', 'control': 'slider', 'category': 'effect'},
            },
            'mode': {
                'type': 'int', 'default': 1, 'uniform': 'mode', 'define': 'PROBE_MODE',
                'choices': {'off': 0, 'on': 1, 'Group:': None},
                'ui': {'label': 'mode', 'control': 'dropdown', 'enabledBy': 'amount'},
            },
            'flag': {
                'type': 'boolean', 'default': True, 'uniform': 'flag',
                'ui': {'label': 'flag', 'control': 'checkbox',
                       'enabledBy': {'param': 'mode', 'eq': 1}},
            },
            'tint': {
                'type': 'color', 'default': [1, 0, 0], 'uniform': 'tint',
                'ui': {'label': 'tint', 'control': 'color'},
            },
            'point': {
                'type': 'vec3', 'default': [0, 0, 0], 'uniform': 'point',
                'min': [-1, -1, -1], 'max': [1, 1, 1],
                'ui': {'label': 'point', 'control': 'vector3', 'format': 'x/y/z'},
            },
            'table': {
                'type': 'int', 'default': 7, 'choices': {'a': 7, 'b': 9},
                'ui': {'label': 'table', 'control': 'dropdown', 'hidden': True},
            },
            'surfaceIn': {
                'type': 'surface', 'default': 'none', 'colorModeUniform': 'surfaceActive',
                'ui': {'label': 'surface', 'control': False},
            },
        },
        'passes': [{
            'name': 'render',
            'program': 'probe',
            'type': 'compute',
            'drawMode': 'points',
            'count': 'input',
            'countUniform': 'mode',
            'repeat': 2,
            'blend': ['ONE', 'ONE_MINUS_SRC_ALPHA'],
            'drawBuffers': 2,
            'workgroups': [8, 8, 1],
            'viewport': {'width': {'param': 'volumeSize', 'paramDefault': 64}, 'height': 32},
            'conditions': {
                'runIf': [{'uniform': 'mode', 'equals': 1}],
                'skipIf': [{'uniform': 'flag', 'equals': False}],
            },
            'uniforms': {'amount': 'amount', 'literal': 3},
            'inputs': {'srcTex': 'inputTex', 'scratchTex': 'scratch',
                       'paramTex': 'surfaceIn'},
            'outputs': {'fragColor': 'outputTex'},
        }],
    }


class TestEffectValidator(unittest.TestCase):

    def validate(self, d):
        return validate_effect_definition(d)

    def test_null_array_and_primitive_containers_produce_errors_without_throwing(self):
        self.assertEqual(validate_effect_definition(None),
                         ['Effect definition is null or undefined'])
        for bad in ([], ['x'], 'string', 42, True):
            errors = validate_effect_definition(bad)
            self.assertIsInstance(errors, list)
            self.assertTrue(errors)
            for e in errors:
                self.assertIsInstance(e, str)

    def test_valid_plain_object_definition_returns_no_errors(self):
        self.assertEqual(validate_effect_definition(valid_definition()), [])

    def test_unknown_top_level_field_is_diagnosed(self):
        d = valid_definition()
        d['globalz'] = d['globals']
        self.assertEqual(
            len([e for e in validate_effect_definition(d) if 'globalz' in e]), 1)

    def test_unknown_spec_ui_pass_and_texture_fields_are_diagnosed(self):
        d = valid_definition()
        d['globals']['amount']['unkown'] = 1
        d['globals']['mode']['ui']['colour'] = 'red'
        d['passes'][0]['progam'] = 'typo'
        d['textures']['scratch']['widht'] = 8
        errors = validate_effect_definition(d)
        for needle in ('unkown', 'colour', 'progam', 'widht'):
            self.assertEqual(len([e for e in errors if needle in e]), 1, needle)

    def test_malformed_containers_are_reported_without_throwing(self):
        mutations = [
            lambda d: d.update(globals=['nope']),
            lambda d: d.update(globals='nope'),
            lambda d: d.update(globals={'g': None}),
            lambda d: d.update(globals={'g': []}),
            lambda d: d.update(globals={'g': {'type': 'float', 'default': 0.5, 'ui': 'slider'}}),
            lambda d: d.update(passes={'program': 'x'}),
            lambda d: d.update(passes=[None]),
            lambda d: d.update(passes=[{'program': 'p', 'inputs': 'x'}]),
            lambda d: d.update(passes=[{'program': 'p', 'outputs': 3}]),
            lambda d: d.update(passes=[{'program': 'p', 'uniforms': 'x'}]),
            lambda d: d.update(passes=[{'program': 'p', 'conditions': 'always'}]),
            lambda d: d.update(passes=[{'program': 'p', 'conditions': {'runIf': [None]}}]),
            lambda d: d.update(passes=[{'program': 'p',
                                        'conditions': {'runIf': [{'uniform': 7}]}}]),
            lambda d: d.update(passes=[{'program': 'p',
                                        'conditions': {'runIf': [{'uniform': 'mode'}]}}]),
            lambda d: d.update(passes=[{'program': 'p', 'conditions': {
                'runIf': [{'uniform': 'mode'}]}}]),
            lambda d: d.update(textures=['x']),
            lambda d: d.update(textures={'t': 'big'}),
            lambda d: d.update(textures={'t': {'width': 'banana'}}),
            lambda d: d.update(textures={'t': {'width': {'param': 42}}}),
            lambda d: d.update(textures={'t': {'width': {'wrong': 1}}}),
            lambda d: d.update(textures={'t': {'width': -4}}),
            lambda d: d.update(textures={'t': {'format': 'rgba999'}}),
            lambda d: d.update(uniformLayout={'u': {'slot': 'x', 'components': 'x'}}),
            lambda d: d.update(uniformLayout={'u': {'slot': 0, 'components': 'xyzwq'}}),
            lambda d: d.update(uniformLayout={'u': {'slot': 0, 'components': 'zy'}}),
            lambda d: d.update(uniformLayout={'u': {'slot': 0.5, 'components': 'x'}}),
            lambda d: d.update(uniformLayout={'u': {'slot': 0, 'components': 'x'},
                                              'v': {'slot': 0, 'components': 'y'},
                                              'w': {'slot': 0, 'components': 'x'}}),
            lambda d: d.update(uniformLayouts={'p': 'layout'}),
            lambda d: d.update(paramAliases='aliases'),
            lambda d: d.update(paramAliases={'amt': 'nosuchglobal'}),
            lambda d: d.update(tags='noise'),
            lambda d: d.update(tags=['not-a-tag']),
            lambda d: d.update(tags=[42]),
            lambda d: d.update(openCategories=[7]),
            lambda d: d.update(onInit='nope'),
            lambda d: d.update(onUpdate=42),
            lambda d: d.update(onDestroy={}),
            lambda d: d.update(asyncInit=True),
            lambda d: d.update(shaders='inline'),
            lambda d: d.update(shaders={'main': 'source'}),
            lambda d: d.update(deprecatedBy=5),
            lambda d: d.update(externalTexture=7),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                d = valid_definition()
                mutate(d)
                errors = validate_effect_definition(d)
                self.assertTrue(errors)
                for e in errors:
                    self.assertIsInstance(e, str)

    def test_global_type_and_primitive_constraints_are_enforced(self):
        mutations = [
            lambda g: g['amount'].update(type='vec9'),
            lambda g: g['amount'].update(type=3),
            lambda g: g['amount'].update(default='high'),
            lambda g: g['amount'].update(default=float('nan')),
            lambda g: g['amount'].update(default=float('inf')),
            lambda g: g['mode'].update(default=1.5),
            lambda g: g['mode'].update(default='one'),
            lambda g: g['flag'].update(default=1),
            lambda g: g['tint'].update(default=[1, 0]),
            lambda g: g['tint'].update(default=[1, 0, 'a']),
            lambda g: g['point'].update(default=[0, 0]),
            lambda g: g['point'].update(min=[-1, -1]),
            lambda g: g['point'].update(max=1),
            lambda g: g['point'].update(default=[0, 0, 2]),
            lambda g: g['amount'].update(min='low'),
            lambda g: g['amount'].update(max=float('nan')),
            lambda g: g['amount'].update(min=0.9),
            lambda g: g['amount'].update(max=0.4),
            lambda g: g['amount'].update(step='x'),
            lambda g: g['amount'].update(zero=float('nan')),
            lambda g: g['mode'].update(choices=[0, 1]),
            lambda g: g['mode'].update(choices={'bad': 'x'}),
            lambda g: g['mode'].update(default=5),
            lambda g: g['table'].update(default=8),
            lambda g: g['surfaceIn'].update(colorModeUniform=3),
            lambda g: g['amount'].update(uniform=9),
            lambda g: g['mode'].update(define=5),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                d = valid_definition()
                mutate(d['globals'])
                self.assertTrue(validate_effect_definition(d))

    def test_member_typed_globals_resolve_through_the_std_enum_tables(self):
        d = valid_definition()
        d['globals']['memberProbe'] = {
            'type': 'member', 'default': 'noSuchTable.member', 'enum': 'noSuchTable',
            'ui': {'label': 'member', 'control': 'dropdown'},
        }
        self.assertTrue(any('noSuchTable' in e for e in validate_effect_definition(d)))

        d2 = valid_definition()
        d2['globals']['memberProbe'] = {
            'type': 'member', 'default': 'oscType.sine', 'enum': 'oscType',
            'ui': {'label': 'member', 'control': 'dropdown'},
        }
        self.assertEqual(validate_effect_definition(d2), [])
        self.assertEqual(resolve_std_enum('oscType.sine'), ('leaf', 0))

    def test_duplicate_and_conflicting_bindings_and_layouts_are_diagnosed(self):
        d = valid_definition()
        d['globals']['other'] = {'type': 'float', 'default': 0, 'uniform': 'amount'}
        errors = validate_effect_definition(d)
        self.assertTrue(any('amount' in e for e in errors))

        d2 = valid_definition()
        d2['uniformLayout'] = {'a': {'slot': 1, 'components': 'x'},
                               'b': {'slot': 1, 'components': 'xy'}}
        self.assertTrue(any('slot 1' in e for e in validate_effect_definition(d2)))

        d3 = valid_definition()
        d3['uniformLayout'] = {'a': {'slot': 1, 'components': 'x'},
                               'b': {'slot': 1, 'components': 'x'}}
        self.assertTrue(validate_effect_definition(d3))

    def test_unsupported_binding_references_are_diagnosed(self):
        mutations = [
            lambda p: p['inputs'].update(bad=7),
            lambda p: p['inputs'].update(bad='notDeclaredAnywhere'),
            lambda p: p['outputs'].update(bad='notDeclaredAnywhere'),
            lambda p: p['uniforms'].update(bad=[]),
            lambda p: p['uniforms'].update(bad={'ref': 1}),
            lambda p: p['conditions']['runIf'].__setitem__(
                0, {'uniform': 'nosuch', 'equals': 1}),
            lambda p: p.update(countUniform='nosuch'),
            lambda p: p.update(count='banana'),
            lambda p: p.update(count=-1),
            lambda p: p.update(repeat=[]),
            lambda p: p.update(drawMode='hexagons'),
            lambda p: p.update(type='vertex'),
            lambda p: p.update(drawBuffers=0),
            lambda p: p.update(blend='on'),
            lambda p: p.update(blend=['ONE']),
            lambda p: p.update(workgroups='8'),
            lambda p: p.update(viewport=32),
            lambda p: p.update(entryPoint=7),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                d = valid_definition()
                mutate(d['passes'][0])
                self.assertTrue(validate_effect_definition(d))

    def test_ui_enabledby_references_are_diagnosed(self):
        cases = [
            lambda ui: ui.update(enabledBy={'param': 'nosuch', 'eq': 1}),
            lambda ui: ui.update(enabledBy='nosuch'),
            lambda ui: ui.update(enabledBy={'param': 'mode'}),
            lambda ui: ui.update(enabledBy={'and': 'x'}),
            lambda ui: ui.update(control='dropdownx'),
            lambda ui: ui.update(label=7),
        ]
        for i, mutate in enumerate(cases):
            with self.subTest(i=i):
                d = valid_definition()
                mutate(d['globals']['flag']['ui'])
                self.assertTrue(validate_effect_definition(d))

    def test_numeric_pass_uniform_literals_and_dimension_expressions_are_preserved(self):
        d = valid_definition()
        self.assertEqual(validate_effect_definition(d), [])
        d['passes'][0]['uniforms']['literal'] = 0
        d['passes'][0]['uniforms']['another'] = 12.5
        self.assertEqual(validate_effect_definition(d), [])
        d['textures']['expressions'] = {
            'width': {'scale': 0.5, 'clamp': {'min': 8, 'max': 256}},
            'height': {'param': 'volumeSize', 'multiply': 2, 'paramDefault': 64},
        }
        self.assertEqual(validate_effect_definition(d), [])

    def test_external_texture_and_mesh_declarations_resolve_declared_pass_inputs(self):
        for effect, field in (('filter/text', 'externalTexture'),
                              ('synth/media', 'externalTexture'),
                              ('render/meshLoader', 'externalMesh')):
            with self.subTest(effect=effect):
                with open(f'{EFFECTS_ROOT}/{effect}.json') as fh:
                    d = json.load(fh)
                self.assertEqual(validate_effect_definition(d), [])
                declared = d[field]
                self.assertTrue(declared)

    def test_validator_does_not_invoke_lifecycle_hooks(self):
        calls = []

        def hook():
            calls.append(1)

        d = valid_definition()
        d['onInit'] = hook
        d['onUpdate'] = hook
        d['onDestroy'] = hook
        d['asyncInit'] = hook
        self.assertEqual(validate_effect_definition(d), [])
        self.assertEqual(calls, [])

    def test_validator_never_mutates_the_definition(self):
        d = valid_definition()
        before = copy.deepcopy(d)
        self.assertEqual(validate_effect_definition(d), [])
        self.assertEqual(d, before)

    def test_validation_errors_follow_declaration_insertion_order(self):
        d = valid_definition()
        d['globals'] = {
            'zzz': {'type': 'float', 'default': 'bad'},
            'aaa': {'type': 'float', 'default': 'bad'},
        }
        errors = validate_effect_definition(d)
        z = next(i for i, e in enumerate(errors) if "'zzz'" in e)
        a = next(i for i, e in enumerate(errors) if "'aaa'" in e)
        self.assertLess(z, a)

    def test_dynamic_definition_corpus_every_tracked_effect_validates(self):
        files = sorted(glob.glob(f'{EFFECTS_ROOT}/**/*.json', recursive=True))
        self.assertTrue(files, 'expected a nonempty tracked definition inventory')
        failures = []
        for path in files:
            try:
                with open(path) as fh:
                    d = json.load(fh)
            except Exception as exc:  # import errors are failures, not skips
                failures.append(f'{path}: load failed: {exc}')
                continue
            try:
                errors = validate_effect_definition(d)
            except Exception as exc:
                failures.append(f'{path}: validator threw: {exc}')
                continue
            if errors:
                failures.append(f'{path}: {len(errors)} error(s): {errors[:3]}')
        self.assertEqual(failures, [], f'{len(files) - len(failures)}/{len(files)} clean; '
                                       f'failures: {failures[:5]}')
        print(f'[effect-validator corpus] files={len(files)} pass={len(files) - len(failures)} '
              f'failure={len(failures)} skip=0 unexecuted=0')

    # ------------------------------------------------------------------
    # GAP-004 texture-policy fields (mirrors shaders/tests/test_mip_controls.js
    # @2f47612c29045c1b91af94887a8ff20106e980ef, Part 1: 5 cases)
    # ------------------------------------------------------------------

    @staticmethod
    def _mip_probe_definition(textures, textures3d):
        """The reference suite's baseDefinition (message-identical shape)."""
        return {
            'name': 'Mip Probe',
            'namespace': 'synth',
            'func': 'mipProbe',
            'description': 'Texture policy probe used by tests',
            'tags': ['noise', 'util'],
            'textures': textures,
            'textures3d': textures3d,
            'passes': [
                {
                    'program': 'probe',
                    'inputs': {},
                    'outputs': {'color': 'acc'},
                },
            ],
        }

    def test_validator_accepts_policy_fields_on_their_declared_containers(self):
        errors = validate_effect_definition(self._mip_probe_definition(
            {'acc': {'width': 64, 'height': 64, 'format': 'rgba16f',
                     'mipmaps': True, 'persistent': True}},
            {'vol': {'width': 8, 'height': 8, 'depth': 8, 'format': 'rgba16f',
                     'filter': 'nearest'}},
        ))
        self.assertEqual(errors, [], f'expected no errors, got: {errors}')

    def test_validator_rejects_unknown_texture_spec_fields_typo_protection(self):
        errors = validate_effect_definition(self._mip_probe_definition(
            {'acc': {'width': 64, 'height': 64, 'mipps': True}},
            None,
        ))
        self.assertTrue(any("unknown field 'mipps'" in e for e in errors),
                         f'missing unknown-field report: {errors}')

    def test_validator_rejects_filter_outside_textures3d(self):
        errors = validate_effect_definition(self._mip_probe_definition(
            {'acc': {'width': 64, 'height': 64, 'filter': 'nearest'}},
            None,
        ))
        self.assertTrue(any('"filter" is only supported on 3D' in e for e in errors),
                         f'missing filter-container report: {errors}')

    def test_validator_rejects_unknown_filter_values(self):
        errors = validate_effect_definition(self._mip_probe_definition(
            None,
            {'vol': {'width': 8, 'height': 8, 'depth': 8, 'filter': 'bilinear'}},
        ))
        self.assertTrue(any("unknown filter 'bilinear'" in e for e in errors),
                         f'missing filter-value report: {errors}')

    def test_validator_rejects_mipmaps_persistent_on_3d_specs_and_non_booleans(self):
        errors = validate_effect_definition(self._mip_probe_definition(
            {'acc': {'width': 64, 'height': 64, 'mipmaps': 'yes', 'persistent': 1}},
            {'vol': {'width': 8, 'height': 8, 'depth': 8, 'mipmaps': True,
                     'persistent': True}},
        ))
        for fragment in (
            '"mipmaps" must be a boolean',
            '"persistent" must be a boolean',
            '"mipmaps" is only supported on 2D',
            '"persistent" is only supported on 2D',
        ):
            self.assertTrue(any(fragment in e for e in errors),
                            f'missing report for {fragment}: {errors}')


if __name__ == '__main__':
    unittest.main()