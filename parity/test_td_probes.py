"""Contract tests for parity/td_probes.py, the in-host probe launcher.

TouchDesigner is not needed: stand-in executables play its part. They check
that the launcher stops only the processes it started, by exact PID, and
leaves none behind; that every report check fails on the field it guards and
passes the values the probes record on a licensed host; and that the phases
run in order, stop at the first failure and never pass on a stale report.
"""
import contextlib
import copy
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import td_probes  # noqa: E402


def alive(pid):
    state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith('Z')


def live_members(pgid):
    return [pid for pid in td_probes.group_members(pgid) if alive(pid)]


def executable(directory, name, body):
    path = Path(directory) / name
    path.write_text('#!%s\n%s' % (sys.executable, body))
    path.chmod(0o755)
    return path


# --- reports as the probes record them on a licensed host -------------------

def render(**extra):
    row = {'png': 'x.png', 'sha256': 'ab', 'stats': {'all_black': False, 'unique_bytes': -1},
           'top_errors': None, 'meaningful': True}
    row.update(extra)
    return row


def installed_kit_steps(phase, folder):
    return [
        {'step': 'project-opened', 'project.folder': folder, 'phase': phase},
        {'step': 'kit-onstart-build-present', 'host_comp': '/project1/noisemaker',
         'output_top': '/project1/noisemaker/node_8_write_blit_17'},
        {'step': 'kit-tree', 'checks': {
            'program.dsl': {'present': True}, 'integrate.py': {'present': True},
            'engine/noisemaker/runtime/nm_renderer.py': {'present': True},
            'engine/noisemaker/shaders': {'present': True, 'frag_count': 3}}},
        {'step': 'probe-started', 'host_present_at_probe_start': True},
        # TouchDesigner 2025.32820 silently refuses the documented connect.
        {'step': 'rebuild-and-connect', 'rebuild_returned': True, 'out_inputs': [], 'wired': False,
         'connect_attempt': {'silently_refused': True, 'consistent_with_gap_002_finding': True}},
        dict(render(), step='render'),
    ]


def kit_report(phase, folder):
    if phase in ('build', 'relocate', 'reinstall'):
        steps = installed_kit_steps(phase, folder)
        if phase == 'relocate':
            steps.append({'step': 'relocation-byte-compare', 'byte_identical': True})
        if phase == 'reinstall':
            steps.append({'step': 'reinstall-byte-compare', 'byte_identical_vs_build': True})
    elif phase == 'recover':
        steps = [
            {'step': 'project-opened', 'project.folder': folder, 'program_sha256': 'p1'},
            {'step': 'rebuild-failure', 'failure': {'raised': True, 'type': 'DslSyntaxError'},
             'host_present': True, 'renderer_after_failure': True},
            {'step': 'program-restored', 'sha256': 'p1'},
            dict(render(rebuild_returned=True), step='recovery-render'),
            {'step': 'recovery-byte-compare', 'byte_identical': True},
        ]
    elif phase == 'parameters':
        steps = [
            {'step': 'project-opened', 'project.folder': folder},
            {'step': 'enumeration', 'custom_pars': []},
            dict(render(), step='baseline-render'),
            {'step': 'custom-parameters-driven', 'count': 0, 'driven': []},
            dict(render(byte_identical_to_baseline=True), step='rebuild-control-render'),
            {'step': 'rebuild-control', 'rebuild_returned': True},
            {'step': 'dsl-change', 'applied': True, 'from': 'heightScale: 25', 'to': 'heightScale: 45'},
            dict(render(byte_identical_to_baseline=False), step='dsl-changed-render'),
            dict(render(byte_identical_to_baseline=True), step='restored-render'),
        ]
    elif phase == 'license':
        steps = [{'step': 'project-opened', 'project.folder': folder},
                 {'step': 'license-state', 'activation_needed': False,
                  'activation_needed_basis': 'measured: installed licenses present'}]
    else:
        steps = [{'step': 'kit-onstart-build-present', 'host_comp': '/project1/noisemaker'},
                 {'step': 'uninstall', 'destroyed': ['noisemaker', 'out'], 'remaining_ops': [], 'clean': True}]
    return {'phase': phase, 'td': {}, 'steps': steps, 'log': ['probe line']}


