#!/usr/bin/env python3
"""scripts/parity-summary maps sweep ledger rows to the PARITY-SUMMARY classes."""

import importlib.machinery
import importlib.util
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_loader = importlib.machinery.SourceFileLoader("parity_summary", str(ROOT / "scripts" / "parity-summary"))
_spec = importlib.util.spec_from_loader("parity_summary", _loader)
parity_summary = importlib.util.module_from_spec(_spec)
_loader.exec_module(parity_summary)


def row(name, verdict, max_diff="-", ssim="-"):
    return [name, verdict, str(max_diff), str(ssim), "2.001", "0.98", "sweep", "golden.png"]


class ClassifyTests(unittest.TestCase):
    def test_byte_identical_pass_is_exact(self):
        self.assertEqual(parity_summary.classify(row("a", "PASS", 0.0, 1.0)), "exact")

    def test_pass_within_the_strict_gate_is_strict(self):
        # compare.py's float round trip reads one 8-bit step as 1.0000037.
        self.assertEqual(parity_summary.classify(row("a", "PASS", 1.0000037, 0.9999)), "strict")
        self.assertEqual(parity_summary.classify(row("a", "PASS", 2.0, 0.98)), "strict")

    def test_wider_tolerance_results_are_near(self):
        self.assertEqual(parity_summary.classify(row("a", "NEAR", 32.0, 0.9999)), "near")
        self.assertEqual(parity_summary.classify(row("a", "PASS", 3.0, 0.9999)), "near")

    def test_deferred_failed_and_absent_cases(self):
        self.assertEqual(parity_summary.classify(row("a", "DEFER")), "defer")
        self.assertEqual(parity_summary.classify(row("a", "FAIL", 255, 0.1)), "fail")
        self.assertEqual(parity_summary.classify(row("a", "PASS", "nan?", 1.0)), "fail")
        self.assertEqual(parity_summary.classify(None), "missing")


class SummaryTests(unittest.TestCase):
    def test_counts_cover_every_expected_case(self):
        rows = {
            "exact": row("exact", "PASS", 0.0, 1.0),
            "strict": row("strict", "PASS", 1.0, 0.999),
            "near": row("near", "NEAR", 12.0, 0.999),
            "defer": row("defer", "DEFER"),
            "fail": row("fail", "FAIL", 200, 0.5),
        }
        counts, lines = parity_summary.summarize(
            ["exact", "strict", "near", "defer", "fail", "missing"], rows)
        self.assertEqual(counts, {"expected": 6, "executed": 4, "exact": 1, "strict": 1,
                                  "near": 1, "defer": 1, "skip": 0, "fail": 1, "missing": 1})
        self.assertEqual(len(lines), 6)

    def test_ledger_rows_are_keyed_by_case(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "ledger.tsv"
            ledger.write_text("case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                              "adjust\tPASS\t0.0\t1.0\t2.001\t0.98\tsweep\tg.png\n")
            rows = parity_summary.read_ledger(ledger)
        self.assertEqual(parity_summary.classify(rows["adjust"]), "exact")


class PinTests(unittest.TestCase):
    def test_the_pin_comes_from_scripts_test(self):
        self.assertRegex(parity_summary.pinned_revision(), re.compile(r"^[0-9a-f]{40}$"))


class AlignReferenceTests(unittest.TestCase):
    PIN = "b" * 40

    def _run(self, ref, pin=None):
        return parity_summary.align_reference(ref, pin or self.PIN)

    def test_a_stale_git_clone_is_fetched_and_checked_out_to_the_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed = root / "seed"
            seed.mkdir()
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
            for argv in (["git", "init", "-q", str(seed)],
                         ["git", "-C", str(seed), "commit", "-q", "--allow-empty",
                          "-m", "seed", "--"], ["git", "-C", str(seed), "branch", "-m", "main"]):
                subprocess.run(argv, check=True, capture_output=True, env=env)
            clone = root / "ref"
            subprocess.run(["git", "clone", "-q", str(seed), str(clone)],
                           check=True, capture_output=True)
            stale = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                                   check=True, capture_output=True, text=True).stdout.strip()
            subprocess.run(["git", "-C", str(seed), "commit", "-q", "--allow-empty",
                            "-m", "newer", "--"], check=True, capture_output=True, env=env)
            seed_head = subprocess.run(["git", "-C", str(seed), "rev-parse", "HEAD"],
                                       check=True, capture_output=True, text=True).stdout.strip()
            pin = seed_head
            head, err = self._run(str(clone), pin=pin)
            self.assertEqual(head, pin)
            self.assertIsNone(err)
            self.assertNotEqual(stale, pin)
            self.assertEqual(
                subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                               check=True, capture_output=True, text=True).stdout.strip(),
                pin)

    def test_a_fetch_failure_fails_closed_with_the_observed_head(self):
        pin = "d" * 40
        def fetch_fails(argv, **kw):
            result = mock.Mock(returncode=0, stdout="", stderr="")
            if "--is-inside-work-tree" in argv:
                result.stdout = "true\n"
            if "fetch" in argv:
                result.returncode = 128
                result.stderr = "no net"
            if "checkout" in argv:
                result.returncode = 1
                result.stderr = "aborted"
            return result

        with mock.patch.object(parity_summary, "reference_head", return_value="e" * 40) as head_mock, \
                mock.patch.object(parity_summary.subprocess, "run", side_effect=fetch_fails) as run_mock:
            head, err = self._run("/does/not/matter")
        self.assertEqual(head, "e" * 40)
        self.assertIn("fetch origin", err)
        calls = [c.args[0] for c in run_mock.call_args_list if c.args]
        self.assertTrue(all(isinstance(a, list) for a in calls), calls)

    def test_a_non_clone_fails_closed(self):
        head, err = self._run("/tmp")
        self.assertIsNone(head)
        self.assertEqual(err, "not a git clone")


