#!/usr/bin/env python3
"""materialize_kit.py -- reproduce the served Noisedeck TouchDesigner export kit.

Downloads https://kits.noisedeck.app/touchdesigner/0/deployment-meta.json and
kit.json, then every listed file, verifying each file's SHA-256 and byte count
against the served inventory. Writes a machine-readable summary next to the
target so the download step of a kit qualification is reproducible.

With ``--git-source SHA`` the kit is instead reproduced from this repository at
that commit (the same path mappings the served inventory uses), which is how an
older kit version is materialized for an upgrade leg when the deployment only
serves the latest version. The upstream MIT notice is vendored from the
reference engine checkout (NM_REFERENCE_ROOT); it is not stored in this
repository.

The served inventory is the platform-neutral export minus the per-export user
content: Noisedeck injects ``program.dsl`` (the user's DSL), renders
``README.md`` from the served ``README.template.md`` (placeholders
``{{NM_PROGRAM_NAME}}``, ``{{NM_ENGINE_VERSION}}``, ``{{NM_EFFECT_LIST}}``), and
writes ``noisedeck-export.json``. This tool reproduces those three the same way
a Noisedeck export would, from explicit values, and records their hashes in the
summary so they are never confused with served bytes.

Usage:
    python3 tools/materialize_kit.py DEST \
        [--program PATH] [--program-name NAME] [--engine-version VER] \
        [--effects ID,ID,...] [--git-source SHA] [--reference-root DIR]
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

BASE = 'https://kits.noisedeck.app/touchdesigner/0'


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def git_bytes(sha, repo_path):
    """Bytes of repo_path at commit sha (git show)."""
    out = subprocess.run(['git', 'show', '%s:%s' % (sha, repo_path)],
                         capture_output=True, check=True)
    return out.stdout


def git_ls(sha, repo_path):
    """All blob paths under repo_path at commit sha."""
    out = subprocess.run(['git', 'ls-tree', '-r', '--name-only', sha, '--', repo_path],
                         capture_output=True, check=True, text=True)
    return [ln for ln in out.stdout.splitlines() if ln]


def build_git_inventory(sha, reference_root):
    """Reproduce the export-kit inventory from this repository at git commit sha.

    Same path mappings as the served inventory (engine/noisemaker/* ->
    td/noisemaker/*, shaders/* -> td/noisemaker/shaders/*, LICENSES/
    noisemaker-for-touchdesigner-LICENSE.txt -> LICENSE, README.template.md/
    integrate.py -> export-kit/kit/); compat.json ids are the namespace/func
    effect ids under td/noisemaker/effects at that commit minus the
    kit.config.json excludeNames. The upstream MIT notice is vendored from the
    reference engine checkout (it is not stored in this repository).

    Returns (files, effect_ids) where files maps export path -> source spec:
    a repo path ('git:<path>') or '@reference:<abs path>'.
    """
    files = {}
    for p in git_ls(sha, 'td/noisemaker'):
        rel = os.path.relpath(p, 'td/noisemaker')
        files[os.path.join('engine', 'noisemaker', rel)] = 'git:' + p
    for p in git_ls(sha, 'td/noisemaker/shaders'):
        rel = os.path.relpath(p, 'td/noisemaker/shaders')
        files[os.path.join('shaders', rel)] = 'git:' + p
    files['LICENSES/noisemaker-for-touchdesigner-LICENSE.txt'] = 'git:LICENSE'
    files['README.template.md'] = 'git:export-kit/kit/README.template.md'
    files['integrate.py'] = 'git:export-kit/kit/integrate.py'
    config = json.loads(git_bytes(sha, 'export-kit/kit.config.json'))
    exclude = set(config.get('compat', {}).get('excludeNames', []))
    ids = []
    for p in git_ls(sha, 'td/noisemaker/effects'):
        if not p.endswith('.json'):
            continue
        rel = os.path.relpath(p, 'td/noisemaker/effects')
        ns, _, fn = rel.replace('.json', '').replace(os.sep, '/').rpartition('/')
        ident = '%s/%s' % (ns, fn)
        if ident not in exclude:
            ids.append(ident)
    notice = os.path.join(reference_root, 'LICENSE')
    if not os.path.isfile(notice):
        raise SystemExit('NM_REFERENCE_ROOT has no LICENSE (upstream MIT notice)')
    files['LICENSES/noisemaker-MIT.txt'] = '@reference:' + notice
    return files, sorted(ids)


def fetch_bytes(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def render_readme(template, name, engine_version, effects):
    text = template
    for key, value in (('NM_PROGRAM_NAME', name),
                       ('NM_ENGINE_VERSION', engine_version),
                       ('NM_EFFECT_LIST', effects)):
        text = text.replace('{{%s}}' % key, value)
    if '{{' in text:
        raise SystemExit('README template still has unresolved placeholders')
    return text


def resolve_source(spec, sha):
    if spec.startswith('@reference:'):
        return pathlib.Path(spec[len('@reference:'):]).read_bytes()
    return git_bytes(sha, spec[len('git:'):])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dest')
    ap.add_argument('--program', required=True, help='DSL file to inject as program.dsl')
    ap.add_argument('--program-name', default='Noisemaker export')
    ap.add_argument('--engine-version', required=True)
    ap.add_argument('--effects', default='')
    ap.add_argument('--git-source', default=None,
                    help='reproduce the kit from this repository at this commit instead of the served deployment')
    ap.add_argument('--reference-root', default=os.environ.get('NM_REFERENCE_ROOT'),
                    help='reference engine checkout (for the vendored upstream MIT notice in --git-source mode)')
    args = ap.parse_args()

    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    served, mismatches, skipped = [], [], []
    if args.git_source:
        if not args.reference_root:
            ap.error('--git-source requires --reference-root (or NM_REFERENCE_ROOT)')
        meta = {'git_hash': args.git_source, 'date': None, 'version': 'source-history'}
        entries, effect_ids = build_git_inventory(args.git_source, args.reference_root)
        compat = {'mode': 'list', 'effects': effect_ids}
        inventory = {path: None for path in entries}
        inventory['compat.json'] = None
        kit_version = 'source-history:%s' % args.git_source
        for rel in inventory:
            # Paths are constructed here, but validate anyway.
            p = pathlib.PurePosixPath(rel)
            if p.is_absolute() or '..' in p.parts or not p.parts:
                skipped.append({'path': rel, 'error': 'unsafe inventory path refused'})
                continue
            try:
                data = compat_json_bytes(compat) if rel == 'compat.json' \
                    else resolve_source(entries[rel], args.git_source)
            except Exception as err:  # noqa: BLE001
                skipped.append({'path': rel, 'error': str(err)})
                continue
            write_verified(dest, rel, data)
            served.append({'path': rel, 'bytes': len(data), 'sha256': sha256(data),
                           'source': ('compat:synthesized' if rel == 'compat.json'
                                      else entries[rel])})
    else:
        meta = fetch_json(BASE + '/deployment-meta.json')
        kit = fetch_json(BASE + '/kit.json')
        kit_version = kit['version']
        for entry in kit['files']:
            path = dest / entry['path']
            rel = entry['path']
            # Paths come from the remote inventory; never let one escape the destination.
            p = pathlib.PurePosixPath(rel)
            if p.is_absolute() or '..' in p.parts or not p.parts:
                skipped.append({'path': rel, 'error': 'unsafe inventory path refused'})
                continue
            try:
                data = fetch_bytes(BASE + '/' + urllib.request.quote(rel))
            except Exception as err:  # noqa: BLE001
                skipped.append({'path': rel, 'error': str(err)})
                continue
            got = sha256(data)
            row = {'path': rel, 'bytes': len(data), 'sha256': got,
                   'served_bytes': entry['bytes'], 'served_sha256': entry['sha256']}
            if got != entry['sha256'] or len(data) != entry['bytes']:
                mismatches.append(row)
            row['match'] = row['sha256'] == entry['sha256'] and len(data) == entry['bytes']
            served.append(row)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    # Per-export user content, rendered as a Noisedeck export would (recorded, not served).
    injected = {}
    program = pathlib.Path(args.program).read_text()
    (dest / 'program.dsl').write_text(program)
    injected['program.dsl'] = {'sha256': sha256(program.encode()), 'bytes': len(program)}
    readme_md = render_readme((dest / 'README.template.md').read_text(),
                              args.program_name, args.engine_version, args.effects)
    (dest / 'README.md').write_text(readme_md)
    injected['README.md'] = {'sha256': sha256(readme_md.encode()), 'bytes': len(readme_md),
                             'rendered_from': 'README.template.md'}
    export_meta = {
        'program': args.program_name,
        'exported_at': (datetime.datetime.fromtimestamp(
            meta['date'], datetime.timezone.utc).isoformat()
            if meta.get('date') is not None else 'not-served'),
        'engine': args.engine_version,
        'source': meta['git_hash'],
    }
    blob = json.dumps(export_meta, indent=2) + '\n'
    (dest / 'noisedeck-export.json').write_text(blob)
    injected['noisedeck-export.json'] = {'sha256': sha256(blob.encode()), 'bytes': len(blob)}

    summary = {
        'base': BASE,
        'mode': 'git-source' if args.git_source else 'served',
        'git_source': args.git_source,
        'deployment_meta': meta,
        'kit_version': kit_version,
        'inventory_count': len(inventory) if args.git_source else len(kit['files']),
        'materialized': len(served),
        'matches': (len(served) if args.git_source
                    else sum(1 for r in served if r['match'])),
        'mismatches': mismatches,
        'skipped': skipped,
        'injected_not_served': injected,
        'dest': str(dest),
    }
    out = dest / 'materialize-summary.json'
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in
                      ('mode', 'kit_version', 'inventory_count', 'materialized',
                       'matches', 'mismatches', 'skipped')}))
    if mismatches or skipped:
        sys.exit(1)


def write_verified(dest, rel, data):
    path = dest / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def compat_json_bytes(compat):
    return (json.dumps(compat, indent=2) + '\n').encode()


if __name__ == '__main__':
    main()
