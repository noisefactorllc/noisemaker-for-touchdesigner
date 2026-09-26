"""kit_probe.py -- GAP-003 kit qualification probe (runs inside TouchDesigner).

Executed by the `kit.toe` bootstrap inside a materialized Noisedeck export kit
directory (built by td/build_kit_toe.py). The kit's own `integrate.py` Execute
DAT performs the documented installation build on project start (`onStart` with
its Start toggle enabled); this probe verifies the result, records a
machine-readable report and PNG artifacts under parity/out/kit-qual/, and quits
(project.quit(force=True) from the exec DAT's finally block).

Phases (NM_KIT_PHASE, passed through the host broker env):
  build     -- wait for the kit's onStart build, add the documented `out` Null
               TOP beside the Base COMP, call the documented rebuild()
               (which wires the output), cook, verify meaningful TOP output,
               record source paths, notices, and PNG; quit.
  relocate  -- same verification after the export directory (with the saved
               kit.toe) was MOVED to a different path; the render PNG must be
               byte-identical to the build phase (all paths relative to
               project.folder).
  reinstall -- the kit files were re-materialized over the installed directory
               before this run; rebuild and verify the render again.
  remove    -- uninstall: destroy the noisemaker Base COMP and the out TOP,
               verify no remaining ops, and quit.
"""
import hashlib
import json
import os
import sys
import time
import traceback


def _find_repo():
    env = os.environ.get('NM_TD_REPO')
    if env and os.path.isdir(os.path.join(env, 'td', 'noisemaker')):
        return env
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        raise RuntimeError('cannot locate the noisemaker-for-touchdesigner repo: set NM_TD_REPO')


REPO = _find_repo()
OUT = os.path.join(REPO, 'parity', 'out', 'kit-qual')
PHASE = os.environ.get('NM_KIT_PHASE') or 'build'
HOST_COMP = 'noisemaker'
OUT_TOP = 'out'

_lines = []


def log(m):
    _lines.append(str(m))
    try:
        print('[nm-kit]', m)
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
            'std': round(float(a.std()), 6),
            'unique_bytes': len(set(b)) if len(b) <= (1 << 24) else -1,
            'all_black': bool(a.max() == 0)}


def _versions():
    v = {}
    for attr in ('version', 'osName', 'osVersion', 'licenseType', 'build'):
        try:
            v[attr] = str(getattr(app, attr))  # noqa: F821
        except Exception:
            pass
    return v


def _write_report(name, payload):
    os.makedirs(OUT, exist_ok=True)
    payload = dict(payload)
    payload['log'] = _lines
    p = os.path.join(OUT, name)
    with open(p, 'w') as f:
        json.dump(payload, f, indent=2, default=str)
    log('report written: %s' % name)


def wait_for_built_host(timeout_seconds=60.0):
    """Wait until the kit's integrate onStart build has finished.

    integrate.py builds synchronously during project load; this probe's exec is
    deferred past load (the bootstrap runs it `delayFrames` after start), so the
    built host COMP should already exist. The wait only guards against slow
    first-time GLSL setup, and sleeps rather than pumping frames so the load
    path stays serial.
    """
    root = op('/')  # noqa: F821
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        container = root.op('project1')
        host = container.op(HOST_COMP) if container else None
        if host is not None:
            nm = host.fetch('nm', None, search=False)
            if nm is not None:
                return host, nm
        time.sleep(0.25)
    raise RuntimeError('kit build (noisemaker COMP with stored renderer) not present '
                       'after %.0fs' % timeout_seconds)


def verify_kit_tree(root_dir):
    """Record the installed kit's source paths, engine, and notices."""
    import pathlib
    d = pathlib.Path(root_dir)
    checks = {}
    for name in ('program.dsl', 'integrate.py', 'README.md', 'README.template.md',
                 'noisedeck-export.json', 'compat.json'):
        p = d / name
        checks[name] = {'present': p.exists(),
                        'sha256': _sha256(str(p)) if p.exists() else None}
    for name in ('LICENSES/noisemaker-MIT.txt',
                 'LICENSES/noisemaker-for-touchdesigner-LICENSE.txt'):
        p = d / name
        checks[name] = {'present': p.exists(),
                        'sha256': _sha256(str(p)) if p.exists() else None}
    engine = d / 'engine' / 'noisemaker'
    checks['engine/noisemaker/runtime/nm_renderer.py'] = {
        'present': (engine / 'runtime' / 'nm_renderer.py').exists()}
    shaders = engine / 'shaders'
    checks['engine/noisemaker/shaders'] = {
        'present': shaders.is_dir(),
        'frag_count': (len(list(shaders.rglob('*.frag'))) if shaders.is_dir() else 0)}
    return checks