class ResolveReferenceTests(unittest.TestCase):
    def test_an_unset_root_falls_back_to_the_vendored_clone_at_the_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendored = root / "upstream-noisemaker"
            vendored.mkdir()
            pin = "f" * 40
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "reference_head", return_value=pin), \
                    mock.patch.object(parity_summary, "pinned_revision", return_value=pin), \
                    mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("NM_REFERENCE_ROOT", None)
                self.assertEqual(parity_summary.resolve_reference(root), str(vendored))

    def test_a_stale_root_that_cannot_align_falls_back_to_the_vendored_clone(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendored = root / "upstream-noisemaker"
            vendored.mkdir()
            pin = "1" * 40
            stale = "2" * 40
            heads = {str(root / "stale"): stale, str(vendored): pin}
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "reference_head",
                                      side_effect=lambda r: heads.get(str(r))), \
                    mock.patch.object(parity_summary, "align_reference",
                                      return_value=(stale, "fetch failed")), \
                    mock.patch.object(parity_summary, "pinned_revision", return_value=pin), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root / "stale")}):
                self.assertEqual(parity_summary.resolve_reference(root), str(vendored))

    def test_no_vendored_clone_falls_back_to_a_provisioned_reference_at_the_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "work"
            work.mkdir()
            pin = "4" * 40
            provisioned = str(work / "reference")
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "reference_head",
                                      return_value=None), \
                    mock.patch.object(parity_summary, "align_reference",
                                      return_value=(None, "not a git clone")), \
                    mock.patch.object(parity_summary, "provision_reference",
                                      return_value=provisioned), \
                    mock.patch.object(parity_summary, "pinned_revision", return_value=pin), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root / "missing")}):
                self.assertEqual(parity_summary.resolve_reference(work), provisioned)

    def test_no_usable_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "work"
            work.mkdir()
            pin = "3" * 40
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "pinned_revision", return_value=pin), \
                    mock.patch.object(parity_summary, "provision_reference",
                                      return_value=None), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root / "missing")}):
                with self.assertRaises(SystemExit):
                    parity_summary.resolve_reference(work)


