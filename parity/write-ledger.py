#!/usr/bin/env python3
"""Merge one TouchDesigner parity sweep into the canonical TSV ledger."""

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import runpy
from pathlib import Path


FIELDS = (
    "case", "verdict", "max_abs_diff", "ssim", "tol_max", "tol_ssim",
    "source", "golden",
)
STRICT_TOLERANCE = 2.001
STRICT_SSIM_MIN = 0.98
ALLOWED_PRESERVED_SOURCES = {"3d/mrt/points", "accumulate", "cubemap"}
PRESENT_HERO_PROTOCOL = {
    "reference_sha": "d0ed94ae19cca7328bc7d6b28902712a0838e1a9",
    "size": 256, "time": 0.25, "timestep": 0,
    "reference_backend": "webgl2", "reference_frames": [1, 2, 8],
    "native_frames": 8, "native_samples": [1, 2, 8], "initial_state": "zeroed",
    "fixture_sha256": "e0c083445a843a137e76fbba4572c897a6a0b034956253910dd61b9638493e08",
}
# Multi-frame cases graded by parity/accumulate.sh at frames 1, 2 and 8 from a zeroed start.
ACCUMULATION_CASES = (
    "cellularAutomata", "motionBlur", "convolutionFeedback", "reactionDiffusion",
    "synth3d_cellularAutomata3d", "synth3d_reactionDiffusion3d", "present_hero",
    "buddhabrot", "physical", "filter3d_flow3d", "heightGrid_billboard",
    "heightGrid_billboard_alpha", "heightGrid_pointsRender_perspective",
)
ACCUMULATION_FRAMES = (1, 2, 8)
# Reviewed NEAR frames: (max_abs_diff bound, SSIM minimum, mean_abs_diff limit), each the measured
# value rounded up, with side-by-side review at native size. Every other frame is strict.
#   convolutionFeedback f8: rgba8 feedback convolution re-quantization; max 9, mean 0.1936.
#   physical f1/f2/f8: agents whose summed float16 deposits differ in one pixel; max 3, 4, 4.
ACCUMULATION_NEAR = {
    ("convolutionFeedback", 8): (9.001, 0.9999, 0.194),
    ("physical", 1): (3.001, 0.9999, 0.254),
    ("physical", 2): (4.001, 0.9999, 0.233),
    ("physical", 8): (4.001, 0.9999, 0.178),
}


def accumulation_frame_bound(name, frame):
    """(max_abs_diff bound, SSIM minimum, mean limit or None) for one accumulation frame."""
    if name not in ACCUMULATION_CASES:
        raise ValueError("unsupported accumulation case")
    return ACCUMULATION_NEAR.get((name, frame), (STRICT_TOLERANCE, STRICT_SSIM_MIN, None))


def accumulation_bound(name):
    """The case's aggregate (max_abs_diff bound, SSIM minimum) across its graded frames."""
    bounds = [accumulation_frame_bound(name, frame) for frame in ACCUMULATION_FRAMES]
    return max(bound[0] for bound in bounds), min(bound[1] for bound in bounds)
CUBEMAP_CASES = {"synth3d_renderCubemap3d", "synth3d_renderCubemapSurface"}
CUBEMAP_PROTOCOL = {"size": 256, "time": 0.25, "backend": "webgl2",
                    "face_order": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
                    "cross_cells": [[0, 1], [2, 1], [1, 0], [1, 2], [1, 1], [3, 1]]}