def workflow_report(phase):
    if phase == 'build':
        return {'phase': 'build', 'verdict': 'complete', 'steps': [
            {'step': 'host-environment', 'phase': 'build'},
            {'step': 'create-isolated-base-comp', 'consumer': '/nm_workflow_consumer'},
            {'step': 'documented-example-set-dsl', 'output_top': '/nm_workflow_consumer/out1'},
            {'step': 'connect-top', 'connected': True, 'readme_cross_network_form_connected': False,
             'display_top': '/nm_workflow_consumer/out'},
            dict(render(shader_errors=None), step='cook-1280'),
            dict(render(width=320, height=240), step='resize-320x240'),
            {'step': 'invalid-dsl', 'raised': 'DslSyntaxError', 'message': 'Unexpected character'},
            {'step': 'recover-valid-dsl', 'recovered': True},
            {'step': 'save-project', 'size': 4096, 'sha256': 's1'},
        ]}
    return {'phase': 'reopen', 'steps': [
        {'step': 'host-environment', 'phase': 'reopen'},
        {'step': 'reopen-project', 'consumer_present': True, 'saved_toe_sha256': 's1', 'build_saved_sha256': 's1'},
        {'step': 'top-connected', 'display_top': '/nm_workflow_consumer/out', 'consumer_output_present': True},
        {'step': 'recook-after-reopen', 'bytes_match_build_render': True},
        {'step': 'cleanup', 'destroyed': True, 'remaining_ops': [], 'clean': True},
    ]}


def step(report, name):
    return next(row for row in report['steps'] if row['step'] == name)


class ProcessTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / 'td.log'

    def tearDown(self):
        self.tmp.cleanup()

    def run_td(self, body, timeout=20, grace=2):
        td = executable(self.dir, 'touchdesigner', body)
        return td_probes.run_touchdesigner(td, self.dir / 'probe.toe', dict(os.environ), self.log,
                                           timeout=timeout, grace=grace)

    def test_a_touchdesigner_that_quits_by_itself_is_left_alone(self):
        run = self.run_td('import sys\nprint(sys.argv[1])\nsys.exit(0)\n')
        self.assertEqual((run.returncode, run.timed_out, run.leftovers), (0, False, []))
        self.assertIn('probe.toe', self.log.read_text())
        self.assertEqual(live_members(run.pgid), [])

    def test_its_exit_code_is_reported(self):
        self.assertEqual(self.run_td('import sys\nsys.exit(3)\n').returncode, 3)

    def test_a_touchdesigner_that_never_quits_is_stopped_by_its_pid(self):
        started = time.monotonic()
        run = self.run_td('import time\ntime.sleep(600)\n', timeout=1)
        self.assertTrue(run.timed_out)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(live_members(run.pgid), [])

    def test_one_that_does_not_quit_in_time_is_first_asked_to_quit(self):
        marker = self.dir / 'asked'
        run = self.run_td('import signal, sys, time\n'
                          'def quit(*_):\n    open(%r, "w").write("term")\n    sys.exit(0)\n'
                          'signal.signal(signal.SIGTERM, quit)\ntime.sleep(600)\n' % str(marker), timeout=1)
        self.assertTrue(run.timed_out)
        self.assertEqual(marker.read_text(), 'term')
        self.assertEqual(run.returncode, 0)

    def test_it_signals_processes_only_by_their_exact_pid(self):
        source = Path(td_probes.__file__).read_text()
        self.assertNotRegex(source, r"killpg|os\.kill\(\s*-|_signal\(\s*-")
        self.assertNotIn('pkill', source)
        self.assertNotIn('killall', source)

    def test_one_that_ignores_the_stop_request_is_killed(self):
        run = self.run_td('import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                          'time.sleep(600)\n', timeout=1, grace=1)
        self.assertTrue(run.timed_out)
        self.assertEqual(run.returncode, -signal.SIGKILL)
        self.assertEqual(live_members(run.pgid), [])

    def test_a_process_it_leaves_behind_is_stopped_by_its_pid(self):
        pid_file = self.dir / 'child.pid'
        run = self.run_td('import subprocess, sys\n'
                          'child = subprocess.Popen(["sleep", "600"])\n'
                          'open(%r, "w").write(str(child.pid))\n' % str(pid_file))
        child = int(pid_file.read_text())
        self.assertEqual(run.leftovers, [child])
        self.assertFalse(alive(child))
        self.assertEqual(live_members(run.pgid), [])

    def test_a_process_outside_its_group_is_never_signalled(self):
        outsider = subprocess.Popen(['sleep', '600'])
        try:
            run = self.run_td('import time\ntime.sleep(600)\n', timeout=1)
            self.assertTrue(run.timed_out)
            self.assertNotIn(outsider.pid, run.leftovers)
            self.assertIsNone(outsider.poll())
        finally:
            outsider.kill()
            outsider.wait()


class ReportCheckTests(unittest.TestCase):
    FOLDER = '/kit-moved'

    def assert_fails(self, failures, text):
        self.assertTrue(any(text in failure for failure in failures), '%r not in %r' % (text, failures))

    def test_the_recorded_values_pass(self):
        self.assertEqual(td_probes.check_workflow_build(workflow_report('build')), [])
        self.assertEqual(td_probes.check_workflow_reopen(workflow_report('reopen')), [])
        for phase in td_probes.KIT_PHASES:
            self.assertEqual(td_probes.check_kit(phase, kit_report(phase, self.FOLDER), self.FOLDER), [], phase)

    def test_a_wired_out_passes_as_well_as_a_recorded_refusal(self):
        report = kit_report('build', self.FOLDER)
        step(report, 'rebuild-and-connect').update(wired=True, connect_attempt={})
        self.assertEqual(td_probes.check_kit('build', report, self.FOLDER), [])

    def test_every_kit_check_fails_on_the_field_it_guards(self):
        cases = [
            ('build', 'render', {'meaningful': False}, 'meaningful'),
            ('build', 'render', {'top_errors': 'GLSL error'}, 'top_errors'),
            ('build', 'kit-onstart-build-present', {'output_top': None}, 'output_top'),
            ('build', 'probe-started', {'host_present_at_probe_start': False}, 'host_present_at_probe_start'),
            ('build', 'rebuild-and-connect', {'rebuild_returned': False}, 'rebuild_returned'),
            ('build', 'rebuild-and-connect', {'connect_attempt': {'silently_refused': True, 'exception': 'x'}},
             'no silent refusal'),
            ('build', 'kit-tree', {'checks': {'program.dsl': {'present': False}}}, 'kit-tree: missing'),
            ('build', 'project-opened', {'project.folder': '/kit'}, 'project.folder'),
            ('relocate', 'relocation-byte-compare', {'byte_identical': False}, 'byte_identical'),
            ('reinstall', 'reinstall-byte-compare', {'byte_identical_vs_build': False}, 'byte_identical_vs_build'),
            ('recover', 'rebuild-failure', {'failure': {'raised': False}}, 'did not raise'),
            ('recover', 'rebuild-failure', {'host_present': False}, 'host_present'),
            ('recover', 'program-restored', {'sha256': 'p2'}, 'program-restored'),
            ('recover', 'recovery-render', {'meaningful': False}, 'meaningful'),
            ('recover', 'recovery-byte-compare', {'byte_identical': False}, 'byte_identical'),
            ('parameters', 'rebuild-control-render', {'byte_identical_to_baseline': False}, 'byte_identical'),
            ('parameters', 'dsl-change', {'applied': False}, 'applied'),
            ('parameters', 'dsl-changed-render', {'byte_identical_to_baseline': True}, 'byte_identical'),
            ('parameters', 'restored-render', {'byte_identical_to_baseline': False}, 'byte_identical'),
            ('parameters', 'rebuild-control', {'rebuild_returned': None}, 'rebuild_returned'),
            ('parameters', 'custom-parameters-driven',
             {'driven': [{'par': 'Speed', 'render': {'meaningful': False}, 'rebuild_returned': True}]},
             'custom parameter Speed'),
            ('license', 'license-state', {'activation_needed': True}, 'activation_needed'),
            ('license', 'license-state', {'activation_needed': None}, 'activation_needed'),
            ('remove', 'uninstall', {'clean': False}, 'clean'),
            ('remove', 'uninstall', {'remaining_ops': ['out']}, 'remaining_ops'),
        ]
        for phase, name, change, text in cases:
            with self.subTest(phase=phase, step=name, change=change):
                report = kit_report(phase, self.FOLDER)
                step(report, name).update(change)
                self.assert_fails(td_probes.check_kit(phase, report, self.FOLDER), text)

    def test_every_workflow_check_fails_on_the_field_it_guards(self):
        cases = [
            ('build', 'connect-top', {'connected': False}, 'connected'),
            ('build', 'cook-1280', {'meaningful': False}, 'meaningful'),
            ('build', 'cook-1280', {'shader_errors': ['x']}, 'shader_errors'),
            ('build', 'resize-320x240', {'width': 1280}, 'width'),
            ('build', 'resize-320x240', {'meaningful': False}, 'meaningful'),
            ('build', 'invalid-dsl', {'raised': None}, 'raised'),
            ('build', 'recover-valid-dsl', {'recovered': False}, 'recovered'),
            ('build', 'save-project', {'size': 0}, 'size'),
            ('build', 'documented-example-set-dsl', {'output_top': None}, 'output_top'),
            ('reopen', 'reopen-project', {'consumer_present': False}, 'consumer_present'),
            ('reopen', 'reopen-project', {'saved_toe_sha256': 's2'}, 'not the one the build phase saved'),
            ('reopen', 'top-connected', {'consumer_output_present': False}, 'consumer_output_present'),
            ('reopen', 'recook-after-reopen', {'bytes_match_build_render': False}, 'bytes_match_build_render'),
            ('reopen', 'cleanup', {'clean': False}, 'clean'),
        ]
        for phase, name, change, text in cases:
            with self.subTest(phase=phase, step=name, change=change):
                report = workflow_report(phase)
                step(report, name).update(change)
                check = td_probes.check_workflow_build if phase == 'build' else td_probes.check_workflow_reopen
                self.assert_fails(check(report), text)

    def test_a_report_fails_without_its_steps_its_phase_or_its_verdict(self):
        build = workflow_report('build')
        build['verdict'] = 'incomplete'
        self.assert_fails(td_probes.check_workflow_build(build), 'verdict')
        report = kit_report('build', self.FOLDER)
        report['phase'] = 'relocate'
        self.assert_fails(td_probes.check_kit('build', report, self.FOLDER), 'not \'build\'')
        self.assert_fails(td_probes.check_kit('remove', {'phase': 'remove', 'steps': []}, self.FOLDER),
                          'records no steps')
        report = kit_report('remove', self.FOLDER)
        report['steps'] = [row for row in report['steps'] if row['step'] != 'uninstall']
        self.assert_fails(td_probes.check_kit('remove', report, self.FOLDER), 'uninstall: recorded 0 times')

    def test_a_fatal_or_failed_step_fails_the_report(self):
        report = kit_report('recover', self.FOLDER)
        report['steps'].append({'step': 'FATAL-recover', 'error': 'Traceback\nRuntimeError: no renderer'})
        self.assert_fails(td_probes.check_kit('recover', report, self.FOLDER), 'RuntimeError: no renderer')
        report = workflow_report('build')
        step(report, 'save-project')['error'] = 'PermissionError: denied'
        self.assert_fails(td_probes.check_workflow_build(report), 'PermissionError: denied')


class FakeProbes(td_probes.Probes):
    """The launcher with stand-ins for TouchDesigner's toe tools and the kit materializer."""

    def workflow_bootstrap(self):
        return [sys.executable, '-c', 'import pathlib, sys\np = pathlib.Path(sys.argv[1])\n'
                'p.parent.mkdir(parents=True, exist_ok=True)\np.write_text("toe")\n',
                str(self.repo / 'td' / 'nm_workflow.toe')]

    def kit_bootstrap(self, kit):
        return [sys.executable, '-c', 'import pathlib, sys\n(pathlib.Path(sys.argv[1]) / "kit.toe").write_text("toe")\n',
                str(kit)]

    def materialize(self, dest):
        return [sys.executable, '-c', 'import json, os, pathlib, sys\nd = pathlib.Path(sys.argv[1])\n'
                'd.mkdir(parents=True, exist_ok=True)\n(d / "program.dsl").write_text("x")\n'
                'open(os.environ["FAKE_TD_LOG"], "a").write(json.dumps({"materialize": d.name}) + "\\n")\n',
                str(dest)]


FAKE_TD = '''import json, os, sys
toe = sys.argv[1]
kit = 'NM_KIT_PHASE' in os.environ
phase = os.environ['NM_KIT_PHASE' if kit else 'NM_WORKFLOW_PHASE']
with open(os.environ['FAKE_TD_LOG'], 'a') as log:
    log.write(json.dumps({'kind': 'kit' if kit else 'workflow', 'phase': phase, 'toe': toe,
                          'from': os.environ.get('NM_PARAM_DSL_FROM'),
                          'to': os.environ.get('NM_PARAM_DSL_TO')}) + '\\n')
reports = json.load(open(os.environ['FAKE_TD_REPORTS']))
text = json.dumps(reports['kit' if kit else 'workflow'][phase]).replace(
    '@FOLDER@', os.path.dirname(os.path.abspath(toe)))
out = os.environ['NM_KIT_OUT'] if kit else os.path.join(os.environ['NM_TD_REPO'], 'parity', 'out', 'workflow')
os.makedirs(out, exist_ok=True)
if phase not in os.environ.get('FAKE_TD_SILENT', '').split(','):
    open(os.path.join(out, 'report.%s.json' % phase), 'w').write(text)
if not kit and phase == 'build':
    open(os.path.join(out, 'nm_workflow_saved.toe'), 'w').write('saved')
sys.exit(int(os.environ.get('FAKE_TD_EXIT_' + phase.upper(), '0')))
'''


class OrchestrationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo, self.work, self.log = root / 'repo', root / 'work', root / 'calls.jsonl'
        self.repo.mkdir()
        self.work.mkdir()
        self.td = executable(root, 'touchdesigner', FAKE_TD)
        self.reports = {'workflow': {phase: workflow_report(phase) for phase in td_probes.WORKFLOW_PHASES},
                        'kit': {phase: kit_report(phase, '@FOLDER@') for phase in td_probes.KIT_PHASES}}
        self.env = dict(os.environ, FAKE_TD_LOG=str(self.log), FAKE_TD_REPORTS=str(root / 'reports.json'))
        for name in ('NM_KIT_PHASE', 'NM_WORKFLOW_PHASE', 'NM_KIT_OUT'):
            self.env.pop(name, None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_probes(self, **env):
        (Path(self.tmp.name) / 'reports.json').write_text(json.dumps(self.reports))
        probes = FakeProbes(self.repo, self.td, '/reference', '1.0.0', '0' * 40, self.work,
                            dict(self.env, **env), timeout=20, grace=2)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = probes.run_all()
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return code, probes, calls, out.getvalue()

    def test_every_phase_runs_in_order_and_the_run_passes(self):
        code, probes, calls, out = self.run_probes()
        self.assertEqual(code, 0, out)
        order = [call.get('materialize') or '%s %s' % (call['kind'], call['phase']) for call in calls]
        self.assertEqual(order, ['workflow build', 'workflow reopen', 'kit', 'kit build', 'kit relocate',
                                 'kit-moved', 'kit reinstall', 'kit recover', 'kit parameters',
                                 'kit license', 'kit remove'])
        toes = {'%s %s' % (call['kind'], call['phase']): call['toe'] for call in calls if 'kind' in call}
        self.assertEqual(toes['workflow build'], str(self.repo / 'td' / 'nm_workflow.toe'))
        self.assertEqual(toes['workflow reopen'],
                         str(self.repo / 'parity' / 'out' / 'workflow' / 'nm_workflow_saved.toe'))
        self.assertEqual(toes['kit build'], str(self.work / 'kit' / 'kit.toe'))
        for phase in td_probes.KIT_PHASES[1:]:
            self.assertEqual(toes['kit %s' % phase], str(self.work / 'kit-moved' / 'kit.toe'), phase)
        parameters = next(call for call in calls if call.get('phase') == 'parameters')
        self.assertEqual((parameters['from'], parameters['to']), ('heightScale: 25', 'heightScale: 45'))
        self.assertEqual(sorted(probes.results), sorted(probes.expected()))
        self.assertIn('every phase passed', out)

    def test_a_failed_phase_fails_the_run_and_the_later_phases_do_not_run(self):
        step(self.reports['kit']['relocate'], 'render')['meaningful'] = False
        code, probes, calls, out = self.run_probes()
        self.assertEqual(code, 1)
        self.assertTrue(probes.results['kit relocate'])
        for phase in ('reinstall', 'recover', 'parameters', 'license', 'remove'):
            self.assertEqual(probes.results['kit %s' % phase], ['not run: the relocate phase failed'])
        self.assertNotIn('reinstall', [call.get('phase') for call in calls])
        self.assertIn('FAILED: kit relocate', out)

    def test_a_phase_that_records_nothing_fails_the_run(self):
        class SkipsTheKit(FakeProbes):
            def run_kit(self):
                pass
        (Path(self.tmp.name) / 'reports.json').write_text(json.dumps(self.reports))
        probes = SkipsTheKit(self.repo, self.td, '/reference', '1.0.0', '0' * 40, self.work, self.env,
                             timeout=20, grace=2)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probes.run_all(), 1)
        self.assertIn('FAILED: kit build', out.getvalue())

    def test_a_non_zero_exit_fails_the_phase(self):
        code, probes, calls, out = self.run_probes(FAKE_TD_EXIT_BUILD='1')
        self.assertEqual(code, 1)
        self.assertIn('TouchDesigner exited 1', probes.results['workflow build'])
        self.assertEqual(probes.results['workflow reopen'], ['not run: the build phase failed'])

    def test_a_stale_report_never_passes(self):
        out = self.work / 'kit-qual'
        out.mkdir()
        (out / 'report.build.json').write_text(json.dumps(kit_report('build', str(self.work / 'kit'))))
        code, probes, calls, _ = self.run_probes(FAKE_TD_SILENT='build')
        self.assertEqual(code, 1)
        self.assertIn('the probe wrote no report', probes.results['kit build'])
        self.assertIn('the probe wrote no report', probes.results['workflow build'])

    def test_paths_in_the_log_are_shown_relative(self):
        step(self.reports['kit']['build'], 'render')['top_errors'] = 'error in %s/kit/x.frag' % self.work
        code, probes, calls, out = self.run_probes()
        self.assertEqual(code, 1)
        self.assertIn('<work>/kit/x.frag', out)
        self.assertNotIn(str(self.work), out)


class MainTests(unittest.TestCase):

    def run_main(self, env):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = td_probes.main(env)
        return code, err.getvalue()

    def test_a_missing_touchdesigner_fails_by_name(self):
        code, err = self.run_main({'TD_BIN': '/no/such/TouchDesigner', 'NM_REFERENCE_ROOT': '/'})
        self.assertEqual(code, 1)
        self.assertIn('no TouchDesigner binary', err)

    def test_a_missing_reference_fails_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            td = executable(tmp, 'touchdesigner', 'pass\n')
            code, err = self.run_main({'TD_BIN': str(td)})
            self.assertEqual(code, 1)
            self.assertIn('set NM_REFERENCE_ROOT', err)
            (Path(tmp) / 'shaders').mkdir()
            code, err = self.run_main({'TD_BIN': str(td), 'NM_REFERENCE_ROOT': tmp})
            self.assertEqual(code, 1)
            self.assertIn('no engine version', err)


if __name__ == '__main__':
    unittest.main()