class InstallReferenceDependenciesTests(unittest.TestCase):
    def test_a_torn_node_modules_is_rebuilt_by_npm_ci(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{}\n")

            def run(argv, **kwargs):
                commands.append(list(argv))
                if argv[0] == "node":
                    if len(commands) == 1:
                        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
                    return subprocess.CompletedProcess(argv, 0,
                                                       stdout=str(root / "node_modules"), stderr="")
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.object(parity_summary, "shutil") as sh:
                sh.which.side_effect = lambda name: "/usr/bin/" + name if name else None
                with mock.patch.object(parity_summary, "subprocess") as sp:
                    sp.run.side_effect = run
                    with mock.patch.object(parity_summary, "reference_browser_ready",
                                           return_value=True):
                        error, _ = parity_summary.install_reference_dependencies(str(root), root)
            self.assertIsNone(error)
            npm_calls = [c for c in commands if c and c[0].endswith("npm")]
            self.assertEqual(len(npm_calls), 1)
            self.assertIn("ci", npm_calls[0])
            self.assertIn("--prefix", npm_calls[0])

    def test_a_failed_install_reports_the_npm_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{}\n")
            with mock.patch.object(parity_summary, "shutil") as sh:
                sh.which.side_effect = lambda name: "/usr/bin/" + name if name else None
                with mock.patch.object(parity_summary, "subprocess") as sp:
                    def run(argv, **kwargs):
                        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")
                    sp.run.side_effect = run
                    error, _ = parity_summary.install_reference_dependencies(str(root), root)
            self.assertIn("npm ci in the reference failed", error)
            self.assertIn("boom", error)

    def test_a_missing_tls_root_retries_with_the_system_ca_bundle(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{}\n")
            bundles = [b for b in parity_summary.CA_BUNDLES if Path(b).is_file()]
            self.assertTrue(bundles, "the test host has a system CA bundle")

            installed = {"ready": False}

            def run(argv, **kwargs):
                env = kwargs.get("env") or {}
                commands.append((list(argv), dict(env)))
                if "NODE_EXTRA_CA_CERTS" in env:
                    installed["ready"] = True
                    return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="UNABLE_TO_GET_ISSUER")

            with mock.patch.object(parity_summary, "shutil") as sh:
                sh.which.side_effect = lambda name: "/usr/bin/" + name if name else None
                with mock.patch.object(parity_summary, "subprocess") as sp:
                    def probe(argv, **kwargs):
                        commands.append((list(argv), {}))
                        if installed["ready"]:
                            return subprocess.CompletedProcess(argv, 0, stdout="/ok", stderr="")
                        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")

                    sp.run.side_effect = lambda argv, **kw: probe(argv, **kw) if argv[0] == "node" else run(argv, **kw)
                    with mock.patch.object(parity_summary, "reference_browser_ready",
                                           return_value=True):
                        error, _ = parity_summary.install_reference_dependencies(str(root), root)
            self.assertIsNone(error)
            retries = [env for _, env in commands if "NODE_EXTRA_CA_CERTS" in env]
            self.assertEqual(len(retries), 1)
            self.assertIn(bundles[0], retries[0]["NODE_EXTRA_CA_CERTS"])


    def test_a_missing_browser_is_installed_by_the_reference_playwright(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{}\n")
            cli = root / "node_modules" / "playwright-core" / "cli.js"
            cli.parent.mkdir(parents=True)
            cli.write_text("// playwright cli\n")

            def run(argv, **kwargs):
                commands.append((list(argv), dict(kwargs.get("env") or {})))
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.object(parity_summary, "shutil") as sh:
                sh.which.side_effect = lambda name: "/usr/bin/" + name if name else None
                with mock.patch.object(parity_summary, "subprocess") as sp:
                    sp.run.side_effect = run
                    with mock.patch.object(parity_summary, "reference_harness_ready",
                                           return_value=True), \
                            mock.patch.object(parity_summary, "reference_browser_ready",
                                              side_effect=[False, False, False, True]):
                        error, extra_env = parity_summary.install_reference_dependencies(str(root), root)
            self.assertIsNone(error)
            installs = [c for c, _ in commands if "install" in c and "chromium" in c]
            self.assertEqual(len(installs), 2)
            self.assertEqual(installs[0][:2], ["node", str(cli)])
            managed = [env for _, env in commands if env.get("PLAYWRIGHT_BROWSERS_PATH")]
            self.assertEqual(managed, [dict(os.environ,
                                            PLAYWRIGHT_BROWSERS_PATH=str(root / ("browsers-" + sys.platform)))])
            self.assertEqual(extra_env.get("PLAYWRIGHT_BROWSERS_PATH"),
                                 str(root / ("browsers-" + sys.platform)))

    def test_a_failed_browser_install_reports_the_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text("{}\n")
            cli = root / "node_modules" / "playwright-core" / "cli.js"
            cli.parent.mkdir(parents=True)
            cli.write_text("// playwright cli\n")
            with mock.patch.object(parity_summary, "shutil") as sh:
                sh.which.side_effect = lambda name: "/usr/bin/" + name if name else None
                with mock.patch.object(parity_summary, "subprocess") as sp:
                    def run(argv, **kwargs):
                        if "install" in argv and "chromium" in argv:
                            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no net")
                        if argv[0] == "node":
                            return subprocess.CompletedProcess(argv, 0, stdout="ready", stderr="")
                        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
                    sp.run.side_effect = run
                    with mock.patch.object(parity_summary, "reference_harness_ready",
                                           return_value=True), \
                            mock.patch.object(parity_summary, "reference_browser_ready",
                                              return_value=False):
                        error, _ = parity_summary.install_reference_dependencies(str(root), root)
            self.assertIn("the reference browser install failed", error)
            self.assertIn("no net", error)


class ScopedRunTests(unittest.TestCase):
    def _prepare(self, root, render_set):
        (root / "parity" / "out").mkdir(parents=True, exist_ok=True)
        (root / "scripts").mkdir(exist_ok=True)
        (root / "package.json").write_text("{}\n")
        pin = "b" * 40
        (root / "scripts" / "test").write_text(f'NM_REFERENCE_SHA_PINNED="{pin}"\n')
        render = root / "parity" / "out" / "_render_set.txt"
        render.write_text(render_set)
        return pin, render

    def test_named_cases_render_and_count_only_those(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin, render = self._prepare(root, "adjust\nbitwise\npresent_hero\n")
            sweep = root / "parity" / "sweep.sh"
            ledger_sha = hashlib.sha256(
                ("case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                 "bitwise\tPASS\t0\t1\t2.001\t0.98\tsweep\tbitwise.golden.png\n").encode()).hexdigest()
            sweep.write_text(
                'printf "%s" "$NM_CASES" > "$NM_PARITY_WORK/cases.env"\n'
                'cat > "$LEDGER_PATH" <<\'LEDGER\'\n'
                "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                "bitwise\tPASS\t0\t1\t2.001\t0.98\tsweep\tbitwise.golden.png\n"
                "LEDGER\n"
                f'printf \'{{"source": "test-source", "pin": "{pin}", '
                f'"ledger_sha256": "{ledger_sha}"}}\\n\' '
                '> "$LEDGER_PATH.binding.json"\n'
                "exit 0\n")
            output = io.StringIO()
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "RENDER_SET", render), \
                    mock.patch.object(parity_summary, "reference_head", return_value=pin), \
                    mock.patch.object(parity_summary, "checkout_source",
                                      return_value="test-source"), \
                    mock.patch.object(parity_summary, "reference_harness_ready",
                                      return_value=True), \
                    mock.patch.object(parity_summary, "reference_browser_ready",
                                      return_value=True), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root),
                                                "NM_PARITY_WORK": str(root / "work"),
                                                "TD_BIN": sys.executable}), \
                    contextlib.redirect_stdout(output):
                status = parity_summary.main(["bitwise"])
            self.assertEqual(status, 0)
            self.assertEqual((root / "work" / "cases.env").read_text(), "bitwise")
            self.assertIn('"expected":1,"executed":1,"exact":1', output.getvalue())

    def test_an_unknown_case_fails_before_the_sweep(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin, render = self._prepare(root, "adjust\n")
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "RENDER_SET", render), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root)}):
                with self.assertRaises(SystemExit) as caught:
                    parity_summary.main(["nope"])
            self.assertIn("not staged cases: nope", str(caught.exception))


