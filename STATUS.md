# Noisemaker for TouchDesigner — status & parity

*Last verified 2026-07-14 on Apple Silicon / Metal. Re-crystallized (full re-verification, not an
incremental sync) against upstream Noisemaker **content** frozen at commit `75507112`. **The SHA is
UNSTABLE** — upstream rebases/amends the artistic-filter batch in place, so this port pins by
reference CONTENT (tree-diffed, per-effect+mode parity-proven), never by history. The sources of
truth are `parity/sweep.sh`, `parity/accumulate.sh`, `parity/cubemap.sh`, `parity/compiler/check_*.py`,
and the machine-readable per-(effect,mode) ledger `parity/ledger.tsv`.*

*Incrementally synced 2026-07-23 to reference `349e9909` — `filter/pondRipples` gained a `speed`
control, the only port-affecting change in that range. Re-swept in full: **279/279 PASS** (6 via
`accumulate.sh`), including two new animated fixtures. Numbers below are refreshed accordingly.*

*Incrementally synced 2026-09-15 to reference `0ed489ec4684` (range `246ff57f43cc..0ed489ec4684`,
the same range ported into the sibling blender/cables/cpu/godot/qt/three.js ports this round;
catalog now 213 effects — +`synth3d/heightmap3d`, +`render/renderLandscape3d`, +`points/heightGrid`,
an isometric/perspective voxel landscape renderer). `render/pointsRender` + `render/pointsBillboardRender`
gain a perspective `viewMode` (2); billboard additionally gains a depth-sorted alpha-blend path
(`depthKeys`+`depthMerge`) and aperture defocus blur (`spriteMeanTiles`/`spriteMean`/`clearDefocus`).
`synth/remap`'s zone compositor was fully rewritten (UBO 267→275 std140 slots). Premultiplied-alpha
fixes landed in `filter/invert`, `filter/tint`, `filter/adjust`, `filter/grade`, `mixer/alphaMask`,
`mixer/blendMode`, `synth/media`, plus a gradient-normalization fix in `filter/chrome`.

*Incrementally synced 2026-09-17 to reference `688c5146` (range `5a14256732b5..688c514655d3`) — audited upstream WebGPU frame export row-inversion changes. TouchDesignerFrameExportAdapter in `td/noisemaker/runtime/td_frame_export.py` already applies `output[::-1]` on TOP.numpyArray() readback, correctly translating TouchDesigner bottom-row-first arrays to top-down row orientation. Verified via parity unit test suite (`./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"`, all 63 tests PASS).*

*Incrementally synced 2026-09-18 to reference `ead42a5d` (`688c514655d3..ead42a5df110a7f04d732cb200a1a39629db8a67`) — regenerated effect definitions via `tools/convert-definitions.mjs` (213/213 effects). Updated `defaultProgram` in `td/noisemaker/effects/synth3d/heightmap3d.json`, `td/noisemaker/effects/render/renderLandscape3d.json`, and `parity/programs/heightmap3d_landscape.dsl` to use discrete write/read chains. Verified compiler parity gates: check_lex (329/329 PASS), check_parse (329/329 PASS), check_validate (329/329 PASS), check_graph (328 PASS / 0 DIFF / 0 STAGE / 1 SKIP), and unit test suite (`./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"`, 63/63 PASS).*

Three real compiler bugs were found and fixed along the way (none specific to this round's new
effects — all three were pre-existing gaps this round's `.flatMap()`-per-viewMode-clone pattern was
the first to actually exercise): (1) pass-level `defines`/`conditions` (the clone pattern itself) had
NO propagation path in `expander.py` at all — every corpus program using `pointsRender`/
`pointsBillboardRender` compiled with only ONE deposit variant instead of the reference's 2-8 clones,
a ~30-50-pass-per-program gap on affected corpus files; (2) `tools/convert-definitions.mjs`'s
`projectPass()` captured `conditions` but not `defines` per pass (same class of gap independently
found in the blender/godot/cpu/qt ports this round); (3) `stateSize` texture-dimension scoping
preferred chain scope over the originating particle-pipeline id for a non-global texture that still
references it — matches a same-round reference fix, found via a real corpus diff not a guess. Also
implemented `TDBackend._should_skip_pass()`, which **did not exist before this round**: every pass
built unconditionally regardless of `conditions`, which was harmless pre-round (no effect had a
conditions-gated pass yet) but would have built ALL of pointsRender's/pointsBillboardRender's clone
variants simultaneously post-round — a double/triple-deposit bug of the same class independently
found and fixed in the cables and three.js sibling ports this session.

