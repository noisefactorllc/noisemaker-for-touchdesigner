#!/usr/bin/env bash
# parity/sweep.sh — full parity sweep: render every staged program in TouchDesigner, then compare
# each against its reference golden with a PER-EFFECT tolerance. Effects with hard discontinuities
# (fractal root basins, step() thresholds, df64 ULP, NEAREST coord tie-breaks) cannot be bit-exact
# cross-device (Metal vs ANGLE/WebGL2), so they are gated on structural SSIM (per-effect, with
# TD-measured pixel counts in the comments below).
#
# Self-contained: the DSLs are in-repo (parity/programs/) and the goldens are rendered from the
# upstream engine via NM_REFERENCE_ROOT (no sibling project assumed on clone).
#
#   NM_REFERENCE_ROOT=/path/to/noisemaker parity/sweep.sh   # classify + render goldens + compare
#   parity/sweep.sh --no-stage      # skip re-staging; use the DSLs/goldens already in out/
#   parity/sweep.sh --compare-only  # don't render; re-grade the existing candidates
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
PY="$REPO/parity/.venv/bin/python"; [ -x "$PY" ] || PY=python3
OUT="$REPO/parity/out"; CHUNK="${CHUNK:-15}"
LEDGER_PATH="${LEDGER_PATH:-parity/ledger.tsv}"
case "$LEDGER_PATH" in /*) ;; *) LEDGER_PATH="$REPO/$LEDGER_PATH" ;; esac
RESULTS="$(mktemp -t noisemaker-for-touchdesigner-ledger.XXXXXX)"
REPORTS="$(mktemp -d -t noisemaker-for-touchdesigner-reports.XXXXXX)"
trap 'rm -f "$RESULTS"; rm -rf "$REPORTS"' EXIT
record_result() {
  printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" >> "$RESULTS"
}

# Per-effect tolerance: "<max-abs-diff/255> <ssim-min>". Default 2.001 is the epsilon-tolerant
# form of "<= 2" (compare.py's float round-trip reads an exact 2.0 as 2.0000001). SSIM stays 0.98.
# Mode fixtures (`<effect>_<axis>_<value>.dsl`) share their base effect's mechanism, so they inherit
# its tolerance class (a compile-time-selected variant of the SAME shader — same cross-device residual).
tol_for() { case "$1" in
  newton)     echo "255 0.98" ;;  # Newton-fractal root basins = Julia set; df64 ULP across Metal/ANGLE (60 px)
  shadow)     echo "255 0.99" ;;  # step(threshold) flips fg<->shadow where mask ~= threshold (95 px); SSIM-gated
  uvRemap)    echo "22 0.98" ;;   # NEAREST coord-resampling tie-breaks on exact texel boundaries (30 px, 0.05%)
  distortion) echo "12 0.98" ;;   # Sobel-over-noise + NEAREST coord boundary amplifies +/-1 drift (7 px, 0.01%)
  edge|edge_kernel_*) echo "8 0.98" ;;  # x2 contrast convolution amplifies upstream 1-LSB noise; fine/bold
                                   # kernels are the same convolution mechanism (bold 6 px, fine 3 px)
  refract)    echo "8 0.98" ;;    # mirror wrap (default) reflects at a hard texel seam; NEAREST-adjacent
                                   # tie-break at the reflection boundary (3 px / 0.005%, ssim 0.99998)
  crt)        echo "3 0.98" ;;    # transcendental cos/pow seam flips one texel index (max diff exactly 2)
  parallax)   echo "24 0.98" ;;   # height-map raymarch step count flips at one grazing-angle texel
                                   # (1 px / 0.0015%, ssim 0.99998) -- df64-ULP-across-GPU class, like newton
  # --- selection / argmax-tie class: a discrete pick amplifies the 1-LSB cross-device noise INPUT
  #     (base noise is max-diff<=1); the pick is always a real neighbour so means + SSIM are preserved.
  oilPaint|oilPaint_mode_*) echo "110 0.98" ;;  # flatten pass's local-mode color VOTE ties at a pixel;
                                   # Metal/ANGLE pick a different (both locally-plausible) bucket. All 6
                                   # modes <=108 px (daubs 108, fresco 48, sponge 43, dryBrush 37, knife 27,
                                   # facet 19), ssim >=0.99998 -- argmax-tie class, like newton.
  median|median_radius_*) echo "255 0.99" ;;  # quickselect median RANK reorders under the 1-LSB input;
                                   # scatter scales with window (r1 mean 0.35 / r2 3.18 / r3 7.30), ssim
                                   # r1 0.99992 / r2 0.99871 / r3 0.99523; means identical -- rank-selection.
  hatch_mode_coloredPencil|hatch_coloredPencil_*) echo "255 0.99" ;;  # per-cell pencil-HUE selection flips a sparse pixel set to
                                   # a different (valid) pencil colour (rightDiag mean 0.20,
                                   # ssim 0.99986; leftDiag mean 0.20, ssim 0.99991).
  dither_type_errorDiffusion) echo "255 0.99" ;;  # Floyd-Steinberg diffusion is SEQUENTIAL; a 1-LSB input
                                   # flips a threshold that cascades then re-converges (mean 0.012, ssim
                                   # 0.99993) -- order-dependent, not bit-reproducible cross-device.
  strokes_mode_smudge) echo "255 0.99" ;;  # smear direction = perpendicular to the Sobel luminance gradient;
                                   # in near-flat regions the direction is ill-defined and a 1-LSB input
                                   # flips it, moving a sparse pixel set (mean 0.14, ssim 0.99996).
  # --- grazing-angle specular / reflection tie ---
  chrome)     echo "34 0.98" ;;   # reflection-map lookup grazing-angle NEAREST tie; the release-pass
                                   # ("distortion responsive") strengthened the warp, widening the tie set
                                   # from the old 2 px to 32 px (mean 0.13, ssim 0.99999).
  plasticWrap|plasticWrap_directed) echo "32 0.98" ;;  # specular-highlight grazing-angle tie; release-pass
                                   # vec3 light dir + stronger relief (default 20 px; directed 30 px;
                                   # mean <=0.14 and ssim 0.99998 for both).
  # --- warp / threshold / convolution +/-1-2 LSB boundary (unchanged shaders; cross-device residual) ---
  spiral|tunnel) echo "3 0.98" ;; # polar/radial warp with NEAREST resample -> texel-boundary tie (3 px)
  degauss)    echo "4 0.98" ;;    # CRT scanline displacement warp; NEAREST tie + transcendental (4 px)
  step)       echo "3 0.99" ;;    # hard step() threshold; boundary pixels flip under the 1-LSB input (ssim 1.0)
  unsharpMask) echo "3 0.98" ;;   # 3-pass blur + high-frequency amplification accumulates +/-1 LSB (3 px)
  relief_mode_plaster) echo "8 0.98" ;;  # relief bevel gradient boundary (explicit lightAngle 37:
                                   # max 7, mean 0.06, ssim 0.99999)
  *)          echo "2.001 0.98" ;;
esac; }

# Multi-frame FEEDBACK-ACCUMULATION effects. The single-frame sweep force-cooks ONE frame, so it
# cannot drive a feedback loop that only latches on a real engine tick. These are driven + graded
# separately by parity/accumulate.sh (the evolve harness IS that frame loop — 8 frames-from-zero,
# the reference golden protocol). Verdicts there (8/8 gated checks pass): cellularAutomata
# byte-identical at every frame (strict); motionBlur f1/f2 byte-exact then SSIM-gated at f8 (8-bit
# rgba8unorm feedback re-quantization rounding drift, Metal vs ANGLE); reactionDiffusion seed/f1/f2
# bit-exact then f4+ chaos-gated (continuous Gray-Scott — no stable golden; even two reference
# WebGL2 harnesses diverge). So here they are reported, not graded.
defer_reason() { case "$1" in
  cellularAutomata|reactionDiffusion|motionBlur|convolutionFeedback)
    echo "multi-frame feedback — driven + graded by parity/accumulate.sh (8/8 gated checks pass)" ;;
  synth3d_cellularAutomata3d|synth3d_reactionDiffusion3d)
    echo "3D-volume stateful (<sim>3d().render3d()) — driven + graded by parity/accumulate.sh (f1/f2 max-diff=1)" ;;
  *) echo "" ;;
esac; }

stage=1; render=1
for a in "$@"; do case "$a" in
  --no-stage)     stage=0 ;;
  --compare-only) stage=0; render=0 ;;
esac; done

if [ "$stage" = 1 ]; then "$PY" "$REPO/parity/stage_coverage.py" >/dev/null || exit $?; fi
SET="$(cat "$OUT/_render_set.txt" 2>/dev/null || true)"
[ -n "$SET" ] || { echo "no render set — run parity/stage_coverage.py first"; exit 1; }
if ! "$PY" "$REPO/parity/stage_coverage.py" --validate-set "$OUT/_render_set.txt"; then
  echo "[FAIL] render set does not match the expected staged universe"
  exit 1
fi

# 1. render all candidates (chunked TD sessions). Permissive tol so the render step always emits a
#    candidate; the authoritative verdict is the per-effect compare in step 2.
render_failed=""
if [ "$render" = 1 ]; then
  read -ra ALL <<< "$SET"; n=${#ALL[@]}; i=0
  while [ $i -lt $n ]; do
    chunk="${ALL[*]:i:CHUNK}"
    if ! TOL=255 SSIM=0 bash "$REPO/parity/run.sh" "$chunk" >/dev/null 2>&1; then
      render_failed="$render_failed $chunk"
    fi
    i=$((i + CHUNK))
  done
fi

# 2. per-effect compare with the tolerance table.
pass=0; fail=0; defer=0; failed=""
for name in $SET; do
  case " $render_failed " in
    *" $name "*)
      echo "[FAIL] $name (renderer exited nonzero)"
      record_result "$name" FAIL "TouchDesigner renderer exited nonzero" - -
      fail=$((fail + 1)); failed="$failed $name"; continue ;;
  esac
  d="$(defer_reason "$name")"
  if [ -n "$d" ]; then
    echo "[ACCUM] $name — $d"; record_result "$name" DEFER "$d" - -
    defer=$((defer + 1)); continue
  fi
  read -r TOL SSIM <<< "$(tol_for "$name")"
  if [ ! -f "$OUT/$name.golden.png" ]; then
    echo "[FAIL] $name (no golden)"; record_result "$name" FAIL "missing reference golden" "$TOL" "$SSIM"
    fail=$((fail + 1)); failed="$failed $name"; continue
  fi
  if [ ! -f "$OUT/$name.candidate.png" ]; then
    echo "[FAIL] $name (no candidate)"; record_result "$name" FAIL "missing TouchDesigner candidate" "$TOL" "$SSIM"
    fail=$((fail + 1)); failed="$failed $name"; continue
  fi
  report="$REPORTS/$name.json"
  if "$PY" "$REPO/parity/compare.py" "$OUT/$name.golden.png" "$OUT/$name.candidate.png" \
       --name "$name" --tolerance "$TOL" --ssim-min "$SSIM" --report "$report"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); failed="$failed $name"
  fi
  record_result "$name" REPORT "$report" "$TOL" "$SSIM"
done
if ! "$PY" "$REPO/parity/write-ledger.py" --root "$REPO" --results "$RESULTS" \
     --expected-set "$OUT/_render_set.txt" --output "$LEDGER_PATH"; then
  echo "[FAIL] canonical ledger contains rejecting or incomplete evidence: $LEDGER_PATH"
  if [ "$fail" -eq 0 ]; then fail=$((fail + 1)); failed="$failed ledger"; fi
fi
echo "=== SWEEP: $pass / $((pass + fail)) PASS, $defer via accumulate.sh${failed:+  — FAILED:$failed} ==="
[ "$fail" -eq 0 ]
