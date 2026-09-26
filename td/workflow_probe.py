"""workflow_probe.py — GAP-002 installed developer workflow probe (runs inside TouchDesigner).

Executed by the `td/nm_workflow.toe` bootstrap (built by td/build_workflow_toe.py, same
toeexpand/toecollapse transplant as build_parity_toe.py). It exercises the documented
installed workflow from README "Use it in your own TouchDesigner project" on an isolated
consumer, records a machine-readable report and PNG artifacts under parity/evidence/workflow/ (a tracked, gitignored-exempt evidence path),
and quits (project.quit(force=True) from the exec DAT's finally block, so the host run
always terminates itself).

Phases (NM_WORKFLOW_PHASE, passed through the host broker env):
  build   — fresh isolated consumer Base COMP in a fresh project; documented NMRenderer
            example (1280x1280, README DSL); connect its Output to an `out` TOP; cook and
            verify meaningful output; resize(320, 240) and re-cook; feed invalid DSL and
            verify the error is raised, then recover by re-setting the valid DSL; save the
            project (.toe) with its sha256 recorded; quit.
  reopen  — the saved .toe is re-opened (the same exec DAT runs again); verify the network
            survived, re-cook, compare the reopened output PNG bytes with the build-phase
            artifact (file preservation), record cleanup (destroy the consumer + out TOP,
            verify nothing remains), and quit.
"""
import hashlib
import json
import os
import sys
import time
import traceback


def _find_repo():
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    env = os.environ.get('NM_TD_REPO')
    if env and os.path.isdir(os.path.join(env, 'td', 'noisemaker')):
        return env
    raise RuntimeError('cannot locate the noisemaker-for-touchdesigner repo: set NM_TD_REPO or run via the .toe')


REPO = _find_repo()
TD_DIR = os.path.join(REPO, 'td')
OUT = os.path.join(REPO, 'parity', 'evidence', 'workflow')
PHASE = os.environ.get('NM_WORKFLOW_PHASE') or 'build'
# The documented example (README "Use it in your own TouchDesigner project"), verbatim.
DOC_DSL = 'search synth\nsolid(color: [0.9, 0.3, 0.5]).write(o0)\nrender(o0)'
CONSUMER = 'nm_workflow_consumer'
OUT_TOP = 'out'

if TD_DIR not in sys.path:
    sys.path.insert(0, TD_DIR)

_lines = []
def log(m):
    _lines.append(str(m))
    try:
        print('[nm-workflow]', m)
    except Exception:
        pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _stats(top):
    a = top.numpyArray()
    b = a.tobytes()
    return {'shape': list(a.shape), 'mean': round(float(a.mean()), 6),
            'std': round(float(a.std()), 6), 'unique_bytes': len(set(b)) if len(b) <= (1 << 24) else -1,
            'all_black': bool(a.max() == 0)}


def _shader_errors(ops):
    found = []
    for c in ops:
        try:
            err = (c.errors() or '') if hasattr(c, 'errors') else ''
        except Exception:
            err = ''
        if err:
            found.append('%s(%s) errors=%s' % (c.name, c.type, ' '.join(err.split())[:240]))
        if c.type in ('glsl', 'glslmulti'):
            try:
                warn = (c.warnings() or '') if hasattr(c, 'warnings') else ''
            except Exception:
                warn = ''
            if 'compile error' in warn.lower():
                found.append('%s(%s) compile-error' % (c.name, c.type))
    return ' | '.join(found)


def _versions():
    v = {}
    for attr in ('version', 'osName', 'osVersion', 'licenseType', 'build'):
        try:
            v[attr] = str(getattr(app, attr))
        except Exception:
            pass
    return v