**Local verification only — no TouchDesigner session.** All four Python/Node compiler-parity gates
are clean: `check_lex.py`/`check_parse.py`/`check_validate.py` 324/324, `check_graph.py` 323/323 (1
skip, unrelated to this round). All app-free `parity/test_*.py` suites (12 files) pass. The
auto-transpiled shader corpus (`tools/convert-shaders.mjs`) regenerated cleanly for all 3 new effects
with no manual MRT finishing needed (output layouts/swizzle already matched the established
convention). `render/pointsRender`+`render/pointsBillboardRender`'s hand-maintained `deposit`
GL_POINT shaders (`td/noisemaker/runtime/deposit_shaders.py`, not part of the auto-transpiled
`shaders/` tree — TD has no bufferless draw) were extended for perspective mode and the depth-sort
reindex.

**Known limitation, newly introduced this round, NOT ported:** aperture defocus blur. The reference
renders each billboard as an oversized quad whose UV range is padded past `[0,1]` so a multi-sample
kernel against the `spriteMean` precompute can blend a wider footprint than the sprite itself. TD's
`deposit` shaders use `GL_POINTS` + `gl_PointSize` (a pre-existing architectural choice, already the
reason `rotationVar` is a documented gap) — `TDPointCoord()` is always exactly `[0,1]²` over the
point's own fixed footprint, with no way to pad it. `sizeDistance`/`brightnessDistance` fades and a
`gl_PointSize` growth with distance-from-focus ARE ported (pure per-vertex math, no quad needed);
the exact gaussian defocus blend is not. `depositDefocus_1`/`depositDefocus_2` and their `defocus`
precompute chain still build without erroring — they just contribute a plain sharp scatter rather
than the reference's wide footprint. **No pixel-parity evidence exists for ANY of this round's
changes** — this needs a TouchDesigner+GPU session to render and grade against fresh goldens
(`parity/run.sh <name>` per PORTING-GUIDE.md; NM_REFERENCE_ROOT + GODOT-equivalent TD binary path).
The billboard perspective+depth-sort+defocus path carries the most risk (hand-written GL_POINT GLSL,
no transpiler safety net, no local render capability to catch a mistake before a human/peer session
does); the 3 new effects' auto-transpiled shaders and the premultiplied-alpha/remap fixes carry much
less (byte-identical reference GLSL, same low-risk class as the cables/babylonjs/qt ports).

*GPU-verified 2026-09-16 (TouchDesigner on Apple Silicon / Metal, license-activated). Tier-1 smoke
set 8/8 PASS (unchanged from before this round). `remap`/`remap_zone` (zone-compositor rewrite):
both PASS, max-abs-diff=1 — confirms the rewrite is correct.*

