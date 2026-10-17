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


def candidate_sources(root):
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
        "parity/programs/cellularAutomata.dsl",
    ))
    if any(path.is_symlink() for path in paths):
        raise ValueError("candidate sources contain a symbolic link")
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


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
        if (name != "cellularAutomata" or evidence["case"] != name
                or evidence["reference_sha"] != pin
                or evidence["candidate_sources"] != candidate_sources(root)
                or [item["frame"] for item in frames] != [1, 2, 8]
                or tolerance != STRICT_TOLERANCE or ssim_min != STRICT_SSIM_MIN):
            return row
        for item in frames:
            report = item["report"]
            if (report["name"] != f'{name}.f{item["frame"]:04d}'
                    or report["passed"] is not True
                    or report["tolerance"] != STRICT_TOLERANCE
                    or report["ssim_min"] != STRICT_SSIM_MIN
                    or report["shape"] != [256, 256, 4]
                    or not math.isfinite(report["max_abs_diff"])
                    or not math.isfinite(report["mean_abs_diff"])
                    or not math.isfinite(report["ssim"])
                    or not 0 <= report["max_abs_diff"] <= STRICT_TOLERANCE
                    or not 0 <= report["mean_abs_diff"] <= report["max_abs_diff"]
                    or not STRICT_SSIM_MIN <= report["ssim"] <= 1):
                return row
            for kind in ("golden", "candidate"):
                if hashlib.sha256(Path(report[kind]).read_bytes()).hexdigest() != item[f"{kind}_sha256"]:
                    return row
        row.update(verdict="PASS", max_abs_diff=str(max(item["report"]["max_abs_diff"] for item in frames)),
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
