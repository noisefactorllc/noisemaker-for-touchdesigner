# Noisemaker for TouchDesigner — Architecture

A port of the Noisemaker shader engine to **Derivative TouchDesigner**: the DSL compiler, the
effect catalog, and a runtime that builds a program as a live network of **GLSL TOP** operators.
Sibling ports: `noisemaker-for-unity`, `noisemaker-for-godot`, `noisemaker-for-blender`,
`noisemaker-for-threejs`, `noisemaker-for-babylonjs`.

## The seam: render graph JSON

Every port consumes the normalized **render graph JSON** (`docs/GRAPH-JSON-SCHEMA.md`). Two
producers emit it:

- **In TouchDesigner:** the Python port of the DSL compiler (`td/noisemaker/compiler/`: lex, parse,
  validate, expand, resources), which `NMRenderer.set_dsl` runs.
- **Offline:** the unchanged reference JavaScript compiler, run under Node by
  `tools/export-graph.mjs`. The compiler gates use it as the oracle.

`parity/compiler/check_{lex,parse,validate,graph}.py` compare the two over `parity/corpus/` and
`parity/programs/`. The reference revision is pinned by `NM_REFERENCE_SHA_PINNED` in
`scripts/test`.

## The consumer: a network builder

TouchDesigner cooks a pull-based operator network every frame, so the runtime builds the network
once from the graph and then feeds time and uniforms.

| Render graph concept            | TouchDesigner realization                                            |
|---------------------------------|----------------------------------------------------------------------|
| effect pass (`passType:effect`) | a **GLSL TOP** (`pixeldat` → the effect `.frag`; inputs wired; uniforms set) |
| blit pass (`passType:blit`)     | a **Null TOP**                                                        |
| pooled texture (`phys_N`)       | the upstream TOP's output (TouchDesigner manages texture memory)      |
| global surface `o0..o7`, state  | a **Feedback TOP** pair (double-buffered, cross-frame persistence)   |
| `inputs{name:texId}`            | TOP input connections, in stable order → `sTD2DInputs[i]`            |
| `outputs{color,color1,...}` MRT | GLSL TOP **# of Color Buffers** > 1, one common format                |
| `uniforms{name:value}`          | GLSL TOP **Vectors** page, or an **Arrays** CHOP for uniform arrays   |
| `defines{KEY:val}`              | `#define KEY val` lines prepended per pass                            |
| `drawMode:"points"` (scatter)   | Geometry COMP + GLSL MAT + Render TOP                                 |
| `repeat:"iterations"`           | a chain of N GLSL TOPs (the Passes parameter is not used)             |
| `renderSurface`                 | the presented output TOP (`NMRenderer.Output`)                        |

Texture formats follow the graph: `rgba8`/`rgba8unorm` → `rgba8fixed`, `rgba16f`/`rgba16float` →
`rgba16float`, `rgba32f`/`rgba32float` → `rgba32float` (`runtime/td_backend.py`, `FORMAT_MAP`).

## Shader strategy: the reference GLSL, translated mechanically

TouchDesigner's GLSL TOP is OpenGL GLSL with the same bottom-left raster origin as the reference's
WebGL2 backend, so `tools/convert-shaders.mjs` translates each reference
`shaders/effects/<ns>/<name>/glsl/*.glsl` structurally, with no math edits and no Y-flip:

- strip the `#version 300 es` / `precision` header;
- replace named input-sampler declarations with `#define inputTex sTD2DInputs[i]` in stable input
  order;
- rename the effect `main()` to `nm_main()` and wrap it:
  `void main(){ nm_main(); fragColor = TDOutputSwizzle(fragColor); }`.

The emitted `.frag` files are self-contained, as the reference programs are. `--flip-y` exists for a
host that would need a flipped origin; it is off. MRT programs are emitted verbatim and wired by the
runtime (see `PORTING-GUIDE.md`).

## Parity

Golden truth is the reference engine's own output at the pinned revision, rendered by the reference
harness in headless Chromium (ANGLE on Metal on macOS, the same GPU class as the candidate).

- `parity/sweep.sh` stages every program in `parity/programs/`, renders goldens
  (`parity/batch-golden.mjs`), renders candidates in TouchDesigner (`parity/run.sh`), and grades
  each with `parity/compare.py` against a per-effect tolerance listed in the script. Feedback
  effects are graded by `parity/accumulate.sh`. The script writes its results to a ledger
  (`LEDGER_PATH`, default `parity/out/ledger.tsv`).
- `scripts/parity-summary` runs the sweep against a reference checkout at the pinned revision and
  classifies every staged case as exact, strict (max-abs-diff ≤ 2, SSIM ≥ 0.98), near (passes only
  the wider per-effect tolerance), defer, fail or missing, ending with a `PARITY-SUMMARY` line.
- `parity/corpus_sweep.sh` renders the live programs in `parity/corpus/` through the in-TouchDesigner
  compiler.
- `parity/evolve.sh` evolves stateful programs over many frames; chaotic programs are graded for
  stability and character (`docs/CHAOS-GATE.md`).

Measured results live on the compatibility report issue, not in the repository.

TouchDesigner has no headless startup hook, so `parity/run.sh` builds a bootstrap `.toe`
(`td/build_parity_toe.py`) whose Execute DAT renders the requested programs through
`td/parity_render_all.py` and quits. The scripts stop only the TouchDesigner instance they launched.

## Platform constraints

See `docs/TD-PLATFORM-NOTES.md`.

- **Not headless:** TouchDesigner needs a logged-in GPU desktop session.
- **Licensing:** the free Non-Commercial tier renders without a watermark but caps resolution at
  1280×1280, so 3D volumes are clamped by `NM_MAX_VOLUME_SIZE` (default 32). A fresh install stops
  at an activation modal until a Derivative account activates it in the GUI.
- **No offline `.toe`/`.tox` authoring:** the network is built from Python at startup.

## Tech stack

TouchDesigner 2025.32820 and later (arm64, macOS) with its bundled Python 3.11 and GLSL 4.60;
Node for the offline tooling; Python 3 with numpy and Pillow for grading.
