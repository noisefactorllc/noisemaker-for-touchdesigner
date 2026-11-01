import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('archive', Path(__file__).with_name('reference_archive.py'))


class ReferenceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.store = base / 'objects.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.store)], check=True)
        self.root = base / 'archive'
        self.root.mkdir()
        def git(*args, data=None):
            return subprocess.check_output(['git', '--git-dir=' + str(self.store), *args], input=data)
        self.git = git
        blob = git('hash-object', '-w', '--stdin', data=b'payload\n').decode().strip()
        alias = git('hash-object', '-w', '--stdin', data=b'../share').decode().strip()
        shared = git('mktree', data=f'100644 blob {blob}\tasset.bin\n'.encode()).decode().strip()
        shaders = git('mktree', data=f'120000 blob {alias}\tshare\n'.encode()).decode().strip()
        tree = git('mktree', data=f'040000 tree {shared}\tshare\n040000 tree {shaders}\tshaders\n100755 blob {blob}\trun\n'.encode()).decode().strip()
        commit = f'tree {tree}\nauthor Test <test@example.invalid> 0 +0000\ncommitter Test <test@example.invalid> 0 +0000\n\nfixture\n'.encode()
        self.commit = git('hash-object', '-t', 'commit', '-w', '--stdin', data=commit).decode().strip()
        for name in ['share/asset.bin', 'shaders/share/asset.bin', 'run']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'payload\n')
            p.chmod(0o755 if name == 'run' else 0o644)

    def verify(self, commit=None):
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        return module.verify_archive(self.root, self.store, commit or self.commit)

    def test_exact_inventory_and_projection(self):
        receipt = self.verify()
        self.assertEqual(receipt['commit'], self.commit)
        self.assertEqual(receipt['kind'], 'verified-archive')
        self.assertEqual(receipt['projection']['path'], 'shaders/share')

    def test_modified_missing_extra_and_wrong_mode_reject(self):
        for defect in ['modified', 'missing', 'extra', 'mode']:
            with self.subTest(defect=defect):
                p = self.root / 'share/asset.bin'
                if defect == 'modified': p.write_bytes(b'changed')
                if defect == 'missing': p.unlink()
                if defect == 'extra': (self.root / 'extra').write_bytes(b'x')
                if defect == 'mode': p.chmod(0o755)
                with self.assertRaises(ValueError): self.verify()
                p.write_bytes(b'payload\n'); p.chmod(0o644)
                (self.root / 'extra').unlink(missing_ok=True)

    def test_projection_tamper_rejects(self):
        (self.root / 'shaders/share/asset.bin').write_bytes(b'forged')
        with self.assertRaises(ValueError): self.verify()

    def test_wrong_commit_and_forged_inventory_reject(self):
        with self.assertRaises(ValueError): self.verify('f' * 40)
        (self.root / 'manifest.json').write_text('{"verified":true}')
        with self.assertRaises(ValueError): self.verify()

    def test_untrusted_git_config_rejects(self):
        with (self.store / 'config').open('a') as f: f.write('\n[include]\npath = /untrusted\n')
        with self.assertRaises(ValueError): self.verify()

    def test_ambient_git_identity_cannot_redirect_objects(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {'GIT_OBJECT_DIRECTORY': '/untrusted',
                                           'GIT_CONFIG_COUNT': '1',
                                           'GIT_CONFIG_KEY_0': 'include.path',
                                           'GIT_CONFIG_VALUE_0': '/untrusted'}):
            self.assertEqual(self.verify()['commit'], self.commit)

    def test_projection_omission_and_extra_reject(self):
        path = self.root / 'shaders/share/asset.bin'
        path.unlink()
        with self.assertRaises(ValueError): self.verify()
        path.write_bytes(b'payload\n'); path.chmod(0o644)
        (self.root / 'shaders/share/extra').write_bytes(b'x')
        with self.assertRaises(ValueError): self.verify()

    def test_resolved_tree_must_belong_to_authenticated_commit(self):
        from unittest import mock
        blob = self.git('hash-object', '-w', '--stdin', data=b'other').decode().strip()
        rows = self.git('ls-tree', self.commit)
        tree = self.git('mktree', data=rows + f'100644 blob {blob}\textra\n'.encode()).decode().strip()
        (self.root / 'extra').write_bytes(b'other')
        (self.root / 'extra').chmod(0o644)
        original = subprocess.check_output
        def read(args, **kwargs):
            if args[-3:] == ['rev-parse', '--verify', self.commit + '^{tree}']:
                return (tree + '\n').encode()
            if args[-4:] == ['ls-tree', '-rtz', '--full-tree', self.commit]:
                return original([*args[:-1], tree], **kwargs)
            return original(args, **kwargs)
        with mock.patch.object(subprocess, 'check_output', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'tree'):
                self.verify()

    def test_forged_alias_object_payload_is_rejected(self):
        from unittest import mock
        alias = self.git('hash-object', '-w', '--stdin', data=b'../other').decode().strip()
        shaders = self.git('mktree', data=f'120000 blob {alias}\tshare\n'.encode()).decode().strip()
        root_rows = self.git('ls-tree', self.commit).decode().splitlines()
        root_rows = [f'040000 tree {shaders}\tshaders' if row.endswith('\tshaders') else row for row in root_rows]
        tree = self.git('mktree', data=('\n'.join(root_rows) + '\n').encode()).decode().strip()
        content = f'tree {tree}\nauthor Test <test@example.invalid> 0 +0000\ncommitter Test <test@example.invalid> 0 +0000\n\nforged fixture\n'.encode()
        commit = self.git('hash-object', '-t', 'commit', '-w', '--stdin', data=content).decode().strip()
        original = subprocess.check_output
        def read(args, **kwargs):
            if args[-3:] == ['cat-file', 'blob', alias]:
                return b'../share'
            return original(args, **kwargs)
        with mock.patch.object(subprocess, 'check_output', side_effect=read):
            with self.assertRaises(ValueError): self.verify(commit)

    def test_nested_object_store_link_is_rejected(self):
        from unittest import mock
        nested = self.store / 'objects/pack/linked.pack'
        nested.write_bytes(b'not a pack')
        with mock.patch.object(Path, 'is_symlink', lambda path: path == nested):
            with self.assertRaises(ValueError): self.verify()

    def test_nested_symbolic_link_metadata_is_rejected(self):
        from unittest import mock
        with mock.patch.object(Path, 'is_symlink', lambda path: path == self.root / 'share/asset.bin'):
            with self.assertRaises(ValueError): self.verify()

    def test_symbolic_link_metadata_is_rejected(self):
        from unittest import mock
        with mock.patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaises(ValueError): self.verify()
