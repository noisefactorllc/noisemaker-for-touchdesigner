"""The golden renderer's browser provisioning must not write into a verified reference archive.

parity/export-and-render.mjs provisions the reference's browser before each golden render. A verified
archive (NM_REFERENCE_OBJECT_STORE) is checked again after the render, and any file or symbolic link an
install adds to it fails that check. These tests run the real ensureReferenceBrowser() against a
temporary reference, with npm and the Playwright CLI replaced by recording stubs.
"""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDERER = REPO / "parity" / "export-and-render.mjs"
NODE = shutil.which("node")

DRIVER = textwrap.dedent("""
    const [renderer, cache] = process.argv.slice(1)
    const { ensureReferenceBrowser } = await import(renderer)
    try {
      ensureReferenceBrowser(cache)
      process.stdout.write('RESULT ok')
    } catch (error) {
      process.stdout.write('RESULT ' + error.message)
    }
""")


def tree(root):
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


class ReferenceBrowserProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(NODE, "node must be on PATH")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference"
        (self.reference / "shaders").mkdir(parents=True)
        (self.reference / "vendor" / "shade-mcp" / "harness").mkdir(parents=True)
        (self.reference / "package.json").write_text("{}\n")
        self.objects = self.root / "objects.git"
        self.objects.mkdir()
        self.cache = self.root / "cache"
        self.npm_log = self.root / "npm.log"
        self.cli_log = self.root / "cli.log"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        npm = bin_dir / "npm"
        npm.write_text('#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s"\nexit 1\n' % self.npm_log)
        npm.chmod(0o755)
        self.dependencies = self.root / "dependencies"
        cli = self.dependencies / "node_modules" / "playwright-core" / "cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text(
            "require('fs').appendFileSync(%s, JSON.stringify({argv: process.argv.slice(2), "
            "cache: process.env.PLAYWRIGHT_BROWSERS_PATH}) + '\\n')\nprocess.exit(1)\n"
            % json.dumps(str(self.cli_log)))
        self.path = os.pathsep.join([str(bin_dir), str(Path(NODE).parent), "/usr/bin", "/bin"])

    def tearDown(self):
        self.temp.cleanup()

    def provision(self, **extra):
        env = {"PATH": self.path, "HOME": str(self.root), "NM_REFERENCE_ROOT": str(self.reference)}
        env.update(extra)
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", DRIVER, RENDERER.as_uri(), str(self.cache)],
            capture_output=True, text=True, env=env, timeout=120)
        self.assertIn("RESULT ", result.stdout, result.stdout + result.stderr)
        return result.stdout.split("RESULT ", 1)[1]

    def test_a_verified_archive_takes_playwright_from_its_external_dependencies(self):
        before = tree(self.reference)
        message = self.provision(NM_REFERENCE_OBJECT_STORE=str(self.objects),
                                 NM_REFERENCE_DEPENDENCIES=str(self.dependencies))
        self.assertFalse(self.npm_log.exists(), "npm ran against a verified archive")
        self.assertEqual(tree(self.reference), before, "the verified archive changed")
        calls = [json.loads(line) for line in self.cli_log.read_text().splitlines()]
        self.assertTrue(calls, "the external Playwright CLI was not used")
        self.assertEqual(calls[0]["argv"], ["install", "chromium"])
        self.assertEqual(calls[0]["cache"], str(self.cache))
        self.assertIn("the reference browser install failed", message)

    def test_a_verified_archive_without_external_dependencies_fails_before_any_install(self):
        before = tree(self.reference)
        message = self.provision(NM_REFERENCE_OBJECT_STORE=str(self.objects))
        self.assertFalse(self.npm_log.exists(), "npm ran against a verified archive")
        self.assertFalse(self.cli_log.exists())
        self.assertEqual(tree(self.reference), before, "the verified archive changed")
        self.assertIn("verified archives require ready external dependencies", message)

    def test_a_checkout_reference_still_installs_its_own_dependencies(self):
        message = self.provision()
        self.assertTrue(self.npm_log.exists(), "npm ci did not run for a checkout reference")
        first = self.npm_log.read_text().splitlines()[0].split()
        self.assertEqual(first[:3], ["ci", "--prefix", str(self.reference)])
        self.assertIn("npm ci in the reference failed", message)


if __name__ == "__main__":
    unittest.main()
