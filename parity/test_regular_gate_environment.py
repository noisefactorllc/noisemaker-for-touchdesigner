import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

class RegularGateEnvironmentTests(unittest.TestCase):
    def run_environment(self, mode):
        source = (REPO / 'scripts/test').read_text()
        block = source.split('echo "== python environment', 1)[1]
        block = block[block.index('\n') + 1:block.index('VPY="$VENV/bin/python"')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = r'''set -euo pipefail
VENV="$ROOT/venv"; LOGS="$ROOT/logs"; NUMPY_VERSION=2.4.6; PYTHON=mock_python
mkdir -p "$LOGS"
fail() { echo "$*" >&2; exit 1; }
mock_python() {
  [[ "$1 $2" == '-m venv' ]] || return 91
  [[ " $* " == *' --copies '* ]] || return 92
  [[ -d "$VENV/lib64" && ! -L "$VENV/lib64" ]] || return 93
  printf '%s\n' "$*" >> "$ROOT/calls"
  if [[ "$MODE" == unavailable ]]; then return 94; fi
  if [[ "$MODE" == fallback && " $* " != *' --without-pip '* ]]; then return 95; fi
  mkdir -p "$VENV/bin"
  printf '#!/bin/sh\nexit 0\n' > "$VENV/bin/python"
  chmod +x "$VENV/bin/python"
}
uv() {
  printf '%s\n' "$*" >> "$ROOT/uv-calls"
  [[ "$1 $2" == 'pip install' ]] || return 96
  [[ " $* " == *' --link-mode copy '* ]] || return 97
  [[ -f "$VENV/bin/python" && ! -L "$VENV/bin/python" ]] || return 98
}
'''+block
            result = subprocess.run(['bash', '-c', script], env={**os.environ, 'ROOT':str(root), 'MODE':mode}, capture_output=True, text=True)
            calls = (root/'calls').read_text() if (root/'calls').exists() else ''
            uv_calls = (root/'uv-calls').read_text() if (root/'uv-calls').exists() else ''
            self.assertFalse(any(p.is_symlink() for p in root.rglob('*')))
            return result, calls, uv_calls

    def test_primary_uses_regular_copies(self):
        result, calls, uv_calls = self.run_environment('primary')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--copies', calls)
        self.assertNotIn('--without-pip', calls)
        self.assertEqual(uv_calls, '')

    def test_fallback_copies_before_uv_installs(self):
        result, calls, uv_calls = self.run_environment('fallback')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--without-pip', calls)
        self.assertEqual(len(calls.splitlines()), 2)
        self.assertIn('pip install', uv_calls)
        self.assertIn('--link-mode copy', uv_calls)
        self.assertNotIn('venv', uv_calls.split(' --python')[0])

    def test_absent_venv_module_fails_without_uv_environment(self):
        result, calls, uv_calls = self.run_environment('unavailable')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(uv_calls, '')
        self.assertIn('regular', result.stderr)

    def test_reference_checkout_disables_links(self):
        source = (REPO / 'scripts/test').read_text()
        self.assertIn('git -C "$REF" -c core.symlinks=false -c advice.detachedHead=false checkout', source)

if __name__ == '__main__':
    unittest.main()
