# Noisemaker for TouchDesigner — status & parity

*Last verified 2026-07-14 on Apple Silicon / Metal. Re-crystallized (full re-verification, not an
incremental sync) against upstream Noisemaker **content** frozen at commit `75507112`. **The SHA is
UNSTABLE** — upstream rebases/amends the artistic-filter batch in place, so this port pins by
reference CONTENT (tree-diffed, per-effect+mode parity-proven), never by history. The sources of
truth are `parity/sweep.sh`, `parity/accumulate.sh`, `parity/cubemap.sh`, `parity/compiler/check_*.py`,
and the machine-readable per-(effect,mode) ledger `parity/ledger.tsv`.*

This file holds the detailed coverage and parity numbers. For what the project is and how to use it,
see the [README](README.md).

## Coverage

**210 effect definitions** and **295 transpiled programs** across 8 namespaces (273 auto-transpiled,
22 hand-flagged: 21 MRT + 1 std140-UBO). Two structural drifts landed in this crystallization beyond
the tracked artistic-filter batch: `filter/median` collapsed from a 3-pass `seed`/`pass`/`final`
chain to a **single exact-quickselect pass** (−2 programs), and `render/renderCubemap3D` was renamed
`render/renderCubemap3d` to match the reference's lowercase-`3d` convention (a directory/func rename,
net 0 programs).

| Namespace | Effects | Programs | Status |
|---|---|---|---|
| `synth` | 29 | auto | renders (generators, fractals, value/simplex/cell noise) |
| `filter` | 116 | auto | renders (color ops, convolutions, warps, multi-pass, feedback) |
| `mixer` | 15 | auto | renders (whole namespace; `remap` via std140 UBO) |
| `classicNoisedeck` | 20 | auto | renders (legacy generators) |
| `points` | 10 | MRT/points (manual) | renders — agents; chaotic flows chaos-gated |
| `render` | 11 | MRT/points (manual) | renders — agent render, 3D raymarch, cubemaps |
| `synth3d` | 7 | MRT (manual) | renders (3D volume) |
| `filter3d` | 2 | MRT (manual) | renders (3D volume) |
| **total** | **210** | **295** | |

### Crystallization (2026-07-14) — re-verified against frozen reference content `75507112`

Upstream squashed the artistic-filter batch into one amended-in-place commit and did a
release-readiness pass that **changed effects already ported**. Because the batch SHA is unstable
(rebase/amend), this round diffed reference **trees** (a `git archive` snapshot of `75507112`), not
histories, and re-minted a golden for **every effect and every mode**. The port's codegen
(`tools/convert-{definitions,shaders}.mjs`) is content-driven, so the re-port was mechanical: regenerate
from the pinned snapshot, tree-diff against the committed port, and re-prove by pixel parity.

**37 reference effect dirs had drifted.** All were re-crystallized to the frozen content. The
release-pass corrections captured: `strokes` (single-pass `MODE==3`-gated Sumi-e via a locally-eroded
`srcSample()` — the separate `stkErode` pass is gone; the whole smear was reworked to coherent
value-noise fields); `texture` (10 material modes, smooth quintic gradient fields); `edge` (contour
kernel `kernelType==2`, dead tile uniforms dropped); `emboss` (color/gray styles); `invert` (opt-in
solarize); `lowPoly` (flat/edges/distance2/distance3 + border/light); `median` (exact quickselect,
radii 1/2/3, **3→1 pass**); `oilPaint` (loop-domain→`ceil(radius)`+`texelFetch` optimization,
byte-identical); `craquelure`/`mosaicTiles` (dead `fullResolution` removed); and the WGSL-only
rotation/jitter fixes in `hatch`/`pondRipples`/`stipple`/`strokes`/`spinBlur` (verified N/A to this
GLSL-sourced port — GLSL is the reference-correct side). **`grain` was reverted upstream** back to its
pinned `alpha`/`pause`-only form (the round-1 grain-types feature is gone) — the port matches. The
WGSL-only effects (`synth/sacredGeometry`, `synth/mandala`) and help.md-only changes
(`mixer/channelCombine`, `filter/temporalAberration`) are byte-identical N/A (GLSL unchanged, verified).
`Pipeline.adoptIterationBindings` is re-confirmed structurally N/A: TD unrolls `repeat:N` into N chained
GLSL TOPs (`td_backend.build`), so there is no frame-local ping-pong to re-adopt.

