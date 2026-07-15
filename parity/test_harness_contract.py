#!/usr/bin/env python3
"""App-free regressions for parity gate failure propagation."""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]


def load_stage_coverage():
    spec = importlib.util.spec_from_file_location(
        "nm_td_stage_coverage", REPO / "parity" / "stage_coverage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessContractTests(unittest.TestCase):
    def test_batch_golden_sets_nonzero_exit_when_any_item_fails(self):
        source = (REPO / "parity" / "batch-golden.mjs").read_text()
        self.assertRegex(source, r"if \(fail > 0\) process\.exitCode = 1")

    def test_stage_removes_stale_goldens_and_propagates_batch_failure(self):
        stage = load_stage_coverage()
        with tempfile.TemporaryDirectory(prefix="nm-td-stage-") as temp:
            root = Path(temp)
            out = root / "out"
            programs = root / "programs"
            out.mkdir()
            programs.mkdir()
            (programs / "chrome.dsl").write_text("noise().chrome().write(o0)\n")
            stale = out / "chrome.golden.png"
            stale.touch()
            stage.OUT = str(out)
            stage.PROGRAMS = str(programs)
            stage.REPO = str(root)

            def failed_run(*args, **kwargs):
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(1, args[0])
                return subprocess.CompletedProcess(args[0], 1)

            with mock.patch.object(stage.subprocess, "run", side_effect=failed_run):
                with self.assertRaises(subprocess.CalledProcessError):
                    stage.render_goldens(["chrome"])
            self.assertFalse(stale.exists())

    def test_compare_only_sweep_counts_a_missing_golden_as_failure(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-sweep-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                source = REPO / "parity" / helper
                if source.exists():
                    shutil.copy2(source, parity / helper)
            (parity / "programs").mkdir()
            (parity / "programs" / "missingGolden.dsl").write_text(
                "noise().chrome().write(o0)\n"
            )
            (out / "_render_set.txt").write_text("missingGolden\n")

            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--compare-only"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("no golden", result.stdout.lower())

    def test_compare_only_sweep_refreshes_machine_ledger_and_preserves_other_evidence(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-ledger-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            (parity / "programs").mkdir()
            for name in ("adjust", "chrome", "cellularAutomata"):
                (parity / "programs" / f"{name}.dsl").write_text(
                    f"noise().{name}().write(o0)\n"
                )
            (out / "_render_set.txt").write_text(
                "adjust chrome cellularAutomata\n"
            )
            for name in ("adjust", "chrome"):
                (out / f"{name}.golden.png").touch()
                (out / f"{name}.candidate.png").touch()
            (parity / "ledger.tsv").write_text(
                "case\tverdict\tmax_abs_diff\tssim\ttol_max\ttol_ssim\tsource\tgolden\n"
                "legacy3d\tDEFER\t-\t-\t-\t-\t3d/mrt/points\tseparate evidence\n"
                "adjust\tPASS\t99\t0\t100\t0\tstale\tstale.png\n"
            )
            (parity / "compare.py").write_text(
                "import argparse,json\n"
                "p=argparse.ArgumentParser(); p.add_argument('golden'); p.add_argument('candidate'); "
                "p.add_argument('--name'); p.add_argument('--tolerance',type=float); "
                "p.add_argument('--ssim-min',type=float); p.add_argument('--report'); a=p.parse_args()\n"
                "diff=1.0 if a.name == 'adjust' else 32.0\n"
                "json.dump({'name':a.name,'max_abs_diff':diff,'ssim':0.9999,'tolerance':a.tolerance,"
                "'ssim_min':a.ssim_min,'passed':True},open(a.report,'w'))\n"
            )

            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--compare-only"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            lines = (parity / "ledger.tsv").read_text().splitlines()
            rows = {
                row.split("\t", 1)[0]: row.split("\t")
                for row in lines[1:]
            }
            self.assertEqual(rows["adjust"][1:3], ["PASS", "1.0"])
            self.assertEqual(rows["chrome"][1:3], ["NEAR", "32.0"])
            self.assertEqual(rows["cellularAutomata"][1], "DEFER")
            self.assertEqual(rows["legacy3d"][1], "DEFER")

    def test_renderer_nonzero_with_a_current_candidate_cannot_pass(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-render-status-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            (parity / "programs").mkdir()
            (parity / "programs" / "adjust.dsl").write_text(
                "noise().adjust().write(o0)\n"
            )
            (out / "_render_set.txt").write_text("adjust\n")
            (out / "adjust.golden.png").touch()
            runner = parity / "run.sh"
            runner.write_text(
                "#!/usr/bin/env bash\n"
                "touch parity/out/adjust.candidate.png\n"
                "exit 7\n"
            )
            runner.chmod(0o755)
            (parity / "compare.py").write_text(
                "import argparse,json\n"
                "p=argparse.ArgumentParser(); p.add_argument('golden'); p.add_argument('candidate'); "
                "p.add_argument('--name'); p.add_argument('--tolerance',type=float); "
                "p.add_argument('--ssim-min',type=float); p.add_argument('--report'); a=p.parse_args()\n"
                "json.dump({'name':a.name,'max_abs_diff':0,'ssim':1,'tolerance':a.tolerance,"
                "'ssim_min':a.ssim_min,'passed':True},open(a.report,'w'))\n"
            )

            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--no-stage"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = (parity / "ledger.tsv").read_text().splitlines()
            self.assertEqual(rows[1].split("\t")[1], "FAIL")

    def test_compare_only_sweep_rejects_a_truncated_nonempty_render_set(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-truncated-set-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            programs = parity / "programs"
            out.mkdir(parents=True)
            programs.mkdir()
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            for name in ("adjust", "chrome"):
                (programs / f"{name}.dsl").write_text(
                    f"noise().{name}().write(o0)\n"
                )
            (out / "_render_set.txt").write_text("adjust\n")
            (out / "adjust.golden.png").touch()
            (out / "adjust.candidate.png").touch()
            (parity / "compare.py").write_text(
                "import argparse,json\n"
                "p=argparse.ArgumentParser(); p.add_argument('golden'); p.add_argument('candidate'); "
                "p.add_argument('--name'); p.add_argument('--tolerance',type=float); "
                "p.add_argument('--ssim-min',type=float); p.add_argument('--report'); a=p.parse_args()\n"
                "json.dump({'name':a.name,'max_abs_diff':0,'ssim':1,'tolerance':a.tolerance,"
                "'ssim_min':a.ssim_min,'passed':True},open(a.report,'w'))\n"
            )

            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--compare-only"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not match the expected staged universe", result.stdout)

    def test_ledger_writer_requires_one_current_result_per_expected_case(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-ledger-universe-") as temp:
            root = Path(temp)
            parity = root / "parity"
            parity.mkdir()
            shutil.copy2(REPO / "parity" / "write-ledger.py", parity / "write-ledger.py")
            expected = root / "expected.txt"
            expected.write_text("adjust chrome\n")
            results = root / "results.tsv"
            results.write_text("adjust\tFAIL\tinjected\t2.001\t0.98\n")

            result = subprocess.run([
                "python3", str(parity / "write-ledger.py"),
                "--root", str(root), "--results", str(results),
                "--expected-set", str(expected), "--output", "parity/ledger.tsv",
            ], capture_output=True, text=True)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("missing current sweep result", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
