# noisemaker-for-touchdesigner: compatibility report

## 1. Source and authority revisions

Daily review: 2026-09-26. Current inspected source: [`143a89915429f97b16c4f85efedafd739ca8c0b7`](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/commit/143a89915429f97b16c4f85efedafd739ca8c0b7).
Full rendered parity remains **unverified**. No release approval follows from this review.
Current synced reference: `403c2a4bf2cb` (port commit `143a899`, audit-only round). Upstream head at review: `0ac5250052e2b2e683f086959451c3bad8369a68`, docs-only above `403c2a4bf2cb` with an identical `shaders/` tree. Published Noisemaker authority: `1.0.185`, 210 effect IDs, recorded source `6a0af04d3c4f345ffab5e9f8e54e532216b4cdaa` ([manifest](https://shaders.noisedeck.app/1.0.185/effects/manifest.json), retrieved 2026-09-26). Authority reconciliation, measured by this review: `git diff --stat 6a0af04d..403c2a4 -- shaders/` lists exactly 8 changed files. They are `src/lang/transform.js`, `src/lang/paramAliases.js` (new), `src/index.js`, `src/lang/index.js`, and four test-harness files — the GAP-008/009 delivery that the port's `143a899` range audit classified as having no TD consumption path. The compiler oracle surface (`lexer.js`, `parser.js`, `validator.js`, `diagnostics.js`) and the effect definitions are unchanged between `6a0af04d` and the tested reference. The re-run compiler gates therefore cover the same compiled surface as the published authority. Rendered goldens for the planned sweep must come from the published authority source `6a0af04d` (or a tree with an identical `shaders/` surface).
The observations below retain their original source and authority identities. They do not qualify later updates.
Current served kit: `0.1.27`, source `3064d0dc9c58840bf7a1510ffd37f7707b6cc9ba` (retrieved and spot-verified 2026-09-26; the served `integrate.py` and `README.template.md` carry the corrected in-COMP `out` wiring, byte-identical to the `3064d0dc` tree). At the 2026-09-25 review the served kit was `0.1.23`, source `de416d7606e231bf6e38027316269640a1d7d096`. The intervening `0.1.26` artifact (source `6c96151d`) was byte-verified and then replaced by the rolling deployment. Artifact identity does not establish host qualification. The executed kit host legs ran on the frozen `0.1.26` artifact (2026-09-26, see [completion gaps](COMPLETION_GAPS.md), section 3). No `0.1.27` host install exists.

### Earlier source observations

Report date: 2026-09-24. Source inspected: [`66426bc41c2b85940322ae843ba04f41b7905ce4`](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/commit/66426bc41c2b85940322ae843ba04f41b7905ce4).
Full rendered parity at this SHA: **unverified**. This is not a release approval.
A later documentation-only commit does not change this tested source identity.
Any runtime, package, or authority update requires fresh evidence before this report can qualify it.

TouchDesigner Python compiler and native operator network. README requires an activated GPU desktop and identifies build 2025.32820 on Apple Silicon. [Source contract](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md).

Latest status entry records upstream `5b81e04f8a4b53c2be43b8e328cee0c3365f352f`. Runtime and rendered evidence beyond that revision remain unverified.
Current upstream discovery SHA: `c9ee8a049b2b63cd300da67c01ee40baf29dc288`.
Published authority: `1.0.176`, source `c9ee8a049b2b63cd300da67c01ee40baf29dc288`.
[Immutable published manifest](https://shaders.noisedeck.app/1.0.176/effects/manifest.json) contains 210 effect IDs.
Its SHA-256 is `05c4d7b7744837ae90a3bb4c89e5403ff09448a74d9d7e824abb3d719ad3314e`.
These IDs do not define complete parameter, state, input, or platform coverage.

Served kit `0.1.20` records `66426bc41c2b85940322ae843ba04f41b7905ce4`. [Source metadata](https://kits.noisedeck.app/touchdesigner/0/deployment-meta.json).
Historical measurements remain bound to their original revisions in [completion gaps](COMPLETION_GAPS.md).

## 2. Host and distribution matrix

Current tests and qualification limits are in [section 3](#3-parity-coverage).
The matrix below retains the earlier measured scope. A historical verified row is not a current-source or full-platform certification.

| Dimension | Status | Measured scope or limit |
|---|---|---|
| Source-level checks | verified | 119 Python unit tests passed at `143a899` (review re-run 2026-09-26; earlier 76-test and 118-test runs retained in the pass history). License activation on fresh installs and accessibility were not exercised. |
| Actual host rendering | verified | Three declared native `touchdesigner-parity` cases (`adjust`/`alphaMask`/`bitwise`) passed at thresholds 2/0.98 across four machine-verification receipts; the 2026-09-26 review re-ran the workflow probe on TD 2025.32820 and reproduced the documented-example render byte-identically. The full 301-fixture sweep remains unexecuted (GAP-004). |
| Minimum and current host versions | blocked (minimum verified) | Minimum supported build 2025.32820 qualified: compiler gates (326/326 lex/parse/validate, graph 325 PASS/1 SKIP) run on Linux at source `6c96151` per the pass history and re-run at `143a899` by the review, native `touchdesigner-parity` cases `adjust`/`alphaMask`/`bitwise` passed at thresholds 2/0.98, plus the full installed workflow (isolated Base COMP, documented NMRenderer example, TOP connect/resize, invalid-DSL recovery, save/reopen, cleanup) and the native-parity machine-verification receipts — [Completion gaps](COMPLETION_GAPS.md), section 3, 2026-09-26. The current official build 2025.33230 leg is blocked for automation: not installed on the only reachable host and obtainable only via a licensed Derivative download channel. |
| Supported operating systems and backends | unverified | This pass does not establish Windows, Linux, and macOS coverage. |
| Installed package and first useful result | verified for `0.1.26`; `0.1.27` unverified | The executed install/render legs ran on the frozen served kit `0.1.26` (source `6c96151d`) on TD 2025.32820. It was installed per its README: isolated project, kit `onStart` build at load, meaningful 1280×1280 render from the kit's own output TOP, mean 0.674927. The current served kit `0.1.27` (source `3064d0dc`) received a file-level spot check only (4 of 852 files inventory- and tree-verified; the corrected in-COMP `out` wiring is present in the served bytes). No `0.1.27` install or first-result on a host exists, and the corrected wiring has not been exercised through a kit install. [Completion gaps](COMPLETION_GAPS.md), section 3, 2026-09-26. |
| Parameters, external inputs, state, and chains | unverified | Full current-authority combinations remain unmeasured. |
| Invalid input and recovery | verified (documented example entry point) | Invalid DSL at the documented example raises `DslSyntaxError` with a structured `L001` lexer diagnostic and recovers to a valid render (workflow probe, re-verified by the review re-run 2026-09-26). Other installed public entry points remain unmeasured. |
| Upgrade, removal, and resource cleanup | verified | Saved-project relocation, version-delta upgrade (older kit from source history `66426bc` → served `0.1.26`, in place, reopen/rebuild byte-identical), reinstall-over, and removal verified with the served kit on TD 2025.32820. A served-version-to-served-version upgrade pass does not exist (single rolling deployment). [Completion gaps](COMPLETION_GAPS.md), section 3, 2026-09-26. |
| Accessibility of provided controls | unverified | Keyboard, focus, labels, and diagnostics need host observations where applicable. |
| Release readiness | blocked | Full parity and the platform matrix remain incomplete; installation, kit legs, and artifact evidence are qualified (2026-09-26 — [completion gaps](COMPLETION_GAPS.md), section 3). |

## 3. Parity coverage

### Daily review, 2026-09-26

The reviewer re-executed the recorded gates at head `143a899` (Linux x86_64, reference checkout at `0ac52500`, content-equivalent to the synced `403c2a4bf2cb`): 119/119 unit tests, lexer/parser/validator parity 326/326 each, definitions conversion 210/210 with an empty tree diff. The declared native `touchdesigner-parity` cases `adjust`/`alphaMask`/`bitwise` passed at thresholds 2/0.98 across four machine-verification receipts at published candidates. The workflow probe was re-run on TD 2025.32820 and reproduced the documented-example render byte-identically. See [completion gaps](COMPLETION_GAPS.md), section 3.

| Gate | Expected cases | Executed | Strict passes | Failures | Skips | Status |
|---|---|---|---|---|---|---|
| Compiler lexer parity | 326 | 326 | 326 | 0 | 0 | verified (review re-run) |
| Compiler parser parity | 326 | 326 | 326 | 0 | 0 | verified (review re-run) |
| Compiler validator parity | 326 | 326 | 326 | 0 | 0 | verified (review re-run) |
| Compiler graph parity | 326 | 326 | 325 | 0 | 1 rejection-parity SKIP | verified (both producers reject `B5oBsA.dsl`) |
| Declared native parity cases | 3 | 3 | 3 at thresholds 2/0.98 | 0 | 0 | verified (four machine receipts; review re-ran the workflow probe) |
| Full 301-fixture native sweep | 301 | 5 | not measured | not measured | not measured | unverified (GAP-004) |

The full sweep denominator is 301 program fixtures plus corpus, per-mode, stateful, and cubemap coverage. Five fixtures have native evidence; 296 remain unexecuted at the current authority. Unknown values mean `not measured`, never zero.

### Daily review, 2026-09-25

91 harness tests pass. The actual TouchDesigner process renders the current runtime: solid is byte-exact and noise differs by at most 1 in 38,396 channels against retained historical goldens. Both cases executed. This two-case result does not qualify the current authority, full fixture inventory, Windows, or installed workflows. TouchDesigner retains equal priority with every other port. [Raw evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-native-comparisons.json).

The current full case denominator remains incomplete. Missing parameters, hosts, external inputs, and stateful sequences remain qualification gaps. No skip or tolerated difference counts as exact parity.

### Earlier measurements

Full parity requires complete applicable coverage with no skips or missing cases.
Historical NEAR, CHAOS, and tolerated differences do not count as strict equality.
The existing numerical contracts remain separate from exact comparison. This report does not change tolerances or goldens.
Unknown values mean `not measured`, never zero.

| Gate | Expected cases | Executed | Strict passes | Failures | Skips | Status |
|---|---|---|---|---|---|---|
| Current full render suite | not measured | not measured | not measured | not measured | not measured | unverified |
| Retained native probes | 2 | 2 | 1 | 1 exact mismatch | 0 | bounded probe; historical golden provenance unverified |

Earlier served compatibility inventory declares 207 effect IDs. Declaration does not establish execution or parity.
IDs absent from the served declaration: `synth/media`, `synth/scope`, `synth/spectrum`.
Missing effects remain visible toward the full-parity goal. Contract exclusions do not become successful tests.

Current served declaration: 207 effect IDs (kit `0.1.27`, `compat.json` sha256 `b4c57ae75efe…`, unchanged from the `0.1.26` verification). This inventory is not evidence of execution. The declaration column below reflects the current served kit.

### Effect inventory

| Effect ID | Declared in served kit | Current full parity |
|---|---|---|
| `classicNoisedeck/bitEffects` | yes | unverified |
| `classicNoisedeck/caustic` | yes | unverified |
| `classicNoisedeck/cellNoise` | yes | unverified |
| `classicNoisedeck/cellRefract` | yes | unverified |
| `classicNoisedeck/coalesce` | yes | unverified |
| `classicNoisedeck/colorLab` | yes | unverified |
| `classicNoisedeck/composite` | yes | unverified |
| `classicNoisedeck/effects` | yes | unverified |
| `classicNoisedeck/fractal` | yes | unverified |
| `classicNoisedeck/glitch` | yes | unverified |
| `classicNoisedeck/kaleido` | yes | unverified |
| `classicNoisedeck/lensDistortion` | yes | unverified |
| `classicNoisedeck/moodscape` | yes | unverified |
| `classicNoisedeck/noise` | yes | unverified |
| `classicNoisedeck/noise3d` | yes | unverified |
| `classicNoisedeck/refract` | yes | unverified |
| `classicNoisedeck/shapeMixer` | yes | unverified |
| `classicNoisedeck/shapes` | yes | unverified |
| `classicNoisedeck/shapes3d` | yes | unverified |
| `classicNoisedeck/splat` | yes | unverified |
| `filter/adjust` | yes | unverified |
| `filter/bloom` | yes | unverified |
| `filter/blur` | yes | unverified |
| `filter/bulge` | yes | unverified |
| `filter/celShading` | yes | unverified |
| `filter/channel` | yes | unverified |
| `filter/chroma` | yes | unverified |
| `filter/chromaticAberration` | yes | unverified |
| `filter/chrome` | yes | unverified |
| `filter/clouds` | yes | unverified |
| `filter/colorReplace` | yes | unverified |
| `filter/convolutionFeedback` | yes | unverified |
| `filter/corrupt` | yes | unverified |
| `filter/craquelure` | yes | unverified |
| `filter/crt` | yes | unverified |
| `filter/degauss` | yes | unverified |
| `filter/deriv` | yes | unverified |
| `filter/directionalBlur` | yes | unverified |
| `filter/dither` | yes | unverified |
| `filter/edge` | yes | unverified |
| `filter/emboss` | yes | unverified |
| `filter/extrude` | yes | unverified |
| `filter/feedback` | yes | unverified |
| `filter/fibers` | yes | unverified |
| `filter/flipMirror` | yes | unverified |
| `filter/fxaa` | yes | unverified |
| `filter/glowingEdge` | yes | unverified |
| `filter/glyphMap` | yes | unverified |
| `filter/grade` | yes | unverified |
| `filter/grain` | yes | unverified |
| `filter/grime` | yes | unverified |
| `filter/halftone` | yes | unverified |
| `filter/hatch` | yes | unverified |
| `filter/highPass` | yes | unverified |
| `filter/historicPalette` | yes | unverified |
| `filter/invert` | yes | unverified |
| `filter/lens` | yes | unverified |
| `filter/lensFlare` | yes | unverified |
| `filter/lensWarp` | yes | unverified |
| `filter/lightLeak` | yes | unverified |
| `filter/lighting` | yes | unverified |
| `filter/lowPoly` | yes | unverified |
| `filter/median` | yes | unverified |
| `filter/morphology` | yes | unverified |
| `filter/mosaicTiles` | yes | unverified |
| `filter/motionBlur` | yes | unverified |
| `filter/normalMap` | yes | unverified |
| `filter/normalize` | yes | unverified |
| `filter/octaveWarp` | yes | unverified |
| `filter/oilPaint` | yes | unverified |
| `filter/osd` | yes | unverified |
| `filter/outline` | yes | unverified |
| `filter/palette` | yes | unverified |
| `filter/parallax` | yes | unverified |
| `filter/patchwork` | yes | unverified |
| `filter/photocopy` | yes | unverified |
| `filter/pinch` | yes | unverified |
| `filter/pixelSort` | yes | unverified |
| `filter/pixels` | yes | unverified |
| `filter/plasticWrap` | yes | unverified |
| `filter/polar` | yes | unverified |
| `filter/pondRipples` | yes | unverified |
| `filter/posterize` | yes | unverified |
| `filter/prismaticAberration` | yes | unverified |
| `filter/reindex` | yes | unverified |
| `filter/relief` | yes | unverified |
| `filter/repeat` | yes | unverified |
| `filter/reverb` | yes | unverified |
| `filter/ridge` | yes | unverified |
| `filter/rotate` | yes | unverified |
| `filter/scale` | yes | unverified |
| `filter/scanlineError` | yes | unverified |
| `filter/scatter` | yes | unverified |
| `filter/scratches` | yes | unverified |
| `filter/scroll` | yes | unverified |
| `filter/seamless` | yes | unverified |
| `filter/sharpen` | yes | unverified |
| `filter/simpleAberration` | yes | unverified |
| `filter/sine` | yes | unverified |
| `filter/skew` | yes | unverified |
| `filter/smooth` | yes | unverified |
| `filter/smoothstep` | yes | unverified |
| `filter/snow` | yes | unverified |
| `filter/sobel` | yes | unverified |
| `filter/spatter` | yes | unverified |
| `filter/spinBlur` | yes | unverified |
| `filter/spiral` | yes | unverified |
| `filter/spookyTicker` | yes | unverified |
| `filter/stamp` | yes | unverified |
| `filter/step` | yes | unverified |
| `filter/stipple` | yes | unverified |
| `filter/strayHair` | yes | unverified |
| `filter/strokes` | yes | unverified |
| `filter/temporalAberration` | yes | unverified |
| `filter/tetraColorArray` | yes | unverified |
| `filter/tetraCosine` | yes | unverified |
| `filter/text` | yes | unverified |
| `filter/texture` | yes | unverified |
| `filter/threshold` | yes | unverified |
| `filter/tile` | yes | unverified |
| `filter/tint` | yes | unverified |
| `filter/translate` | yes | unverified |
| `filter/tunnel` | yes | unverified |
| `filter/unsharpMask` | yes | unverified |
| `filter/vaseline` | yes | unverified |
| `filter/vignette` | yes | unverified |
| `filter/warp` | yes | unverified |
| `filter/watercolor` | yes | unverified |
| `filter/waves` | yes | unverified |
| `filter/wind` | yes | unverified |
| `filter/wobble` | yes | unverified |
| `filter/wormhole` | yes | unverified |
| `filter/zoomBlur` | yes | unverified |
| `filter3d/flow3d` | yes | unverified |
| `filter3d/palette3d` | yes | unverified |
| `mixer/alphaMask` | yes | unverified |
| `mixer/applyMode` | yes | unverified |
| `mixer/blendMode` | yes | unverified |
| `mixer/cellSplit` | yes | unverified |
| `mixer/centerMask` | yes | unverified |
| `mixer/channelCombine` | yes | unverified |
| `mixer/distortion` | yes | unverified |
| `mixer/focusBlur` | yes | unverified |
| `mixer/mashup` | yes | unverified |
| `mixer/patternMix` | yes | unverified |
| `mixer/shadow` | yes | unverified |
| `mixer/shapeMask` | yes | unverified |
| `mixer/split` | yes | unverified |
| `mixer/thresholdMix` | yes | unverified |
| `mixer/uvRemap` | yes | unverified |
| `points/attractor` | yes | unverified |
| `points/buddhabrot` | yes | unverified |
| `points/dla` | yes | unverified |
| `points/flock` | yes | unverified |
| `points/flow` | yes | unverified |
| `points/heightGrid` | yes | unverified |
| `points/hydraulic` | yes | unverified |
| `points/lenia` | yes | unverified |
| `points/life` | yes | unverified |
| `points/physarum` | yes | unverified |
| `points/physical` | yes | unverified |
| `render/loopBegin` | yes | unverified |
| `render/loopEnd` | yes | unverified |
| `render/meshLoader` | yes | unverified |
| `render/meshRender` | yes | unverified |
| `render/pointsBillboardRender` | yes | unverified |
| `render/pointsEmit` | yes | unverified |
| `render/pointsRender` | yes | unverified |
| `render/render3d` | yes | unverified |
| `render/renderCubemap3d` | yes | unverified |
| `render/renderCubemapSurface` | yes | unverified |
| `render/renderLandscape3d` | yes | unverified |
| `render/renderLit3d` | yes | unverified |
| `synth/bitwise` | yes | unverified |
| `synth/cell` | yes | unverified |
| `synth/cellularAutomata` | yes | unverified |
| `synth/curl` | yes | unverified |
| `synth/gabor` | yes | unverified |
| `synth/gradient` | yes | unverified |
| `synth/julia` | yes | unverified |
| `synth/mandala` | yes | unverified |
| `synth/mandelbrot` | yes | unverified |
| `synth/media` | no | unverified |
| `synth/mnca` | yes | unverified |
| `synth/modPattern` | yes | unverified |
| `synth/navierStokes` | yes | unverified |
| `synth/newton` | yes | unverified |
| `synth/noise` | yes | unverified |
| `synth/osc2d` | yes | unverified |
| `synth/pattern` | yes | unverified |
| `synth/perlin` | yes | unverified |
| `synth/polygon` | yes | unverified |
| `synth/reactionDiffusion` | yes | unverified |
| `synth/remap` | yes | unverified |
| `synth/roll` | yes | unverified |
| `synth/sacredGeometry` | yes | unverified |
| `synth/scope` | no | unverified |
| `synth/shape` | yes | unverified |
| `synth/solid` | yes | unverified |
| `synth/spectrum` | no | unverified |
| `synth/subdivide` | yes | unverified |
| `synth/testPattern` | yes | unverified |
| `synth3d/cell3d` | yes | unverified |
| `synth3d/cellularAutomata3d` | yes | unverified |
| `synth3d/flythrough3d` | yes | unverified |
| `synth3d/fractal3d` | yes | unverified |
| `synth3d/heightmap3d` | yes | unverified |
| `synth3d/noise3d` | yes | unverified |
| `synth3d/reactionDiffusion3d` | yes | unverified |
| `synth3d/shape3d` | yes | unverified |

## 4. Evidence

Review CI boundary: Exact-source runs: Export kit. A passing export dispatch does not qualify rendered parity. Current complete-render enforcement remains an open verification requirement. [Exact-source responses and workflows](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/noisemaker-for-touchdesigner-remote-evidence.json).

[Bounded test evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-tests.json). [Exact-source Actions](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/actions?query=head_sha%3A66426bc41c2b85940322ae843ba04f41b7905ce4).
[This run evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents) retains commands, exit codes, source identities, and distribution metadata.
Official ecosystem reference: [TouchDesigner 2025 requirements, accessed 2026-09-24](https://derivative.ca/UserGuide/System_Requirements).
Source CI, export dispatch, artifact delivery, and rendered parity are separate evidence dimensions.
A successful dispatch or unit-test summary does not establish a full rendered gate.

Native follow-up used TouchDesigner 2025.32820 on Apple M4 macOS 26.5, with an isolated copy of the existing bootstrap and renderer.
Source `c5242301da6c6bb096f716623f92edf63a34f36b` differs from the inspected revision only in audit documents.
Both 256×256 probes rendered at time 0.25. `solid` matched its retained golden exactly; `noise` had maximum byte difference 1 across 38,396 channels.
These measurements do not independently qualify golden provenance or current-authority parity. Existing tolerances and goldens were unchanged.
The staged inventory contains 301 program fixtures: two executed and 299 unexecuted. Separate corpus and stateful coverage remain unqualified.
[Command and runtime evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native.json). [Input hashes](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native-input-hashes.json).
[Exact comparisons](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native-comparisons.json). [Unexecuted fixture IDs](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-fixture-inventory.json).

## 5. Open compatibility limits

Next bounded check: Run the full fixture sweep (GAP-004) on the qualified TD host — goldens from the published authority source `6a0af04d`, then `parity/run.sh`, `sweep.sh`, `accumulate.sh`, and `cubemap.sh` over every tracked fixture, with every mismatch, skip, and missing case itemized. A fresh install of the served `0.1.27` kit (none exists yet), parameters, cook failure, and recovery against its entry points, and the unsupported host/version matrix, remain to be recorded.
See the stable entries in [completion gaps](COMPLETION_GAPS.md).

See [the complete gap register](COMPLETION_GAPS.md#4-known-gaps) for evidence, dependencies, and acceptance criteria.

1. Reconcile the current authority and complete case inventory, including parameters, inputs, stateful frames, and host versions.
2. Run the existing actual-renderer suite without skip options. Record every missing, failed, refused, or timed-out case.
3. Installation, useful output, relocation, version-delta upgrade (source-history kit → served kit), reinstall-over, and removal were executed with the frozen served kit `0.1.26` on TD 2025.32820 (2026-09-26 — [completion gaps](COMPLETION_GAPS.md), section 3). A `0.1.27` host install, parameters, external inputs, cook failure, and recovery against its entry points remain unmeasured. A served-version-to-served-version upgrade pass does not exist (single rolling deployment).
4. Inspect exact-source CI and retain artifact hashes. Keep unresolved qualification failed or unverified.

All eligible ports have equal priority. Full parity and zero skipped cases remain the goal.
Implementation corrections remain with the separate job. This report does not advance the parity checkpoint.

## 6. History

2026-09-25 daily review at `de416d7606e231bf6e38027316269640a1d7d096`: source freshness and bounded evidence reviewed. Open qualification limits retained. [Retained review evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-native-comparisons.json). No new closure claimed.

2026-09-26 daily review at `143a89915429f97b16c4f85efedafd739ca8c0b7`: implementation range `7d533b9e..143a899` reviewed. Gates re-executed, workflow probe re-run natively, served deployment re-fetched as `0.1.27` at `3064d0dc` (file-level check, no host install). GAP-004 added for the unexecuted fixture sweep. Evidence in [completion gaps](COMPLETION_GAPS.md), section 3.

| Date | Source | Result | Change |
|---|---|---|---|
| 2026-09-26 | `143a89915429f97b16c4f85efedafd739ca8c0b7` | Full qualification unverified; GAP-001 closed (verified), GAP-002/GAP-003 blocked, GAP-004 open | Daily review: gates re-executed (119/119 unit, 326/326 lex/parse/validate, graph 325 PASS/1 SKIP, 210/210 definitions), workflow probe re-run on TD 2025.32820 with byte-identical renders, served kit `0.1.27` file-level spot check (no host install), matrix refreshed. |
| 2026-09-24 | `66426bc41c2b85940322ae843ba04f41b7905ce4` | Full qualification unverified | Created the requested maintained compatibility report. Preserved historical evidence and open gaps. |

Native follow-up: recorded two rendered probes and 299 unexecuted staged fixtures. No gap was closed.

Run: `20260924-remaining-gap-documents`. Later audits and reviews update this report with source-bound results.
