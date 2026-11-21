"""The weekly export-kit run also runs the in-host TouchDesigner probes.

.github/workflows/export-kit.yml's parity job runs on the self-hosted GPU
group with the qualified TouchDesigner build. It runs parity/td_probes.py,
alone and through the parity venv, only on the schedule or a manual dispatch,
after the pinned reference is in place and with its environment, and the kit
dispatch waits for the job. The workflow is read as text, because the
engine-free suite has no YAML parser. These checks guard against accidental
regressions (a deleted step, a widened trigger, a soft fail, a dropped or added
argument); they do not pin the job's text, so a reviewed edit such as an action
pin bump still passes. The mutants below are kept beside the checks.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'export-kit.yml'
CONDITION = "if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
COMMAND = 'run: parity/.venv/bin/python parity/td_probes.py'


def job(text, name):
    """The lines of a job, up to the next job header or top-level key, or None."""
    lines = text.splitlines()
    if '  %s:' % name not in lines:
        return None
    block = []
    for line in lines[lines.index('  %s:' % name) + 1:]:
        if re.match(r'^ {2}[A-Za-z0-9_-]+:\s*$', line) or re.match(r'^[^ #]', line):
            break
        block.append(line)
    return block


def steps(block):
    """Each `      - ` step of a job as its own text."""
    found = []
    for line in block:
        if line.startswith('      - '):
            found.append([line])
        elif found and (line.startswith('        ') or not line.strip()):
            found[-1].append(line)
    return ['\n'.join(step) for step in found]


def probe_step_failures(text):
    """Why the workflow does not run the probes as reviewed; empty when it does."""
    parity, dispatch = job(text, 'parity'), job(text, 'dispatch')
    if parity is None:
        return ['export-kit.yml has no parity job']
    found = steps(parity)
    probes = [step for step in found if 'parity/td_probes.py' in step]
    if len(probes) != 1:
        return ['the parity job runs parity/td_probes.py %d times, not once' % len(probes)]
    probe, failures = probes[0], []
    runs = [line.strip() for line in probe.splitlines() if line.strip().startswith('run:')]
    if runs != [COMMAND]:
        failures.append('the probe step runs %r, not the launcher alone through the parity venv' % runs)
    conditions = [line.strip() for line in probe.splitlines() if line.strip().startswith('if:')]
    if conditions != [CONDITION]:
        failures.append('the probe step runs on %r, not the schedule or a dispatch only' % conditions)
    if re.search(r'(?m)^ {8}env:', probe):
        failures.append('the probe step overrides the environment the pinned reference set')
    reference = [index for index, step in enumerate(found) if 'name: Check out the pinned reference' in step]
    if not reference or found.index(probe) < reference[0]:
        failures.append('the probe step runs before the pinned reference is in place')
    if 'continue-on-error' in '\n'.join(parity):
        failures.append('a step or the parity job soft-fails')
    needs = [line.strip() for line in dispatch or [] if line.startswith('    needs:')]
    if len(needs) != 1 or not re.match(r'^needs: (parity|\[([^\]]*,\s*)?parity(\s*,[^\]]*)?\])$', needs[0]):
        failures.append('the kit dispatch does not wait for the parity job')
    return failures


class ProbeStepTests(unittest.TestCase):

    def setUp(self):
        self.text = WORKFLOW.read_text()

    def mutate(self, old, new):
        self.assertIn(old, self.text, 'the mutant no longer applies: %r' % old)
        return self.text.replace(old, new, 1)

    def test_the_workflow_runs_the_probes_as_reviewed(self):
        self.assertEqual(probe_step_failures(self.text), [])

    def test_a_reviewed_edit_such_as_an_action_pin_bump_still_passes(self):
        bumped = re.sub(r'(uses: actions/[a-z-]+@)[0-9a-f]{40}', lambda m: m.group(1) + '0' * 40, self.text)
        self.assertNotEqual(bumped, self.text)
        self.assertEqual(probe_step_failures(bumped), [])

    def test_every_regression_fails(self):
        step = '      - name: Run the in-host probes\n'
        mutants = {
            'step removed': self.mutate(step + '        ' + CONDITION + '\n        ' + COMMAND + '\n', ''),
            'condition widened': self.mutate('        ' + CONDITION + '\n', '        if: always()\n'),
            'condition negated': self.mutate('        ' + CONDITION + '\n', "        if: github.event_name != 'push'\n"),
            'condition dropped': self.mutate('        ' + CONDITION + '\n', ''),
            'soft fail on the step': self.mutate(step, step + '        continue-on-error: true\n'),
            'soft fail on the job': self.mutate('  parity:\n', '  parity:\n    continue-on-error: true\n'),
            'ignored exit status': self.mutate(COMMAND + '\n', COMMAND + ' || true\n'),
            'a narrowing argument': self.mutate(COMMAND + '\n', COMMAND + ' --only workflow\n'),
            'the system python': self.mutate(COMMAND, 'run: python3 parity/td_probes.py'),
            'an environment override': self.mutate(step, step + '        env:\n          NM_REFERENCE_ROOT: /tmp/other\n'),
            'dispatch no longer waits': self.mutate('  dispatch:\n    needs: parity\n', '  dispatch:\n'),
        }
        for name, text in mutants.items():
            with self.subTest(name):
                self.assertNotEqual(probe_step_failures(text), [], name)


if __name__ == '__main__':
    unittest.main()
