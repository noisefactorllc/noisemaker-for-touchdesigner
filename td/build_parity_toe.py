#!/usr/bin/env python3
"""build_parity_toe.py — author the bootstrap `td/nm_parity.toe` used by parity/run.sh.

TouchDesigner has no headless startup-script hook and its `.toe` is a binary, so we build a
minimal project containing one Execute DAT (callbacks `onStart`/`onCreate`) by transplanting
into the stock NewProject.toe skeleton via `toeexpand`/`toecollapse` (TD's own tools). On
load the Execute DAT execs `td/parity_render_all.py` (which renders the Tier-1 candidates),
then quits.

Run with stock python3 (no TD needed to BUILD the .toe; TD is needed to RUN it):
    python3 td/build_parity_toe.py

Paths are derived from this file's location; the TouchDesigner install is discovered
portably (override with the TD_APP env var: an .app bundle, an install root, or the
bin directory containing toeexpand/toecollapse). Nothing here is machine-specific in
committed form — the absolute repo path is baked only into the generated `.toe`, which
is gitignored.
"""
import glob
import os
import shutil
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_DIR = os.path.join(REPO, 'td')
RENDER = os.path.join(TD_DIR, 'parity_render_all.py')
OUT_TOE = os.path.join(TD_DIR, 'nm_parity.toe')

NEWPROJ_REL = ('Samples', 'Setup', 'Base', 'NewProject.toe')


def _has_toe_tools(d):
    if not os.path.isdir(d):
        return False
    for tool in ('toeexpand', 'toecollapse'):
        if not (os.path.exists(os.path.join(d, tool))
                or os.path.exists(os.path.join(d, tool + '.exe'))):
            return False
    return True


def _find_newproj(roots):
    """Locate the stock NewProject.toe skeleton near a TD install (bounded search)."""
    for root in roots:
        direct = os.path.join(root, *NEWPROJ_REL)
        if os.path.exists(direct):
            return direct
        # macOS bundles keep Samples under Contents/Resources/tfs; installs keep it
        # beside bin/. Walk up a few levels from the bin dir without scanning the tree.
        base = root
        for _ in range(4):
            base = os.path.dirname(base)
            cand = os.path.join(base, *NEWPROJ_REL)
            if os.path.exists(cand):
                return cand
            cand = os.path.join(base, 'Resources', 'tfs', *NEWPROJ_REL)
            if os.path.exists(cand):
                return cand
    return None


def discover_td():
    """Return (bin_dir, newproj_toe) for the local TouchDesigner install.

    Accepts TD_APP as an .app bundle, an install root, or the bin dir itself.
    Candidates cover the macOS bundle layout plus Windows/Linux install roots.
    """
    env = os.environ.get('TD_APP')
    roots = []
    if env:
        if env.endswith('.app'):
            roots.append(os.path.join(env, 'Contents'))
        elif os.path.isfile(env):
            roots.append(os.path.dirname(os.path.abspath(env)))   # the TD binary itself
        else:
            roots.append(env)
            for sub in ('bin', os.path.join('Contents', 'MacOS')):
                b = os.path.join(env, sub)
                if _has_toe_tools(b):
                    roots.append(b)
    roots += [os.path.join(p, 'Contents') for p in sorted(glob.glob('/Applications/TouchDesigner*.app'))]
    roots += [os.path.join(p, 'Contents') for p in sorted(glob.glob(os.path.expanduser('~/Applications/TouchDesigner*.app')))]
    for pat in ('/opt/TouchDesigner*', '/opt/touchdesigner*', '/usr/local/TouchDesigner*',
                '/usr/local/touchdesigner*', os.path.expanduser('~/TouchDesigner*'),
                os.path.expanduser('~/touchdesigner*'),
                '/c/Program Files*/Derivative/TouchDesigner*',
                '/c/Program Files*/Derivative/*TouchDesigner*',
                'C:/Program Files*/Derivative/TouchDesigner*',
                'C:/Program Files*/Derivative/*TouchDesigner*'):
        roots += sorted(glob.glob(pat))
    # Each root may BE the bin dir, or hold it (install roots keep tools in bin/,
    # macOS bundle roots in Contents/MacOS).
    bins = []
    for root in roots:
        for cand in (root, os.path.join(root, 'bin'), os.path.join(root, 'Contents', 'MacOS')):
            if _has_toe_tools(cand) and cand not in bins:
                bins.append(cand)
    for b in bins:
        np = _find_newproj([b])
        if np:
            return b, np
    return None, None