def candidate_sources(root, name="cellularAutomata"):
    if name not in ACCUMULATION_CASES:
        raise ValueError("unsupported accumulation case")
    if name == "present_hero":
        override = root / "parity" / "corpus" / "present_hero.dsl"
        if override.exists() or override.is_symlink():
            raise ValueError("The hero protocol does not permit a corpus override.")
        pin = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                        (root / "scripts" / "test").read_text(), re.M)
        if not pin or pin.group(1) != PRESENT_HERO_PROTOCOL["reference_sha"]:
            raise ValueError("The hero authority does not match the visual policy.")
    runtime = root / "td" / "noisemaker"
    entries = list(runtime.rglob("*"))
    if runtime.is_symlink() or any(path.is_symlink() for path in entries):
        raise ValueError("candidate runtime contains a symbolic link")
    paths = [path for path in entries if path.is_file()
             and "__pycache__" not in path.parts and path.suffix != ".pyc"]
    if not paths:
        raise ValueError("candidate runtime sources are missing")
    paths.extend(root / name for name in (
        "td/parity_evolve.py", "td/build_evolve_toe.py", "parity/evolve.sh",
        "parity/accumulate.sh", "parity/pylib.sh", "parity/compare.py", "parity/write-ledger.py",
        f"parity/programs/{name}.dsl",
    ))
    if name == "present_hero":
        paths.append(root / "parity" / "batch-golden.mjs")
    if any(path.is_symlink() for path in paths):
        raise ValueError("candidate sources contain a symbolic link")
    sources = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(paths)}
    if name == "present_hero" and sources["parity/programs/present_hero.dsl"] != PRESENT_HERO_PROTOCOL["fixture_sha256"]:
        raise ValueError("The hero fixture does not match the visual policy.")
    return sources


def frame_pixel_counts(golden, candidate, details=False):
    from io import BytesIO
    import numpy as np
    from PIL import Image

    arrays = [np.asarray(Image.open(BytesIO(data)).convert("RGBA"), dtype=np.int16)
              for data in (golden, candidate)]
    if any(array.shape != (256, 256, 4) for array in arrays):
        raise ValueError("unexpected accumulation capture shape")
    difference = np.abs(arrays[0] - arrays[1])
    counts = {
        "pixels": int(difference.shape[0] * difference.shape[1]),
        "channels": int(difference.size),
        "different_pixels": int(np.any(difference != 0, axis=2).sum()),
        "different_channels": int((difference != 0).sum()),
        **{f"{kind}_over_{limit}": int((np.any(difference > limit, axis=2)
            if kind == "pixels" else difference > limit).sum())
           for limit in (1, 2) for kind in ("pixels", "channels")},
    }
    if details:
        maximum = difference.max(axis=2)
        y, x, channel = np.argwhere(difference == difference.max())[0]
        counts.update(
            pixels_over_16=int((maximum > 16).sum()),
            channels_over_16=int((difference > 16).sum()),
            pixel_max_histogram={str(value): int((maximum == value).sum()) for value in np.unique(maximum)},
            channel_abs_histogram={str(value): int((difference == value).sum()) for value in np.unique(difference)},
            peak={"origin": "top-left", "x": int(x), "y": int(y), "channel": int(channel),
                  "golden_rgba": arrays[0][y, x].tolist(), "candidate_rgba": arrays[1][y, x].tolist()},
        )
    return counts


