#!/usr/bin/env python3
"""td_probes.py -- run the in-host TouchDesigner probes; fail on any failed check.

TouchDesigner has no headless mode. Each probe is a bootstrap .toe whose
Execute DAT runs the probe on load, writes a JSON report and quits:

- the installed developer workflow (td/workflow_probe.py, bootstrap from
  td/build_workflow_toe.py): phase build, then phase reopen on the project
  that the build phase saved;
- the export kit (td/kit_probe.py, bootstrap from td/build_kit_toe.py),
  reproduced from this commit by tools/materialize_kit.py: phases build,
  relocate (the export directory moved), reinstall (the kit materialized
  again over the install), recover, parameters, license and remove.

Every phase is its own TouchDesigner process. The launcher starts it in a
process group that a holder process of its own leads, so the group's ID stays
reserved for the whole run. It waits for TouchDesigner to quit and, when it
does not quit in time, stops it by its exact PID. It then stops every other
process left in that group by its exact PID, so no TouchDesigner process or
window outlives the run, and it never signals a process outside the group.

A phase passes only when TouchDesigner exits 0 by itself, the phase writes its
report and every check on that report holds. A phase after a failed one does
not run and counts as failed. The run passes only when every phase passes.
Paths in the log are shown relative to the work directory, the repository and
the home directory.

Usage: parity/.venv/bin/python parity/td_probes.py
  NM_REFERENCE_ROOT  the reference engine checkout (required)
  TD_BIN             the TouchDesigner binary (default: the one inside
                     /Applications/TouchDesigner.app)
"""
import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_TD_BIN = '/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner'
RUN_TIMEOUT = 600
STOP_GRACE = 10
LOG_TAIL = 40
KIT_PROGRAM = Path('parity') / 'programs' / 'heightGrid_billboard.dsl'
# The parameters phase changes this literal in program.dsl through rebuild()
# and expects a different render, then the baseline again once it is restored.
PARAM_DSL_FROM = 'heightScale: 25'
PARAM_DSL_TO = 'heightScale: 45'
WORKFLOW_PHASES = ('build', 'reopen')
DOC_MEAN = (0.9 + 0.3 + 0.5 + 1.0) / 4
DOC_MEAN_TOLERANCE = 0.01
KIT_PHASES = ('build', 'relocate', 'reinstall', 'recover', 'parameters', 'license', 'remove')


# --- processes ---------------------------------------------------------------

class Run:
    def __init__(self, returncode, timed_out, leftovers, pgid):
        self.returncode = returncode
        self.timed_out = timed_out
        self.leftovers = leftovers
        self.pgid = pgid


def group_members(pgid):
    """The PIDs whose process group is pgid."""
    listing = subprocess.run(['ps', '-A', '-o', 'pid=', '-o', 'pgid='],
                             capture_output=True, text=True, check=True).stdout
    members = []
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == str(pgid):
            members.append(int(fields[0]))
    return sorted(members)


def _signal(pid, sig):
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, sig)


# The holder leads the run's process group. When its launcher is gone without having stopped the
# run (a SIGKILL nothing can catch), it stops every other process left in its own group, each by its
# exact PID, and exits, so not even a killed launcher leaves TouchDesigner behind.
HOLDER = '''import os, signal, subprocess, time
parent, group = os.getppid(), os.getpgrp()
while os.getppid() == parent:
    time.sleep(1)
def members():
    ps = subprocess.Popen(['ps', '-A', '-o', 'pid=', '-o', 'pgid='], stdout=subprocess.PIPE, text=True)
    listing = ps.communicate()[0]
    rows = [line.split() for line in listing.splitlines()]
    return [int(row[0]) for row in rows if len(row) == 2 and row[1] == str(group) and int(row[0]) not in (group, ps.pid)]
for sig in (signal.SIGTERM, signal.SIGKILL):
    for pid in members():
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while members() and time.monotonic() < deadline:
        time.sleep(0.2)
'''


