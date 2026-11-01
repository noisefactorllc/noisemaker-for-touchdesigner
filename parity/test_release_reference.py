import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_reference_archive

ROOT = Path(__file__).resolve().parents[1]


class ReleaseReferenceTests(unittest.TestCase):
    setUp = test_reference_archive.ReferenceArchiveTests.setUp
    verify = test_reference_archive.ReferenceArchiveTests.verify

    def test_materializes_authenticated_regular_projection(self):
        module = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
            'archive_release', ROOT / 'parity/reference_archive.py'))
        module.__spec__.loader.exec_module(module)
        destination = self.root.parent / 'materialized'
        destination.mkdir()
        result = module.verify_archive(destination, self.store, self.commit, materialize=True)
        self.assertEqual(result, self.verify())
        self.assertFalse(any(p.is_symlink() for p in destination.rglob('*')))
        self.assertEqual((destination / 'shaders/share/asset.bin').read_bytes(), b'payload\n')
        self.assertEqual((destination / 'run').stat().st_mode & 0o777, 0o755)
        with self.assertRaisesRegex(ValueError, 'empty'):
            module.verify_archive(destination, self.store, self.commit, materialize=True)

    def test_materialization_rejects_bad_objects_before_writing(self):
        module = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
            'archive_release', ROOT / 'parity/reference_archive.py'))
        module.__spec__.loader.exec_module(module)
        destination = self.root.parent / 'rejected'
        destination.mkdir()
        with self.assertRaises(ValueError):
            module.verify_archive(destination, self.store, 'f' * 40, materialize=True)
        self.assertEqual(list(destination.iterdir()), [])

    def test_materialization_rejects_forged_blob_before_writing(self):
        from unittest import mock
        module = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
            'archive_release', ROOT / 'parity/reference_archive.py'))
        module.__spec__.loader.exec_module(module)
        destination = self.root.parent / 'forged'
        destination.mkdir()
        original = subprocess.check_output
        def read(args, **kwargs):
            result = original(args, **kwargs)
            if args[-2:] == ['cat-file', '--batch'] and b'payload\n' in result:
                return result.replace(b'payload\n', b'forged!\n')
            return result
        with mock.patch.object(subprocess, 'check_output', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'blob'):
                module.verify_archive(destination, self.store, self.commit, materialize=True)
        self.assertEqual(list(destination.iterdir()), [])

    def test_release_uses_external_regular_dependencies(self):
        workflow = (ROOT / '.github/workflows/export-kit.yml').read_text()
        self.assertIn('reference_archive.py --materialize', workflow)
        self.assertIn('--no-bin-links', workflow)
        self.assertNotIn('git clone', workflow)
        self.assertNotIn('npx playwright', workflow)
        self.assertIn('NM_REFERENCE_OBJECT_STORE=', workflow)
        self.assertIn('NM_REFERENCE_DEPENDENCIES=', workflow)

    def test_loader_is_scoped_to_render_process(self):
        workflow = (ROOT / '.github/workflows/export-kit.yml').read_text()
        prepare = workflow.split('      - name: Check out the pinned reference', 1)[1].split('      - name: Run full rendered parity', 1)[0]
        self.assertNotIn('NODE_OPTIONS', prepare)
        render = workflow.split('      - name: Run full rendered parity', 1)[1].split('  dispatch:', 1)[0]
        self.assertIn('NODE_OPTIONS=', render)
        self.assertIn('parity/.venv/bin/python scripts/parity-summary', render)
        command = next(line.split('run: ', 1)[1] for line in render.splitlines() if 'run: ' in line)
        command = command.replace('parity/.venv/bin/python scripts/parity-summary', 'probe')
        environment = {key: value for key, value in os.environ.items() if key != 'NODE_OPTIONS'}
        environment['GITHUB_WORKSPACE'] = str(ROOT)
        script = ('set -eu\nprobe() { test "$NODE_OPTIONS" = "--import $GITHUB_WORKSPACE/tools/reference-dependencies.mjs"; '
                  "bash -c 'test -n \"$NODE_OPTIONS\"'; }\n" + command + '\n'
                  'test -z "${NODE_OPTIONS+x}"\n')
        result = subprocess.run(['bash', '-c', script], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_external_playwright_resolves_import_and_require(self):
        with tempfile.TemporaryDirectory() as directory:
            deps = Path(directory)
            package = deps / 'node_modules/playwright'
            package.mkdir(parents=True)
            (package / 'index.js').write_text('module.exports = { marker: "external" };\n')
            (package / 'index.mjs').write_text('export const marker = "external";\n')
            result = subprocess.run(['node', '--import', str(ROOT / 'tools/reference-dependencies.mjs'),
                '--input-type=module', '-e', 'import {marker} from "playwright"; '
                'import {createRequire} from "node:module"; '
                'const require=createRequire(import.meta.url); '
                'const resolved=require.resolve("playwright",{paths:[process.cwd()+"/vendor/shade-mcp/harness"]}); '
                'if(marker!=="external" || require(resolved).marker!==marker) process.exit(1);'],
                cwd=ROOT, env={**os.environ, 'NM_REFERENCE_DEPENDENCIES': str(deps)},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