def cubemap_sources(root, name):
    if name not in CUBEMAP_CASES:
        raise ValueError("unsupported cubemap case")
    runtime = root / "td/noisemaker"
    entries = list(runtime.rglob("*"))
    if runtime.is_symlink() or any(path.is_symlink() for path in entries):
        raise ValueError("candidate runtime contains a symbolic link")
    paths = [path for path in entries if path.is_file()
             and "__pycache__" not in path.parts and path.suffix != ".pyc"]
    if not paths:
        raise ValueError("candidate runtime sources are missing")
    paths.extend(root / relative for relative in (
        "td/cubemap_bake.py", "td/build_points_probe_toe.py", "parity/cubemap.sh",
        "parity/pylib.sh",
        "parity/cube_cross.py", "parity/export-and-render.mjs", "parity/harness-port.mjs",
        "parity/compare.py", "parity/write-ledger.py", "tools/export-graph.mjs",
        "tools/reference-root.mjs", "scripts/test",
        f"parity/programs/{name}.dsl",
    ))
    if any(path.is_symlink() for path in paths):
        raise ValueError("candidate sources contain a symbolic link")
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def cubemap_row(root, name, report_path, tolerance, ssim_min):
    row = {"case": name, "verdict": "FAIL", "max_abs_diff": "-", "ssim": "-",
           "tol_max": str(tolerance), "tol_ssim": str(ssim_min), "source": "cubemap", "golden": str(report_path)}
    try:
        evidence = json.loads(report_path.read_text())
        pin = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                        (root / "scripts/test").read_text(), re.M).group(1)
        outputs = evidence["outputs"]
        if (name not in CUBEMAP_CASES or evidence["case"] != name
                or evidence["reference_sha"] != pin or evidence["protocol"] != CUBEMAP_PROTOCOL
                or evidence["candidate_sources"] != cubemap_sources(root, name)
                or tolerance != STRICT_TOLERANCE or ssim_min != STRICT_SSIM_MIN
                or [item["output"] for item in outputs] != [f"face{face}" for face in range(6)] + ["cross"]):
            return row
        from io import BytesIO
        import numpy as np

        compare = runpy.run_path(str(root / "parity/compare.py"))
        arrays = {kind: [] for kind in ("golden", "candidate")}
        for item in outputs:
            report = item["report"]
            shape = [768, 1024, 4] if item["output"] == "cross" else [256, 256, 4]
            if (report["name"] != f'{name}.{item["output"]}' or report["passed"] is not True
                    or report["shape"] != shape or report["tolerance"] != STRICT_TOLERANCE
                    or report["ssim_min"] != STRICT_SSIM_MIN
                    or not all(math.isfinite(report[key]) for key in ("max_abs_diff", "mean_abs_diff", "ssim"))
                    or not 0 <= report["max_abs_diff"] <= STRICT_TOLERANCE
                    or not 0 <= report["mean_abs_diff"] <= report["max_abs_diff"]
                    or not STRICT_SSIM_MIN <= report["ssim"] <= 1.000001):
                return row
            for kind in arrays:
                path = Path(report[kind])
                if path.is_symlink() or path.name != f'{name}.{item["output"]}.{kind}.png':
                    return row
                capture = path.read_bytes()
                if hashlib.sha256(capture).hexdigest() != item[f"{kind}_sha256"]:
                    return row
                array = compare["load_rgba"](BytesIO(capture))
                if list(array.shape) != shape:
                    return row
                arrays[kind].append(array)
            pair = [arrays[kind][-1] for kind in arrays]
            for key, function in (("max_abs_diff", "max_abs_diff"), ("mean_abs_diff", "mean_abs_diff"), ("ssim", "global_ssim")):
                if not math.isclose(report[key], compare[function](*pair), rel_tol=0, abs_tol=0.000001):
                    return row
        for captures in arrays.values():
            cross = np.zeros_like(captures[-1])
            for face, (x, y) in enumerate(CUBEMAP_PROTOCOL["cross_cells"]):
                cross[y * 256:(y + 1) * 256, x * 256:(x + 1) * 256] = captures[face]
            if not np.array_equal(cross, captures[-1]):
                return row
        row.update(verdict="PASS", max_abs_diff=str(max(item["report"]["max_abs_diff"] for item in outputs)),
                   ssim=str(min(item["report"]["ssim"] for item in outputs)), golden=outputs[-1]["report"]["golden"])
    except (OSError, AttributeError, ImportError, IndexError, KeyError, TypeError, ValueError):
        pass
    return row


def load_existing(path):
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"unexpected ledger header: {reader.fieldnames}")
        return {row["case"]: row for row in reader}


