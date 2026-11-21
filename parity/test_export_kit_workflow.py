"""The weekly export-kit run also runs the in-host TouchDesigner probes.

.github/workflows/export-kit.yml's parity job runs on the self-hosted GPU
group with the qualified TouchDesigner build. It runs parity/td_probes.py
through the parity venv, only on the schedule or a manual dispatch, after the
pinned reference is in place, and the kit dispatch waits for the job. The
workflow is read as text, because the engine-free suite has no YAML parser.
These checks guard against accidental regressions (a deleted step, a widened
trigger, a soft fail, a dropped argument); they do not pin the job's text, so
a reviewed edit such as an action pin bump still passes.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'export-kit.yml'
CONDITION = "if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"


def job(text, name):
    """The lines of a job, up to the next job header or top-level key."""
    lines = text.splitlines()
    start = lines.index('  %s:' % name)
    block = []
    for line in lines[start + 1:]:
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


class ProbeStepTests(unittest.TestCase):

    def setUp(self):
        text = WORKFLOW.read_text()
        self.assertIn('  parity:', text.splitlines(), 'export-kit.yml has no parity job')
        self.parity = job(text, 'parity')
        self.dispatch = job(text, 'dispatch')
        self.steps = steps(self.parity)
        self.probes = [step for step in self.steps if 'parity/td_probes.py' in step]

    def test_the_parity_job_runs_the_probes_once_through_the_parity_venv(self):
        self.assertEqual(len(self.probes), 1, 'the parity job runs parity/td_probes.py once')
        self.assertIn('run: parity/.venv/bin/python parity/td_probes.py', self.probes[0])

    def test_the_probe_step_runs_only_on_the_schedule_or_a_dispatch(self):
        conditions = [line.strip() for line in self.probes[0].splitlines() if line.strip().startswith('if:')]
        self.assertEqual(conditions, [CONDITION])

    def test_the_probe_step_runs_after_the_pinned_reference_is_in_place(self):
        reference = next(i for i, step in enumerate(self.steps) if 'name: Check out the pinned reference' in step)
        self.assertGreater(self.steps.index(self.probes[0]), reference)

    def test_nothing_in_the_parity_job_soft_fails(self):
        self.assertNotIn('continue-on-error', '\n'.join(self.parity), 'neither the job nor a step may soft-fail')
        self.assertNotRegex(self.probes[0], r'\|\|\s*true', 'the probe command must not ignore its exit status')

    def test_the_kit_dispatch_waits_for_the_parity_job(self):
        needs = [line.strip() for line in self.dispatch if line.startswith('    needs:')]
        self.assertEqual(len(needs), 1)
        self.assertRegex(needs[0], r'^needs: (parity|\[([^\]]*,\s*)?parity(\s*,[^\]]*)?\])$')


if __name__ == '__main__':
    unittest.main()
