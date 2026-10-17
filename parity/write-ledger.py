#!/usr/bin/env python3
"""Merge one TouchDesigner parity sweep into the canonical TSV ledger."""

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


FIELDS = (
    "case", "verdict", "max_abs_diff", "ssim", "tol_max", "tol_ssim",
    "source", "golden",
)
STRICT_TOLERANCE = 2.001
STRICT_SSIM_MIN = 0.98
ALLOWED_PRESERVED_SOURCES = {"3d/mrt/points", "accumulate", "cubemap"}


def candidate_sources(root, name="cellularAutomata"):
    if name not in ("cellularAutomata", "motionBlur", "convolutionFeedback", "synth3d_cellularAutomata3d", "reactionDiffusion"):
        raise ValueError("unsupported accumulation case")
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
        "parity/accumulate.sh", "parity/compare.py", "parity/write-ledger.py",
        f"parity/programs/{name}.dsl",
    ))
    if any(path.is_symlink() for path in paths):
        raise ValueError("candidate sources contain a symbolic link")
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


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
        expected_tolerance = {"motionBlur": 3.001, "convolutionFeedback": 41.001,
                              "synth3d_cellularAutomata3d": 178.001, "reactionDiffusion": 41.001}.get(name, STRICT_TOLERANCE)
        if (name not in ("cellularAutomata", "motionBlur", "convolutionFeedback", "synth3d_cellularAutomata3d", "reactionDiffusion")
                or evidence["case"] != name
                or evidence["reference_sha"] != pin
                or evidence["candidate_sources"] != candidate_sources(root, name)
                or [item["frame"] for item in frames] != [1, 2, 8]
                or tolerance != expected_tolerance or ssim_min != STRICT_SSIM_MIN):
            return row
        for item in frames:
            report = item["report"]
            frame_tolerance, frame_ssim = (3.001, 0.9999) if name == "motionBlur" and item["frame"] == 8 else (
                STRICT_TOLERANCE, STRICT_SSIM_MIN)
            if name == "convolutionFeedback" and item["frame"] == 8:
                frame_tolerance, frame_ssim = 41.001, 0.9948
            if name == "synth3d_cellularAutomata3d" and item["frame"] == 8:
                frame_tolerance, frame_ssim = 178.001, 0.9968
            if name == "reactionDiffusion" and item["frame"] == 8:
                frame_tolerance, frame_ssim = 41.001, 0.9879
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
            if name in ("motionBlur", "convolutionFeedback", "synth3d_cellularAutomata3d", "reactionDiffusion"):
                counts = item["pixel_counts"]
                detailed = name in ("convolutionFeedback", "synth3d_cellularAutomata3d", "reactionDiffusion")
                expected_counts = frame_pixel_counts(**captures, details=detailed)
                if json.dumps(counts, sort_keys=True) != json.dumps(expected_counts, sort_keys=True):
                    return row
                if detailed:
                    histogram = expected_counts["channel_abs_histogram"]
                    mean = sum(int(value) * count for value, count in histogram.items()) / expected_counts["channels"]
                    maximum = max(map(int, histogram))
                    if (abs(report["max_abs_diff"] - maximum) > 0.001
                            or abs(report["mean_abs_diff"] - mean) > 0.001
                            or (item["frame"] == 8 and mean > {"convolutionFeedback": 3.8,
                                "synth3d_cellularAutomata3d": 0.41, "reactionDiffusion": 3.92}[name])):
                        return row
        max_diff = max(item["report"]["max_abs_diff"] for item in frames)
        row.update(verdict="PASS" if max_diff <= STRICT_TOLERANCE else "NEAR", max_abs_diff=str(max_diff),
                   ssim=str(min(item["report"]["ssim"] for item in frames)),
                   golden=frames[-1]["report"]["golden"])
    except (OSError, AttributeError, KeyError, TypeError, ValueError):
        pass
    return row


def main():
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
    if any(row["verdict"] == "FAIL" for row in rows.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
