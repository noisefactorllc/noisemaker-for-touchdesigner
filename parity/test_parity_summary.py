#!/usr/bin/env python3
"""scripts/parity-summary maps sweep ledger rows to the PARITY-SUMMARY classes."""

import importlib.machinery
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
