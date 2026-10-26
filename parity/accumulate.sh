#!/usr/bin/env bash
# parity/accumulate.sh — parity for the multi-frame FEEDBACK-ACCUMULATION effects.
#
# The single-frame sweep.sh force-cooks ONE frame, which cannot drive a stateful effect whose state
# only latches on a real engine tick. These cases instead evolve 8 frames-from-zero (timestep 0 — the
# reference golden protocol, parity/batch-golden.mjs) through the evolve harness (non-real-time
# timeline playback; one simulation step per Feedback TOP latch), then grade frames 1, 2 and 8
# against batch-golden references.
#
# The case list and every frame bound come from parity/write-ledger.py (ACCUMULATION_CASES,
# ACCUMULATION_NEAR). Frames are strict (max-abs-diff <= 2, SSIM >= 0.98) except the reviewed NEAR
# frames listed there with their measured bounds. Earlier "chaos" classifications of
# reactionDiffusion and the 3D sims were a harness defect: the evolve driver lost one step at frame 3
# (td/parity_evolve.py). With exact stepping they match at frame 8 with max-abs-diff 1.
#
#   NM_REFERENCE_ROOT=/path/to/noisemaker parity/accumulate.sh   # regen goldens, drive all, grade
#   parity/accumulate.sh --no-stage   # reuse existing parity/out/<e>.f*.golden.png; just drive+grade
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
# Pick an interpreter that has numpy + pillow (see parity/pylib.sh).
if ! PY="$(bash "$HERE/pylib.sh" "$REPO")"; then exit 2; fi
OUT="$REPO/parity/out"; mkdir -p "$OUT"

EFFECTS="$("$PY" "$REPO/parity/write-ledger.py" --accumulation-cases)" || exit 2
GRADE_FRAMES="1 2 8"          # frames captured + graded (per-effect verdict below)

stage=1; selected=""; result_report=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-stage) stage=0; shift ;;
    --effect|--report)
      [ "$#" -ge 2 ] || exit 2
      if [ "$1" = --effect ]; then selected="$2"; else result_report="$2"; fi
      shift 2 ;;
    *) exit 2 ;;
  esac
done
check_reference() {
  "$PY" - "$REPO" "${NM_REFERENCE_ROOT:-}" <<'PY'
import os
import re
import subprocess
import sys
from pathlib import Path

root, reference = sys.argv[1:]
pin = re.search(r'^NM_REFERENCE_SHA_PINNED="([0-9a-f]{40})"$',
                (Path(root) / "scripts" / "test").read_text(), re.M).group(1)
actual = subprocess.check_output(["git", "-C", reference, "rev-parse", "HEAD"], text=True).strip()
dirty = subprocess.check_output(["git", "-C", reference, "status", "--porcelain"], text=True)
if dirty or actual != pin or os.environ.get("NM_REFERENCE_SHA", actual) != actual:
    raise SystemExit("The reference checkout must be clean and match the current authority pin.")
print(actual)
PY
}
if [ -n "$selected$result_report" ]; then
  case " $EFFECTS " in *" $selected "*) ;; *) exit 2 ;; esac
  [ -n "$result_report" ] && [ "$stage" = 1 ] || exit 2
  EFFECTS="$selected"
  rm -f "$result_report"
  reference_sha="$(check_reference)" || exit 2
  frame_reports="$result_report.frames"
  mkdir -p "$frame_reports"
  for n in $GRADE_FRAMES; do rm -f "$frame_reports/$n.json"; done
  "$PY" - "$REPO" "$frame_reports/candidate-sources.json" "$selected" <<'PY' || exit 2
import json
import runpy
import sys
from pathlib import Path

root = Path(sys.argv[1])
sources = runpy.run_path(str(root / "parity" / "write-ledger.py"))["candidate_sources"](root, sys.argv[3])
Path(sys.argv[2]).write_text(json.dumps(sources))
PY
fi

# 1. Reference goldens — batch-golden.mjs renders frame N from a clean zeroed start (timestep 0,
#    time 0.25). One run per frame count over the case manifest; rename to <name>.f<NNNN>.golden.
if [ "$stage" = 1 ]; then
  command -v node >/dev/null || { echo "node not found (needed to regenerate goldens); use --no-stage"; exit 2; }
  MAN="$(mktemp)"; for e in $EFFECTS; do echo "$e parity/programs/$e.dsl" >> "$MAN"; done
  backend_args=(); [ "$selected" != present_hero ] || backend_args=(--backend webgl2)
  for N in $GRADE_FRAMES; do
    f="$(printf '%04d' "$N")"; gdir="$OUT/_acc_g$N"; rm -rf "$gdir"
    ( cd "$REPO" && node parity/batch-golden.mjs "$MAN" "$gdir" --size 256 --frames "$N" --timestep 0 --time 0.25 ${backend_args[@]+"${backend_args[@]}"} ) \
      >/dev/null 2>&1 || { echo "golden gen failed at frames=$N (set NM_REFERENCE_ROOT to the upstream engine)"; exit 2; }
    for e in $EFFECTS; do
      cp "$gdir/$e.golden.png" "$OUT/$e.f$f.golden.png" || exit 2
      if [ -n "$result_report" ]; then cp "$gdir/$e.graph.json" "$OUT/$e.graph.json" || exit 2; fi
    done
  done
  rm -f "$MAN"
