"""Structural contract for the converted TouchDesigner shader programs.

The converter (tools/convert-shaders.mjs, rulebook PORTING-GUIDE.md) turns each
reference GLSL program into td/noisemaker/shaders/effects/<ns>/<name>/<prog>.frag.
This suite checks the emitted contract every converted program must satisfy, so a
changed .frag has an engine-free test that runs under scripts/test's
NM_CHANGED_FILES filter (parity/nm_changed_files.py routes changed shaders here).
With NM_CHANGED_FILES unset it checks every converted program; with it set it
checks exactly the changed programs.
"""
import glob
import os
import re
import unittest

SHADER_GLOB = 'td/noisemaker/shaders/effects/**/*.frag'


def shader_programs():
    changed = [f.strip() for f in os.environ.get('NM_CHANGED_FILES', '').splitlines()
               if f.strip().startswith('td/noisemaker/shaders/')
               and f.strip().endswith(('.frag', '.vert'))]
    if changed:
        return sorted(f for f in changed if os.path.exists(f))
    return sorted(glob.glob(SHADER_GLOB, recursive=True))


def input_names(source):
    header = re.search(r'^// NM_INPUTS: (.*)$', source, re.M)
    if not header or header.group(1).strip() == '(none)':
        return []
    return [part.split('=')[0] for part in header.group(1).split() if '=' in part]


class ShaderContract(unittest.TestCase):
    def test_converted_programs_match_the_converter_contract(self):
        programs = shader_programs()
        self.assertGreater(len(programs), 0,
                           'no converted shader programs found under %s' % SHADER_GLOB)
        problems = []
        for path in programs:
            with self.subTest(program=path):
                with open(path, encoding='utf-8') as fh:
                    source = fh.read()
                # TouchDesigner prepends its own #version and precision preamble;
                # the converter strips them (PORTING-GUIDE step 1).
                if re.search(r'^#version', source, re.M):
                    problems.append('%s: emits its own #version' % path)
                if re.search(r'^precision\s', source, re.M):
                    problems.append('%s: emits its own precision qualifier' % path)
                output = re.search(r'^// NM_OUTPUT: (.*)$', source, re.M)
                if not output:
                    problems.append('%s: no // NM_OUTPUT: header' % path)
                else:
                    # Non-MRT programs get the wrapper that applies TDOutputSwizzle
                    # exactly once (PORTING-GUIDE step 3); MRT programs wire their
                    # outputs per-location in the runtime instead.
                    swizzles = source.count('TDOutputSwizzle')
                    if 'MRT' not in output.group(1) and swizzles != 1:
                        problems.append('%s: expected exactly one TDOutputSwizzle, found %d'
                                        % (path, swizzles))
                # Every declared input is bound to its sTD2DInputs slot
                # (PORTING-GUIDE step 2).
                for name in input_names(source):
                    if not re.search(r'^#define %s sTD2DInputs\[' % re.escape(name),
                                     source, re.M):
                        problems.append('%s: input %s has no sTD2DInputs binding'
                                        % (path, name))
        self.assertEqual(problems, [])


if __name__ == '__main__':
    unittest.main()
