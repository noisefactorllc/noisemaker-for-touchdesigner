"""App-free checks for canonical cubemap dispatch and capture validation."""

import hashlib
import io
import json
import os
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
CASES = ("synth3d_renderCubemap3d", "synth3d_renderCubemapSurface")
CELLS = [(0, 1), (2, 1), (1, 0), (1, 2), (1, 1), (3, 1)]
PROTOCOL = {"size": 256, "time": 0.25, "backend": "webgl2",
            "face_order": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
            "cross_cells": [list(cell) for cell in CELLS]}
BOUND_FILES = ("td/cubemap_bake.py", "td/build_points_probe_toe.py", "parity/cubemap.sh",
               "parity/pylib.sh",
               "parity/cube_cross.py", "parity/export-and-render.mjs", "parity/harness-port.mjs",
               "parity/compare.py", "parity/write-ledger.py", "tools/export-graph.mjs",
               "tools/reference-root.mjs", "scripts/test")
IMAGE_STUB = '''import pathlib,struct,types,zlib,numpy as np
class Image:
    @staticmethod
    def open(handle):
        data=handle.read() if hasattr(handle,'read') else pathlib.Path(handle).read_bytes()
        width,height=struct.unpack('>II',data[16:24])
        offset=8; compressed=b''
        while offset<len(data):
            length=struct.unpack('>I',data[offset:offset+4])[0]
            if data[offset+4:offset+8]==b'IDAT': compressed+=data[offset+8:offset+8+length]
            offset+=length+12
        rows=np.frombuffer(zlib.decompress(compressed),dtype=np.uint8).reshape(height,width*4+1)
        assert not np.any(rows[:,0])
        return types.SimpleNamespace(convert=lambda mode: rows[:,1:].reshape(height,width,4))
    @staticmethod
    def fromarray(array,mode):
        def save(path):
            def chunk(kind,data):
                return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
            height,width,_=array.shape
            rows=b''.join(b'\\0'+row.tobytes() for row in array)
            pathlib.Path(path).write_bytes(b'\\x89PNG\\r\\n\\x1a\\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
                +chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
        return types.SimpleNamespace(save=save)
'''


