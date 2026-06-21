#!/usr/bin/env python3
"""check_validate.py — gate the Python validator port against the reference compile() output.

For each DSL file: dump the reference `{plans,diagnostics,render,...}` via tools/dump-validated.mjs
(golden) and run lex->parse->validate (port), then deep-compare the flattened `plans` plus
`render` and `searchNamespaces`. `rawKwargs` is stripped from the reference steps (hlsl omits it;
it is round-trip metadata that does not affect the graph). Diagnostics are reporting-only (their
effect — clamps/defaults — is already baked into the plan args) and are not gated here; the graph
gate (#20) is the final authority.

Usage:
  parity/compiler/check_validate.py                 # all corpus + programs
  parity/compiler/check_validate.py path/to.dsl ... # specific files
"""
import glob
import json
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'td'))

from noisemaker.compiler.lang.lexer import lex                       # noqa: E402
from noisemaker.compiler.lang.parser import parse                    # noqa: E402
from noisemaker.compiler.lang.validator import validate              # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402

DUMP = os.path.join(REPO, 'tools', 'dump-validated.mjs')

_REG = None


def reg():
    global _REG
    if _REG is None:
        _REG = EffectRegistry.load_from_directory()
    return _REG


def strip_raw(plans):
    for p in plans:
        for s in p.get('chain', []):
            s.pop('rawKwargs', None)
    return plans


def ref_compile(path):
    r = subprocess.run(['node', DUMP, path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or 'node failed').strip().splitlines()[-1]
    return json.loads(r.stdout), None


def my_compile(path):
    with open(path) as f:
        src = f.read()
    return validate(parse(lex(src), reg()), reg())


def diff(a, b, path='$'):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            extra = sorted(set(b) - set(a))
            missing = sorted(set(a) - set(b))
            return path, 'keys missing=%s extra=%s' % (missing, extra)
        for k in a:
            d = diff(a[k], b[k], path + '.' + k)
            if d:
                return d
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return path, 'list len ref=%d mine=%d' % (len(a), len(b))
        for idx in range(len(a)):
            d = diff(a[idx], b[idx], '%s[%d]' % (path, idx))
            if d:
                return d
        return None
    if isinstance(a, bool) != isinstance(b, bool):
        return path, 'ref=%r mine=%r' % (a, b)
    if a == b:
        return None
    return path, 'ref=%r mine=%r' % (a, b)


def compare(path):
    rref, err = ref_compile(path)
    if rref is None:
        return 'REFERR', err
    try:
        got = my_compile(path)
    except Exception:
        return 'MYERR', traceback.format_exc().strip().splitlines()[-1]
    exp = {'plans': strip_raw(rref['plans']), 'render': rref.get('render'),
           'searchNamespaces': rref.get('searchNamespaces')}
    act = {'plans': got['plans'], 'render': got.get('render'),
           'searchNamespaces': got.get('searchNamespaces')}
    d = diff(exp, act)
    if d is None:
        return 'PASS', ''
    return 'DIFF', '%s  %s' % (d[0], d[1])


def main():
    files = sys.argv[1:]
    if not files:
        files = (sorted(glob.glob(os.path.join(REPO, 'parity', 'corpus', '*.dsl')))
                 + sorted(glob.glob(os.path.join(REPO, 'parity', 'programs', '*.dsl'))))
    npass = 0
    fails = []
    for f in files:
        status, info = compare(f)
        name = os.path.relpath(f, REPO)
        if status == 'PASS':
            npass += 1
        else:
            fails.append(name)
            print('%-30s %-7s %s' % (name, status, info))
    print('=== validator parity: %d/%d PASS ===' % (npass, len(files)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
