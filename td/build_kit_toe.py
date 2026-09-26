#!/usr/bin/env python3
"""build_kit_toe.py -- author the `kit.toe` bootstrap inside a Noisedeck export kit.

Same transplant mechanism as build_workflow_toe.py / build_parity_toe.py (stock
NewProject.toe skeleton via toeexpand/toecollapse). The resulting kit.toe lives
BESIDE program.dsl in the unzipped export, exactly as the kit README's install
steps describe, and carries two Execute DATs:

  integrate1  -- the kit's own integrate.py (Start toggle enabled): the
                 documented installation build, which runs onStart on load and
                 wires a sibling `out` Null TOP when found.
  kit_probe1  -- the GAP-003 qualification probe (td/kit_probe.py), deferred
                 past load, which verifies the install, renders, records a
                 report under parity/out/kit-qual/, and quits.

Run on a host that has TouchDesigner's toeexpand/toecollapse (TD_APP set):

    python3 td/build_kit_toe.py EXPORT_DIR
"""
import os
import shutil
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD_DIR = os.path.join(REPO, 'td')
PROBE = os.path.join(TD_DIR, 'kit_probe.py')

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


PROBE_CALLBACK = '''# noisemaker GAP-003 kit qualification probe — deferred past load, then quits.
def _run():
    p = %r
    g = {'__file__': p, '__name__': '__nm_kit_probe__'}
    for _n in ('op','ops','project','parent','me','root','var','mod','debug','tdu',
               'baseCOMP','glslTOP','glslmultiTOP','nullTOP','textDAT','feedbackTOP',
               'app','sys','os'):
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
    run('_run()', delayFrames=180, fromOP=me)

def onCreate():
    pass
''' % PROBE


def main():
    global TD_BIN_DIR
    if len(sys.argv) != 2:
        sys.exit('usage: build_kit_toe.py EXPORT_DIR (the unzipped export holding '
                 'program.dsl and integrate.py)')
    export = os.path.abspath(sys.argv[1])
    integrate_py = os.path.join(export, 'integrate.py')
    if not os.path.exists(integrate_py):
        sys.exit('no integrate.py in %s' % export)
    TD_BIN_DIR, NEWPROJ = _discover_td()
    if not TD_BIN_DIR or not NEWPROJ:
        sys.exit('TouchDesigner install not found (set TD_APP to the install root or the '
                 'bin directory containing toeexpand/toecollapse and NewProject.toe).')
    work = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'nm_kit_toe_build')
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(NEWPROJ, os.path.join(work, 'boot.toe'))
    # NOTE: toeexpand/toecollapse exit non-zero even on success — verify by output files.
    subprocess.run([_tool('toeexpand'), 'boot.toe'], cwd=work,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dd = os.path.join(work, 'boot.toe.dir')
    if not os.path.isdir(dd):
        sys.exit('toeexpand failed')

    proj = os.path.join(dd, 'project1')
    os.makedirs(proj, exist_ok=True)

    # integrate1 — the kit's own script, Start toggle enabled (README install step 6).
    name = 'integrate1'
    with open(os.path.join(proj, name + '.n'), 'w') as f:
        f.write('DAT:execute\ntile 0 0 130 90\nflags =  viewer 1 parlanguage 0\n'
                'color 0.55 0.55 0.55 \nview 8 0 1 1 1 0 0 0 0 1 1\nend\n')
    with open(os.path.join(proj, name + '.parm'), 'w') as f:
        f.write('?\nstart 0 on\ncreate 0 off\nlanguage 0 python\n?\n')
    with open(os.path.join(proj, name + '.text'), 'wb') as f:
        f.write(_toe_text(open(integrate_py).read()))

    # kit_probe1 — qualification probe, deferred past load.
    name = 'kit_probe1'
    with open(os.path.join(proj, name + '.n'), 'w') as f:
        f.write('DAT:execute\ntile 200 200 130 90\nflags =  viewer 1 parlanguage 0\n'
                'color 0.55 0.55 0.55 \nview 8 0 1 1 1 0 0 0 0 1 1\nend\n')
    with open(os.path.join(proj, name + '.parm'), 'w') as f:
        f.write('?\nstart 0 on\ncreate 0 off\nlanguage 0 python\n?\n')
    with open(os.path.join(proj, name + '.text'), 'wb') as f:
        f.write(_toe_text(PROBE_CALLBACK))

    toc = os.path.join(work, 'boot.toe.toc')
    lines = open(toc).read().splitlines()
    entries = ['project1/%s.%s' % (n, ext) for n in ('integrate1', 'kit_probe1')
               for ext in ('n', 'parm', 'text')]
    out, done = [], False
    for ln in lines:
        out.append(ln)
        if ln.strip() in ('project1.panel', 'project1.parm') and not done:
            out.extend(entries)
            done = True
    open(toc, 'w').write('\n'.join(out) + '\n')

    out_toe = os.path.join(export, 'kit.toe')
    if os.path.exists(out_toe):
        os.remove(out_toe)
    subprocess.run([_tool('toecollapse'), 'boot.toe'], cwd=work,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    built = os.path.join(work, 'boot.toe')
    if not os.path.exists(built):
        sys.exit('toecollapse failed')
    shutil.copy(built, out_toe)
    print('wrote %s (%d bytes)' % (out_toe, os.path.getsize(out_toe)))


if __name__ == '__main__':
    main()
