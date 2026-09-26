"""Contract tests for tools/materialize_kit.py (--git-source kit mode)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'tools'))
import materialize_kit  # noqa: E402

# The source the served kit 0.1.20 recorded (docs/COMPLETION_GAPS.md).
OLD_SOURCE = '66426bc41c2b85940322ae843ba04f41b7905ce4'


class TestGitSourceCompatIds(unittest.TestCase):
    def test_excludes_declared_names(self):
        with tempfile.TemporaryDirectory() as ref:
            with open(os.path.join(ref, 'LICENSE'), 'wb') as f:
                f.write(b'MIT notice')
            files, ids = materialize_kit.build_git_inventory(OLD_SOURCE, ref)
        # The declared exclusions are bare func names; the synthesized compat id
        # list must omit them exactly as the served kit does (207 ids).
        for name in ('media', 'scope', 'spectrum'):
            self.assertNotIn('synth/%s' % name, ids)
            self.assertNotIn(name, ids)
        self.assertNotIn('media', ids)
        self.assertEqual(len(ids), 207)
        self.assertEqual(len(set(ids)), len(ids))
        # Path mappings present.
        for path in ('engine/noisemaker/runtime/nm_renderer.py',
                     'shaders/effects/synth/solid/solid.frag',
                     'LICENSES/noisemaker-MIT.txt',
                     'LICENSES/noisemaker-for-touchdesigner-LICENSE.txt',
                     'README.template.md', 'integrate.py', 'compat.json'):
            self.assertIn(path, files)
        # Served-kit parity for the mapping: engine carries its own shaders copy.
        engine_shaders = [p for p in files if p.startswith('engine/noisemaker/shaders/')]
        top_shaders = [p for p in files if p.startswith('shaders/')]
        self.assertEqual(len(engine_shaders), 301)
        self.assertEqual(len(top_shaders), 301)
        # compat.json synthesizes in the served shape.
        compat = json.loads(materialize_kit.compat_json_bytes({'mode': 'list', 'effects': ids}))
        self.assertEqual(compat['mode'], 'list')


if __name__ == '__main__':
    unittest.main()
