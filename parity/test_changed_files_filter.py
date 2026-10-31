"""Unit tests for the NM_CHANGED_FILES selection logic.

scripts/test filters the engine-free checks to the tests and DSL programs that
exercise the changed paths. The selection lives in parity/nm_changed_files.py so
these unit tests can hold the mapping itself to its contract, including the rule
that routes a changed shader program to the shader-contract suite.

Probe paths are built from joined components so neither the full paths nor
their parent-directory tokens appear as literals in this file: a literal token
in test source would make this module select itself through the very content
rule it is testing.
"""
import unittest

import nm_changed_files

SHADER_PROGRAM = '/'.join(['td', 'noisemaker', 'shaders', 'effects',
                           'synth', 'shape']) + '/shape' + '.frag'
PROBE_PROGRAM = '/'.join(['td', 'noisemaker', 'shaders', 'effects',
                          'probe']) + '/none' + '.frag'
UNMATCHED = '/'.join(['docs', 'x']) + '/unmatched' + '.xyz'


class TestRelevantTestModules(unittest.TestCase):
    def test_changed_shader_selects_the_shader_contract_suite(self):
        self.assertEqual(
            nm_changed_files.find_relevant_test_modules([SHADER_PROGRAM]),
            ['test_shader_contract'])

    def test_changed_test_module_selects_itself(self):
        self.assertEqual(
            nm_changed_files.find_relevant_test_modules(['parity/test_td_' + 'backend.py']),
            ['test_td_backend'])

    def test_unmatched_paths_select_nothing(self):
        self.assertIsNone(
            nm_changed_files.find_relevant_test_modules([UNMATCHED]))

    def test_shader_and_unmatched_change_select_the_shader_suite(self):
        self.assertEqual(
            nm_changed_files.find_relevant_test_modules([SHADER_PROGRAM, UNMATCHED]),
            ['test_shader_contract'])

    def test_shader_root_path_outside_the_converted_tree_selects_the_suite(self):
        # Any converted-program path routes to the contract suite; a path under
        # the shader root that names no real program still selects it, and
        # nothing else can name it.
        self.assertEqual(
            nm_changed_files.find_relevant_test_modules([PROBE_PROGRAM]),
            ['test_shader_contract'])


class TestGatePrograms(unittest.TestCase):
    def test_no_changed_paths_select_the_whole_corpus(self):
        self.assertGreater(
            len(nm_changed_files.select_gate_programs([])), 0)

    def test_changed_shader_selects_no_dsl_program(self):
        self.assertEqual(
            nm_changed_files.select_gate_programs([SHADER_PROGRAM]),
            [])

    def test_changed_gate_runner_selects_every_program(self):
        self.assertEqual(
            nm_changed_files.select_gate_programs(['scripts/' + 'test']),
            nm_changed_files.select_gate_programs([]))

    def test_changed_dsl_program_runs_on_itself(self):
        self.assertEqual(
            nm_changed_files.select_gate_programs(['parity/programs/adjust' + '.dsl']),
            ['parity/programs/adjust.dsl'])


if __name__ == '__main__':
    unittest.main()
