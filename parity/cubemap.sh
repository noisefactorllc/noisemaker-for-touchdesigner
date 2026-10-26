#!/usr/bin/env bash
# parity/cubemap.sh <prog> — 6-FACE CUBEMAP BAKE parity.
#
#   parity/cubemap.sh                              # synth3d_renderCubemapSurface
#   parity/cubemap.sh synth3d_renderCubemap3d      # the lit-blob renderer
#   SIZE=256 parity/cubemap.sh <prog>
#
# A full cubemap is HOST-DRIVEN: render the same graph 6x, setting cubeBasis to each GL face
# basis (+X,-X,+Y,-Y,+Z,-Z) between renders. This drives BOTH sides of that loop and grades:
#   1. reference 6 faces  — export-and-render.mjs --cubemap (pipeline.renderCubemap)
#   2. TD 6 faces         — td/cubemap_bake.py rebinds cubeBasis per face (uniform_binder Matrices)
#   3. assemble both into the canonical horizontal cross (cube_cross.py) and compare
# Each face is a deterministic single render (like the single-face test), so the bar is max-diff<=1.
set -uo pipefail
# Stop only the TouchDesigner instance this script launched (never every TouchDesigner on the
# host): ask it to quit, then force it after 10 s.
stop_td() {
  kill "$1" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$1" 2>/dev/null || return 0; sleep 1; done
  kill -9 "$1" 2>/dev/null
}
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
REF="${NM_REFERENCE_ROOT:-}"
[ -n "$REF" ] && [ -d "$REF/shaders" ] || { echo "set NM_REFERENCE_ROOT to the upstream Noisemaker engine (tree with shaders/)"; exit 2; }
TD="${TD_BIN:-/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner}"
# Prefer the venv only when its interpreter actually runs (a venv built by a
# since-removed interpreter execs the CLT stub and every python call fails).
PY="$REPO/parity/.venv/bin/python"
"$PY" -c 'import numpy, PIL' >/dev/null 2>&1 || PY=python3
PROG="${1:-synth3d_renderCubemapSurface}"
[ "$#" -eq 0 ] || shift
result_report=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --report) [ "$#" -ge 2 ] || exit 2; result_report="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
SIZE="${SIZE:-256}"
OUT="$REPO/parity/out"; mkdir -p "$OUT"
DSL="$REPO/parity/programs/$PROG.dsl"; [ -f "$DSL" ] || DSL="$REPO/parity/corpus/$PROG.dsl"
[ -f "$DSL" ] || { echo "no DSL for $PROG"; exit 2; }

check_reference() {
  "$PY" - "$REPO" "$REF" <<'PY'
import os
import re
import subprocess
import sys
from pathlib import Path

root, reference = sys.argv[1:]
pin = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                (Path(root) / "scripts/test").read_text(), re.M).group(1)
actual = subprocess.check_output(["git", "-C", reference, "rev-parse", "HEAD"], text=True).strip()
dirty = subprocess.check_output(["git", "-C", reference, "status", "--porcelain"], text=True)
if dirty or actual != pin or os.environ.get("NM_REFERENCE_SHA", actual) != actual:
    raise SystemExit("The reference checkout must be clean and match the current authority pin.")
print(actual)
PY
}
if [ -n "$result_report" ]; then
  rm -f "$result_report"
  case "$PROG" in synth3d_renderCubemap3d|synth3d_renderCubemapSurface) ;; *) exit 2 ;; esac
  [ "$SIZE" = 256 ] || exit 2
  TOL=2.001; SSIM=0.98
  reference_sha="$(check_reference)" || exit 2
  output_reports="$result_report.outputs"
  mkdir -p "$output_reports" || exit 2
  for suffix in face0 face1 face2 face3 face4 face5 cross; do rm -f "$output_reports/$suffix.json"; done
  "$PY" - "$REPO" "$PROG" "$output_reports/candidate-sources.json" <<'PY' || exit 2
import json
import runpy
import sys
from pathlib import Path

root, name, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sources = runpy.run_path(str(root / "parity/write-ledger.py"))["cubemap_sources"](root, name)
output.write_text(json.dumps(sources))
PY
fi

# 1. reference 6 faces
rm -f "$OUT/$PROG".face*.golden.png "$OUT/$PROG".face*.candidate.png \
  "$OUT/$PROG.cross.golden.png" "$OUT/$PROG.cross.candidate.png"
