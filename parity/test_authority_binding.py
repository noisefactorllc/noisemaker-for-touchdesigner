import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('ledger_authority', Path(__file__).with_name('write-ledger.py'))
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class AuthorityBindingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/test').write_text('NM_REFERENCE_SHA_PINNED="' + 'a' * 40 + '"\n')

    def bind(self, observed, requested=None, dirty=''):
        env = {'NM_REFERENCE_ROOT': str(self.root / 'reference')}
        if requested is not None:
            env['NM_REFERENCE_SHA'] = requested
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ledger.subprocess, 'check_output', side_effect=[observed + '\n', dirty]), \
                mock.patch.object(ledger.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'c' * 40 + '\n', '')):
            return ledger.ledger_binding(self.root)

    def test_observed_current_authority_is_recorded(self):
        self.assertEqual(self.bind('a' * 40), {'source': 'c' * 40, 'pin': 'a' * 40, 'authority': {'kind': 'clean-git', 'commit': 'a' * 40}})

    def test_verified_override_is_truthfully_recorded(self):
        self.assertEqual(self.bind('b' * 40, 'b' * 40)['pin'], 'b' * 40)

    def test_wrong_observed_authority_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'authority'):
            self.bind('b' * 40)

    def test_dirty_authority_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'clean'):
            self.bind('a' * 40, dirty=' M shader.glsl\n')

    def test_malformed_override_is_rejected(self):
        with self.assertRaises(ValueError):
            self.bind('a' * 40, requested='main')

    def test_missing_reference_cannot_create_binding(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            ledger.ledger_binding(self.root)

    def test_hero_protocol_preserves_historical_and_current_contracts(self):
        old = ledger.PRESENT_HERO_PROTOCOL
        current = '06070900e506b6c8ff6eb7b12d33e6c1bf285108'
        with mock.patch.dict(os.environ, {'NM_REFERENCE_SHA': old['reference_sha']}, clear=True):
            self.assertEqual(ledger.hero_protocol(self.root), old)
        with mock.patch.dict(os.environ, {'NM_REFERENCE_SHA': current}, clear=True):
            self.assertEqual(ledger.hero_protocol(self.root), dict(old, reference_sha=current))
        with mock.patch.dict(os.environ, {'NM_REFERENCE_SHA': 'b' * 40}, clear=True):
            with self.assertRaisesRegex(ValueError, 'hero authority'):
                ledger.hero_protocol(self.root)