TD_BIN_DIR, NEWPROJ = discover_td()
if not TD_BIN_DIR or not NEWPROJ:
    seen = []
    env = os.environ.get('TD_APP')
    if env:
        seen.append('TD_APP=%s' % env)
    for root in sorted(glob.glob('/Applications/TouchDesigner*.app')) + \
            sorted(glob.glob(os.path.expanduser('~/Applications/TouchDesigner*.app'))) + \
            sorted(glob.glob('/opt/TouchDesigner*')) + sorted(glob.glob('/opt/touchdesigner*')) + \
            sorted(glob.glob('/usr/local/TouchDesigner*')) + sorted(glob.glob('/usr/local/touchdesigner*')) + \
            sorted(glob.glob(os.path.expanduser('~/TouchDesigner*'))) + \
            sorted(glob.glob(os.path.expanduser('~/touchdesigner*'))) + \
            sorted(glob.glob('C:/Program Files*/Derivative/*TouchDesigner*')) + \
            sorted(glob.glob('/c/Program Files*/Derivative/*TouchDesigner*')):
        if os.path.isdir(root):
            seen.append(root)
    sys.exit('TouchDesigner install not found (searched: %s; set TD_APP to the install root '
             'or the bin directory containing toeexpand/toecollapse and NewProject.toe).'
             % ('; '.join(seen) or 'no candidate roots'))
WORK = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'nm_parity_build')

# The Execute DAT body: define onStart/onCreate, exec the render script with a namespace that
# carries the TD operator globals + __file__ (so the imported runtime resolves them and the
# script's own __file__-based repo lookup works), then quit.
CALLBACK = '''# noisemaker parity bootstrap — renders Tier-1 candidates on load, then quits.
def _run():
    p = %r
    g = {'__file__': p, '__name__': '__nm_parity__'}
    for _n in ('op','ops','project','parent','me','root','var','mod','debug','tdu',
               'baseCOMP','glslTOP','glslmultiTOP','nullTOP','textDAT','feedbackTOP'):
        try:
            g[_n] = eval(_n)
        except Exception:
            pass
    try:
        exec(compile(open(p).read(), p, 'exec'), g)
    finally:
        try:
            project.quit(force=True)
        except Exception:
            pass

def onStart():
    _run()

def onCreate():
    _run()
''' % RENDER


def _tool(name):
    for cand in (os.path.join(TD_BIN_DIR, name), os.path.join(TD_BIN_DIR, name + '.exe')):
        if os.path.exists(cand):
            return cand
    return name


def _toe_text(code):
    """Frame DAT text as TD stores it: '2\\n*' + 6 BE int32 [1,1,1,1,2,len] + utf8 body."""
    b = code.encode('utf-8')
    return b'2\n*' + struct.pack('>6i', 1, 1, 1, 1, 2, len(b)) + b


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    shutil.copy(NEWPROJ, os.path.join(WORK, 'boot.toe'))
    # NOTE: toeexpand/toecollapse exit non-zero even on success — verify by output files.
    subprocess.run([_tool('toeexpand'), 'boot.toe'], cwd=WORK,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dd = os.path.join(WORK, 'boot.toe.dir')
    if not os.path.isdir(dd):
        sys.exit('toeexpand failed')

    proj = os.path.join(dd, 'project1')
    os.makedirs(proj, exist_ok=True)
    name = 'nm_parity_exec'
    with open(os.path.join(proj, name + '.n'), 'w') as f:
        f.write('DAT:execute\ntile 200 200 130 90\nflags =  viewer 1 parlanguage 0\n'
                'color 0.55 0.55 0.55 \nview 8 0 1 1 1 0 0 0 0 1 1\nend\n')
    with open(os.path.join(proj, name + '.parm'), 'w') as f:
        f.write('?\nstart 0 on\ncreate 0 on\nlanguage 0 python\n?\n')   # enable onStart + onCreate
    with open(os.path.join(proj, name + '.text'), 'wb') as f:
        f.write(_toe_text(CALLBACK))

    # register the three child files in the .toc (authoritative recursive file list)
    toc = os.path.join(WORK, 'boot.toe.toc')
    lines = open(toc).read().splitlines()
    entries = ['project1/%s.%s' % (name, ext) for ext in ('n', 'parm', 'text')]
    out, done = [], False
    for ln in lines:
        out.append(ln)
        if ln.strip() in ('project1.panel', 'project1.parm') and not done:
            out.extend(entries); done = True
    open(toc, 'w').write('\n'.join(out) + '\n')

    if os.path.exists(OUT_TOE):
        os.remove(OUT_TOE)
    subprocess.run([_tool('toecollapse'), 'boot.toe'], cwd=WORK,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    built = os.path.join(WORK, 'boot.toe')
    if not os.path.exists(built):
        sys.exit('toecollapse failed')
    shutil.copy(built, OUT_TOE)
    print('wrote %s (%d bytes)' % (OUT_TOE, os.path.getsize(OUT_TOE)))


if __name__ == '__main__':
    main()
