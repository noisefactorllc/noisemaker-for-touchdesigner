# noisemaker-td — status & parity

*Last verified 2026-07-10 on Apple Silicon / Metal, synced through upstream Noisemaker commit
`36e7f3f5`. The sources of truth are `parity/sweep.sh`, `parity/corpus_sweep.sh`, and
`parity/compiler/check_*.py`.*

This file holds the detailed coverage and parity numbers. For what the project is and how to use it,
see the [README](README.md).

## Coverage

**210 effect definitions** and **297 transpiled programs** across 8 namespaces (275 auto-transpiled,
22 hand-flagged: 21 MRT + 1 std140-UBO).

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
| **total** | **210** | **297** | |

`filter` grew by 21 (the b7c1bc36 sync's Photoshop-parity batch): `parallax`, `unsharpMask`,
`highPass`, `median`, `morphology`, `directionalBlur`, `spinBlur`, `scatter`, `wind`, `pondRipples`,
`extrude`, `halftone`, `stipple`, `oilPaint`, `watercolor`, `plasticWrap`, `relief`, `photocopy`,
`stamp`, `chrome`, `hatch` — all auto-transpiled (no MRT/UBO flags), all at single-frame pixel parity.
That sync also extended `lighting` (height-map input), `emboss` (angle/height + rotation-handedness
alignment), `invert` (solarize mode), `edge` (contour tracing), and `grain` (grain types + a
hash-coordinate cross-backend parity fix), and carried two more shader-level fixes into already-shipped
effects: `simpleAberration` (GL2 Y-orientation) and `classicNoisedeck`'s `cellRefract`/`refract`
(mirror wrap mode was a no-op; now reflects). All 29 are at pixel parity — see `parity/sweep.sh`'s
`tol_for()` for the handful that needed a documented SSIM gate (`parallax`, `oilPaint`, `chrome`,
`refract` — each a single-digit-pixel-count grazing-angle/tie-break residual, ssim ≥ 0.99998).

The b7c1bc36..36e7f3f5 sync then added 5 more (`strokes`, `craquelure`, `mosaicTiles`, `patchwork`,
`lensFlare`) and extended `lowPoly` (stained-glass `borderWidth`/`lightIntensity`, both exact
0=off no-ops) — all auto-transpiled, all at default-tolerance pixel parity with **no new SSIM gates**
(max-abs-diff ≤ 2/255, ssim ≥ 0.99998 across all 6). Two of the five (`craquelure`, `mosaicTiles`)
share a bevel-polarity idiom worth noting for future ports: a carved groove/dip must feed
`reliefShade` a **negated** height (`hC = -k`, not `+k`) or the bevel lights the wrong wall, and
`reliefShade`'s flat-gradient baseline is `0.6` for any light angle (not the naively-assumed `0.5`) —
`craquelure` additionally gates its bevel multiplier by a `wallMask` (the crack mask's gradient
magnitude) since its border wobble doesn't saturate to a hard flat plateau the way `mosaicTiles`'
grout mask does. `lensFlare` separately fixed four ghost helpers calling `smoothstep(edge0, edge1, x)`
with `edge0 > edge1` (implementation-defined per the GLSL spec) — normalized to
`1 - smoothstep(edge1, edge0, x)`. `strokes`' WGSL-only `textureSampleLevel` early-exit fix (WGSL
can't `break` out of a per-pixel-bounded loop before an unconditional `textureSample` the way GLSL
can) has no GLSL-side counterpart — the reference GLSL twin already used a plain `break`. None of
this round's changes needed an expander.py/validator.py fix (no new surface-arg kinds, MRT, or
compute passes — unlike b7c1bc36's `filter/lighting` height-map-input feature, below).

## Parity

- **In-engine compiler:** all four compiler-parity gates are byte-exact against the reference oracle
  over a 212-program corpus — lexer / parser / validator **212/212**, graph **211/212** (the 1 skip is
  `B5oBsA`, a nonexistent effect the reference also rejects).
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
- **2D catalog (single-frame, `parity/sweep.sh`):** ~**165 single-pass** effects at parity — byte-exact,
  or SSIM-gated for cross-rasterizer discontinuities — plus multi-pass and stateful effects. Most land
  within 1/255; a few discontinuity-heavy effects are gated on structural **SSIM ≥ 0.98**.
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
clone provides this; it is intentionally not a noisemaker-td dependency (this repo's own tooling has
zero npm dependencies by design — see `tools/package.json`).