class LedgerBindingTests(unittest.TestCase):
    PIN = "c" * 40
    SOURCE = "d" * 40

    def _bound_ledger(self, root, source=None, pin=None, ledger_sha256=None, omit_sha=False):
        ledger = root / "ledger.tsv"
        ledger.write_text(
            "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
            "adjust\tPASS\t0\t1\t2.001\t0.98\tsweep\tadjust.golden.png\n")
        binding = {"source": source or self.SOURCE, "pin": pin or self.PIN,
                   "ledger_sha256": ledger_sha256 or hashlib.sha256(ledger.read_bytes()).hexdigest()}
        if omit_sha:
            binding.pop("ledger_sha256")
        Path(str(ledger) + ".binding.json").write_text(json.dumps(binding) + "\n")
        return ledger

    def _main(self, root, ledger):
        render_set = root / "_render_set.txt"
        render_set.write_text("adjust\n")
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render_set), \
                mock.patch.object(parity_summary, "checkout_source",
                                  return_value=self.SOURCE), \
                mock.patch.object(parity_summary, "pinned_revision",
                                  return_value=self.PIN), \
                contextlib.redirect_stdout(io.StringIO()):
            return parity_summary.main(["--ledger", str(ledger)])

    def test_a_ledger_bound_to_this_source_and_pin_grades(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = self._bound_ledger(root)
            self.assertEqual(self._main(root, ledger), 0)

    def test_a_ledger_without_a_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = root / "ledger.tsv"
            ledger.write_text(
                "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                "adjust\tPASS\t0\t1\t2.001\t0.98\tsweep\tadjust.golden.png\n")
            with self.assertRaises(SystemExit) as caught:
                self._main(root, ledger)
            self.assertIn("has no binding", str(caught.exception))

    def test_a_ledger_bound_to_another_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = self._bound_ledger(root, source="e" * 40)
            with self.assertRaises(SystemExit) as caught:
                self._main(root, ledger)
            self.assertIn("bound to source", str(caught.exception))

    def test_a_ledger_bound_to_another_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = self._bound_ledger(root, pin="f" * 40)
            with self.assertRaises(SystemExit) as caught:
                self._main(root, ledger)
            self.assertIn("bound to source", str(caught.exception))

    def test_a_ledger_whose_binding_omits_the_ledger_sha256_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = self._bound_ledger(root, omit_sha=True)
            with self.assertRaises(SystemExit) as caught:
                self._main(root, ledger)
            self.assertIn("does not bind the ledger bytes", str(caught.exception))

    def test_a_ledger_whose_bytes_do_not_match_the_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = self._bound_ledger(root, ledger_sha256="0" * 64)
            with self.assertRaises(SystemExit) as caught:
                self._main(root, ledger)
            self.assertIn("bytes do not match the binding", str(caught.exception))


class LedgerFallbackTests(unittest.TestCase):
    """The whole-port run grades a bound ledger when TouchDesigner cannot run here."""

    PIN = "b" * 40
    SOURCE = "a" * 40

    def _prepare(self, render_set="adjust\n"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        work = root / "work"
        work.mkdir()
        (root / "scripts").mkdir()
        (root / "scripts" / "test").write_text(f'NM_REFERENCE_SHA_PINNED="{self.PIN}"\n')
        render = root / "_render_set.txt"
        render.write_text(render_set)
        return root, work, render

    def _bound_ledger(self, work, source=None, pin=None, ledger_sha256=None, omit_sha=False):
        ledger = work / "ledger.tsv"
        ledger.write_text(
            "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
            "adjust\tPASS\t0\t1\t2.001\t0.98\tsweep\tadjust.golden.png\n")
        binding = {"source": source or self.SOURCE, "pin": pin or self.PIN,
                   "ledger_sha256": ledger_sha256 or hashlib.sha256(ledger.read_bytes()).hexdigest()}
        if omit_sha:
            binding.pop("ledger_sha256")
        Path(str(ledger) + ".binding.json").write_text(json.dumps(binding) + "\n")
        return ledger

    def _main(self, root, render):
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render), \
                mock.patch.object(parity_summary, "checkout_source", return_value=self.SOURCE), \
                mock.patch.object(parity_summary, "pinned_revision", return_value=self.PIN), \
                mock.patch.dict(os.environ, {"NM_PARITY_WORK": str(root / "work")}):
            os.environ.pop("TD_BIN", None)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                status = parity_summary.main([])
        return status, out.getvalue()

    def test_a_whole_port_run_without_touchdesigner_grades_a_bound_ledger(self):
        root, work, render = self._prepare()
        self._bound_ledger(work)
        status, out = self._main(root, render)
        self.assertEqual(status, 0)
        self.assertIn('"exact":1', out)

    def test_a_whole_port_run_without_touchdesigner_fails_closed_without_a_ledger(self):
        root, work, render = self._prepare()
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render), \
                mock.patch.dict(os.environ, {"NM_PARITY_WORK": str(work)}):
            os.environ.pop("TD_BIN", None)
            with self.assertRaises(SystemExit) as caught:
                parity_summary.main([])
        self.assertIn("TouchDesigner binary not found", str(caught.exception))

    def test_a_whole_port_run_without_touchdesigner_rejects_a_foreign_ledger(self):
        root, work, render = self._prepare()
        self._bound_ledger(work, source="e" * 40)
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render), \
                mock.patch.object(parity_summary, "checkout_source", return_value=self.SOURCE), \
                mock.patch.object(parity_summary, "pinned_revision", return_value=self.PIN), \
                mock.patch.dict(os.environ, {"NM_PARITY_WORK": str(work)}):
            os.environ.pop("TD_BIN", None)
            with self.assertRaises(SystemExit) as caught:
                parity_summary.main([])
        self.assertIn("bound to source", str(caught.exception))

    def test_a_whole_port_run_without_touchdesigner_rejects_an_incomplete_ledger(self):
        root, work, render = self._prepare(render_set="adjust\nblur\n")
        self._bound_ledger(work)
        status, out = self._main(root, render)
        self.assertEqual(status, 1)
        self.assertIn('"missing":1', out)

    def test_a_whole_port_run_without_touchdesigner_rejects_a_binding_without_the_ledger_sha256(self):
        root, work, render = self._prepare()
        self._bound_ledger(work, omit_sha=True)
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render), \
                mock.patch.object(parity_summary, "checkout_source", return_value=self.SOURCE), \
                mock.patch.object(parity_summary, "pinned_revision", return_value=self.PIN), \
                mock.patch.dict(os.environ, {"NM_PARITY_WORK": str(work)}):
            os.environ.pop("TD_BIN", None)
            with self.assertRaises(SystemExit) as caught:
                parity_summary.main([])
        self.assertIn("does not bind the ledger bytes", str(caught.exception))

    def test_a_whole_port_run_without_touchdesigner_rejects_ledger_bytes_that_differ(self):
        root, work, render = self._prepare()
        self._bound_ledger(work, ledger_sha256="0" * 64)
        with mock.patch.object(parity_summary, "ROOT", root), \
                mock.patch.object(parity_summary, "RENDER_SET", render), \
                mock.patch.object(parity_summary, "checkout_source", return_value=self.SOURCE), \
                mock.patch.object(parity_summary, "pinned_revision", return_value=self.PIN), \
                mock.patch.dict(os.environ, {"NM_PARITY_WORK": str(work)}):
            os.environ.pop("TD_BIN", None)
            with self.assertRaises(SystemExit) as caught:
                parity_summary.main([])
        self.assertIn("bytes do not match the binding", str(caught.exception))