def report_row(name, report_path, tolerance, ssim_min):
    try:
        report = json.loads(report_path.read_text())
        max_diff = float(report["max_abs_diff"])
        ssim = float(report["ssim"])
        report_matches = (
            report.get("name") == name
            and float(report.get("tolerance")) == tolerance
            and float(report.get("ssim_min")) == ssim_min
        )
        accepted = (
            report_matches
            and bool(report.get("passed"))
            and max_diff <= tolerance
            and ssim >= ssim_min
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        max_diff = None
        ssim = None
        accepted = False
    verdict = "FAIL"
    if accepted:
        verdict = (
            "PASS"
            if max_diff <= STRICT_TOLERANCE and ssim >= STRICT_SSIM_MIN
            else "NEAR"
        )
    return {
        "case": name,
        "verdict": verdict,
        "max_abs_diff": "-" if max_diff is None else str(max_diff),
        "ssim": "-" if ssim is None else str(ssim),
        "tol_max": str(tolerance),
        "tol_ssim": str(ssim_min),
        "source": "sweep",
        "golden": f"parity/out/{name}.golden.png",
    }


def accumulate_row(root, name, report_path, tolerance, ssim_min):
    row = {"case": name, "verdict": "FAIL", "max_abs_diff": "-", "ssim": "-",
           "tol_max": str(tolerance), "tol_ssim": str(ssim_min),
           "source": "accumulate", "golden": str(report_path)}
    try:
        evidence = json.loads(report_path.read_text())
        pin = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                        (root / "scripts" / "test").read_text(), re.M).group(1)
        frames = evidence["frames"]
        if (name not in ACCUMULATION_CASES
                or evidence["case"] != name
                or evidence["reference_sha"] != pin
                or evidence["candidate_sources"] != candidate_sources(root, name)
                or [item["frame"] for item in frames] != list(ACCUMULATION_FRAMES)
                or (tolerance, ssim_min) != accumulation_bound(name)):
            return row
        if name == "present_hero" and (
                evidence.get("protocol") != PRESENT_HERO_PROTOCOL
                or evidence["candidate_sources"]["parity/programs/present_hero.dsl"] != PRESENT_HERO_PROTOCOL["fixture_sha256"]):
            return row
        for item in frames:
            report = item["report"]
            frame_tolerance, frame_ssim, mean_limit = accumulation_frame_bound(name, item["frame"])
            if (report["name"] != f'{name}.f{item["frame"]:04d}'
                    or report["passed"] is not True
                    or report["tolerance"] != frame_tolerance
                    or report["ssim_min"] != frame_ssim
                    or report["shape"] != [256, 256, 4]
                    or not math.isfinite(report["max_abs_diff"])
                    or not math.isfinite(report["mean_abs_diff"])
                    or not math.isfinite(report["ssim"])
                    or not 0 <= report["max_abs_diff"] <= frame_tolerance
                    or not 0 <= report["mean_abs_diff"] <= report["max_abs_diff"]
                    or not frame_ssim <= report["ssim"] <= 1):
                return row
            captures = {kind: Path(report[kind]).read_bytes() for kind in ("golden", "candidate")}
            for kind in ("golden", "candidate"):
                if hashlib.sha256(captures[kind]).hexdigest() != item[f"{kind}_sha256"]:
                    return row
            counts = item["pixel_counts"]
            expected_counts = frame_pixel_counts(**captures, details=True)
            if json.dumps(counts, sort_keys=True) != json.dumps(expected_counts, sort_keys=True):
                return row
            histogram = expected_counts["channel_abs_histogram"]
            mean = sum(int(value) * count for value, count in histogram.items()) / expected_counts["channels"]
            if (abs(report["max_abs_diff"] - max(map(int, histogram))) > 0.001
                    or abs(report["mean_abs_diff"] - mean) > 0.001
                    or (mean_limit is not None and mean > mean_limit)):
                return row
        max_diff = max(item["report"]["max_abs_diff"] for item in frames)
        row.update(verdict="PASS" if max_diff <= STRICT_TOLERANCE else "NEAR", max_abs_diff=str(max_diff),
                   ssim=str(min(item["report"]["ssim"] for item in frames)),
                   golden=frames[-1]["report"]["golden"])
    except (OSError, AttributeError, KeyError, TypeError, ValueError):
        pass
    return row


def ledger_binding(root):
    """The source SHA and pinned authority a ledger was produced at."""
    try:
        pin_match = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                              (root / "scripts" / "test").read_text(), re.M)
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True)
    except OSError as error:
        raise ValueError("cannot bind the ledger: %s" % error) from error
    if not pin_match:
        raise ValueError("cannot bind the ledger: no NM_REFERENCE_SHA_PINNED in scripts/test")
    if head.returncode != 0:
        raise ValueError("cannot bind the ledger: %s" % head.stderr.strip()[:200])
    return {"source": head.stdout.strip(), "pin": pin_match.group(1)}


