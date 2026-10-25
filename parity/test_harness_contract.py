#!/usr/bin/env python3
"""App-free regressions for parity gate failure propagation."""

import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


REPO = Path(__file__).resolve().parents[1]


def fixture_png(rgba, first_pixel=None):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    row = b"\0" + bytes(rgba) * 256
    first_row = row if first_pixel is None else b"\0" + bytes(first_pixel) + bytes(rgba) * 255
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(first_row + row * 255))
            + chunk(b"IEND", b""))


def load_write_ledger():
    spec = importlib.util.spec_from_file_location("nm_td_write_ledger", REPO / "parity" / "write-ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_stage_coverage():
    spec = importlib.util.spec_from_file_location(
        "nm_td_stage_coverage", REPO / "parity" / "stage_coverage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvolveFrameDriverTests(unittest.TestCase):
    """td/parity_evolve.py must advance exactly one simulation step per sampled frame.

    The fake clock models the measured TouchDesigner 2025.32820 behaviour: a Feedback TOP latches
    once per absolute frame in which the graph cooks, and it snapshots its target at the end of
    the frame BEFORE the Execute DAT's onFrameEnd runs. From the third frame on, TouchDesigner
    also cooks the graph by itself at the start of each frame.
    """

    class _Clock:
        frame = 0

    class _Feedback:
        def __init__(self):
            self.totalCooks = 0
            self.cookAbsFrame = None
            self.output = (0, None)
            self.snapshot = (0, None)

    class _Out:
        def __init__(self, clock, feedback, saved):
            self.clock, self.feedback, self.saved = clock, feedback, saved
            self.state = (0, None)
            self.time = None
            self.width = self.height = 1

        def cook(self, force=False):
            # Each cook computes (steps, time of the cook) from the feedback latched this frame.
            if self.feedback.cookAbsFrame != self.clock.frame:
                self.feedback.cookAbsFrame = self.clock.frame
                self.feedback.totalCooks += 1
                self.feedback.output = self.feedback.snapshot
            self.state = (self.feedback.output[0] + 1, self.time)

        def save(self, path):
            self.saved[Path(path).name] = self.state
            return path

        def numpyArray(self):
            raise RuntimeError('not needed')

    def _run(self, frames, samples, timestep="0.01"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "td").mkdir()
            (root / "parity" / "out").mkdir(parents=True)
            source = (REPO / "td" / "parity_evolve.py").read_text()
            clock, feedback, saved = self._Clock(), self._Feedback(), {}
            out = self._Out(clock, feedback, saved)
            project = SimpleNamespace(realTime=False, quit=lambda force=False: None)
            namespace = {"__file__": str(root / "td" / "parity_evolve.py"),
                         "__name__": "parity_evolve_test", "absTime": clock, "project": project}
            env = {"NM_PROGRAM": "probe", "NM_FRAMES": str(frames), "NM_TIME": "0.25",
                   "NM_TIMESTEP": timestep, "NM_SAMPLES": ",".join(str(s) for s in samples)}
            with mock.patch.dict(os.environ, env):
                exec(compile(source, "parity_evolve.py", "exec"), namespace)
            nm = SimpleNamespace(pipeline=SimpleNamespace(
                set_time=lambda t: setattr(out, "time", round(t, 6)),
                backend=SimpleNamespace(_feedback={"state": feedback})))
            namespace["_state"].update(nm=nm, out=out, done=False)
            for frame in range(1, frames + 3):
                if namespace["_state"].get("done"):
                    break
                clock.frame += 1
                if frame >= 3:
                    out.cook()                      # TouchDesigner's own start-of-frame cook
                namespace["evolve_frame_start"](frame)
                feedback.snapshot = out.state       # end-of-frame snapshot, before onFrameEnd
                namespace["evolve_frame_end"](frame)
                clock.frame += 1 if frame == 1 else 0   # an absolute frame without callbacks
            return saved

    def test_each_sample_holds_exactly_its_step_and_time(self):
        # Step k computes at the reference's frame time: base + (k - 1) * timestep.
        saved = self._run(8, (1, 2, 3, 8))
        self.assertEqual(saved, {"probe.f0001.candidate.png": (1, 0.25), "probe.f0002.candidate.png": (2, 0.26),
                                 "probe.f0003.candidate.png": (3, 0.27), "probe.f0008.candidate.png": (8, 0.32)})


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

    def test_selected_convolution_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("convolutionFeedback")

    def test_selected_cellular_3d_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("synth3d_cellularAutomata3d")

    def test_selected_reaction_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("reactionDiffusion")

    def test_selected_reaction_3d_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("synth3d_reactionDiffusion3d")

    def test_selected_hero_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("present_hero")

    def test_selected_buddhabrot_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("buddhabrot")

    def test_selected_physical_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("physical")

    def test_selected_flow3d_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("filter3d_flow3d")

    def test_selected_billboard_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("heightGrid_billboard")

    def test_selected_billboard_alpha_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("heightGrid_billboard_alpha")

    def test_selected_perspective_points_accumulation_enters_the_canonical_summary(self):
        self.check_selected_accumulation("heightGrid_pointsRender_perspective")

    def test_stage_and_ledger_share_the_accumulation_cases(self):
        stage = load_stage_coverage()
        self.assertEqual(stage.ACCUM_EFFECTS, set(load_write_ledger().ACCUMULATION_CASES))
        self.assertEqual(stage.DEFERRED_EFFECTS, set())
        self.assertEqual(len(stage.expected_sweep_names()), len(stage.program_names()))

    def test_hero_uses_the_accumulation_manifest_route(self):
        stage = load_stage_coverage()
        self.assertIn("present_hero", stage.ACCUM_EFFECTS)
        self.assertNotIn("present_hero", stage.DEFERRED_EFFECTS)
        self.assertIn("present_hero", stage.expected_sweep_names())

    def test_stage_keeps_measured_static_3d_separate_from_cubemap_dispatch(self):
        stage = load_stage_coverage()
        names = ["_vs32probe", "filter3d_palette3d", "synth3d_cell3d",
                 "synth3d_flythrough3d", "synth3d_fractal3d", "synth3d_noise",
                 "synth3d_renderLit3d", "synth3d_shape3d"]
        with tempfile.TemporaryDirectory(prefix="nm-td-static-3d-stage-") as temp:
            root = Path(temp)
            programs = root / "programs"
            programs.mkdir()
            (root / "shaders").mkdir()
            for name in names + ["synth3d_renderCubemap3d", "synth3d_renderCubemapSurface"]:
                (programs / f"{name}.dsl").write_text("shape3d().render3d().write(o0)\n")
            graph = root / "graph.json"
            graph.write_text(json.dumps({"passes": [{"passType": "effect",
                "namespace": "synth3d", "func": "shape3d", "progName": "precompute"}]}))
            stage.PROGRAMS = str(programs)
            stage.OUT = str(root / "out")
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root)}), \
                    mock.patch.object(stage, "export_graph", return_value=(str(graph), None)), \
                    mock.patch.object(sys, "argv", ["stage_coverage.py", "--emit", "render"]), \
                    redirect_stdout(output):
                stage.main()
            self.assertEqual(output.getvalue().split(), names)
            staged = root / "render-set.txt"
            cubemaps = ["synth3d_renderCubemap3d", "synth3d_renderCubemapSurface"]
            staged.write_text(output.getvalue() + " ".join(cubemaps))
            self.assertTrue(stage.validate_render_set(staged))
            staged.write_text(" ".join(names[1:] + cubemaps))
            errors = io.StringIO()
            with redirect_stderr(errors):
                self.assertFalse(stage.validate_render_set(staged))
            self.assertIn("missing staged cases: _vs32probe", errors.getvalue())

    def test_stage_rejects_missing_fragments_and_graphs_for_measured_static_3d(self):
        for defect in ("missing_fragment", "missing_graph"):
            with self.subTest(defect=defect), \
                    tempfile.TemporaryDirectory(prefix="nm-td-static-3d-reject-") as temp:
                stage = load_stage_coverage()
                root = Path(temp)
                programs = root / "programs"
                programs.mkdir()
                (root / "shaders").mkdir()
                (programs / "synth3d_shape3d.dsl").write_text("shape3d().render3d().write(o0)\n")
                graph = root / "graph.json"
                graph.write_text(json.dumps({"passes": [{"passType": "effect",
                    "namespace": "synth3d", "func": "shape3d", "progName": "missing"}]}))
                stage.PROGRAMS = str(programs)
                stage.OUT = str(root / "out")
                exported = (str(graph), None) if defect == "missing_fragment" else (None, "compile failed")
                errors = io.StringIO()
                with mock.patch.dict(os.environ, {"NM_REFERENCE_ROOT": str(root)}), \
                        mock.patch.object(stage, "export_graph", return_value=exported), \
                        mock.patch.object(sys, "argv", ["stage_coverage.py", "--emit", "render"]), \
                        redirect_stdout(io.StringIO()), redirect_stderr(errors):
                    with self.assertRaises(SystemExit) as raised:
                        stage.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("unclassified gateable cases: synth3d_shape3d", errors.getvalue())

    def check_selected_accumulation(self, name):
        ledger_module = load_write_ledger()
        frame_bounds = {frame: ledger_module.accumulation_frame_bound(name, frame) for frame in (1, 2, 8)}
        tolerance, aggregate_ssim = ledger_module.accumulation_bound(name)
        near_frames = [frame for frame, bound in frame_bounds.items() if bound[0] > 2.001]
        reference_sha = "d0ed94ae19cca7328bc7d6b28902712a0838e1a9" if name == "present_hero" else "a" * 40
        with tempfile.TemporaryDirectory(prefix="nm-td-accumulate-") as temp:
            root = Path(temp)
            parity = root / "parity"
            out = parity / "out"
            out.mkdir(parents=True)
            (parity / "programs").mkdir()
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            python = root / "bin" / "python3"
            python.write_text("#!" + sys.executable + "\nimport os,sys\nos.execv(sys.executable,[sys.executable,*sys.argv[1:]])\n")
            python.chmod(0o755)
            for helper in ("accumulate.sh", "write-ledger.py", "sweep.sh", "stage_coverage.py", "compare.py"):
                shutil.copy2(REPO / "parity" / helper, parity / helper)
            if name == "present_hero":
                shutil.copy2(REPO / "parity" / "batch-golden.mjs", parity / "batch-golden.mjs")
            (root / "td" / "noisemaker" / "runtime").mkdir(parents=True)
            runtime_source = root / "td" / "noisemaker" / "runtime" / "probe.py"
            runtime_source.write_text("version = 1\n")
            for helper in ("parity_evolve.py", "build_evolve_toe.py"):
                shutil.copy2(REPO / "td" / helper, root / "td" / helper)
            shutil.copy2(REPO / "scripts" / "parity-summary", root / "scripts" / "parity-summary")
            (root / "scripts" / "test").write_text('NM_REFERENCE_SHA_PINNED="' + reference_sha + '"\n')
            (out / "_render_set.txt").write_text(name + "\n")
            (parity / "programs" / f"{name}.dsl").write_text(f"{name}().write(o0)\n")
            if name == "present_hero":
                shutil.copy2(REPO / "parity" / "programs" / "present_hero.dsl",
                             parity / "programs" / "present_hero.dsl")
            fixtures = root / "fixtures"
            fixtures.mkdir()
            (fixtures / "golden.png").write_bytes(fixture_png((255, 255, 255, 255)))
            for frame, bound in frame_bounds.items():
                # Strict frames differ by one level everywhere; NEAR frames differ in one pixel by
                # the integer part of their bound, keeping the mean far below the frame's limit.
                if frame in near_frames:
                    level = 255 - int(bound[0])
                    data = fixture_png((255, 255, 255, 255), (level, level, level, 255))
                else:
                    data = fixture_png((254, 254, 254, 255))
                (fixtures / f"{name}.f{frame:04d}.png").write_bytes(data)
            image_stub = root / "image-stub" / "PIL"
            image_stub.mkdir(parents=True)
            (image_stub / "__init__.py").write_text(
                "import struct,zlib,types,pathlib,numpy as np\n"
                "class Image:\n"
                "    @staticmethod\n"
                "    def open(handle):\n"
                "        data=handle.read() if hasattr(handle,'read') else pathlib.Path(handle).read_bytes()\n"
                "        assert data[:8]==b'\\x89PNG\\r\\n\\x1a\\n'\n"
                "        width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data[16:29])\n"
                "        assert (depth,color,compression,filtering,interlace)==(8,6,0,0,0)\n"
                "        offset=8; compressed=b''\n"
                "        while offset<len(data):\n"
                "            length=struct.unpack('>I',data[offset:offset+4])[0]\n"
                "            if data[offset+4:offset+8]==b'IDAT': compressed+=data[offset+8:offset+8+length]\n"
                "            offset+=length+12\n"
                "        rows=np.frombuffer(zlib.decompress(compressed),dtype=np.uint8).reshape(height,width*4+1)\n"
                "        assert not np.any(rows[:,0])\n"
                "        return types.SimpleNamespace(convert=lambda mode: rows[:,1:].reshape(height,width,4))\n"
            )
            node = root / "bin" / "node"
            node.write_text(
                "#!" + sys.executable + "\n"
                "import pathlib,shutil,sys\n"
                "manifest=pathlib.Path(sys.argv[2]).read_text().splitlines()\n"
                f"assert len(manifest)==1 and manifest[0].split()[0]=={name!r}\n"
                + ("assert sys.argv[4:]==['--size','256','--frames',sys.argv[7],'--timestep','0','--time','0.25','--backend','webgl2']\n"
                   if name == "present_hero" else "")
                +
                "out=pathlib.Path(sys.argv[3]); out.mkdir(parents=True)\n"
                f"shutil.copyfile({str(fixtures / 'golden.png')!r},out/{name + '.golden.png'!r})\n"
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
                + ('test "$NM_SIZE,$NM_TIME,$NM_TIMESTEP,$NM_FRAMES,$NM_SAMPLES" = "256,0.25,0,8,1,2,8" || exit 20\n'
                   'test -z "$NM_DUMP_PROG$NM_DUMP_TEXID" || exit 21\n'
                   if name == "present_hero" else "")
                +
                'touch evolve-called\n'
                'for f in 0001 0002 0008; do cp "fixtures/$1.f$f.png" "parity/out/$1.f$f.candidate.png"; done\n'
            )
            report = root / f"{name}.json"
            environment = dict(os.environ, PATH=os.pathsep.join((str(root / "bin"),
                               str(Path(sys.executable).parent), os.environ["PATH"])),
                               PYTHONPATH=os.pathsep.join((str(image_stub.parent), os.environ.get("PYTHONPATH", ""))),
                               NM_REFERENCE_SHA=reference_sha, NM_REFERENCE_ROOT=str(root / "authority"),
                               TEST_REFERENCE_HEAD=reference_sha,
                               TEST_REFERENCE_DIRTY_MARKER=str(root / "reference-dirty"))
            if name == "present_hero":
                environment.update(NM_SIZE="64", NM_DUMP_PROG="noise", NM_DUMP_TEXID="other")
            result = subprocess.run(
                ["bash", str(parity / "accumulate.sh"), "--effect", name, "--report", str(report)],
                cwd=root, capture_output=True, text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence["reference_sha"], reference_sha)
            self.assertEqual([frame["frame"] for frame in evidence["frames"]], [1, 2, 8])
            self.assertIn("candidate_sources", evidence)
            for item in evidence["frames"]:
                bound = frame_bounds[item["frame"]]
                self.assertEqual((item["report"]["tolerance"], item["report"]["ssim_min"]), bound[:2])
                histogram = item["pixel_counts"]["channel_abs_histogram"]
                if item["frame"] in near_frames:
                    self.assertEqual(histogram, {"0": 262141, str(int(bound[0])): 3})
                else:
                    self.assertEqual(histogram, {"0": 65536, "1": 196608})
            if name == "present_hero":
                self.assertEqual(evidence["protocol"], {
                    "reference_sha": reference_sha,
                    "size": 256, "time": 0.25, "timestep": 0,
                    "reference_backend": "webgl2", "reference_frames": [1, 2, 8],
                    "native_frames": 8, "native_samples": [1, 2, 8], "initial_state": "zeroed",
                    "fixture_sha256": "e0c083445a843a137e76fbba4572c897a6a0b034956253910dd61b9638493e08",
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
            results.write_text(f"{name}\tACCUMULATE\t{report}\t{tolerance}\t{aggregate_ssim}\n")
            written = subprocess.run(
                [sys.executable, str(parity / "write-ledger.py"), "--root", str(root),
                 "--results", str(results), "--expected-set", str(out / "_render_set.txt"),
                 "--output", str(out / "ledger.tsv")], capture_output=True, text=True, env=environment,
            )
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            self.assertIn(f"\t{tolerance}\t{aggregate_ssim}\taccumulate\t", (out / "ledger.tsv").read_text())
            correct_result = results.read_text()
            results.write_text(f"{name}\tACCUMULATE\t{report}\t{tolerance + 1}\t{aggregate_ssim}\n")
            wrong_bound = subprocess.run(written.args, capture_output=True, text=True, env=environment)
            self.assertNotEqual(wrong_bound.returncode, 0, wrong_bound.stdout + wrong_bound.stderr)
            results.write_text(correct_result)
            restored = subprocess.run(written.args, capture_output=True, text=True, env=environment)
            self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
            if name == "present_hero":
                (root / "scripts" / "test").write_text('NM_REFERENCE_SHA_PINNED="' + "b" * 40 + '"\n')
                later_pin = json.loads(json.dumps(evidence))
                later_pin["reference_sha"] = "b" * 40
                report.write_text(json.dumps(later_pin))
                rejected_pin = subprocess.run(written.args, capture_output=True, text=True, env=environment)
                self.assertNotEqual(rejected_pin.returncode, 0, rejected_pin.stdout + rejected_pin.stderr)
                (root / "scripts" / "test").write_text('NM_REFERENCE_SHA_PINNED="' + reference_sha + '"\n')
                report.write_text(json.dumps(evidence))
                restored = subprocess.run(written.args, capture_output=True, text=True, env=environment)
                self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
            summary = subprocess.run(
                [sys.executable, str(root / "scripts" / "parity-summary"), "--ledger", str(out / "ledger.tsv")],
                capture_output=True, text=True,
            )
            self.assertEqual(summary.returncode, 0, summary.stdout + summary.stderr)
            counts = json.loads(summary.stdout.split("PARITY-SUMMARY ", 1)[1])
            self.assertEqual(counts, {"expected": 1, "executed": 1, "exact": 0,
                                      "strict": 0 if near_frames else 1, "near": 1 if near_frames else 0,
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
            verdict = "NEAR" if near_frames else "PASS"
            self.assertIn(f"{name}\t{verdict}\t", (sweep_output / "ledger.tsv").read_text())
            self.assertTrue((sweep_output / f"{name}.json").exists())
            defects = ["missing_frame", "wrong_pin", "wide_frame", "failed_frame", "invalid_mean",
                       "wrong_frame_bound", "wrong_capture", "early_wide", "low_ssim", "missing_counts",
                       "invalid_counts", "missing_histogram", "wrong_mean", "plausible_wrong_histogram"]
            if name == "present_hero":
                defects.extend(("missing_protocol", "wrong_size", "wrong_time", "wrong_timestep",
                                "wrong_reference_backend", "wrong_reference_frames", "wrong_native_frames",
                                "wrong_native_samples", "wrong_initial_state", "wrong_fixture_sha256"))
            for defect in defects:
                with self.subTest(defect=defect):
                    invalid = json.loads(json.dumps(evidence))
                    first, last = invalid["frames"][0], invalid["frames"][-1]
                    if defect == "missing_frame":
                        invalid["frames"].pop()
                    elif defect == "wrong_pin":
                        invalid["reference_sha"] = "b" * 40
                    elif defect == "wide_frame":
                        last["report"]["max_abs_diff"] = frame_bounds[8][0] + 1
                    elif defect == "failed_frame":
                        last["report"]["passed"] = False
                    elif defect == "invalid_mean":
                        last["report"]["mean_abs_diff"] = float("nan")
                    elif defect == "wrong_frame_bound":
                        first["report"]["tolerance"] = 99.0
                    elif defect == "wrong_capture":
                        last["candidate_sha256"] = "0" * 64
                    elif defect == "early_wide":
                        first["report"]["max_abs_diff"] = frame_bounds[1][0] + 1
                    elif defect == "low_ssim":
                        last["report"]["ssim"] = frame_bounds[8][1] - 0.0001
                    elif defect == "missing_counts":
                        del last["pixel_counts"]
                    elif defect == "invalid_counts":
                        last["pixel_counts"]["different_channels"] = 262145
                    elif defect == "missing_histogram":
                        del last["pixel_counts"]["channel_abs_histogram"]
                    elif defect == "wrong_mean":
                        last["report"]["mean_abs_diff"] += 0.5
                    elif defect == "plausible_wrong_histogram":
                        histogram = last["pixel_counts"]["pixel_max_histogram"]
                        key = max(histogram, key=histogram.get)
                        histogram[key] -= 1
                        histogram["2" if key != "2" else "3"] = histogram.get("2" if key != "2" else "3", 0) + 1
                    elif defect == "missing_protocol":
                        del invalid["protocol"]
                    elif defect.startswith("wrong_") and defect[6:] in invalid.get("protocol", {}):
                        invalid["protocol"][defect[6:]] = "other"
                    report.write_text(json.dumps(invalid))
                    rejected = subprocess.run(written.args, capture_output=True, text=True, env=environment)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())
            report.write_text(json.dumps(evidence))
            if name == "present_hero":
                override = parity / "corpus" / "present_hero.dsl"
                override.parent.mkdir()
                override.write_text("noise().write(o0)\n")
                (root / "evolve-called").unlink(missing_ok=True)
                wrong_fixture = subprocess.run(result.args, cwd=root, capture_output=True, text=True,
                                               env=environment)
                self.assertNotEqual(wrong_fixture.returncode, 0, wrong_fixture.stdout + wrong_fixture.stderr)
                self.assertFalse((root / "evolve-called").exists())
                override.unlink()
                report.write_text(json.dumps(evidence))
            runtime_source.write_text("version = 2\n")
            stale = subprocess.run(written.args, capture_output=True, text=True, env=environment)
            self.assertNotEqual(stale.returncode, 0, stale.stdout + stale.stderr)
            self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())
            runtime_source.write_text("version = 1\n")
            (parity / "programs" / f"{name}.dsl").write_text(f"{name}().write(o1)\n")
            changed_fixture = subprocess.run(written.args, capture_output=True, text=True, env=environment)
            self.assertNotEqual(changed_fixture.returncode, 0, changed_fixture.stdout + changed_fixture.stderr)
            self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())
            if near_frames:
                # A NEAR frame within its max bound but over its mean limit is rejected.
                (parity / "programs" / f"{name}.dsl").write_text(f"{name}().write(o0)\n")
                (fixtures / f"{name}.f{near_frames[0]:04d}.png").write_bytes(fixture_png((253, 253, 253, 255)))
                high_mean = subprocess.run(result.args, cwd=root, capture_output=True, text=True, env=environment)
                self.assertNotEqual(high_mean.returncode, 0, high_mean.stdout + high_mean.stderr)
                measured = json.loads(Path(str(report) + f".frames/{near_frames[0]}.json").read_text())
                self.assertLessEqual(measured["max_abs_diff"], frame_bounds[near_frames[0]][0])
                self.assertGreater(measured["mean_abs_diff"], frame_bounds[near_frames[0]][2])

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