class TouchDesignerGateTests(unittest.TestCase):
    def _prepare(self, root, render_set):
        (root / "parity" / "out").mkdir(parents=True, exist_ok=True)
        (root / "scripts").mkdir(exist_ok=True)
        (root / "package.json").write_text("{}\n")
        pin = "b" * 40
        (root / "scripts" / "test").write_text(f'NM_REFERENCE_SHA_PINNED="{pin}"\n')
        render = root / "parity" / "out" / "_render_set.txt"
        render.write_text(render_set)
        return pin, render

    def test_td_bin_names_the_binary_the_sweep_launches(self):
        with mock.patch.dict(os.environ, {"TD_BIN": sys.executable}):
            self.assertEqual(parity_summary.touchdesigner_binary(), sys.executable)

    def test_a_bundle_without_a_readable_version_is_not_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "Broken.app"
            binary = app / "Contents" / "MacOS" / "TouchDesigner"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")
            binary.chmod(0o755)
            with mock.patch.dict(os.environ, {"TD_BIN": str(binary)}):
                self.assertIsNone(parity_summary.touchdesigner_binary())

    def test_a_bundle_that_reports_its_version_is_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "TouchDesigner.app"
            binary = app / "Contents" / "MacOS" / "TouchDesigner"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")
            binary.chmod(0o755)
            (app / "Contents" / "Info.plist").write_text("<plist/>")
            probe = subprocess.CompletedProcess([], 0, stdout="2025.32820\n", stderr="")
            with mock.patch.dict(os.environ, {"TD_BIN": str(binary)}), \
                    mock.patch.object(parity_summary.subprocess, "run",
                                      return_value=probe):
                self.assertEqual(parity_summary.touchdesigner_binary(), str(binary))

    def test_a_missing_touchdesigner_fails_closed_before_any_setup(self):
        # A host without TouchDesigner must stop before reference resolution,
        # dependency installs and rendering; the whole port would otherwise be
        # graded against a ledger of renderer failures that are not parity data.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin, render = self._prepare(root, "adjust\n")
            env = {"NM_REFERENCE_ROOT": str(root), "NM_PARITY_WORK": str(root / "work")}
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "RENDER_SET", render), \
                    mock.patch.object(parity_summary, "resolve_reference") as resolve, \
                    mock.patch.object(parity_summary, "install_reference_dependencies") as install, \
                    mock.patch.dict(os.environ, env):
                os.environ.pop("TD_BIN", None)
                with self.assertRaises(SystemExit) as caught:
                    parity_summary.main(["adjust"])
            self.assertIn("TouchDesigner binary not found", str(caught.exception))
            resolve.assert_not_called()
            install.assert_not_called()