def png(array):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    height, width, _ = array.shape
    rows = b"".join(b"\0" + row.tobytes() for row in array)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class CubemapTests(unittest.TestCase):
    def test_cubemap_sources_bind_the_golden_loader(self):
        sources = runpy.run_path(str(REPO / "parity/write-ledger.py"))["cubemap_sources"](REPO, CASES[0])
        self.assertIn("tools/reference-root.mjs", sources)

    def test_cubemap_wrapper_binds_current_sources_and_rejects_capture_failures(self):
        import numpy as np

        name = CASES[0]
        with tempfile.TemporaryDirectory(prefix="nm-td-cube-wrapper-") as temp:
            root = Path(temp)
            for relative in BOUND_FILES:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / relative, target)
            (root / "scripts/test").write_text('NM_REFERENCE_SHA_PINNED="' + "a" * 40 + '"\n')
            runtime = root / "td/noisemaker/runtime/probe.py"
            runtime.parent.mkdir(parents=True)
            runtime.write_text("version = 1\n")
            fixture = root / "parity/programs" / f"{name}.dsl"
            fixture.parent.mkdir()
            shutil.copy2(REPO / "parity/programs" / f"{name}.dsl", fixture)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            for kind, rgba in (("golden", (255, 255, 255, 255)), ("candidate", (254, 254, 254, 255))):
                (fixtures / f"{kind}.png").write_bytes(png(np.full((256, 256, 4), rgba, dtype=np.uint8)))
            stub = root / "image-stub/PIL"
            stub.mkdir(parents=True)
            (stub / "__init__.py").write_text(IMAGE_STUB)
            binary = root / "bin"
            binary.mkdir()
            (root / "reference/shaders").mkdir(parents=True)
            scripts = {
                "python3": "import os,sys\nif sys.argv[1].endswith('build_points_probe_toe.py'): sys.exit(0)\n"
                           "os.execv(sys.executable,[sys.executable,*sys.argv[1:]])\n",
                "git": "import os,pathlib,sys\n"
                       "if 'rev-parse' in sys.argv: print(('b' if os.environ.get('TEST_WRONG_PIN') else 'a')*40)\n"
                       "elif 'status' in sys.argv and pathlib.Path('dirty-reference').exists(): print(' M source.js')\n",
                "node": "import os,pathlib,shutil,sys\n"
                        "pathlib.Path('golden-called').touch()\n"
                        "assert sys.argv[4:]==['--size','256','--cubemap']\n"
                        "name=pathlib.Path(sys.argv[2]).stem; out=pathlib.Path(sys.argv[3])\n"
                        "for face in range(6): shutil.copy2('fixtures/golden.png',out/f'{name}.face{face}.golden.png')\n"
                        "if os.environ.get('TEST_DIRTY_AFTER_GOLDEN'): pathlib.Path('dirty-reference').touch()\n",
                "td": "import os,pathlib,shutil,sys\npathlib.Path('native-called').touch()\n"
                      "out=pathlib.Path('parity/out')\n"
                      "if os.environ.get('TEST_NATIVE_FAIL'):\n"
                      "    (out/'_cubemap_log.txt').write_text('FAIL\\n'); sys.exit(7)\n"
                      "for face in range(6): shutil.copy2('fixtures/candidate.png',out/f'{os.environ[\"NM_PROGRAM\"]}.face{face}.candidate.png')\n"
                      "(out/'_cubemap_log.txt').write_text('=== BAKE DONE: 6 faces, 6 distinct face-means ===\\n')\n"
                      "if os.environ.get('TEST_STALE_SOURCE'): pathlib.Path('td/noisemaker/runtime/probe.py').write_text('version = 2\\n')\n",
            }
            for executable, body in scripts.items():
                path = binary / executable
                path.write_text("#!" + sys.executable + "\n" + body)
                path.chmod(0o755)
            environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                               PYTHONPATH=str(stub.parent), PYTHONDONTWRITEBYTECODE="1",
                               NM_REFERENCE_ROOT=str(root / "reference"), NM_REFERENCE_SHA="a" * 40,
                               TD_BIN=str(binary / "td"), NM_WAIT="1", SIZE="256", TOL="2.001", SSIM="0.98")
            report = root / "cubemap.json"
            command = ["bash", str(root / "parity/cubemap.sh"), name, "--report", str(report)]
            for defect in ("LEGACY", None, "TEST_WRONG_PIN", "TEST_DIRTY_AFTER_GOLDEN", "TEST_NATIVE_FAIL", "TEST_STALE_SOURCE"):
                with self.subTest(defect=defect):
                    for marker in ("golden-called", "native-called", "dirty-reference"):
                        (root / marker).unlink(missing_ok=True)
                    runtime.write_text("version = 1\n")
                    report.write_text('{"passed":true}\n')
                    result = subprocess.run(command[:3] if defect == "LEGACY" else command, cwd=root,
                                            env=dict(environment, **({defect: "1"} if defect not in (None, "LEGACY") else {})),
                                            capture_output=True, text=True)
                    if defect == "LEGACY":
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    elif defect is None:
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        evidence = json.loads(report.read_text())
                        self.assertIn("outputs", evidence)
                        self.assertEqual([entry["output"] for entry in evidence["outputs"]],
                                         [f"face{face}" for face in range(6)] + ["cross"])
                        self.assertEqual(evidence["reference_sha"], "a" * 40)
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        if defect in ("TEST_WRONG_PIN", "TEST_DIRTY_AFTER_GOLDEN"):
                            self.assertFalse((root / "native-called").exists())
                        if defect != "TEST_STALE_SOURCE":
                            self.assertFalse(report.exists())

    def test_stage_routes_cubemaps_outside_the_static_golden_batch(self):
        stage = runpy.run_path(str(REPO / "parity/stage_coverage.py"))
        with tempfile.TemporaryDirectory(prefix="nm-td-cube-stage-") as temp:
            root = Path(temp)
            (root / "programs").mkdir()
            for name in CASES:
                (root / "programs" / f"{name}.dsl").write_text("fixture\n")
            namespace = stage["main"].__globals__
            with mock.patch.dict(namespace, {"PROGRAMS": str(root / "programs"), "OUT": str(root / "out"),
                    "reference_root": lambda: str(root),
                    "export_graph": lambda name: self.fail("cubemap entered the generic exporter"),
                    "render_goldens": lambda names: self.assertEqual(names, [])}), \
                    mock.patch.object(sys, "argv", ["stage_coverage.py"]), redirect_stdout(io.StringIO()):
                stage["main"]()
            self.assertEqual((root / "out/_render_set.txt").read_text().split(), list(CASES))

    def test_sweep_rejects_failed_or_stale_cubemap_results(self):
        for name in CASES:
            for exit_code in (0, 7):
                with self.subTest(name=name, exit_code=exit_code), \
                        tempfile.TemporaryDirectory(prefix="nm-td-cube-dispatch-") as temp:
                    root = Path(temp)
                    out = root / "parity/out"
                    out.mkdir(parents=True)
                    (root / "parity/programs").mkdir()
                    (root / "parity/programs" / f"{name}.dsl").write_text("fixture\n")
                    (out / "_render_set.txt").write_text(name + "\n")
                    for helper in ("stage_coverage.py", "sweep.sh", "write-ledger.py",
                                   "pylib.sh"):
                        shutil.copy2(REPO / "parity" / helper, root / "parity" / helper)
                    (root / "parity/run.sh").write_text("touch generic-called\nexit 0\n")
                    (root / "parity/cubemap.sh").write_text(
                        "test \"$2\" = --report || exit 8\n"
                        "test ! -e \"$3\" || exit 9\n"
                        f"touch cubemap-called\nexit {exit_code}\n")
                    (out / f"{name}.json").write_text('{"passed":true}\n')
                    result = subprocess.run(["bash", str(root / "parity/sweep.sh"), "--no-stage"],
                                            cwd=root, capture_output=True, text=True)
                    self.assertTrue((root / "cubemap-called").exists(), result.stdout + result.stderr)
                    self.assertFalse((root / "generic-called").exists())
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f"{name}\tFAIL\t", (out / "ledger.tsv").read_text())

    def test_canonical_cubemap_requires_all_current_strict_outputs(self):
        import numpy as np

        for name in CASES:
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="nm-td-cube-ledger-") as temp:
                root = Path(temp)
                for relative in BOUND_FILES:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(REPO / relative, target)
                (root / "scripts/test").write_text('NM_REFERENCE_SHA_PINNED="' + "a" * 40 + '"\n')
                runtime = root / "td/noisemaker/runtime/probe.py"
                runtime.parent.mkdir(parents=True)
                runtime.write_text("version = 1\n")
                fixture = root / "parity/programs" / f"{name}.dsl"
                fixture.parent.mkdir()
                shutil.copy2(REPO / "parity/programs" / f"{name}.dsl", fixture)
                stub = root / "image-stub/PIL"
                stub.mkdir(parents=True)
                (stub / "__init__.py").write_text(IMAGE_STUB)
                image = runpy.run_path(str(stub / "__init__.py"))["Image"]
                with mock.patch.dict(sys.modules, {"PIL": types.SimpleNamespace(Image=image)}):
                    compare = runpy.run_path(str(root / "parity/compare.py"))
                out = root / "captures"
                out.mkdir()
                crosses = {kind: np.zeros((768, 1024, 4), dtype=np.uint8) for kind in ("golden", "candidate")}
                for face, (x, y) in enumerate(CELLS):
                    for kind in crosses:
                        array = np.full((256, 256, 4), (80 + 20 * face, 100, 150, 255), dtype=np.uint8)
                        if kind == "candidate":
                            array[..., 0] -= 1
                        (out / f"{name}.face{face}.{kind}.png").write_bytes(png(array))
                        crosses[kind][y * 256:(y + 1) * 256, x * 256:(x + 1) * 256] = array
                for kind, array in crosses.items():
                    (out / f"{name}.cross.{kind}.png").write_bytes(png(array))

                def output(suffix):
                    paths = {kind: out / f"{name}.{suffix}.{kind}.png" for kind in crosses}
                    arrays = [compare["load_rgba"](paths[kind]) for kind in crosses]
                    report = {"name": f"{name}.{suffix}", **{kind: str(path) for kind, path in paths.items()},
                              "shape": list(arrays[0].shape), "tolerance": 2.001, "ssim_min": 0.98,
                              "max_abs_diff": compare["max_abs_diff"](*arrays),
                              "mean_abs_diff": compare["mean_abs_diff"](*arrays),
                              "ssim": compare["global_ssim"](*arrays), "passed": True}
                    return {"output": suffix, "report": report, **{
                        f"{kind}_sha256": hashlib.sha256(path.read_bytes()).hexdigest() for kind, path in paths.items()}}

                sources = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [runtime, fixture, *(root / relative for relative in BOUND_FILES)]}
                evidence = {"case": name, "reference_sha": "a" * 40, "candidate_sources": sources,
                            "protocol": PROTOCOL, "outputs": [output(f"face{face}") for face in range(6)] + [output("cross")]}
                report_path = root / "cubemap.json"
                results = root / "results.tsv"
                results.write_text(f"{name}\tCUBEMAP\t{report_path}\t2.001\t0.98\n")
                expected = root / "expected.txt"
                expected.write_text(name + "\n")
                command = [sys.executable, "-B", str(root / "parity/write-ledger.py"), "--root", str(root),
                           "--results", str(results), "--expected-set", str(expected), "--output", "ledger.tsv"]
                environment = dict(os.environ, PYTHONPATH=str(stub.parent), PYTHONDONTWRITEBYTECODE="1")

                def grade(value):
                    report_path.write_text(json.dumps(value))
                    return subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)

                valid = grade(evidence)
                self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
                row = (root / "ledger.tsv").read_text().splitlines()[1].split("\t")
                self.assertEqual(row[0:2], [name, "PASS"])
                self.assertEqual(row[6], "cubemap")
                for defect in ("missing_output", "duplicate_output", "wrong_shape", "failed_output", "wide_output",
                               "forged_maximum", "forged_ssim", "wrong_pin", "wrong_protocol", "wrong_capture_hash",
                               "missing_source", "stale_source", "stale_reference_loader", "wrong_capture_name"):
                    with self.subTest(defect=defect):
                        invalid = json.loads(json.dumps(evidence))
                        if defect == "missing_output": invalid["outputs"].pop(2)
                        elif defect == "duplicate_output": invalid["outputs"][1]["output"] = "face0"
                        elif defect == "wrong_shape": invalid["outputs"][-1]["report"]["shape"] = [256, 256, 4]
                        elif defect == "failed_output": invalid["outputs"][0]["report"]["passed"] = False
                        elif defect == "wide_output": invalid["outputs"][0]["report"]["max_abs_diff"] = 3
                        elif defect == "forged_maximum": invalid["outputs"][0]["report"]["max_abs_diff"] = 0
                        elif defect == "forged_ssim": invalid["outputs"][0]["report"]["ssim"] = 0.99
                        elif defect == "wrong_pin": invalid["reference_sha"] = "b" * 40
                        elif defect == "wrong_protocol": invalid["protocol"]["time"] = 0.5
                        elif defect == "wrong_capture_hash": invalid["outputs"][0]["candidate_sha256"] = "0" * 64
                        elif defect == "missing_source": invalid["candidate_sources"].pop("td/noisemaker/runtime/probe.py")
                        elif defect == "stale_source": runtime.write_text("version = 2\n")
                        elif defect == "stale_reference_loader":
                            (root / "tools/reference-root.mjs").write_text("changed authority routing\n")
                        elif defect == "wrong_capture_name":
                            wrong = out / "other.golden.png"
                            shutil.copy2(invalid["outputs"][0]["report"]["golden"], wrong)
                            invalid["outputs"][0]["report"]["golden"] = str(wrong)
                        rejected = grade(invalid)
                        self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                        self.assertIn(f"{name}\tFAIL\t", (root / "ledger.tsv").read_text())
                        runtime.write_text("version = 1\n")
                        if defect == "stale_reference_loader":
                            shutil.copy2(REPO / "tools/reference-root.mjs", root / "tools/reference-root.mjs")
                for kind in crosses:
                    crosses[kind][0, 0, 0] = 1
                    (out / f"{name}.cross.{kind}.png").write_bytes(png(crosses[kind]))
                inconsistent = json.loads(json.dumps(evidence))
                inconsistent["outputs"][-1] = output("cross")
                rejected = grade(inconsistent)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn(f"{name}\tFAIL\t", (root / "ledger.tsv").read_text())


if __name__ == "__main__":
    unittest.main()
