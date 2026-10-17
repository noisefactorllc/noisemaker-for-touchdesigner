#!/usr/bin/env python3
"""App-free regressions for parity gate failure propagation."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
    def test_candidate_binding_rejects_a_symlinked_runtime_file(self):
        spec = importlib.util.spec_from_file_location("nm_td_ledger", REPO / "parity" / "write-ledger.py")
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        target = REPO / "td" / "noisemaker" / "runtime" / "nm_renderer.py"
        original = Path.is_symlink
        with mock.patch.object(Path, "is_symlink", autospec=True,
                               side_effect=lambda path: path == target or original(path)):
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                ledger.candidate_sources(REPO)

    def test_sweep_rejects_failed_cellular_accumulation_instead_of_deferring(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-accumulate-status-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            (parity / "programs").mkdir()
            (parity / "programs" / "cellularAutomata.dsl").write_text("cellularAutomata().write(o0)\n")
            (out / "_render_set.txt").write_text("cellularAutomata\n")
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            (parity / "run.sh").write_text("touch single-render-called\nexit 0\n")
            (parity / "accumulate.sh").write_text("touch accumulation-called\nexit 7\n")
            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--no-stage"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / "accumulation-called").exists())
            self.assertFalse((root / "single-render-called").exists())
            self.assertIn("cellularAutomata\tFAIL\t", (out / "ledger.tsv").read_text())

    def test_sweep_rejects_failed_motion_accumulation_instead_of_deferring(self):
        with tempfile.TemporaryDirectory(prefix="nm-td-motion-status-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            (parity / "programs").mkdir()
            (parity / "programs" / "motionBlur.dsl").write_text("noise().motionBlur().write(o0)\n")
            (out / "_render_set.txt").write_text("motionBlur\n")
            for helper in ("sweep.sh", "write-ledger.py", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            (parity / "run.sh").write_text("touch single-render-called\nexit 0\n")
            (parity / "accumulate.sh").write_text("touch accumulation-called\nexit 7\n")
            result = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--no-stage"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / "accumulation-called").exists())
            self.assertFalse((root / "single-render-called").exists())
            self.assertIn("motionBlur\tFAIL\t", (out / "ledger.tsv").read_text())

    def test_selected_cellular_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("cellularAutomata")

    def test_selected_motion_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("motionBlur")

    def check_selected_accumulation(self, name):
        with tempfile.TemporaryDirectory(prefix="nm-td-accumulate-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            (parity / "programs").mkdir()
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            for helper in ("accumulate.sh", "write-ledger.py", "sweep.sh", "stage_coverage.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            (root / "td" / "noisemaker" / "runtime").mkdir(parents=True)
            runtime_source = root / "td" / "noisemaker" / "runtime" / "probe.py"
            runtime_source.write_text("version = 1\n")
            for helper in ("parity_evolve.py", "build_evolve_toe.py"):
                shutil.copy2(REPO / "td" / helper, root / "td" / helper)
            shutil.copy2(REPO / "scripts" / "parity-summary", root / "scripts" / "parity-summary")
            (root / "scripts" / "test").write_text('NM_REFERENCE_SHA_PINNED="' + "a" * 40 + '"\n')
            (out / "_render_set.txt").write_text(name + "\n")
            (parity / "programs" / f"{name}.dsl").write_text(f"{name}().write(o0)\n")
            node = root / "bin" / "node"
            node.write_text(
                "#!" + sys.executable + "\n"
                "import pathlib,sys\nfrom PIL import Image\n"
                "manifest=pathlib.Path(sys.argv[2]).read_text().splitlines()\n"
                f"assert len(manifest)==1 and manifest[0].split()[0]=={name!r}\n"
                "out=pathlib.Path(sys.argv[3]); out.mkdir(parents=True)\n"
                f"Image.new('RGBA',(256,256),(255,255,255,255)).save(out/{name + '.golden.png'!r})\n"
                f"(out/{name + '.graph.json'!r}).write_text('{{}}')\n"
                "import os\n"
                "if os.environ.get('TEST_DIRTY_AFTER_GOLDENS'):\n"
                "    pathlib.Path(os.environ['TEST_REFERENCE_DIRTY_MARKER']).touch()\n"
            )
            node.chmod(0o755)
            git = root / "bin" / "git"
            git.write_text(
                "#!" + sys.executable + "\nimport os,pathlib,sys\n"
                "if sys.argv[-1]=='HEAD': print(os.environ['TEST_REFERENCE_HEAD'])\n"
                "elif sys.argv[-2:]==['status','--porcelain']:\n"
                "    dirty=os.environ.get('TEST_REFERENCE_STATUS','')\n"
                "    if pathlib.Path(os.environ['TEST_REFERENCE_DIRTY_MARKER']).exists(): dirty=' M shader.js'\n"
                "    print(dirty,end='')\n"
                "else: sys.exit(29)\n"
            )
            git.chmod(0o755)
            (parity / "evolve.sh").write_text(
                f'test "$1" = {name} || exit 19\n'
                'touch evolve-called\n'
                + sys.executable + " - <<'PY'\n"
                "from pathlib import Path\nfrom PIL import Image\n"
                f"name={name!r}\n"
                "for frame in (1,2,8):\n"
                "    rgba=(252,252,252,253) if name=='motionBlur' and frame==8 else (254,254,254,255)\n"
                "    Image.new('RGBA',(256,256),rgba).save(Path('parity/out')/f'{name}.f{frame:04d}.candidate.png')\n"
                "PY\n"
            )
            (parity / "compare.py").write_text(
                "import argparse,json\n"
                "p=argparse.ArgumentParser(); p.add_argument('golden'); p.add_argument('candidate'); "
                "p.add_argument('--name'); p.add_argument('--tolerance',type=float); "
                "p.add_argument('--ssim-min',type=float); p.add_argument('--report'); a=p.parse_args()\n"
                "assert a.report\n"
                "diff=3.0 if a.name=='motionBlur.f0008' else 1.0\n"
                "json.dump({'name':a.name,'golden':a.golden,'candidate':a.candidate,'shape':[256,256,4],"
                "'max_abs_diff':diff,'mean_abs_diff':0.125,'ssim':0.99992,'tolerance':a.tolerance,"
                "'ssim_min':a.ssim_min,'passed':True},open(a.report,'w'))\n"
            )
            report = root / f"{name}.json"
            environment = dict(os.environ, PATH=os.pathsep.join((str(root / "bin"),
                               str(Path(sys.executable).parent), os.environ["PATH"])),
                               NM_REFERENCE_SHA="a" * 40, NM_REFERENCE_ROOT=str(root / "authority"),
                               TEST_REFERENCE_HEAD="a" * 40,
                               TEST_REFERENCE_DIRTY_MARKER=str(root / "reference-dirty"))
            result = subprocess.run(
                ["bash", str(parity / "accumulate.sh"), "--effect", name, "--report", str(report)],
                cwd=root, capture_output=True, text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence["reference_sha"], "a" * 40)
            self.assertEqual([frame["frame"] for frame in evidence["frames"]], [1, 2, 8])
            self.assertEqual([frame["report"]["mean_abs_diff"] for frame in evidence["frames"]], [0.125] * 3)
            self.assertIn("candidate_sources", evidence)
            if name == "motionBlur":
                self.assertEqual(evidence["frames"][-1]["report"]["tolerance"], 3.001)
                self.assertEqual(evidence["frames"][-1]["report"]["ssim_min"], 0.9999)
                self.assertEqual(evidence["frames"][-1]["pixel_counts"], {
                    "pixels": 65536, "channels": 262144, "different_pixels": 65536,
                    "different_channels": 262144, "pixels_over_1": 65536,
                    "channels_over_1": 262144, "pixels_over_2": 65536, "channels_over_2": 196608,
                })
            mismatch = subprocess.run(result.args, cwd=root, capture_output=True, text=True,
                                      env=dict(environment, TEST_REFERENCE_HEAD="b" * 40))
            self.assertNotEqual(mismatch.returncode, 0, mismatch.stdout + mismatch.stderr)
            for dirty_at in ("before", "after"):
                with self.subTest(dirty_at=dirty_at):
                    (root / "evolve-called").unlink(missing_ok=True)
                    dirty_environment = dict(environment)
                    if dirty_at == "before":
                        dirty_environment["TEST_REFERENCE_STATUS"] = " M shader.js"
                    else:
                        dirty_environment["TEST_DIRTY_AFTER_GOLDENS"] = "1"
                    dirty = subprocess.run(result.args, cwd=root, capture_output=True, text=True,
                                           env=dirty_environment)
                    self.assertNotEqual(dirty.returncode, 0, dirty.stdout + dirty.stderr)
                    self.assertFalse((root / "evolve-called").exists())
            report.write_text(json.dumps(evidence))
            results = root / "results.tsv"
            tolerance = 3.001 if name == "motionBlur" else 2.001
            results.write_text(f"{name}\tACCUMULATE\t{report}\t{tolerance}\t0.98\n")
            written = subprocess.run(
                [sys.executable, str(parity / "write-ledger.py"), "--root", str(root),
                 "--results", str(results), "--expected-set", str(out / "_render_set.txt"),
                 "--output", str(out / "ledger.tsv")], capture_output=True, text=True,
            )
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            summary = subprocess.run(
                [sys.executable, str(root / "scripts" / "parity-summary"), "--ledger", str(out / "ledger.tsv")],
                capture_output=True, text=True,
            )
            self.assertEqual(summary.returncode, 0, summary.stdout + summary.stderr)
            counts = json.loads(summary.stdout.split("PARITY-SUMMARY ", 1)[1])
            self.assertEqual(counts, {"expected": 1, "executed": 1, "exact": 0,
                                      "strict": 0 if name == "motionBlur" else 1,
                                      "near": 1 if name == "motionBlur" else 0,
                                      "defer": 0, "skip": 0, "fail": 0, "missing": 0})
            (root / "reference-dirty").unlink(missing_ok=True)
            (parity / "run.sh").write_text("exit 29\n")
            sweep_output = root / "sweep-output"
            sweep_output.mkdir()
            swept = subprocess.run(
                ["bash", str(parity / "sweep.sh"), "--no-stage"], cwd=root,
                capture_output=True, text=True,
                env=dict(environment, LEDGER_PATH=str(sweep_output / "ledger.tsv")),
            )
            self.assertEqual(swept.returncode, 0, swept.stdout + swept.stderr)
            verdict = "NEAR" if name == "motionBlur" else "PASS"
            self.assertIn(f"{name}\t{verdict}\t", (sweep_output / "ledger.tsv").read_text())
            self.assertTrue((sweep_output / f"{name}.json").exists())
            defects = ["missing_frame", "wrong_pin", "wide_frame", "failed_frame", "invalid_mean",
                       "wrong_frame_bound", "wrong_capture", "early_wide"]
            if name == "motionBlur":
                defects.extend(("low_f8_ssim", "missing_counts", "invalid_counts", "plausible_wrong_counts"))
            for defect in defects:
                with self.subTest(defect=defect):
                    invalid = json.loads(json.dumps(evidence))
                    if defect == "missing_frame":
                        invalid["frames"].pop()
                    elif defect == "wrong_pin":
                        invalid["reference_sha"] = "b" * 40
                    elif defect == "wide_frame":
                        invalid["frames"][-1]["report"]["max_abs_diff"] = 4.0
                    elif defect == "failed_frame":
                        invalid["frames"][-1]["report"]["passed"] = False
                    elif defect == "invalid_mean":
                        invalid["frames"][-1]["report"]["mean_abs_diff"] = float("nan")
                    elif defect == "wrong_frame_bound":
                        invalid["frames"][0]["report"]["tolerance"] = 3.001
                    elif defect == "wrong_capture":
                        invalid["frames"][-1]["candidate_sha256"] = "0" * 64
                    elif defect == "early_wide":
                        invalid["frames"][0]["report"]["max_abs_diff"] = 3.0
                    elif defect == "low_f8_ssim":
                        invalid["frames"][-1]["report"]["ssim"] = 0.9998
                    elif defect == "missing_counts":
                        del invalid["frames"][-1]["pixel_counts"]
                    elif defect == "invalid_counts":
                        invalid["frames"][-1]["pixel_counts"]["different_channels"] = 262145
                    else:
                        invalid["frames"][-1]["pixel_counts"]["pixels_over_2"] -= 1
                    report.write_text(json.dumps(invalid))
                    rejected = subprocess.run(written.args, capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())
            report.write_text(json.dumps(evidence))
            runtime_source.write_text("version = 2\n")
            stale = subprocess.run(written.args, capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0, stale.stdout + stale.stderr)
            self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())
            runtime_source.write_text("version = 1\n")
            (parity / "programs" / f"{name}.dsl").write_text(f"{name}().write(o1)\n")
            changed_fixture = subprocess.run(written.args, capture_output=True, text=True)
            self.assertNotEqual(changed_fixture.returncode, 0, changed_fixture.stdout + changed_fixture.stderr)
            self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())

    def test_single_and_batch_exporters_use_the_full_clean_start_protocol(self):
        single = (REPO / "parity" / "export-and-render.mjs").read_text()
        batch = (REPO / "parity" / "batch-golden.mjs").read_text()

        for source in (single, batch):
            self.assertIn("p.graph.id !== base && p.isCompiling === false", source)
            self.assertIn("}, baselineId, { timeout: STATUS_TIMEOUT })", source)
            self.assertIn("for (const texId of backend.textures.keys())", source)
            self.assertIn("backend.clearTexture(texId)", source)
            self.assertIn("surface.read = readId", source)
            self.assertIn("surface.write = writeId", source)
            self.assertIn("p.frameIndex = 0", source)
            self.assertIn("p.lastTime = 0", source)
            self.assertLess(
                source.index("if (window.__noisemakerSetPausedTime)"),
                source.index("p.lastTime = 0"),
            )

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
            deferred = ("cellularAutomata", "motionBlur", "convolutionFeedback", "reactionDiffusion",
                        "synth3d_cellularAutomata3d", "synth3d_reactionDiffusion3d")
            for name in ("adjust", "chrome", *deferred):
                (parity / "programs" / f"{name}.dsl").write_text(
                    f"noise().{name}().write(o0)\n"
                )
            (out / "_render_set.txt").write_text(
                "adjust chrome " + " ".join(deferred) + "\n"
            )
            for name in ("adjust", "chrome"):
                (out / f"{name}.golden.png").touch()
                (out / f"{name}.candidate.png").touch()
            (out / "ledger.tsv").write_text(
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
            lines = (out / "ledger.tsv").read_text().splitlines()
            rows = {
                row.split("\t", 1)[0]: row.split("\t")
                for row in lines[1:]
            }
            self.assertEqual(rows["adjust"][1:3], ["PASS", "1.0"])
            self.assertEqual(rows["chrome"][1:3], ["NEAR", "32.0"])
            for name in deferred:
                self.assertEqual(rows[name][1], "DEFER")
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
            rows = (out / "ledger.tsv").read_text().splitlines()
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