@contextlib.contextmanager
def held_process_group():
    """A new process group led by a holder process; yields the group's ID.

    While the holder lives, no other process can take the group's ID, so every
    member found later is a process this run started or one of its children.
    """
    holder = subprocess.Popen([sys.executable, '-c', HOLDER],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, process_group=0)
    try:
        yield holder.pid
    finally:
        holder.kill()
        holder.wait()


def stop_members(pgid, grace):
    """Stop every process in the group except its holder, each by its exact PID."""
    left = [pid for pid in group_members(pgid) if pid != pgid]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        remaining = [pid for pid in group_members(pgid) if pid != pgid]
        for pid in remaining:
            _signal(pid, sig)
        deadline = time.monotonic() + grace
        while remaining and time.monotonic() < deadline:
            time.sleep(0.2)
            remaining = [pid for pid in group_members(pgid) if pid != pgid and _alive(pid)]
        if not remaining:
            return left
    raise RuntimeError('could not stop processes %s in the TouchDesigner process group' % remaining)


def _alive(pid):
    state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith('Z')


def run_touchdesigner(td_bin, toe, env, log_path, timeout=RUN_TIMEOUT, grace=STOP_GRACE):
    """Run TouchDesigner on toe until it quits; stop only what this run started."""
    with held_process_group() as pgid:
        with open(log_path, 'wb') as log:
            child = subprocess.Popen([str(td_bin), str(toe)], env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, process_group=pgid)
        timed_out = False
        try:
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                stop_child(child, grace)
        except BaseException:
            # An interrupted launcher (Ctrl-C, SIGTERM, SIGHUP) still stops what it started.
            stop_child(child, grace)
            stop_members(pgid, grace)
            raise
        leftovers = stop_members(pgid, grace)
    return Run(child.returncode, timed_out, leftovers, pgid)


def stop_child(child, grace):
    """Ask the TouchDesigner process to quit, then kill it, by its exact PID."""
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def exit_on_signal(signum, _frame):
    raise SystemExit(128 + signum)


# --- report checks -----------------------------------------------------------

def _short(value, limit=200):
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + '...'