def render_and_verify(out_top, png_name):
    out_top.cook(force=True)
    s = _stats(out_top)
    p = os.path.join(OUT, png_name)
    os.makedirs(OUT, exist_ok=True)
    out_top.save(p)
    errs = (out_top.errors() or '') if hasattr(out_top, 'errors') else ''
    return {'png': os.path.basename(p), 'sha256': _sha256(p), 'stats': s,
            'top_errors': errs or None,
            'meaningful': bool(not s['all_black'] and s['unique_bytes'] != 1)}


def do_build_like_phase(extra=None):
    try:
        try:
            project.realTime = False  # noqa: F821
        except Exception as e:
            log('realTime set failed: %s' % e)
        steps = []
        root = op('/')  # noqa: F821
        folder = project.folder  # noqa: F821
        steps.append({'step': 'project-opened', 'project.folder': folder,
                      'phase': PHASE, 'td': _versions()})
        host, nm = wait_for_built_host()
        steps.append({'step': 'kit-onstart-build-present', 'host_comp': host.path,
                      'built_network_children': len(host.children),
                      'output_top': nm.Output.path if nm.Output is not None else None})
        steps.append({'step': 'kit-tree', **{'checks': verify_kit_tree(folder)}})
        # presence here (deferred 180 frames past load) proves the kit's integrate
        # onStart build ran during project load, not just when invoked directly
        pre = root.op('project1').op(HOST_COMP)
        steps.append({'step': 'probe-started', 'host_present_at_probe_start': pre is not None})
        # documented user step: add a Null TOP named `out` beside the Base COMP
        container = root.op('project1')
        out = container.op(OUT_TOP)
        if out is None:
            out = container.create(nullTOP, OUT_TOP)  # noqa: F821
        # documented rebuild entry point: rebuild() re-reads program.dsl and wires `out`
        integ = container.op('integrate1')
        rebuilt = integ.module.rebuild() if integ else None
        host2 = container.op(HOST_COMP)
        nm2 = host2.fetch('nm', None, search=False) if host2 else None
        out.cook(force=True)
        inputs = [o.path for o in (out.inputs or [])]
        wired = bool(inputs)
        # The kit's connect_output wires a sibling `out` to the COMP-internal nm.Output
        # (cross-network connect). GAP-002 measured 2025.32820 silently refusing that
        # form; confirm it here for the shipped kit and record it, then verify the first
        # useful result from the kit's own output TOP (nm.Output), which is what the
        # export delivers as an ordinary TOP.
        refusal = {}
        if not wired and nm2 is not None and nm2.Output is not None:
            try:
                out.inputConnectors[0].connect(nm2.Output)
                out.cook(force=True)
                wired = bool([o.path for o in (out.inputs or [])])
            except Exception as e:  # noqa: BLE001
                refusal['exception'] = str(e)[:200]
            refusal.update({'documented_form': 'out.inputConnectors[0].connect(nm.Output)',
                            'sink': out.path, 'source': nm2.Output.path,
                            'silently_refused': not wired,
                            'consistent_with_gap_002_finding': True})
        steps.append({'step': 'rebuild-and-connect', 'rebuild_returned': rebuilt is not None,
                      'out_inputs': inputs, 'wired': wired, 'connect_attempt': refusal})
        # first useful result: the kit's own output TOP
        target = out if wired else (nm2.Output if nm2 is not None else None)
        if target is None:
            raise RuntimeError('no renderable TOP: out unwired and nm.Output missing')
        target.cook(force=True)
        s = _stats(target)
        p = os.path.join(OUT, 'kit.%s.png' % PHASE)
        os.makedirs(OUT, exist_ok=True)
        target.save(p)
        errs = (target.errors() or '') if hasattr(target, 'errors') else ''
        if not wired:
            errs_out = (out.errors() or '') if hasattr(out, 'errors') else ''
        else:
            errs_out = ''
        steps.append({'step': 'render', 'png': os.path.basename(p), 'sha256': _sha256(p),
                      'rendered_top': target.path, 'stats': s, 'top_errors': errs or None,
                      'unwired_out_errors': (errs_out or None),
                      'meaningful': bool(not s['all_black'] and s['unique_bytes'] != 1)})
        return steps
    except Exception:
        steps.append({'step': 'FATAL-%s' % PHASE, 'error': traceback.format_exc()[-4000:]})
        # Diagnostics: what actually loaded, and what does the kit's integrate module do
        # if invoked directly? This captures a failed onStart (Start toggle off, exception
        # inside build, missing program.dsl) that would otherwise only live in the textport.
        try:
            root = op('/')  # noqa: F821
            container = root.op('project1')
            diag = {'root_children': [c.name for c in root.children],
                    'project1_children': [c.name for c in container.children]}
            integ = container.op('integrate1')
            if integ is None:
                diag['integrate1'] = 'absent'
            else:
                diag['integrate1'] = {'exists': True,
                                      'start': str(integ.par.start),
                                      'start_val': integ.par.start.eval(),
                                      'module_attrs': [a for a in dir(integ.module)
                                                       if not a.startswith('_')][:40]}
                try:
                    integ.module.onStart()
                    diag['direct_onStart'] = 'completed'
                    host = container.op(HOST_COMP)
                    diag['direct_onStart_host'] = host.path if host is not None else None
                except Exception as e:  # noqa: BLE001
                    diag['direct_onStart_error'] = '%s: %s' % (type(e).__name__, str(e)[:800])
            steps.append({'step': 'diagnostics', **diag})
        except Exception:
            steps.append({'step': 'diagnostics', 'error': traceback.format_exc()[-2000:]})
        return steps