def main():
    if sys.argv[1:2] == ["--accumulation-cases"]:
        print(" ".join(ACCUMULATION_CASES))
        return
    if sys.argv[1:2] == ["--accumulation-bound"]:
        name = sys.argv[2]
        if len(sys.argv) > 3:
            print("%s %s" % accumulation_frame_bound(name, int(sys.argv[3]))[:2])
        else:
            print("%s %s" % accumulation_bound(name))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--expected-set", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    rows = load_existing(output)
    expected = None
    if args.expected_set:
        expected_names = args.expected_set.read_text().split()
        if len(expected_names) != len(set(expected_names)):
            raise ValueError("duplicate case in expected sweep set")
        expected = set(expected_names)
        stale = sorted(
            name for name, row in rows.items()
            if name not in expected and row["source"] not in ALLOWED_PRESERVED_SOURCES
        )
        if stale:
            raise ValueError(f"unvalidated stale ledger rows: {', '.join(stale)}")
        rows = {
            name: row for name, row in rows.items()
            if name in expected or row["source"] in ALLOWED_PRESERVED_SOURCES
        }
    updated = set()

    with args.results.open(newline="") as handle:
        for fields in csv.reader(handle, delimiter="\t"):
            if not fields:
                continue
            if len(fields) != 5:
                raise ValueError(f"malformed sweep result: {fields}")
            name, kind, detail, tolerance_text, ssim_text = fields
            if name in updated:
                raise ValueError(f"duplicate sweep result: {name}")
            updated.add(name)
            if kind == "REPORT":
                rows[name] = report_row(
                    name, Path(detail), float(tolerance_text), float(ssim_text)
                )
            elif kind == "ACCUMULATE":
                rows[name] = accumulate_row(
                    args.root, name, Path(detail), float(tolerance_text), float(ssim_text)
                )
            elif kind == "CUBEMAP":
                rows[name] = cubemap_row(
                    args.root, name, Path(detail), float(tolerance_text), float(ssim_text)
                )
            elif kind == "DEFER":
                rows[name] = {
                    "case": name,
                    "verdict": "DEFER",
                    "max_abs_diff": "-",
                    "ssim": "-",
                    "tol_max": "-",
                    "tol_ssim": "-",
                    "source": "accumulate.sh",
                    "golden": detail,
                }
            elif kind == "FAIL":
                rows[name] = {
                    "case": name,
                    "verdict": "FAIL",
                    "max_abs_diff": "-",
                    "ssim": "-",
                    "tol_max": tolerance_text,
                    "tol_ssim": ssim_text,
                    "source": "sweep",
                    "golden": detail,
                }
            else:
                raise ValueError(f"unknown sweep result kind: {kind}")

    if expected is not None and updated != expected:
        missing = sorted(expected - updated)
        unexpected = sorted(updated - expected)
        details = []
        if missing:
            details.append(f"missing current sweep result: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected current sweep result: {', '.join(unexpected)}")
        raise ValueError("; ".join(details))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[name] for name in sorted(rows))
    temporary.replace(output)
    # Bind the ledger to the source it graded and the pin its goldens came from, so a
    # summary can never read stale rows as a pass at a different source. When the
    # binding cannot be established, say so and leave the ledger unbound; the summary
    # then refuses the unbound ledger instead of trusting it.
    try:
        binding = ledger_binding(args.root)
    except ValueError as error:
        print("write-ledger: %s" % error, file=sys.stderr)
    else:
        binding_path = output.with_name(output.name + ".binding.json")
        binding_tmp = binding_path.with_name(binding_path.name + ".tmp")
        binding_tmp.write_text(json.dumps(binding, sort_keys=True) + "\n")
        binding_tmp.replace(binding_path)
    if any(row["verdict"] == "FAIL" for row in rows.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
