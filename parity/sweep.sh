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
# Pick an interpreter that has numpy + pillow (see parity/pylib.sh).
if ! PY="$(bash "$HERE/pylib.sh" "$REPO")"; then exit 2; fi
OUT="$REPO/parity/out"; CHUNK="${CHUNK:-15}"
LEDGER_PATH="${LEDGER_PATH:-parity/out/ledger.tsv}"
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
  oilPaint|oilPaint_mode_*) echo "110 0.98" ;;  # flatten pass's local-mode color VOTE ties at a pixel.
                                   # Measured 2026-10-07 (pin 8e583593, same-GPU goldens): with a
                                   # testPattern() input both engines render identically, oilPaint and all
                                   # its modes are byte-exact at every pass; the fixture's noise input
                                   # differs by one half-float step at 4 pixels (TD's SPIR-V/MoltenVK codegen
                                   # vs ANGLE's), and the vote flips there. Fixture max 108 (default/daubs).
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
  chrome)     echo "34 0.98" ;;   # reflection-map lookup grazing-angle NEAREST tie. Measured 2026-10-07:
                                   # byte-exact at every pass on a testPattern() input; the fixture's 4-pixel
                                   # one-step noise difference moves the lookup across the tie (max 32).
  plasticWrap|plasticWrap_directed) echo "32 0.98" ;;  # specular-highlight grazing-angle tie. Measured
                                   # 2026-10-07: byte-exact at every pass on a testPattern() input; the
                                   # fixture's 4-pixel one-step noise difference crosses the high-exponent
                                   # specular (default max 20, directed max 30).
  # --- warp / threshold / convolution +/-1-2 LSB boundary (unchanged shaders; cross-device residual) ---
  spiral|tunnel) echo "3 0.98" ;; # polar/radial warp with NEAREST resample -> texel-boundary tie (3 px)
  degauss)    echo "4 0.98" ;;    # CRT scanline displacement warp; NEAREST tie + transcendental (4 px)
  step)       echo "3 0.99" ;;    # hard step() threshold; boundary pixels flip under the 1-LSB input (ssim 1.0)
  unsharpMask) echo "3 0.98" ;;   # 3-pass blur + high-frequency amplification accumulates +/-1 LSB (3 px)
  relief_mode_plaster) echo "8 0.98" ;;  # plaster paper threshold. Measured 2026-10-07: byte-exact at
                                   # every pass on a testPattern() input; the fixture's 4-pixel one-step
                                   # noise difference crosses the threshold (max 7).
  *)          echo "2.001 0.98" ;;
esac; }

# Multi-frame cases (parity/write-ledger.py ACCUMULATION_CASES). The single-frame sweep force-cooks
# ONE frame, so it cannot drive state that only latches on a real engine tick. Each is driven and
# graded by parity/accumulate.sh (8 frames-from-zero, frames 1/2/8 against the reference) with the
# per-frame bounds in ACCUMULATION_NEAR; in --compare-only mode they are reported, not graded.
ACCUM="$("$PY" "$REPO/parity/write-ledger.py" --accumulation-cases)" || exit 2
is_accum() { case " $ACCUM " in *" $1 "*) return 0 ;; esac; return 1; }
defer_reason() { if is_accum "$1"; then echo "multi-frame — driven and graded by parity/accumulate.sh"; fi; }

stage=1; render=1
for a in "$@"; do case "$a" in
  --no-stage)     stage=0 ;;
  --compare-only) stage=0; render=0 ;;
esac; done