NM_REFERENCE_ROOT="$REF" node "$REPO/parity/export-and-render.mjs" "$DSL" "$OUT" \
  --size "$SIZE" --cubemap >/dev/null 2>&1 || { echo "FAIL: reference cubemap render"; exit 1; }
if [ -n "$result_report" ]; then [ "$(check_reference)" = "$reference_sha" ] || exit 2; fi

# 2. TD bake (env-parametrized probe builder authors the .toe; it execs td/cubemap_bake.py)
NM_PROBE_FILE="$REPO/td/cubemap_bake.py" NM_PROBE_TOE="$REPO/td/nm_cubemap_bake.toe" \
  python3 "$REPO/td/build_points_probe_toe.py" >/dev/null || { echo "FAIL: build bake .toe"; exit 1; }
rm -f "$OUT/_cubemap_log.txt"
NM_PROGRAM="$PROG" NM_SIZE="$SIZE" "$TD" "$REPO/td/nm_cubemap_bake.toe" >/dev/null 2>&1 &
PID=$!
for i in $(seq 1 "${NM_WAIT:-200}"); do
  grep -qE 'BAKE DONE|abort|FAIL' "$OUT/_cubemap_log.txt" 2>/dev/null && break
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
sleep 1; stop_td "$PID"
if ! grep -q 'BAKE DONE' "$OUT/_cubemap_log.txt" 2>/dev/null; then
  echo "FAIL: TD bake did not finish"; sed 's/^/  /' "$OUT/_cubemap_log.txt" 2>/dev/null; exit 1
fi
if [ -n "$result_report" ]; then [ "$(check_reference)" = "$reference_sha" ] || exit 2; fi

# 3. assemble crosses
"$PY" "$REPO/parity/cube_cross.py" "$OUT/$PROG" candidate >/dev/null || exit 1
"$PY" "$REPO/parity/cube_cross.py" "$OUT/$PROG" golden >/dev/null || exit 1

# 4. grade 6 faces + the cross (deterministic single renders -> max-diff<=1)
rc=0
for k in 0 1 2 3 4 5; do
  set --; [ -z "$result_report" ] || set -- --report "$output_reports/face$k.json"
  "$PY" "$REPO/parity/compare.py" "$OUT/$PROG.face$k.golden.png" "$OUT/$PROG.face$k.candidate.png" \
    --name "$PROG.face$k" --tolerance "${TOL:-2}" --ssim-min "${SSIM:-0.98}" "$@" || rc=1
done
set --; [ -z "$result_report" ] || set -- --report "$output_reports/cross.json"
"$PY" "$REPO/parity/compare.py" "$OUT/$PROG.cross.golden.png" "$OUT/$PROG.cross.candidate.png" \
  --name "$PROG.cross" --tolerance "${TOL:-2}" --ssim-min "${SSIM:-0.98}" "$@" || rc=1
if [ -n "$result_report" ] && [ "$rc" = 0 ]; then
  "$PY" - "$REPO" "$PROG" "$reference_sha" "$output_reports" "$result_report" <<'PY' || exit 1
import hashlib
import json
import runpy
import sys
from pathlib import Path

root, name, reference_sha, reports, output = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5])
ledger = runpy.run_path(str(root / "parity/write-ledger.py"))
outputs = []
for suffix in [f"face{face}" for face in range(6)] + ["cross"]:
    report = json.loads((reports / f"{suffix}.json").read_text())
    outputs.append({"output": suffix, "report": report, **{
        f"{kind}_sha256": hashlib.sha256(Path(report[kind]).read_bytes()).hexdigest()
        for kind in ("golden", "candidate")}})
evidence = {"case": name, "reference_sha": reference_sha, "protocol": ledger["CUBEMAP_PROTOCOL"],
            "candidate_sources": json.loads((reports / "candidate-sources.json").read_text()), "outputs": outputs}
temporary = reports / "aggregate.json"
temporary.write_text(json.dumps(evidence, indent=2) + "\n")
if ledger["cubemap_row"](root, name, temporary, 2.001, 0.98)["verdict"] != "PASS":
    raise SystemExit("The cubemap failed canonical evidence checks.")
temporary.replace(output)
PY
fi
exit $rc
