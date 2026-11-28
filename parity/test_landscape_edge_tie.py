#!/usr/bin/env python3
"""App-free checks for the landscape edge-tie pixel pin and its sweep grading."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import stage_coverage  # noqa: E402

COMPARE = REPO / "parity" / "compare.py"
SWEEP = REPO / "parity" / "sweep.sh"
CASE = "heightmap3d_landscape"
FRAME = (257, 129)
PIXEL = (128, 82)
SHOWS = (179, 205, 168)


def frame_with(pixel, value, size=FRAME, elsewhere=0):
    a = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    a[:, :, 0] = elsewhere
    a[:, :, 1] = elsewhere
    a[:, :, 2] = elsewhere
    a[:, :, 3] = 255
    x, y = pixel
    a[y, x, :3] = value
    return a


def write_png(path, array):
    Image.fromarray(array, "RGBA").save(path)


def run_compare(temp, golden_value, candidate_value=SHOWS, pin="128,82:179,205,168", name=CASE):
    golden = Path(temp) / "golden.png"
    candidate = Path(temp) / "candidate.png"
    report = Path(temp) / "report.json"
    write_png(golden, frame_with(PIXEL, golden_value))
    write_png(candidate, frame_with(PIXEL, candidate_value))
    cmd = [sys.executable, str(COMPARE), str(golden), str(candidate),
           "--name", name, "--tolerance", "2.001", "--ssim-min", "0.98",
           "--report", str(report)]
    if pin is not None:
        cmd += ["--expect-pixel", pin]
    r = subprocess.run(cmd, capture_output=True, text=True)
    report_data = json.loads(report.read_text()) if report.exists() else None
    return r, report_data


class LandscapeEdgeTieTests(unittest.TestCase):
    def test_the_edge_tie_case_is_the_upstream_measurement(self):
        self.assertEqual(
            {CASE: {"size": "257x129", "pixel": PIXEL, "shows": SHOWS}},
            stage_coverage.EDGE_TIE_CASES)
        self.assertEqual(
            "%s 257x129 128,82:179,205,168" % CASE,
            subprocess.run([sys.executable, str(HERE / "stage_coverage.py"), "--edge-tie-cases"],
                           capture_output=True, text=True, check=True).stdout.strip())

    def test_the_pin_accepts_the_measured_value(self):
        r, report = run_compare(tempfile.mkdtemp(), SHOWS)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertTrue(report["expected_pixels"][0]["passed"])
        self.assertEqual(list(SHOWS), report["expected_pixels"][0]["observed"])

    def test_the_pin_tolerates_the_two_step_boundary(self):
        r, _ = run_compare(tempfile.mkdtemp(), tuple(v + 2 for v in SHOWS))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        r, _ = run_compare(tempfile.mkdtemp(), tuple(v - 2 for v in SHOWS))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_pin_fails_when_the_edge_moves(self):
        r, report = run_compare(tempfile.mkdtemp(), (100, 205, 168))
        self.assertEqual(1, r.returncode)
        self.assertIn("128,82", r.stdout)
        self.assertFalse(report["expected_pixels"][0]["passed"])
        self.assertFalse(report["passed"])
        r, _ = run_compare(tempfile.mkdtemp(), (179, 100, 168))
        self.assertEqual(1, r.returncode)
        r, _ = run_compare(tempfile.mkdtemp(), (179, 205, 100))
        self.assertEqual(1, r.returncode)

    def test_the_pin_rejects_a_value_beyond_two_steps(self):
        r, _ = run_compare(tempfile.mkdtemp(), tuple(v + 3 for v in SHOWS))
        self.assertEqual(1, r.returncode)

    def test_a_pin_outside_the_frame_is_bad_input(self):
        r, _ = run_compare(tempfile.mkdtemp(), SHOWS, pin="999,0:1,2,3")
        self.assertEqual(2, r.returncode)
        r, _ = run_compare(tempfile.mkdtemp(), SHOWS, pin="0:1,2,3")
        self.assertEqual(2, r.returncode)

    def test_a_case_without_a_pin_is_unaffected(self):
        r, report = run_compare(tempfile.mkdtemp(), (7, 7, 7), candidate_value=(7, 7, 7), pin=None)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual([], report["expected_pixels"])

    def test_the_sweep_grades_the_edge_tie_case_with_the_pin(self):
        sweep = SWEEP.read_text()
        self.assertIn('--edge-tie-cases', sweep)
        self.assertIn('--expect-pixel', sweep)


if __name__ == "__main__":
    unittest.main()
