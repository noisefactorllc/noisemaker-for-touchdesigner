#!/usr/bin/env python3
"""Merge one TouchDesigner parity sweep into the canonical TSV ledger."""

import argparse
import csv
import json
from pathlib import Path


FIELDS = (
    "case", "verdict", "max_abs_diff", "ssim", "tol_max", "tol_ssim",
    "source", "golden",
)
STRICT_TOLERANCE = 2.001
STRICT_SSIM_MIN = 0.98
ALLOWED_PRESERVED_SOURCES = {"3d/mrt/points", "accumulate", "cubemap"}


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
