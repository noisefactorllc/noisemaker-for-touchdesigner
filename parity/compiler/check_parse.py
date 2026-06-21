#!/usr/bin/env python3
"""check_parse.py — gate the Python parser port against the reference parser's AST.

For each DSL file: dump the reference AST via `tools/dump-ast.mjs` (golden) and parse the same
source with `noisemaker.compiler.lang` (port), then deep-compare structurally and report the
JSON path of the first divergence. Structural (not textual) compare: numbers are matched by
value so JS `5` == Python `5.0`. Default corpus = parity/corpus + parity/programs.

Usage:
  parity/compiler/check_parse.py                 # all corpus + programs
  parity/compiler/check_parse.py path/to.dsl ... # specific files
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'td'))

from noisemaker.compiler.lang.lexer import lex                       # noqa: E402
from noisemaker.compiler.lang.parser import parse                    # noqa: E402
from noisemaker.compiler.lang.effect_registry import EffectRegistry  # noqa: E402

DUMP = os.path.join(REPO, 'tools', 'dump-ast.mjs')


def ref_ast(path):
    r = subprocess.run(['node', DUMP, path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or 'node failed').strip().splitlines()[-1]
    return json.loads(r.stdout), None


def my_ast(path):
    with open(path) as f:
        src = f.read()
    return parse(lex(src), EffectRegistry())


def diff(a, b, path='$'):
    """First structural difference between reference `a` and port `b`, or None. Numbers compare
    by value (5 == 5.0); dict key sets must match exactly; lists by length then element."""
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
    # bool must not unify with int (True == 1 in Python); guard it
    if isinstance(a, bool) != isinstance(b, bool):
        return path, 'ref=%r mine=%r' % (a, b)
    if a == b:
        return None
    return path, 'ref=%r mine=%r' % (a, b)


def compare(path):
    ref, err = ref_ast(path)
    if ref is None:
        return 'REFERR', err
    try:
        got = my_ast(path)
    except Exception as e:
        return 'MYERR', repr(e)
    d = diff(ref, got)
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
    print('=== parser parity: %d/%d PASS ===' % (npass, len(files)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