**Real bug found + fixed:** `_build_effect()`'s shader-compile injection used `p.defines` directly,
but that field is (correctly, by reference design) always effect-level-only — the reference and this
port's own `expander.py` both bake a pass-clone's actual compile-time defines (`VIEW_MODE`/
`BLEND_MODE`/`BLUR_LAYER`) ONLY into the `__KEY_VALUE` suffix of the pass's `program` name, never
into `pass.defines` itself (`expander.py` says as much in its own comment: "a consumer that needs
the actual per-clone value... recovers it from the `__KEY_val` suffix" — but nothing did). This is
not test-only: `set_graph()` (the documented "build from a golden graph JSON" product API, used by
default whenever `NM_LIVE_DSL` isn't set) hits it identically to the live-DSL-compile path, since
neither ever populated `p.defines` with the per-clone value. Result: any `pointsBillboardRender`
pass selected by `conditions` on `viewMode`/`blendMode` (i.e. `depthKeys`, `depthMerge`) failed to
compile — `heightGrid_billboard_alpha`'s `depthKeys` clone hit exactly this: `ERROR: 'VIEW_MODE' :
undeclared identifier`, and the failed compile left the whole render near-blank (ssim 0.00002).
Fixed by adding `_defines_for_pass()` (parses the same `__KEY_VALUE` suffix back off `p.program`,
merged on top of `p.defines`) and using it at the one call site. Verified: the compile error is
gone, `heightGrid_billboard_alpha` now renders the correct terrain shape/colors (ssim 0.00002 ->
0.50), the existing 32-case local unittest suite and the Tier-1 smoke set are unaffected, and
`physical.dsl` (an existing corpus program using `pointsRender`) fails identically with or without
the fix (pre-existing, unrelated — confirmed by reverting and re-testing).

**Two of the three still-failing new fixtures are known, pre-existing limitations, not new bugs:**
- `heightmap3d_landscape`: FAILS pixel-parity (ssim 0.867) but the render log shows why — `"3D
  volume atlas clamped to volumeSize<=32 (TD cook-resolution cap; raise NM_MAX_VOLUME_SIZE on a
  Commercial license)"`. This is `_cap_volume_size()`'s documented, intentional Non-Commercial-license
  platform adaptation (reference uses volumeSize 64); the blockier voxel look is exactly what a 32
  vs 64 atlas predicts. Would pass on a Commercial license. Not a port bug.
- `heightGrid_pointsRender_perspective`: FAILS (ssim 0.693) but `NM_DIAG=1` shows `out-mean` is
  byte-identical across all 8 stepped "frames" (0.3966 every time) — confirming the pre-existing,
  already-documented Phase-5.5 limitation that a TD Feedback TOP only latches on a real engine frame
  tick, which this offline `force-cook` driver never generates, so accumulation-dependent effects
  always render frame-0's state. Not a new bug, not fixable without an async realTime/Movie-File-Out
  driver (bigger work than this verification pass).

**One real, NOT-yet-fixed finding — the aperture defocus path itself (not just its documented
missing blur), FOUND + PARTIALLY FIXED:** `heightGrid_billboard` (blendMode default/additive,
`aperture: 1.5` — the one fixture that actually exercises the defocus precompute chain, unlike
`heightGrid_billboard_alpha` whose `aperture` defaults to 0 and skips it entirely) rendered badly
wrong even after the compile fix above — correct terrain silhouette only in a thin band near the
top, everything below washed to white (ssim 0.671). Root cause: `diffuse.frag`'s `fragColor +=
sampleDefocus(uv)` (byte-identical to the reference — confirmed by diffing against
`glsl/diffuse.glsl`) adds the `node_7_defocus` accumulation-buffer content directly onto the trail
with no normalization, which is fine in the reference because its actual defocus contribution
(`deposit.frag`'s `shadeParticle()`/`blurWeight()`) is a wide, LOW-PEAK gaussian whose integral is
explicitly normalized (`1.0 / (0.19724318 * expansion * expansion)`) to stay bounded regardless of
overlap. TD's un-ported fallback (documented, intentional — see `deposit_shaders.py`'s module
docstring) is a plain FULL-PEAK sharp scatter instead, with no such normalization. Combined with the
`defocus` buffer being declared at 25% linear resolution (`pointsBillboardRender.json`: `"defocus":
{"width": "25%", "height": "25%"}`) — 1/16 the area of the main 256x256 trail — the SAME agent
population (density:100) lands 16x more concentrated per output pixel than in the main trail,
clipping straight past 1.0 once added back in.

Ruled out as red herrings along the way (so a future session doesn't re-check them): the
`"unresolved texId node_7_spriteMeanTiles"`/`"node_7_defocus"` warnings for both billboard fixtures
are benign — `spriteMean.frag` explicitly branches `if (shapeMode != 0) { fragColor =
vec4(proceduralCoverage()); return; }` before ever touching `tilesTex`, and our fixtures use
`shapeMode` defaulting to 1/circle, so the unresolved input is never read; and `_default_input_top()`
already correctly binds reference-matching transparent-black `(0,0,0,0)`.

**Fix:** added an `outputAreaScale` uniform to `BILLBOARD_VERT` (1.0 for the ordinary deposit whose
target matches the main canvas; the resolved output texture's area ratio vs the main canvas
otherwise — `(tw*th)/(width*height)`, bound per-pass in `td_backend.py`'s `_build_points()`),
multiplied into `vColor` alongside the existing `brightnessFade`. This is a linear first-order
compensation for the "same point density, 16x smaller target" effect — not a reproduction of the
reference's true non-constant per-point gaussian energy distribution (that would need porting the
actual oversized-quad multi-sample kernel, ruled out as out of scope for this pass, matching the
already-documented "gaussian blur itself is not ported" limitation). Verified: `heightGrid_billboard`
improves from ssim 0.671 (mean-abs-diff 64.97) to ssim 0.794 (mean-abs-diff 49.04) — most of the
terrain now shows correct shape and color; the remaining oversaturation concentrates specifically
where perspective projection creates the highest local point density and size (near-camera / bottom
of frame), which a single constant compensation factor can't fully correct — a spatially-varying fix
would need to actually port the reference's gaussian kernel, not a small follow-up. Confirmed zero
effect on `heightGrid_billboard_alpha` (aperture=0, this pass never runs), on plain `pointsRender`
(different shader, no `outputAreaScale` declared), on the Tier-1 smoke set (8/8 unchanged), and on
`physical.dsl` (byte-identical failure numbers before/after — pre-existing, unrelated).

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
