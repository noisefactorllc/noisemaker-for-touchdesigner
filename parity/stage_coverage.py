#!/usr/bin/env python3
"""stage_coverage.py — classify the in-repo parity programs and render their reference goldens.

Self-contained: the parity DSLs live in this repo (`parity/programs/`), and the goldens are
rendered from the upstream Noisemaker engine via `parity/batch-golden.mjs`. There is NO dependency
on any sibling project — only on the upstream engine, pointed to by NM_REFERENCE_ROOT (no default;
this repo assumes no sibling on clone). For each in-repo `<name>.dsl`:

  1. produce the reference graph JSON via `tools/export-graph.mjs` (the reference compileGraph),
  2. inspect every *effect* pass's program: `effects/<ns>/<func>/<progName>.frag` must exist and
     not be MRT-flagged (MRT/3D programs are tracked separately),
  3. RENDER the golden (reference WebGL2) for everything that classifies as gateable.

A program whose graph can't be produced (e.g. a 3D effect the reference exporter rejects) or that
references a missing / MRT `.frag` is DEFERred — reported, never silently skipped. The three
multi-frame feedback-accumulation effects are routed to `parity/accumulate.sh` (they can't be graded
by the single-frame sweep) and reported as ACCUM.

Env:
  NM_REFERENCE_ROOT  upstream Noisemaker engine root (REQUIRED; no default — no sibling assumed)
  NM_SIZE/NM_TIME    golden render size / base time (default 256 / 0.25)

Usage:
  parity/stage_coverage.py                 # classify + render goldens; print a report
  parity/stage_coverage.py --emit render   # print only the space-separated RENDER list
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROGRAMS = os.path.join(REPO, 'parity', 'programs')
OUT = os.path.join(REPO, 'parity', 'out')
FRAGS = os.path.join(REPO, 'td', 'noisemaker', 'shaders', 'effects')
EXPORT = os.path.join(REPO, 'tools', 'export-graph.mjs')
BATCH = os.path.join(REPO, 'parity', 'batch-golden.mjs')

# Multi-frame feedback-accumulation effects — driven by the evolve harness (the single-frame sweep
# can't accumulate their feedback). Reported here, not rendered as single-frame goldens.
# convolutionFeedback is the same class (a `feedbackTex` temporal blend); driven + graded by
# parity/accumulate.sh — f1/f2 byte-exact, f8 ssim 0.99483 (8-bit-feedback drift, like motionBlur —
# Metal vs ANGLE convolution over frames).
# The synth3d_* pair are the 3D-volume statefuls (a `<sim>3d().render3d()` chain over a ca_state /
# rd_state feedback volume): same feedback class, graded by parity/accumulate.sh — f1/f2 bit-exact
# (max-abs-diff=1), then cellularAutomata3d ssim-gated (0.996 @ f8) and reactionDiffusion3d chaos-
# reported (continuous Gray-Scott, 0.977 @ f8), mirroring their 2D counterparts.
ACCUM_EFFECTS = {'cellularAutomata', 'reactionDiffusion', 'motionBlur', 'convolutionFeedback',
                 'synth3d_cellularAutomata3d', 'synth3d_reactionDiffusion3d'}
DEFERRED_EFFECTS = {
    '_vs32probe', 'buddhabrot', 'filter3d_flow3d', 'filter3d_palette3d', 'physical',
    'present_hero', 'synth3d_cell3d', 'synth3d_flythrough3d', 'synth3d_fractal3d',
    'synth3d_noise', 'synth3d_renderCubemap3d', 'synth3d_renderCubemapSurface',
    'synth3d_renderLit3d', 'synth3d_shape3d',
}


def reference_root():
    """Upstream engine root from NM_REFERENCE_ROOT (required; no '..' default)."""
    ref = os.environ.get('NM_REFERENCE_ROOT')
    if not ref or not os.path.isdir(os.path.join(ref, 'shaders')):
        sys.stderr.write(
            'NM_REFERENCE_ROOT is not set to a Noisemaker engine root (a tree containing shaders/).\n'
            'This repo assumes no sibling project on clone — set NM_REFERENCE_ROOT to the upstream\n'
            'engine to render reference goldens.\n')
        sys.exit(3)
    return ref


def program_names():
    """Every in-repo parity program (parity/programs/*.dsl), sorted."""
    return sorted(f[:-4] for f in os.listdir(PROGRAMS) if f.endswith('.dsl'))


def expected_sweep_names():
    """Every program required in the single-frame or accumulation sweep."""
    return [name for name in program_names() if name not in DEFERRED_EFFECTS]


def validate_render_set(path):
    """Reject missing, unexpected, or duplicate staged sweep names."""
    with open(path) as fh:
        actual = fh.read().split()
    expected = set(expected_sweep_names())
    actual_set = set(actual)
    missing = sorted(expected - actual_set)
    unexpected = sorted(actual_set - expected)
    duplicates = sorted(name for name in actual_set if actual.count(name) > 1)
    if missing or unexpected or duplicates:
        if missing:
            sys.stderr.write('missing staged cases: %s\n' % ' '.join(missing))
        if unexpected:
            sys.stderr.write('unexpected staged cases: %s\n' % ' '.join(unexpected))
        if duplicates:
            sys.stderr.write('duplicate staged cases: %s\n' % ' '.join(duplicates))
        return False
    return True


def export_graph(name):
    """Reference compileGraph → parity/out/<name>.graph.json. Returns (path|None, err).

    Inherits NM_REFERENCE_ROOT from the environment (export-graph.mjs errors if it is unset)."""
    dst = os.path.join(OUT, name + '.graph.json')
    r = subprocess.run(
        ['node', EXPORT, '--file', os.path.join(PROGRAMS, name + '.dsl'), dst],
        capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        msg = (r.stderr or r.stdout or 'unknown error').strip()
        return None, (msg.splitlines()[-1] if msg else 'unknown error')
    return dst, None


def frag_status(graph_path):
    """(ok, reasons) — ok iff every effect pass has an existing, non-MRT .frag."""
    with open(graph_path) as fh:
        graph = json.load(fh)
    missing, mrt = [], []
    for p in graph.get('passes', []):
        if p.get('passType') != 'effect':
            continue  # blit/copy passes are built by the backend, no .frag
        key = '%s/%s/%s' % (p.get('namespace'), p.get('func'), p.get('progName'))
        frag = os.path.join(FRAGS, p.get('namespace'), p.get('func'), p.get('progName') + '.frag')
        if not os.path.exists(frag):
            missing.append(key)
            continue
        with open(frag) as fh:
            if 'NM_OUTPUT: MRT' in fh.read(400):
                mrt.append(key)
    reasons = []
    if missing:
        reasons.append('missing frag: ' + ', '.join(sorted(set(missing))))
    if mrt:
        reasons.append('MRT/3D: ' + ', '.join(sorted(set(mrt))))
    return (not reasons), reasons


def render_goldens(names):
    """Render reference goldens for `names` via batch-golden.mjs (one browser session).

    Stateless single-pass effects are frame-invariant, so the default 8-frames-from-zero /
    timestep-0 protocol is idempotent for them and matches a single render."""
    if not names:
        return
    man = os.path.join(OUT, '_stage_manifest.txt')
    with open(man, 'w') as fh:
        for n in names:
            fh.write('%s %s\n' % (n, os.path.join(PROGRAMS, n + '.dsl')))
    for name in names:
        try:
            os.remove(os.path.join(OUT, name + '.golden.png'))
        except FileNotFoundError:
            pass
    subprocess.run(
        ['node', BATCH, man, OUT, '--size', os.environ.get('NM_SIZE', '256'),
         '--frames', '8', '--timestep', '0', '--time', os.environ.get('NM_TIME', '0.25')],
        cwd=REPO, check=True)


def main():
    emit = sys.argv[sys.argv.index('--emit') + 1] if '--emit' in sys.argv else None
    if emit == 'expected':
        print(' '.join(expected_sweep_names()))
        return
    if '--validate-set' in sys.argv:
        path = sys.argv[sys.argv.index('--validate-set') + 1]
        if not validate_render_set(path):
            sys.exit(2)
        return
    reference_root()
    os.makedirs(OUT, exist_ok=True)
    render, defer, accum = [], [], []
    for name in program_names():
        if name in ACCUM_EFFECTS:
            accum.append(name)
            continue
        graph, err = export_graph(name)
        if not graph:
            defer.append((name, 'export-graph failed: %s' % err))
            continue
        ok, reasons = frag_status(graph)
        if ok:
            render.append(name)
        else:
            defer.append((name, '; '.join(reasons)))

    actual = set(render + accum)
    expected = set(expected_sweep_names())
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing:
            sys.stderr.write('unclassified gateable cases: %s\n' % ' '.join(missing))
        if unexpected:
            sys.stderr.write('unexpected gateable cases: %s\n' % ' '.join(unexpected))
        sys.exit(2)

    if emit == 'render':
        print(' '.join(render))
        return

    # Render the reference goldens for the gateable set (skipped in --emit mode to keep it cheap).
    render_goldens(render)

    # _render_set.txt drives sweep.sh; include ACCUM names so it reports them ([ACCUM] -> accumulate.sh).
    with open(os.path.join(OUT, '_render_set.txt'), 'w') as fh:
        fh.write(' '.join(render + accum) + '\n')
    print('=== classified %d in-repo programs (goldens from NM_REFERENCE_ROOT) ===' % (
        len(render) + len(defer) + len(accum)))
    print('RENDER (%d):\n  %s' % (len(render), ' '.join(render)))
    print('ACCUM  (%d):  %s   (-> parity/accumulate.sh)' % (len(accum), ' '.join(accum)))
    print('DEFER  (%d):' % len(defer))
    for name, reason in defer:
        print('  %-22s %s' % (name, reason))


if __name__ == '__main__':
    main()
