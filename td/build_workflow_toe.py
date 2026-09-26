#!/usr/bin/env python3
"""build_workflow_toe.py — author the bootstrap `td/nm_workflow.toe` for GAP-002.

Same transplant mechanism as build_parity_toe.py (stock NewProject.toe skeleton via
toeexpand/toecollapse), but the Execute DAT execs `td/workflow_probe.py`: the GAP-002
installed developer workflow probe (isolated Base COMP, documented NMRenderer example,
TOP connect/resize, invalid-DSL recovery, save, reopen, cleanup) instead of the parity
renderer. A saved project from the build phase is re-opened for the reopen phase.

Run with stock python3 (no TD needed to BUILD the .toe; TD is needed to RUN it):
    python3 td/build_workflow_toe.py
"""
import os
import shutil
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_DIR = os.path.join(REPO, 'td')
PROBE = os.path.join(TD_DIR, 'workflow_probe.py')
OUT_TOE = os.path.join(TD_DIR, 'nm_workflow.toe')
WORK = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'nm_workflow_build')

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
    for root in roots:
        direct = os.path.join(root, *NEWPROJ_REL)
        if os.path.exists(direct):
            return direct
        base = root
        for _ in range(4):
            base = os.path.dirname(base)
            for rel in (NEWPROJ_REL, ('Contents', 'Resources', 'tfs') + NEWPROJ_REL,
                        ('Resources', 'tfs') + NEWPROJ_REL):
                cand = os.path.join(base, *rel)
                if os.path.exists(cand):
                    return cand
    return None


def _discover_td():
    """Return the bin dir containing toeexpand/toecollapse (TD_APP, .app bundles, install roots)."""
    env = os.environ.get('TD_APP')
    roots = []
    if env:
        if env.endswith('.app'):
            roots.append(os.path.join(env, 'Contents', 'MacOS'))
        elif os.path.isfile(env):
            roots.append(os.path.dirname(os.path.abspath(env)))
        else:
            roots.append(env)
            for sub in ('bin', os.path.join('Contents', 'MacOS')):
                b = os.path.join(env, sub)
                if _has_toe_tools(b):
                    roots.append(b)
    import glob
    for app in sorted(glob.glob('/Applications/TouchDesigner*.app')) + \
            sorted(glob.glob(os.path.expanduser('~/Applications/TouchDesigner*.app'))):
        roots.append(os.path.join(app, 'Contents', 'MacOS'))
    for pat in ('/opt/TouchDesigner*', '/opt/touchdesigner*', '/usr/local/TouchDesigner*',
                '/usr/local/touchdesigner*', os.path.expanduser('~/TouchDesigner*'),
                os.path.expanduser('~/touchdesigner*'),
                '/c/Program Files*/Derivative/TouchDesigner*', 'C:/Program Files*/Derivative/TouchDesigner*',
                '/c/Program Files*/TouchDesigner*', 'C:/Program Files*/TouchDesigner*'):
        roots += sorted(glob.glob(pat))
    for root in roots:
        for cand in (root, os.path.join(root, 'bin'), os.path.join(root, 'Contents', 'MacOS')):
            if _has_toe_tools(cand):
                np = _find_newproj([cand])
                if np:
                    return cand, np
    return None, None


def _tool(name):
    for cand in (os.path.join(TD_BIN_DIR, name), os.path.join(TD_BIN_DIR, name + '.exe')):
        if os.path.exists(cand):
            return cand
    return name


def _toe_text(code):
    """Frame DAT text as TD stores it: '2\\n*' + 6 BE int32 [1,1,1,1,2,len] + utf8 body."""
    b = code.encode('utf-8')
    return b'2\n*' + struct.pack('>6i', 1, 1, 1, 1, 2, len(b)) + b


CALLBACK = '''# noisemaker GAP-002 workflow bootstrap — runs the installed-workflow probe on load, then quits.
def _run():
    p = %r
    g = {'__file__': p, '__name__': '__nm_workflow__'}
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
''' % PROBE


def main():
    global TD_BIN_DIR
    TD_BIN_DIR, NEWPROJ = _discover_td()
    if not TD_BIN_DIR or not NEWPROJ:
        sys.exit('TouchDesigner install not found (set TD_APP to the install root or the '
                 'bin directory containing toeexpand/toecollapse and NewProject.toe).')
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
    name = 'nm_workflow_exec'
    with open(os.path.join(proj, name + '.n'), 'w') as f:
        f.write('DAT:execute\ntile 200 200 130 90\nflags =  viewer 1 parlanguage 0\n'
                'color 0.55 0.55 0.55 \nview 8 0 1 1 1 0 0 0 0 1 1\nend\n')
    with open(os.path.join(proj, name + '.parm'), 'w') as f:
        f.write('?\nstart 0 on\ncreate 0 on\nlanguage 0 python\n?\n')   # onStart + onCreate
    with open(os.path.join(proj, name + '.text'), 'wb') as f:
        f.write(_toe_text(CALLBACK))

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
