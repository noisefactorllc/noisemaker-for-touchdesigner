#!/usr/bin/env python3
"""check_lex.py — gate the Python lexer port against the reference lexer's token stream.

For each DSL file: dump the reference tokens via `tools/dump-tokens.mjs` (golden) and lex
the same source with `noisemaker.compiler.lang.lexer.lex` (port), then compare token-by-token
and report the first divergence. Default corpus = parity/corpus + parity/programs.

Usage:
  parity/compiler/check_lex.py                 # all corpus + programs
  parity/compiler/check_lex.py path/to.dsl ... # specific files
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'td'))

from noisemaker.compiler.lang.lexer import lex  # noqa: E402

DUMP = os.path.join(REPO, 'tools', 'dump-tokens.mjs')


def ref_tokens(path):
    r = subprocess.run(['node', DUMP, path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or 'node failed').strip().splitlines()[-1]
    return json.loads(r.stdout), None


def my_tokens(path):
    with open(path) as f:
        src = f.read()
    return [{'type': t.type, 'lexeme': t.lexeme, 'line': t.line, 'col': t.col} for t in lex(src)]


def compare(path):
    ref, err = ref_tokens(path)
    if ref is None:
        return 'REFERR', err
    try:
        got = my_tokens(path)
    except Exception as e:
        return 'MYERR', repr(e)
    if got == ref:
        return 'PASS', '%d tokens' % len(ref)
    for k in range(max(len(ref), len(got))):
        a = ref[k] if k < len(ref) else None
        b = got[k] if k < len(got) else None
        if a != b:
            return 'DIFF', 'tok#%d  ref=%s  mine=%s' % (k, a, b)
    return 'DIFF', 'length ref=%d mine=%d' % (len(ref), len(got))


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
    print('=== lexer parity: %d/%d PASS ===' % (npass, len(files)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
