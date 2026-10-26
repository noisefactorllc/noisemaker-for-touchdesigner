#!/usr/bin/env python3
"""scripts/parity-summary maps sweep ledger rows to the PARITY-SUMMARY classes."""

import importlib.machinery
import importlib.util
import contextlib
import io
import os
import re
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
                self.assertEqual(parity_summary.resolve_reference(), str(vendored))

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
                self.assertEqual(parity_summary.resolve_reference(), str(vendored))

    def test_no_usable_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin = "3" * 40
            with mock.patch.object(parity_summary, "ROOT", root), \
                    mock.patch.object(parity_summary, "pinned_revision", return_value=pin), \
                    mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root / "missing")}):
                with self.assertRaises(SystemExit):
                    parity_summary.resolve_reference()


class SweepStatusTests(unittest.TestCase):
    def test_sweep_failure_rejects_an_otherwise_passing_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "parity" / "out").mkdir(parents=True)
            (root / "scripts").mkdir()
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
            for sweep_status, expected_status in ((0, 0), (7, 1)):
                with self.subTest(sweep_status=sweep_status):
                    sweep.write_text(
                        'cat > "$LEDGER_PATH" <<\'LEDGER\'\n'
                        + ledger + f"LEDGER\nexit {sweep_status}\n")
                    output = io.StringIO()
                    with mock.patch.object(parity_summary, "ROOT", root), \
                            mock.patch.object(parity_summary, "RENDER_SET", render_set), \
                            mock.patch.object(parity_summary, "reference_head", return_value=pin), \
                            mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root),
                                                        "NM_PARITY_WORK": str(root / "work")}), \
                            contextlib.redirect_stdout(output):
                        status = parity_summary.main([])
                    self.assertEqual(status, expected_status)
                    self.assertIn('"expected":1,"executed":1,"exact":1', output.getvalue())


if __name__ == "__main__":
    unittest.main()
