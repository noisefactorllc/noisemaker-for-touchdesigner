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


class FeedbackHueContract(unittest.TestCase):
    """Behavioral source contract for filter/feedback's hue path.

    The upstream reference pinned two compiler hazards this port inherits
    through the converted GLSL (td/noisemaker/shaders/effects/filter/
    feedback/feedback.frag). fract() returns 1.0 for a hue just below a whole
    number, and Mesa folds hsv2rgb's fract() into the fract() that wraps the
    hue before the call, so the sector chain can receive h = 1.0. The last
    sector must therefore be the else branch, which also takes 1.0, and
    divRound's remainder correction must be pinned so a compiler cannot
    reassociate the hue-shift sum around it.
    """

    FEEDBACK_SHADER = 'td/noisemaker/shaders/effects/filter/feedback/feedback.frag'

    def test_feedback_wraps_the_hue_and_pins_the_hue_shift_sum(self):
        for path in shader_programs():
            if not path.endswith('filter/feedback/feedback.frag'):
                continue
            with open(path, encoding='utf-8') as fh:
                source = fh.read()
            start = re.search(r'^vec3 hsv2rgb\(', source, re.M)
            self.assertIsNotNone(start, '%s has no hsv2rgb' % path)
            depth = 0
            body = None
            for i in range(source.index('{', start.start()), len(source)):
                if source[i] == '{':
                    depth += 1
                elif source[i] == '}':
                    depth -= 1
                    if depth == 0:
                        body = source[start.start():i + 1]
                        break
            self.assertIsNotNone(body, '%s hsv2rgb has no closing brace' % path)
            self.assertRegex(body, r'float h = fract\(hsv\.x\);',
                             '%s hsv2rgb must wrap the hue with fract()' % path)
            self.assertNotRegex(body, r'h < 1\.0\)',
                                '%s hsv2rgb must not leave h = 1.0 out of the last sector' % path)
            self.assertRegex(
                body,
                r'\belse \{\s*(?://[^\n]*\n\s*)*rgb = vec3\(c, 0\.0, x\);\s*\}\s*return rgb',
                '%s hsv2rgb must give the last sector to every hue the earlier sectors leave' % path)
            self.assertIn('return pin(q + pin(r / b));', source,
                          '%s divRound must pin the hue-shift sum so compilers cannot reassociate it' % path)
            self.assertNotIn('return q + pin(r / b);', source,
                             '%s divRound must not return the unpinned hue-shift sum' % path)


if __name__ == '__main__':
    unittest.main()