fi
if [ -n "$result_report" ]; then [ "$(check_reference)" = "$reference_sha" ] || exit 2; fi

# 2. Drive each effect 8 frames through the evolve harness (permissive internal grade — the
#    authoritative per-effect verdict is step 3). Candidates land in parity/out/<e>.f<NNNN>.candidate.
SMPL="$(echo $GRADE_FRAMES | tr ' ' ',')"
for e in $EFFECTS; do
  evolve_size="${NM_SIZE:-256}"; [ "$e" != present_hero ] || evolve_size=256
  native_env=(); [ "$e" != present_hero ] || native_env=(env -u NM_DUMP_PROG -u NM_DUMP_TEXID)
  if ! NM_SIZE="$evolve_size" NM_FRAMES=8 NM_TIMESTEP=0 NM_TIME=0.25 NM_SAMPLES="$SMPL" NM_WAIT="${NM_WAIT:-280}" \
    TOL=255 SSIM=0 ${native_env[@]+"${native_env[@]}"} bash "$REPO/parity/evolve.sh" "$e" >/dev/null 2>&1; then
    [ -z "$result_report" ] || exit 1
  fi
done

# 3. Per-effect, per-frame verdict.
grade() { # <effect> <frame> <tol> <ssim> ; prints PASS/FAIL line, returns nonzero on fail
  local e="$1" n="$2" tol="$3" ssim="$4" f; f="$(printf '%04d' "$n")"
  local g="$OUT/$e.f$f.golden.png" c="$OUT/$e.f$f.candidate.png"
  [ -f "$c" ] || { echo "  [FAIL] $e f$f — no candidate (evolve did not run)"; return 1; }
  set --
  if [ -n "$result_report" ]; then set -- --report "$frame_reports/$n.json"; fi
  "$PY" "$REPO/parity/compare.py" "$g" "$c" --name "$e.f$f" --tolerance "$tol" --ssim-min "$ssim" 2>&1 \
    "$@" \
    | sed 's/^/  /'
}
bound() { "$PY" "$REPO/parity/write-ledger.py" --accumulation-bound "$1" "$2"; }

if [ -n "$selected" ]; then
  for n in $GRADE_FRAMES; do
    b="$(bound "$selected" "$n")" || exit 2
    read -r tol ssim <<< "$b"; [ -n "${ssim:-}" ] || exit 2
    grade "$selected" "$n" "$tol" "$ssim" || exit 1
  done
  "$PY" - "$result_report" "$reference_sha" "$frame_reports" "$REPO" "$selected" <<'PY'
import hashlib
import json
import runpy
import sys
from pathlib import Path

output, reference_sha, directory, repository, selected = sys.argv[1:]
root = Path(repository)
ledger = runpy.run_path(str(root / "parity" / "write-ledger.py"))
sources = json.loads((Path(directory) / "candidate-sources.json").read_text())
if sources != ledger["candidate_sources"](root, selected):
    raise ValueError("candidate sources changed during accumulation")
frames = []
for frame in ledger["ACCUMULATION_FRAMES"]:
    report = json.loads((Path(directory) / f"{frame}.json").read_text())
    captures = {kind: Path(report[kind]).read_bytes() for kind in ("golden", "candidate")}
    frames.append({"frame": frame, "report": report, **{
        f"{kind}_sha256": hashlib.sha256(captures[kind]).hexdigest()
        for kind in ("golden", "candidate")
    }, "pixel_counts": ledger["frame_pixel_counts"](**captures, details=True)})
evidence = {"case": selected, "reference_sha": reference_sha,
            "candidate_sources": sources, "frames": frames}
if selected == "present_hero":
    evidence.update(protocol=ledger["PRESENT_HERO_PROTOCOL"])
Path(output).write_text(json.dumps(evidence, indent=2) + "\n")
if ledger["accumulate_row"](root, selected, Path(output), *ledger["accumulation_bound"](selected))["verdict"] == "FAIL":
    raise SystemExit("The selected accumulation failed canonical evidence checks.")
PY
  exit $?
fi

pass=0; fail=0
for e in $EFFECTS; do
  echo "=== $e ==="
  for n in $GRADE_FRAMES; do
    b="$(bound "$e" "$n")" || exit 2
    read -r tol ssim <<< "$b"; [ -n "${ssim:-}" ] || exit 2
    if grade "$e" "$n" "$tol" "$ssim"; then pass=$((pass+1)); else fail=$((fail+1)); fi
  done
done
echo "=== ACCUMULATE: $pass / $((pass+fail)) graded frames PASS ==="
[ "$fail" = 0 ]
