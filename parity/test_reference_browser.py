"""The golden renderer's browser provisioning must not write into a verified reference archive or the checkout.

parity/export-and-render.mjs provisions the reference's browser before each golden render. A verified
archive (NM_REFERENCE_OBJECT_STORE) is checked again after the render, and any file or symbolic link an
install adds to it fails that check. Its dependencies and browser must already be available outside
the checkout, as scripts/parity-summary requires, so the renderer launches that browser and downloads
nothing. These tests run the real ensureReferenceBrowser() against a temporary reference, with npm, the
Playwright CLI and Playwright itself replaced by recording stubs.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDERER = REPO / "parity" / "export-and-render.mjs"
LOADER = REPO / "tools" / "reference-dependencies.mjs"
# The renderer's own checkout-local cache, used when no cache is passed in.
DEFAULT_CACHE = REPO / "parity" / "out" / ("browsers-" + sys.platform)
NODE = shutil.which("node")

DRIVER = textwrap.dedent("""
    const [renderer, cache] = process.argv.slice(1)
    const { ensureReferenceBrowser } = await import(renderer)
    let message = 'ok'
    try {
      ensureReferenceBrowser(cache)
    } catch (error) {
      message = error.message
    }
    process.stdout.write('RESULT ' + JSON.stringify({
      message, browsers: process.env.PLAYWRIGHT_BROWSERS_PATH ?? null }))
""")

# A stand-in for the reference's Playwright. Its browser launches only from the cache that
# FAKE_EXTERNAL_BROWSER names (an empty value names the default cache, with no
# PLAYWRIGHT_BROWSERS_PATH); with FAKE_EXTERNAL_BROWSER unset no browser launches.
FAKE_PLAYWRIGHT = textwrap.dedent("""
    const fs = require('fs')
    module.exports = { chromium: { launch: async () => {
      const seen = process.env.PLAYWRIGHT_BROWSERS_PATH ?? null
      fs.appendFileSync(%s, JSON.stringify({ browsers: seen }) + '\\n')
      const ready = process.env.FAKE_EXTERNAL_BROWSER
      if (ready !== undefined && seen === (ready === '' ? null : ready)) return { close: async () => {} }
      throw new Error('no launchable browser')
    } } }
""")


def tree(root):
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def listing(directory):
    return sorted(os.listdir(directory)) if directory.exists() else None


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
        self.cache = self.root / "checkout-cache"
        self.npm_log = self.root / "npm.log"
        self.cli_log = self.root / "cli.log"
        self.launch_log = self.root / "launch.log"
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
        playwright = self.dependencies / "node_modules" / "playwright"
        playwright.mkdir(parents=True)
        (playwright / "index.js").write_text(FAKE_PLAYWRIGHT % json.dumps(str(self.launch_log)))
        (playwright / "index.mjs").write_text(
            "import playwright from './index.js'\nexport const chromium = playwright.chromium\n"
            "export default playwright\n")
        self.path = os.pathsep.join([str(bin_dir), str(Path(NODE).parent), "/usr/bin", "/bin"])

    def tearDown(self):
        self.temp.cleanup()

    def provision(self, **extra):
        env = {"PATH": self.path, "HOME": str(self.root), "NM_REFERENCE_ROOT": str(self.reference)}
        env.update(extra)
        self.default_cache_before = listing(DEFAULT_CACHE)
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", DRIVER, RENDERER.as_uri(), str(self.cache)],
            capture_output=True, text=True, env=env, timeout=120)
        self.assertIn("RESULT ", result.stdout, result.stdout + result.stderr)
        return json.loads(result.stdout.split("RESULT ", 1)[1])

    def archive(self, **extra):
        """Provision for a verified archive whose dependencies are installed outside it, as CI does."""
        return self.provision(NM_REFERENCE_OBJECT_STORE=str(self.objects),
                              NM_REFERENCE_DEPENDENCIES=str(self.dependencies),
                              NODE_OPTIONS="--import " + LOADER.as_uri(), **extra)

    def assert_nothing_downloaded(self, before):
        self.assertFalse(self.npm_log.exists(), "npm ran against a verified archive")
        self.assertFalse(self.cli_log.exists(), "the browser was downloaded for a verified archive")
        self.assertFalse(self.cache.exists(), "a browser cache was created in the checkout")
        self.assertEqual(listing(DEFAULT_CACHE), self.default_cache_before,
                         "the renderer's checkout-local browser cache changed")
        self.assertEqual(tree(self.reference), before, "the verified archive changed")

    def test_a_verified_archive_launches_the_external_default_browser_without_a_download(self):
        before = tree(self.reference)
        result = self.archive(FAKE_EXTERNAL_BROWSER="")
        self.assertEqual(result["message"], "ok")
        self.assertIsNone(result["browsers"], "the render was pointed at another browser cache")
        self.assert_nothing_downloaded(before)
        launches = [json.loads(line) for line in self.launch_log.read_text().splitlines()]
        self.assertEqual(launches, [{"browsers": None}])

    def test_a_verified_archive_launches_the_browser_cache_its_environment_names(self):
        before = tree(self.reference)
        external = str(self.root / "external-browsers")
        result = self.archive(PLAYWRIGHT_BROWSERS_PATH=external, FAKE_EXTERNAL_BROWSER=external)
        self.assertEqual(result["message"], "ok")
        self.assertEqual(result["browsers"], external)
        self.assert_nothing_downloaded(before)

    def test_a_verified_archive_without_a_ready_external_browser_fails_before_any_download(self):
        before = tree(self.reference)
        result = self.archive()
        self.assertIn("verified archives require ready external dependencies and browser", result["message"])
        self.assertTrue(self.launch_log.exists(), "the external browser was not probed")
        self.assert_nothing_downloaded(before)

    def test_a_verified_archive_without_external_dependencies_fails_before_any_download(self):
        before = tree(self.reference)
        result = self.provision(NM_REFERENCE_OBJECT_STORE=str(self.objects))
        self.assertIn("verified archives require ready external dependencies and browser", result["message"])
        self.assert_nothing_downloaded(before)

    def test_a_checkout_reference_still_installs_its_own_dependencies(self):
        result = self.provision()
        self.assertTrue(self.npm_log.exists(), "npm ci did not run for a checkout reference")
        first = self.npm_log.read_text().splitlines()[0].split()
        self.assertEqual(first[:3], ["ci", "--prefix", str(self.reference)])
        self.assertIn("npm ci in the reference failed", result["message"])


if __name__ == "__main__":
    unittest.main()