def build_phase():
    os.makedirs(OUT, exist_ok=True)
    for stale in ('report.build.crash.json', 'nm_workflow_saved.1.toe', 'nm_workflow_saved.2.toe'):
        p = os.path.join(OUT, stale)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    try:
        project.realTime = False   # noqa: F821 — deterministic
    except Exception as e:
        log('realTime set failed: %s' % e)
    steps = []
    def step(name, **kw):
        rec = {'step': name}
        rec.update(kw)
        steps.append(rec)
        log('%s: %s' % (name, json.dumps(kw)[:400]))
        return rec

    root = op('/')   # noqa: F821
    step('host-environment', td=_versions(), phase=PHASE, repo=os.path.basename(REPO))
    # 1. isolated consumer: this run opened a fresh stock project (no prior state); the
    #    consumer is a fresh Base COMP under it — nothing from any earlier session.
    pre = [c.name for c in root.children]
    comp = root.create(baseCOMP, CONSUMER)   # noqa: F821
    step('create-isolated-base-comp', pre_existing_children=pre, consumer=comp.path)
    # 2. documented NMRenderer example (README: set_dsl before wiring the output TOP)
    from noisemaker.runtime.nm_renderer import NMRenderer
    nm = NMRenderer(comp, width=1280, height=1280)
    comp.store('nm', nm)
    nm.set_dsl(DOC_DSL)
    step('documented-example-set-dsl', dsl=DOC_DSL, width=1280, height=1280,
         output_top=(nm.Output.path if nm.Output is not None else None))
    # 3. connect its TOP (README: out Null/Out TOP; nm.Output is an ordinary TOP)
    out = root.op(OUT_TOP)
    if out:
        out.destroy()
    out = root.create(nullTOP, OUT_TOP)   # noqa: F821
    diag = {}
    try:
        diag['dir_connector'] = sorted(dir(out.inputConnectors[0]))[:60]
        diag['dir_out_inputs'] = [a for a in dir(out) if 'nput' in a.lower()][:40]
        diag['n_input_connectors'] = len(out.inputConnectors)
        diag['nm_out_output_connectors'] = len(nm.Output.outputConnectors)
    except Exception as e:
        diag['diag_error'] = str(e)
    log('connect-diag: ' + json.dumps(diag))
    # control: same-level connect at root — distinguishes API misuse from cross-network refusal
    ctrl = {}
    try:
        a = root.create(nullTOP, 'nm_ctrl_a')   # noqa: F821
        b = root.create(nullTOP, 'nm_ctrl_b')   # noqa: F821
        b.inputConnectors[0].connect(a)
        ctrl['same_level_inputs'] = [o.path for o in (b.inputs or [])]
        a.destroy(); b.destroy()
    except Exception:
        ctrl['error'] = traceback.format_exc()[-400:]
    log('connect-control: ' + json.dumps(ctrl))
    # README pattern: out.inputConnectors[0].connect(nm.Output). Empirically that call can
    # return without connecting on some builds, so try the documented form first, then
    # fallbacks, verifying out.inputs after each; record which form actually connected.
    connect_form = None
    nm_out = nm.Output
    candidates = (
        ('inputConnectors[0].connect(nm.Output)', lambda: out.inputConnectors[0].connect(nm_out)),
        ('out.setInputs([nm.Output])', lambda: out.setInputs([nm_out])),
        ('out.setInputs(nm.Output)', lambda: out.setInputs(nm_out)),
        ('inputConnectors[0].connect(nm.Output, 0)', lambda: out.inputConnectors[0].connect(nm_out, 0)),
        ('inputConnectors[0].outOP = nm.Output', lambda: setattr(out.inputConnectors[0], 'outOP', nm_out)),
    )
    for label, fn in candidates:
        try:
            fn()
        except Exception as e:
            log('connect form %s raised: %s' % (label, e))
        try:
            out.cook(force=True)
        except Exception:
            pass
        inputs = [op_.path for op_ in (out.inputs or [])]
        if inputs:
            connect_form = label
            break
    else:
        inputs = [op_.path for op_ in (out.inputs or [])]
    cross_network_refused = not inputs
    if cross_network_refused:
        # TD wires connect siblings only: the README's cross-network form ('/out' at root,
        # nm.Output inside the COMP) is silently refused by 2025.32820. Complete the
        # documented connect step with the display TOP inside the consumer COMP instead,
        # and record the observed refusal as a platform finding.
        out.destroy()
        out = comp.create(nullTOP, OUT_TOP)   # noqa: F821
        out.inputConnectors[0].connect(nm_out)
        out.cook(force=True)
        inputs = [op_.path for op_ in (out.inputs or [])]
        connect_form = ('in-comp out (cross-network form silently refused): '
                        'inputConnectors[0].connect(nm.Output)')
    step('connect-top', form=connect_form, consumer_output=nm.Output.path, consumer_out=nm.Output.type,
         display_top=out.path, display_top_inputs=inputs, connected=bool(inputs),
         readme_cross_network_form_connected=not cross_network_refused)
    out.cook(force=True)
    s1 = _stats(out)
    p1 = os.path.join(OUT, 'workflow.example-1280.png')
    out.save(p1)
    errs1 = (out.errors() or '') if hasattr(out, 'errors') else ''
    sh1 = _shader_errors(nm.pipeline.backend.ops)
    step('cook-1280', png=os.path.basename(p1), sha256=_sha256(p1), stats=s1,
         top_errors=errs1 or None, shader_errors=sh1 or None,
         meaningful=bool(not s1['all_black'] and s1['unique_bytes'] != 1))
    # 4. resize (README: resize(width, height) re-cooks at a new resolution)
    nm.resize(320, 240)
    out.cook(force=True)
    s2 = _stats(out)
    p2 = os.path.join(OUT, 'workflow.resized-320x240.png')
    out.save(p2)
    step('resize-320x240', png=os.path.basename(p2), sha256=_sha256(p2), stats=s2,
         width=out.width, height=out.height,
         meaningful=bool(not s2['all_black'] and s2['unique_bytes'] != 1))
    # 5. invalid DSL: expect a diagnostic error, then recover with the valid program
    recovery = {}
    try:
        try:
            nm.set_dsl('this is: not, a valid noisemaker program !!!')
            recovery['raised'] = None
            recovery['note'] = 'set_dsl did NOT raise for invalid DSL'
        except Exception as e:
            recovery['raised'] = type(e).__name__
            recovery['message'] = str(e)[:400]
            diag = getattr(e, 'diagnostic', None)
            if diag:
                recovery['diagnostic'] = {k: diag.get(k) for k in ('code', 'stage', 'severity', 'message', 'line', 'column') if k in diag}
        step('invalid-dsl', **recovery)
        # recovery: re-set the valid documented DSL and re-render
        nm.set_dsl(DOC_DSL)
        out.cook(force=True)
        s3 = _stats(out)
        p3 = os.path.join(OUT, 'workflow.recovered.png')
        out.save(p3)
        errs3 = (out.errors() or '') if hasattr(out, 'errors') else ''
        step('recover-valid-dsl', png=os.path.basename(p3), sha256=_sha256(p3), stats=s3,
             top_errors=errs3 or None, recovered=bool(not s3['all_black'] and not errs3))
    except Exception:
        step('invalid-dsl-recovery-unexpected', error=traceback.format_exc()[-800:])
    # 6. save the project for the reopen phase (file preservation + reopen check)
    saved = os.path.join(OUT, 'nm_workflow_saved.toe')
    try:
        project.save(saved)   # noqa: F821
        step('save-project', path='parity/evidence/workflow/nm_workflow_saved.toe',
             size=os.path.getsize(saved), sha256=_sha256(saved))
    except Exception:
        step('save-project', error=traceback.format_exc()[-800:])
    report = {'phase': 'build', 'td': _versions(), 'steps': steps,
              'output_path': nm.Output.path if nm.Output is not None else None,
              'verdict': 'complete' if all(s.get('meaningful', True) or 'meaningful' not in s for s in steps) else 'incomplete'}
    with open(os.path.join(OUT, 'report.build.json'), 'w') as f:
        json.dump(report, f, indent=2, default=str)
    log('report written: report.build.json')