if [ "$stage" = 1 ]; then "$PY" "$REPO/parity/stage_coverage.py" >/dev/null || exit $?; fi
SET="$(cat "$OUT/_render_set.txt" 2>/dev/null || true)"
[ -n "$SET" ] || { echo "no render set — run parity/stage_coverage.py first"; exit 1; }
EXPECTED_SET="$OUT/_render_set.txt"
case "${NM_CASES:-}" in
  "")
    if ! "$PY" "$REPO/parity/stage_coverage.py" --validate-set "$OUT/_render_set.txt"; then
      echo "[FAIL] render set does not match the expected staged universe"
      exit 1
    fi ;;
  *)
    # Scoped run: only the named cases. The subset intentionally differs from the staged
    # universe, so the universe validation is skipped and the ledger is graded against the
    # subset instead.
    FILTER=""
    for want in $NM_CASES; do
      case " $SET " in *" $want "*) FILTER="$FILTER $want" ;; *)
        echo "[FAIL] unknown case: $want" >&2; exit 1 ;; esac
    done
    SET="$FILTER"
    EXPECTED_SET="$OUT/_expected_set.txt"
    printf '%s\n' $SET > "$EXPECTED_SET" ;;
esac

# 1. render all candidates (chunked TD sessions). Permissive tol so the render step always emits a
#    candidate; the authoritative verdict is the per-effect compare in step 2.
render_failed=""
if [ "$render" = 1 ]; then
  ALL=()
  for name in $SET; do
    is_accum "$name" && continue
    case "$name" in synth3d_renderCubemap3d|synth3d_renderCubemapSurface) ;; *) ALL+=("$name") ;; esac
  done
  n=${#ALL[@]}; i=0
  while [ $i -lt $n ]; do
    chunk="${ALL[*]:i:CHUNK}"
    chunk_log="$OUT/_chunk_render.log"
    if ! TOL=255 SSIM=0 bash "$REPO/parity/run.sh" "$chunk" >"$chunk_log" 2>&1; then
      reason="$(sed -n '/[^[:space:]]/{p;q;}' "$chunk_log" 2>/dev/null | tr -d '\t')"
      render_failed="$render_failed $chunk"
      render_reason="${reason:-run.sh exited without a message}"
    fi
    i=$((i + CHUNK))
  done
fi

# 2. per-effect compare with the tolerance table.
pass=0; fail=0; defer=0; failed=""
for name in $SET; do
  case "$name" in synth3d_renderCubemap3d|synth3d_renderCubemapSurface)
    report="$(dirname "$LEDGER_PATH")/$name.json"
    if [ "$render" = 1 ]; then
      rm -f "$report"
      if ! SIZE=256 TOL=2.001 SSIM=0.98 bash "$REPO/parity/cubemap.sh" "$name" --report "$report"; then
        record_result "$name" FAIL "cubemap harness exited nonzero" 2.001 0.98
        fail=$((fail + 1)); failed="$failed $name"; continue
      fi
    fi
    record_result "$name" CUBEMAP "$report" 2.001 0.98
    pass=$((pass + 1)); continue ;;
  esac
  case " $render_failed " in
    *" $name "*)
      echo "[FAIL] $name (renderer exited nonzero)"
      record_result "$name" FAIL "renderer exited nonzero: ${render_reason:0:120}" - -
      fail=$((fail + 1)); failed="$failed $name"; continue ;;
  esac
  if is_accum "$name" && [ "$render" = 1 ]; then
    read -r TOL SSIM <<< "$("$PY" "$REPO/parity/write-ledger.py" --accumulation-bound "$name")"
    report="$(dirname "$LEDGER_PATH")/$name.json"
    if bash "$REPO/parity/accumulate.sh" --effect "$name" --report "$report"; then
      record_result "$name" ACCUMULATE "$report" "$TOL" "$SSIM"
      pass=$((pass + 1))
    else
      record_result "$name" FAIL "$name accumulation exited nonzero" "$TOL" "$SSIM"
      fail=$((fail + 1)); failed="$failed $name"
    fi
    continue
  fi
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
     --expected-set "$EXPECTED_SET" --output "$LEDGER_PATH"; then
  echo "[FAIL] canonical ledger contains rejecting or incomplete evidence: $LEDGER_PATH"
  if [ "$fail" -eq 0 ]; then fail=$((fail + 1)); failed="$failed ledger"; fi
fi
echo "=== SWEEP: $pass / $((pass + fail)) PASS, $defer via accumulate.sh${failed:+  — FAILED:$failed} ==="
[ "$fail" -eq 0 ]