class ProvisionReferenceTests(unittest.TestCase):
    def test_a_fresh_fetch_lands_on_the_pin(self):
        calls = []
        pin = "5" * 40
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            target = work / "reference"

            state = {"checked_out": False}

            def run(argv, **kwargs):
                calls.append(list(argv))
                if "rev-parse" in argv:
                    if state["checked_out"]:
                        return subprocess.CompletedProcess(argv, 0, stdout=pin + "\n", stderr="")
                    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
                if "fetch" in argv:
                    return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
                if "checkout" in argv:
                    state["checked_out"] = True
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.object(parity_summary, "subprocess") as sp:
                sp.run.side_effect = run
                result = parity_summary.provision_reference(work, pin)
            self.assertEqual(result, str(target))
            fetches = [c for c in calls if "fetch" in c]
            self.assertEqual(len(fetches), 1)
            self.assertIn(pin, fetches[0])
            self.assertIn(parity_summary.REFERENCE_REPO, fetches[0])

    def test_a_fetch_failure_provides_nothing(self):
        pin = "6" * 40
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)

            def run(argv, **kwargs):
                if "rev-parse" in argv:
                    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
                if "fetch" in argv:
                    return subprocess.CompletedProcess(argv, 128, stdout="", stderr="network down")
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

            with mock.patch.object(parity_summary, "subprocess") as sp:
                sp.run.side_effect = run
                self.assertIsNone(parity_summary.provision_reference(work, pin))