def _last_line(text):
    lines = [line for line in str(text or '').strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else 'no message'


class Checks:
    """Failure messages for one report."""

    def __init__(self, report, phase):
        self.report = report
        self.failures = []
        self.rows = {}
        for row in report.get('steps') or []:
            if isinstance(row, dict):
                self.rows.setdefault(row.get('step'), []).append(row)
        if report.get('phase') != phase:
            self.fail('the report is for phase %s, not %r' % (_short(report.get('phase')), phase))
        if not self.rows:
            self.fail('the report records no steps')
        for name, rows in self.rows.items():
            for row in rows:
                if str(name).startswith('FATAL') or 'error' in row:
                    self.fail('%s: %s' % (name, _last_line(row.get('error'))))

    def fail(self, message):
        if message not in self.failures:
            self.failures.append(message)

    def step(self, name):
        rows = self.rows.get(name, [])
        if len(rows) != 1:
            self.fail('%s: recorded %d times, expected once' % (name, len(rows)))
            return None
        return rows[0]

    def check(self, name, field, ok, wanted):
        row = self.step(name)
        if row is not None and not ok(row.get(field)):
            self.fail('%s: %s is %s, expected %s' % (name, field, _short(row.get(field)), wanted))
        return row

    def equals(self, name, field, expected):
        if isinstance(expected, bool) or expected is None:
            return self.check(name, field, lambda value: value is expected, repr(expected))
        return self.check(name, field, lambda value: value == expected, repr(expected))

    def present(self, name, field, wanted):
        return self.check(name, field, bool, wanted)

    def render(self, name):
        self.equals(name, 'meaningful', True)
        return self.equals(name, 'top_errors', None)

    def folder(self, expected):
        self.check('project-opened', 'project.folder',
                   lambda value: bool(value) and os.path.realpath(value) == os.path.realpath(expected),
                   'the directory this phase opened')


def check_workflow_build(report):
    c = Checks(report, 'build')
    c.step('host-environment')
    c.step('create-isolated-base-comp')
    c.present('documented-example-set-dsl', 'output_top', 'the renderer output TOP')
    # TouchDesigner 2025.32820 silently refuses the README's cross-network
    # connect; the probe then connects a display TOP inside the consumer COMP.
    c.equals('connect-top', 'connected', True)
    c.render('cook-1280')
    c.equals('cook-1280', 'shader_errors', None)
    c.render('resize-320x240')
    c.equals('resize-320x240', 'width', 320)
    c.equals('resize-320x240', 'height', 240)
    # The documented example draws solid(color: [0.9, 0.3, 0.5]) at alpha 1: a mean of 0.675.
    for name in ('cook-1280', 'resize-320x240', 'recover-valid-dsl'):
        c.check(name, 'stats', lambda stats: isinstance(stats, dict) and isinstance(stats.get('mean'), (int, float))
                and abs(stats['mean'] - DOC_MEAN) <= DOC_MEAN_TOLERANCE, 'the documented solid colour')
    c.check('invalid-dsl', 'raised', lambda value: isinstance(value, str) and bool(value),
            'the error set_dsl raises for an invalid program')
    c.equals('recover-valid-dsl', 'recovered', True)
    c.equals('recover-valid-dsl', 'top_errors', None)
    resized = c.step('resize-320x240')
    if resized is not None:
        c.check('recover-valid-dsl', 'sha256', lambda value: bool(value) and value == resized.get('sha256'),
                'the resized render again')
    c.check('save-project', 'size', lambda value: isinstance(value, int) and value > 0, 'a saved project')
    if report.get('verdict') != 'complete':
        c.fail('verdict is %s, expected complete' % _short(report.get('verdict')))
    return c.failures


def check_workflow_reopen(report):
    c = Checks(report, 'reopen')
    c.step('host-environment')
    row = c.equals('reopen-project', 'consumer_present', True)
    if row is not None and not (row.get('saved_toe_sha256') and
                                row.get('saved_toe_sha256') == row.get('build_saved_sha256')):
        c.fail('reopen-project: the reopened project is not the one the build phase saved')
    c.present('top-connected', 'display_top', 'the display TOP')
    c.equals('top-connected', 'consumer_output_present', True)
    c.equals('recook-after-reopen', 'bytes_match_build_render', True)
    c.equals('cleanup', 'clean', True)
    c.equals('cleanup', 'remaining_ops', [])
    return c.failures


def _check_installed_kit(c, folder):
    c.folder(folder)
    c.present('kit-onstart-build-present', 'output_top', 'the kit output TOP')
    tree = c.step('kit-tree')
    if tree is not None:
        checks = tree.get('checks') or {}
        missing = sorted(name for name, entry in checks.items() if not (entry or {}).get('present'))
        if not checks or missing:
            c.fail('kit-tree: missing %s' % (', '.join(missing) or 'every file'))
        if not (checks.get('engine/noisemaker/shaders') or {}).get('frag_count'):
            c.fail('kit-tree: the kit carries no shaders')
    c.equals('probe-started', 'host_present_at_probe_start', True)
    row = c.equals('rebuild-and-connect', 'rebuild_returned', True)
    if row is not None:
        attempt = row.get('connect_attempt') or {}
        refused = attempt.get('silently_refused') is True and 'exception' not in attempt
        if row.get('wired') is not True and not refused:
            c.fail('rebuild-and-connect: out is not wired and no silent refusal was recorded')
    c.render('render')


def check_kit(phase, report, folder):
    c = Checks(report, phase)
    if phase in ('build', 'relocate', 'reinstall'):
        _check_installed_kit(c, folder)
        if phase == 'relocate':
            c.equals('relocation-byte-compare', 'byte_identical', True)
        if phase == 'reinstall':
            c.equals('reinstall-byte-compare', 'byte_identical_vs_build', True)
    elif phase == 'recover':
        c.folder(folder)
        opened = c.present('project-opened', 'program_sha256', 'the program hash')
        row = c.step('rebuild-failure')
        if row is not None and (row.get('failure') or {}).get('raised') is not True:
            c.fail('rebuild-failure: rebuild() did not raise for a broken program.dsl')
        c.equals('rebuild-failure', 'host_present', True)
        if opened is not None:
            c.equals('program-restored', 'sha256', opened.get('program_sha256'))
        c.render('recovery-render')
        c.equals('recovery-render', 'rebuild_returned', True)
        c.equals('recovery-byte-compare', 'byte_identical', True)
    elif phase == 'parameters':
        c.folder(folder)
        enumeration = c.check('enumeration', 'customPars', lambda value: isinstance(value, list), 'the enumerated custom parameters')
        c.render('baseline-render')
        driven = c.step('custom-parameters-driven')
        if driven is not None and enumeration is not None and isinstance(enumeration.get('customPars'), list):
            expected = len(enumeration['customPars'])
            if driven.get('count') != expected or len(driven.get('driven') or []) != expected:
                c.fail('custom-parameters-driven: drove %s of %d enumerated parameters' % (_short(driven.get('count')), expected))
        for entry in (driven or {}).get('driven') or []:
            name = entry.get('par')
            if 'error' in entry or 'restore_error' in entry:
                c.fail('custom parameter %s: %s' % (name, entry.get('error') or entry.get('restore_error')))
            if (entry.get('render') or {}).get('meaningful') is not True:
                c.fail('custom parameter %s: no meaningful render after the change' % name)
            if entry.get('rebuild_returned') is not True:
                c.fail('custom parameter %s: rebuild() did not return' % name)
        c.render('rebuild-control-render')
        c.equals('rebuild-control-render', 'byte_identical_to_baseline', True)
        c.equals('rebuild-control', 'rebuild_returned', True)
        c.equals('dsl-change', 'applied', True)
        c.render('dsl-changed-render')
        c.equals('dsl-changed-render', 'byte_identical_to_baseline', False)
        c.render('restored-render')
        c.equals('restored-render', 'byte_identical_to_baseline', True)
    elif phase == 'license':
        c.folder(folder)
        c.equals('license-state', 'activation_needed', False)
    elif phase == 'remove':
        c.step('kit-onstart-build-present')
        c.equals('uninstall', 'clean', True)
        c.equals('uninstall', 'remaining_ops', [])
    else:
        c.fail('no checks for kit phase %r' % phase)
    return c.failures


# --- the run -----------------------------------------------------------------

class Redactor:
    def __init__(self, pairs):
        self.pairs = []
        for path, label in pairs:
            if path:
                for form in {str(path), os.path.realpath(str(path))}:
                    self.pairs.append((form, label))
        self.pairs.sort(key=lambda pair: -len(pair[0]))

    def __call__(self, text):
        text = str(text)
        for path, label in self.pairs:
            text = text.replace(path, label)
        return text


def _tail(path, limit=LOG_TAIL):
    try:
        return Path(path).read_text(errors='replace').splitlines()[-limit:]
    except OSError:
        return []


class Probes:
    def __init__(self, repo, td_bin, reference_root, engine_version, sha, work, env,
                 timeout=RUN_TIMEOUT, grace=STOP_GRACE):
        self.repo = Path(repo)
        self.td_bin = str(td_bin)
        self.reference_root = str(reference_root)
        self.engine_version = engine_version
        self.sha = sha
        self.work = Path(work)
        self.timeout = timeout
        self.grace = grace
        self.results = {}
        app = self.td_bin.split('/Contents/MacOS/')[0] if '/Contents/MacOS/' in self.td_bin \
            else os.path.dirname(self.td_bin)
        self.env = dict(env, TD_APP=app, NM_TD_REPO=str(self.repo))
        self.redact = Redactor([(self.work, '<work>'), (self.repo, '<repo>'),
                                (env.get('RUNNER_TEMP'), '<runner-temp>'), (env.get('HOME'), '<home>')])
        self.workflow_out = self.repo / 'parity' / 'out' / 'workflow'
        self.kit_out = self.work / 'kit-qual'

    # Commands, kept separate so the tests can stand in for TouchDesigner's tools.
    def workflow_bootstrap(self):
        return [sys.executable, str(self.repo / 'td' / 'build_workflow_toe.py')]

    def kit_bootstrap(self, kit):
        return [sys.executable, str(self.repo / 'td' / 'build_kit_toe.py'), str(kit)]

    def materialize(self, dest):
        return [sys.executable, str(self.repo / 'tools' / 'materialize_kit.py'), str(dest),
                '--program', str(self.repo / KIT_PROGRAM), '--engine-version', self.engine_version,
                '--git-source', self.sha, '--reference-root', self.reference_root]

    def expected(self):
        return ['workflow %s' % phase for phase in WORKFLOW_PHASES] + \
               ['kit %s' % phase for phase in KIT_PHASES]

    def record(self, label, failures, lines=()):
        self.results[label] = list(failures)
        if not failures:
            print('== %s: pass' % label, flush=True)
            return
        print('== %s: FAIL' % label)
        for failure in failures:
            print('   ' + self.redact(failure))
        for line in lines:
            print('   | ' + self.redact(line))
        sys.stdout.flush()

    def not_run(self, labels, reason):
        for label in labels:
            self.record(label, ['not run: %s' % reason])

    def tool(self, label, args, env):
        proc = subprocess.run(args, cwd=self.repo, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            self.record(label, ['exited %d' % proc.returncode],
                        (proc.stdout + proc.stderr).splitlines()[-LOG_TAIL:])
            return False
        last = (proc.stdout.strip().splitlines() or [''])[-1]
        print('== %s: ok %s' % (label, self.redact(last)), flush=True)
        return True

    def phase(self, label, toe, env, report_path, check, crash_path=None, logs=()):
        for stale in (report_path, crash_path, *logs):
            if stale is not None:
                Path(stale).unlink(missing_ok=True)
        td_log = self.work / ('%s.log' % label.replace(' ', '-'))
        run = run_touchdesigner(self.td_bin, toe, env, td_log, self.timeout, self.grace)
        failures = []
        if run.timed_out:
            failures.append('TouchDesigner did not quit within %d s and was stopped (an unactivated '
                            'license blocks at its activation dialog)' % self.timeout)
        elif run.returncode != 0:
            failures.append('TouchDesigner exited %s' % run.returncode)
        for pid in run.leftovers:
            print('== %s: stopped process %d, left in the TouchDesigner process group' % (label, pid))
        lines = []
        if crash_path is not None and Path(crash_path).exists():
            try:
                fatal = json.loads(Path(crash_path).read_text()).get('fatal')
            except ValueError:
                fatal = 'unreadable crash report'
            failures.append('the probe wrote a crash report: %s' % _last_line(fatal))
        if not Path(report_path).exists():
            failures.append('the probe wrote no report')
        else:
            try:
                report = json.loads(Path(report_path).read_text())
            except ValueError as err:
                failures.append('the report is not JSON: %s' % err)
            else:
                failures.extend(check(report))
                lines.extend(str(line) for line in (report.get('log') or [])[-LOG_TAIL:])
        if failures:
            for path in (*logs, td_log):
                lines.extend(_tail(path))
        self.record(label, failures, lines)
        return not failures

    def run_workflow(self):
        out = self.workflow_out
        out.mkdir(parents=True, exist_ok=True)
        (out / 'nm_workflow_saved.toe').unlink(missing_ok=True)
        env = dict(self.env, TMPDIR=str(self._scratch('workflow-tmp')))
        labels = ['workflow %s' % phase for phase in WORKFLOW_PHASES]
        if not self.tool('workflow bootstrap', self.workflow_bootstrap(), env):
            self.not_run(labels, 'the workflow bootstrap failed')
            return
        toe = self.repo / 'td' / 'nm_workflow.toe'
        for index, phase in enumerate(WORKFLOW_PHASES):
            ok = self.phase(labels[index], toe, dict(env, NM_WORKFLOW_PHASE=phase),
                            out / ('report.%s.json' % phase),
                            check_workflow_build if phase == 'build' else check_workflow_reopen,
                            crash_path=out / ('report.%s.crash.json' % phase),
                            logs=[out / ('_workflow_log.%s.txt' % phase)])
            if not ok:
                self.not_run(labels[index + 1:], 'the %s phase failed' % phase)
                return
            # The reopen phase opens the project that the build phase saved.
            toe = out / 'nm_workflow_saved.toe'

    def run_kit(self):
        kit, moved = self.work / 'kit', self.work / 'kit-moved'
        env = dict(self.env, TMPDIR=str(self._scratch('kit-tmp')), NM_KIT_OUT=str(self.kit_out))
        labels = ['kit %s' % phase for phase in KIT_PHASES]
        if not (self.tool('kit materialize', self.materialize(kit), env) and
                self.tool('kit bootstrap', self.kit_bootstrap(kit), env)):
            self.not_run(labels, 'the kit could not be installed')
            return
        folder = kit
        for index, phase in enumerate(KIT_PHASES):
            if phase == 'relocate':
                os.rename(kit, moved)
                folder = moved
            if phase == 'reinstall' and not self.tool('kit materialize over the install',
                                                      self.materialize(moved), env):
                self.not_run(labels[index:], 'the kit could not be materialized again')
                return
            phase_env = dict(env, NM_KIT_PHASE=phase)
            if phase == 'parameters':
                phase_env.update(NM_PARAM_DSL_FROM=PARAM_DSL_FROM, NM_PARAM_DSL_TO=PARAM_DSL_TO)
            ok = self.phase(labels[index], folder / 'kit.toe', phase_env,
                            self.kit_out / ('report.%s.json' % phase),
                            lambda report, phase=phase, folder=folder: check_kit(phase, report, folder),
                            crash_path=self.kit_out / ('report.%s.crash.json' % phase),
                            logs=[self.kit_out / ('_kit_log.%s.txt' % phase)])
            if not ok:
                self.not_run(labels[index + 1:], 'the %s phase failed' % phase)
                return

    def _scratch(self, name):
        path = self.work / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run_all(self):
        self.run_workflow()
        self.run_kit()
        failed = [label for label in self.expected() if self.results.get(label) != []]
        if failed:
            print('== td-probes: FAILED: %s' % ', '.join(failed), flush=True)
            return 1
        print('== td-probes: every phase passed', flush=True)
        return 0


def main(env=None, argv=()):
    env = dict(os.environ if env is None else env)
    redact = Redactor([(REPO, '<repo>'), (env.get('HOME'), '<home>')])
    if argv:
        print('td-probes: takes no arguments; it always runs every phase (got %s)' % ' '.join(argv), file=sys.stderr)
        return 1
    td_bin = env.get('TD_BIN') or DEFAULT_TD_BIN
    if not (os.path.isfile(td_bin) and os.access(td_bin, os.X_OK)):
        print('td-probes: no TouchDesigner binary at %s (set TD_BIN)' % redact(td_bin), file=sys.stderr)
        return 1
    reference = env.get('NM_REFERENCE_ROOT')
    if not reference or not os.path.isdir(os.path.join(reference, 'shaders')):
        print('td-probes: set NM_REFERENCE_ROOT to the reference engine checkout (the tree holding shaders/)',
              file=sys.stderr)
        return 1
    try:
        with open(os.path.join(reference, 'package.json')) as fh:
            engine_version = json.load(fh)['version']
    except (OSError, ValueError, KeyError):
        print('td-probes: no engine version in NM_REFERENCE_ROOT/package.json', file=sys.stderr)
        return 1
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True,
                         text=True).stdout.strip()
    if len(sha) != 40:
        print('td-probes: cannot read this checkout\'s commit', file=sys.stderr)
        return 1
    work = tempfile.mkdtemp(prefix='td-probes.', dir=env.get('RUNNER_TEMP') or None)
    return Probes(REPO, td_bin, reference, engine_version, sha, work, env).run_all()


if __name__ == '__main__':
    # SIGTERM and SIGHUP unwind the run as Ctrl-C does, so it stops what it started.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, exit_on_signal)
    sys.exit(main(argv=sys.argv[1:]))