**Every definition now carries a `uniformLayout` block** (previously only `synth/remap`). It is inert
on the GLSL/Vectors-page path this port mirrors: `td_backend` reads it **only** when the `.frag`
declares a `uniform vec4 data[N]` array (still `synth/remap` alone), and the compiler propagates it
generically — proven by graph parity holding at 312/313 across the change.

**Full effect×mode ledger — all green** (`parity/ledger.tsv`): **300 graded cases, 0 FAIL** —
**265 PASS** (strict: max-abs-diff ≤ 2/255, ssim ≥ 0.98) + **33 NEAR** (mechanism-traced, in a
documented cross-device tolerance class — see `parity/sweep.sh`'s `tol_for()`) + **2 chaos-gated**
(continuous Gray-Scott `reactionDiffusion` f8, reported). **101 per-mode fixtures** cover every
compile-time-`define`-selected variant of the 33 changed filter effects (128 enum modes across 20
effects) plus the define-gated boundary params (`median` radii, `lowPoly` border/light, `pondRipples`
100%). The NEAR classes are all discrete-selection / grazing-angle / warp-boundary residuals where a
1-LSB cross-device input (Metal vs ANGLE) flips a discrete decision: `median` (quickselect RANK — the
biggest, ssim 0.995, scatter scales with window: r1 0.35 / r2 3.18 / r3 7.30 mean-diff; the base noise
input is max-diff ≤ 1, proving the amplification), `oilPaint`+6 modes (argmax color vote, ≤ 108 px),
`chrome` (reflection grazing tie, widened to 32 px by the release-pass stronger warp), `plasticWrap`
(specular grazing), `dither_type_errorDiffusion` (sequential Floyd-Steinberg cascade),
`hatch_mode_coloredPencil` (per-cell hue tie), `strokes_mode_smudge` (Sobel-gradient direction tie),
`edge` kernels (convolution amplifies 1-LSB), and the unchanged warp/threshold set
(`spiral`/`tunnel`/`step`/`degauss`/`unsharpMask`/`relief` plaster, 3–4 px). `convolutionFeedback` was
re-routed to `parity/accumulate.sh` (it is a multi-frame feedback effect — f1/f2 byte-exact, f8
SSIM-gated 0.99483 — but `sweep.sh`'s `defer_reason()` had never listed it, so the single-frame sweep
mis-graded it; now aligned with `stage_coverage.py`'s `ACCUM_EFFECTS`).

For the pre-crystallization sync narrative (the b7c1bc36 / 36e7f3f5 Photoshop-parity batches, the
`filter/lighting` height-map-input expander fix, and the `craquelure`/`mosaicTiles` carved-relief
idiom), see the git history of this file.

## Parity

- **In-engine compiler:** all four compiler-parity gates are byte-exact against the reference oracle
  (the `75507112` snapshot) over a **313**-program corpus (the base 212 + 101 per-mode fixtures) —
  lexer / parser / validator **313/313**, graph **312/313** (the 1 skip is `B5oBsA`, a nonexistent
  effect the reference also rejects).
  `parity/compiler/check_{lex,parse,validate,graph}.py`. (The b7c1bc36 sync's `filter/lighting` /
  `filter/parallax` height-map-input feature — a `type:"surface"` global defaulting to
  self-sampling the pipeline input — needed a matching expander.py fix:
  `_map_inputs`/`_COLORMODE_SURFACE_KINDS` didn't recognize the `pipeline` surface-arg kind the
  reference's `isTextureArg`/`TEXTURE_ARG_KINDS` (commit ad984822) introduced. Porting it also fixed
  a latent, pre-existing graph-parity DIFF on `synth3d_cellularAutomata3d`/`synth3d_reactionDiffusion3d`
  — `vol`/`geo` surface-arg kinds were leaking `source`/`geoSource` into `pass.uniforms` — the same
  upstream commit's `TEXTURE_ARG_KINDS` also covers `vol`/`geo`, confirmed by A/B testing against the
  pre-fix expander. The following 36e7f3f5 sync's 5 filters + 1 extension needed no compiler-side
  change — all plain float/int/color globals, no new surface-arg kinds.)
- **2D catalog + per-mode (single-frame, `parity/sweep.sh`):** **268/268 gateable programs PASS**
  (default effects + the 101 per-mode fixtures). Across the whole ledger (`parity/ledger.tsv`, 300
  graded cases incl. feedback + cubemap): **265 strict PASS** (byte-exact / within 1–2 LSB) + **33
  NEAR** (SSIM-gated cross-rasterizer discontinuities, each mechanism-traced in `tol_for()`) + **2
  chaos-gated**, **0 FAIL**. Discontinuity-heavy effects are gated on structural **SSIM ≥ 0.98**.
- **Stateful / feedback:** `cellularAutomata`, `reactionDiffusion`, `motionBlur`,
  `convolutionFeedback`, and the two 3D variants are driven 8-frames-from-zero through the evolve
  harness (`parity/accumulate.sh`) — discrete CAs byte-exact every frame; continuous solvers bit-exact
  early, then chaos-gated.
- **Full 3D namespace:** volume raymarch (`render3d` / `renderLit3d`) at SSIM ~1.0 / max-diff 1; 6-face
  cubemap bake (`parity/cubemap.sh`) max-diff ≤ 1; `flow3d` 3D-agent flow chaos-gated.
- **std140 UBO:** `remap` is byte-identical via the GLSL TOP Arrays page.
- **Live blaster corpus:** 24/24 renderable composition programs render end-to-end through the live
  compiler (`parity/corpus_sweep.sh`).

Two producers emit **byte-identical** render graphs: the in-engine Python compiler (production) and the
reference `compileGraph` via `tools/export-graph.mjs` (used only to verify the in-engine one).
Rendering either graph produces the same network.

## Known limits

- **The chaos gate.** Every effect is bit-exact to the reference *except chaotic agent flows and
  continuous solvers* (and the flagship `present_hero.dsl`, which feeds particles into a fluid solver):
  those render correctly but as a *different instance* of the chaos, gated by a spec-legal ~1-ULP
  rounding difference that the chaotic loop amplifies. A second, milder class drifts ≤1–2 LSB at
  resampling / discontinuity boundaries and is SSIM-gated. Cause, evidence, and repro:
  [docs/CHAOS-GATE.md](docs/CHAOS-GATE.md).
- **Point rasterization.** TouchDesigner / Metal cannot byte-match WebGL2's point rasterization, so
  particle-deposit chains carry a small residual amplified by feedback — details in
  [docs/TD-PLATFORM-NOTES.md](docs/TD-PLATFORM-NOTES.md).
- **3D-volume clamp:** `NM_MAX_VOLUME_SIZE` defaults to **32** so the volume atlas stays under the free
  tier's 1280×1280 cook limit. Raise it on a Commercial/Educational license (no 1280 cap).
- **Platform:** verified on Apple Silicon / Metal only; rendering needs a logged-in GPU desktop
  (TouchDesigner is not headless).

## Why translate from the reference GLSL (not WGSL)

TouchDesigner's **GLSL TOP** is OpenGL GLSL with the **same bottom-left raster origin** as the
reference's WebGL2 backend. So the per-effect shaders are translated **directly from the reference
GLSL** by a mechanical transpiler — no Y-flip and no math edits, unlike ports onto a top-left /
Vulkan-style target. Most programs are produced automatically; the 22 hand-flagged ones use
multiple-render-target output (agents, 3D volumes) or the std140 uniform-block path (`remap`).

## Regenerating assets (maintainers)

The committed effect JSON and `.frag` shaders are generated from the upstream Noisemaker engine. You
only need this to update them or mint parity goldens — **not to render**. All codegen reads the engine
via `NM_REFERENCE_ROOT` (required; no default — point it at the upstream Noisemaker engine tree
containing `shaders/`, which is not included in this repo). Needs **Node 26**.

```bash
NM_REFERENCE_ROOT=/path/to/noisemaker node tools/convert-definitions.mjs   # 210 effect JSONs
NM_REFERENCE_ROOT=/path/to/noisemaker node tools/convert-shaders.mjs       # 297 .frag (275 auto, 22 flagged)
NM_REFERENCE_ROOT=/path/to/noisemaker node tools/export-graph.mjs --file parity/programs/solid.dsl parity/out/solid.graph.json
```

Goldens, candidate PNGs, and `.toe` files are gitignored (generated). A bare clone renders via the
live compiler immediately; reproducing the parity *numbers* requires regenerating goldens, which needs
the upstream engine via `NM_REFERENCE_ROOT`.

Golden PNGs (`parity/export-and-render.mjs`) need `playwright` resolvable from
`NM_REFERENCE_ROOT`'s own `node_modules` (it drives `vendor/shade-mcp`'s headless-Chromium harness
against the upstream repo's own `demo/` viewer) — a normal `npm install` inside a full upstream
clone provides this; it is intentionally not a noisemaker-for-touchdesigner dependency (this repo's own tooling has
zero npm dependencies by design — see `tools/package.json`).
