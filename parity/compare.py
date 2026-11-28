#!/usr/bin/env python3
"""Compare two PNGs for the Noisemaker parity harness.

Loads a GOLDEN reference PNG (rendered from the upstream engine via
parity/batch-golden.mjs) and a CANDIDATE PNG (rendered in TouchDesigner), computes
max-abs-diff and a simple global SSIM, and fails if either exceeds a per-program
tolerance. Follows the same image-regression conventions as the sibling Noisemaker
ports (argparse CLI, numpy, PIL, max-abs-diff gate) and emits a small JSON report.

Both PNGs are expected to be the SAME size and the SAME orientation (top-down)
and SAME encoding (linear 8-bit, NOT sRGB) — the renderers are responsible for
producing matching orientation/encoding (the Y-flip reconciliation point).

CLI:
  python compare.py golden.png candidate.png [--tolerance 2] [--ssim-min 0.98] \
         [--report out.json] [--name synth/noise]

Exit code 0 = within tolerance, 1 = divergence, 2 = bad input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load_rgba(path: Path) -> np.ndarray:
    """Load a PNG as a float32 HxWx4 array in [0,1]."""
    img = Image.open(path).convert("RGBA")
    return np.asarray(img, dtype=np.float32) / 255.0


def parse_expect_pixel(spec: str):
    """Parse an X,Y:R,G,B pixel pin; raise ValueError on a malformed spec."""
    m = re.match(r"^(\d+),(\d+):(\d+),(\d+),(\d+)$", spec)
    if not m:
        raise ValueError(spec)
    return (int(m.group(1)), int(m.group(2))), tuple(int(m.group(i)) for i in (3, 4, 5))


def max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    """Max absolute per-channel difference in 8-bit units (0..255)."""
    return float(np.max(np.abs(a - b)) * 255.0)


def mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute per-channel difference in 8-bit units (0..255)."""
    return float(np.mean(np.abs(a - b)) * 255.0)


def global_ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Simple global SSIM over luminance (single-window, no Gaussian).

    Adequate as a structural gate for parity (we already have a strict per-pixel
    max-abs gate); kept dependency-free (no skimage) to match the repo's minimal
    Python toolchain.
    """
    # Rec. 601 luma, matching the harness's luma weighting.
    def luma(x):
        return 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]

    la, lb = luma(a).ravel(), luma(b).ravel()
    mu_a, mu_b = la.mean(), lb.mean()
    var_a, var_b = la.var(), lb.var()
    cov = ((la - mu_a) * (lb - mu_b)).mean()
    c1 = (0.01) ** 2
    c2 = (0.03) ** 2
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
    return float(num / den) if den != 0 else 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("golden", type=Path, help="Reference golden PNG")
    parser.add_argument("candidate", type=Path, help="TouchDesigner-rendered candidate PNG")
    parser.add_argument("--name", default=None, help="Program name for the report")
    # Default 2/255 mirrors a tight cross-backend tolerance; loosen per-program
    # for stochastic/feedback effects via --tolerance.
    parser.add_argument("--tolerance", type=float, default=2.0,
                        help="Max allowed max-abs-diff in 8-bit units (default 2)")
    parser.add_argument("--ssim-min", type=float, default=0.98,
                        help="Minimum acceptable global SSIM (default 0.98)")
    parser.add_argument("--expect-pixel", action="append", default=[], metavar="X,Y:R,G,B",
                        help="The golden's pixel at X,Y must sit within the tolerance of R,G,B "
                             "(8-bit units; repeatable)")
    parser.add_argument("--report", type=Path, default=None, help="Write JSON report here")
    args = parser.parse_args()

    if not args.golden.exists():
        print(f"error: golden not found: {args.golden}", file=sys.stderr)
        return 2
    if not args.candidate.exists():
        print(f"error: candidate not found: {args.candidate}", file=sys.stderr)
        return 2

    try:
        pins = [parse_expect_pixel(spec) for spec in args.expect_pixel]
    except ValueError as exc:
        print(f"error: malformed --expect-pixel spec: {exc}", file=sys.stderr)
        return 2

    a = load_rgba(args.golden)
    b = load_rgba(args.candidate)

    if a.shape != b.shape:
        print(f"error: size mismatch golden={a.shape} candidate={b.shape}", file=sys.stderr)
        if args.report:
            args.report.write_text(json.dumps({
                "name": args.name or args.golden.stem,
                "passed": False,
                "error": "size_mismatch",
                "golden_shape": list(a.shape),
                "candidate_shape": list(b.shape),
            }, indent=2) + "\n")
        return 1

    max_diff = max_abs_diff(a, b)
    mean_diff = mean_abs_diff(a, b)
    ssim = global_ssim(a, b)

    height, width = a.shape[:2]
    expected_pixels = []
    for (x, y), expected in pins:
        if not (0 <= x < width and 0 <= y < height):
            print(f"error: --expect-pixel {x},{y} is outside the golden ({width}x{height})",
                  file=sys.stderr)
            return 2
        observed = tuple(int(round(v * 255)) for v in a[y, x, :3])
        diffs = [abs(o - e) for o, e in zip(observed, expected)]
        expected_pixels.append({
            "x": x, "y": y, "expected": list(expected), "observed": list(observed),
            "passed": max(diffs) <= args.tolerance,
        })
    pixel_failures = [p for p in expected_pixels if not p["passed"]]

    passed = (max_diff <= args.tolerance) and (ssim >= args.ssim_min) and not pixel_failures

    report = {
        "name": args.name or args.golden.stem,
        "golden": str(args.golden),
        "candidate": str(args.candidate),
        "shape": list(a.shape),
        "max_abs_diff": max_diff,
        "mean_abs_diff": mean_diff,
        "ssim": ssim,
        "tolerance": args.tolerance,
        "ssim_min": args.ssim_min,
        "expected_pixels": expected_pixels,
        "passed": passed,
    }

    for p in pixel_failures:
        print(f"[FAIL] {report['name']}: golden pixel {p['x']},{p['y']} is "
              f"{','.join(map(str, p['observed']))}, expected {','.join(map(str, p['expected']))} "
              f"within {args.tolerance}")

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {report['name']}: max-abs-diff={max_diff:.3f} "
          f"mean-abs-diff={mean_diff:.4f} ssim={ssim:.5f} "
          f"(tol={args.tolerance}, ssim_min={args.ssim_min})")

    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote report {args.report}", file=sys.stderr)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