def reopen_phase():
    os.makedirs(OUT, exist_ok=True)
    steps = []
    def step(name, **kw):
        rec = {'step': name}
        rec.update(kw)
        steps.append(rec)
        log('%s: %s' % (name, json.dumps(kw)[:400]))
        return rec

    root = op('/')   # noqa: F821
    fp = getattr(project, 'filePath', None)
    if callable(fp):
        try:
            fp = fp()
        except Exception:
            fp = None
    step('host-environment', td=_versions(), phase=PHASE, project_file=fp)
    build = {}
    try:
        with open(os.path.join(OUT, 'report.build.json')) as f:
            build = json.load(f)
    except Exception:
        step('read-build-report', error=traceback.format_exc()[-400:])
    # 1. the saved project re-opened: consumer comp + out TOP must exist unmodified
    comp = root.op(CONSUMER)
    step('reopen-project', consumer_present=bool(comp),
         saved_toe_sha256=_sha256(os.path.join(OUT, 'nm_workflow_saved.toe')),
         build_saved_sha256=(build.get('steps') and next((s.get('sha256') for s in build['steps'] if s.get('step') == 'save-project'), None)))
    out = root.op(OUT_TOP)
    if out is None and build.get('steps'):
        dpath = next((s.get('display_top') for s in build['steps'] if s.get('display_top')), None)
        out = root.op(dpath) if dpath else None
    step('top-connected', display_top=out.path if out else None,
         consumer_output=(root.op(build['output_path']).path
                          if build.get('output_path') and root.op(build['output_path']) else None),
         consumer_output_present=bool(build.get('output_path') and root.op(build['output_path'])))
    # 2. re-cook after reopen and compare bytes with the build-phase recovered render
    if out is not None:
        out.cook(force=True)
        s = _stats(out)
        preopen = os.path.join(OUT, 'workflow.reopened.png')
        out.save(preopen)
        build_png = os.path.join(OUT, 'workflow.recovered.png')
        same = (os.path.exists(build_png) and _sha256(preopen) == _sha256(build_png))
        step('recook-after-reopen', png=os.path.basename(preopen), sha256=_sha256(preopen),
             stats=s, bytes_match_build_render=same)
    # 3. cleanup: remove the consumer and the out TOP; verify nothing remains
    try:
        if out:
            out.destroy()
        if comp:
            comp.destroy()
        remaining = [c.name for c in root.children
                     if c.name in (CONSUMER, OUT_TOP)]
        step('cleanup', destroyed=True, remaining_ops=remaining, clean=not remaining)
    except Exception:
        step('cleanup', error=traceback.format_exc()[-800:])
    report = {'phase': 'reopen', 'td': _versions(), 'steps': steps}
    with open(os.path.join(OUT, 'report.reopen.json'), 'w') as f:
        json.dump(report, f, indent=2, default=str)
    log('report written: report.reopen.json')


try:
    if PHASE == 'reopen':
        reopen_phase()
    else:
        build_phase()
except Exception:
    tb = traceback.format_exc()
    _lines.append('FATAL %s phase:\n' % PHASE + tb)
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'report.%s.crash.json' % PHASE), 'w') as f:
            json.dump({'phase': PHASE, 'fatal': tb[-4000:]}, f, indent=2, default=str)
    except Exception:
        pass
finally:
    with open(os.path.join(OUT, '_workflow_log.%s.txt' % PHASE), 'w') as f:
        f.write('\n'.join(_lines) + '\n')