class SweepStatusTests(unittest.TestCase):
    def test_sweep_failure_rejects_an_otherwise_passing_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "parity" / "out").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "node_modules").mkdir()
            (root / "package.json").write_text("{}\n")
            pin = "a" * 40
            (root / "scripts" / "test").write_text(
                f'NM_REFERENCE_SHA_PINNED="{pin}"\n')
            render_set = root / "parity" / "out" / "_render_set.txt"
            render_set.write_text("adjust\n")
            sweep = root / "parity" / "sweep.sh"
            ledger = (
                "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                "adjust\tPASS\t0\t1\t2.001\t0.98\tsweep\tadjust.golden.png\n"
            )
            ledger_sha = hashlib.sha256(ledger.encode()).hexdigest()
            for sweep_status, expected_status in ((0, 0), (7, 1)):
                with self.subTest(sweep_status=sweep_status):
                    sweep.write_text(
                        'cat > "$LEDGER_PATH" <<\'LEDGER\'\n'
                        + ledger + "LEDGER\n"
                        + f'printf \'{{"source": "test-source", "pin": "{pin}", '
                        + f'"ledger_sha256": "{ledger_sha}"}}\\n\' '
                        + '> "$LEDGER_PATH.binding.json"\n'
                        + f"exit {sweep_status}\n")
                    output = io.StringIO()
                    with mock.patch.object(parity_summary, "ROOT", root), \
                            mock.patch.object(parity_summary, "RENDER_SET", render_set), \
                            mock.patch.object(parity_summary, "reference_head", return_value=pin), \
                            mock.patch.object(parity_summary, "checkout_source",
                                              return_value="test-source"), \
                            mock.patch.object(parity_summary, "reference_harness_ready",
                                              return_value=True), \
                            mock.patch.object(parity_summary, "reference_browser_ready",
                                              return_value=True), \
                            mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root),
                                                        "NM_PARITY_WORK": str(root / "work"),
                                                        "TD_BIN": sys.executable}), \
                            contextlib.redirect_stdout(output):
                        status = parity_summary.main([])
                    self.assertEqual(status, expected_status)
                    self.assertIn('"expected":1,"executed":1,"exact":1', output.getvalue())


if __name__ == "__main__":
    unittest.main()