def build_phase():
    steps = do_build_like_phase()
    # save nothing extra; the .toe already lives beside program.dsl
    _write_report('report.build.json', {'phase': 'build', 'td': _versions(), 'steps': steps})
    return steps


def relocate_phase():
    steps = do_build_like_phase()
    try:
        build_png = os.path.join(OUT, 'kit.build.png')
        this_png = os.path.join(OUT, 'kit.relocate.png')
        same = os.path.exists(build_png) and _sha256(this_png) == _sha256(build_png)
        steps.append({'step': 'relocation-byte-compare', 'build_png_sha256': _sha256(build_png),
                      'relocate_png_sha256': _sha256(this_png), 'byte_identical': same})
    except Exception:
        steps.append({'step': 'relocation-byte-compare', 'error': traceback.format_exc()[-800:]})
    _write_report('report.relocate.json', {'phase': 'relocate', 'td': _versions(), 'steps': steps})
    return steps


def reinstall_phase():
    steps = do_build_like_phase()
    try:
        build_png = os.path.join(OUT, 'kit.build.png')
        this_png = os.path.join(OUT, 'kit.reinstall.png')
        same = os.path.exists(build_png) and _sha256(this_png) == _sha256(build_png)
        steps.append({'step': 'reinstall-byte-compare', 'byte_identical_vs_build': same})
    except Exception:
        steps.append({'step': 'reinstall-byte-compare', 'error': traceback.format_exc()[-800:]})
    _write_report('report.reinstall.json', {'phase': 'reinstall', 'td': _versions(), 'steps': steps})
    return steps


def remove_phase():
    steps = []
    try:
        try:
            project.realTime = False  # noqa: F821
        except Exception as e:
            log('realTime set failed: %s' % e)
        root = op('/')  # noqa: F821
        host, nm = wait_for_built_host()
        steps.append({'step': 'kit-onstart-build-present', 'host_comp': host.path})
        container = root.op('project1')
        out = container.op(OUT_TOP) if container else None
        for target in (out, host):
            if target is not None:
                target.destroy()
        remaining = [c.name for c in container.children
                     if container is not None and c.name in (HOST_COMP, OUT_TOP)]
        steps.append({'step': 'uninstall', 'destroyed': [HOST_COMP, OUT_TOP],
                      'remaining_ops': remaining, 'clean': not remaining})
    except Exception:
        steps.append({'step': 'FATAL-remove', 'error': traceback.format_exc()[-4000:]})
    _write_report('report.remove.json', {'phase': 'remove', 'td': _versions(), 'steps': steps})
    return steps


def main():
    if PHASE == 'relocate':
        relocate_phase()
    elif PHASE == 'reinstall':
        reinstall_phase()
    elif PHASE == 'remove':
        remove_phase()
    else:
        build_phase()
    log('phase %s done' % PHASE)


try:
    main()
except Exception:
    _lines.append('FATAL %s phase:\n' % PHASE + traceback.format_exc())
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'report.%s.crash.json' % PHASE), 'w') as f:
            json.dump({'phase': PHASE, 'fatal': traceback.format_exc()[-4000:]}, f,
                      indent=2, default=str)
    except Exception:
        pass
finally:
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, '_kit_log.%s.txt' % PHASE), 'w') as f:
            f.write('\n'.join(_lines) + '\n')
    except Exception:
        pass
    try:
        project.quit(force=True)  # noqa: F821
    except Exception:
        pass
