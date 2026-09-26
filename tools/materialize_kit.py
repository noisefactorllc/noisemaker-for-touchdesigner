#!/usr/bin/env python3
"""materialize_kit.py -- reproduce the served Noisedeck TouchDesigner export kit.

Downloads https://kits.noisedeck.app/touchdesigner/0/deployment-meta.json and
kit.json, then every listed file, verifying each file's SHA-256 and byte count
against the served inventory. Writes a machine-readable summary next to the
target so the download step of a kit qualification is reproducible.

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
        [--effects ID,ID,...]
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sys
import urllib.request

BASE = 'https://kits.noisedeck.app/touchdesigner/0'


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dest')
    ap.add_argument('--program', required=True, help='DSL file to inject as program.dsl')
    ap.add_argument('--program-name', default='Noisemaker export')
    ap.add_argument('--engine-version', required=True)
    ap.add_argument('--effects', default='')
    args = ap.parse_args()

    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    meta = fetch_json(BASE + '/deployment-meta.json')
    kit = fetch_json(BASE + '/kit.json')

    served, mismatches, skipped = [], [], []
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
        'exported_at': datetime.datetime.fromtimestamp(
            meta['date'], datetime.timezone.utc).isoformat(),
        'engine': args.engine_version,
        'source': meta['git_hash'],
    }
    blob = json.dumps(export_meta, indent=2) + '\n'
    (dest / 'noisedeck-export.json').write_text(blob)
    injected['noisedeck-export.json'] = {'sha256': sha256(blob.encode()), 'bytes': len(blob)}

    summary = {
        'base': BASE,
        'deployment_meta': meta,
        'kit_version': kit['version'],
        'inventory_count': len(kit['files']),
        'downloaded': len(served),
        'matches': sum(1 for r in served if r['match']),
        'mismatches': mismatches,
        'skipped': skipped,
        'injected_not_served': injected,
        'dest': str(dest),
    }
    out = dest / 'materialize-summary.json'
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in
                      ('kit_version', 'inventory_count', 'downloaded', 'matches',
                       'mismatches', 'skipped')}))
    if mismatches or skipped:
        sys.exit(1)


if __name__ == '__main__':
    main()
