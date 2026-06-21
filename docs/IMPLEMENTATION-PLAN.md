# Noisemaker → TouchDesigner Port — Implementation Plan

**Goal:** A structural port of the Noisemaker shader engine (`../noisemaker/shaders`) to
**TouchDesigner 2025.32820+**, mirroring the Unity/HLSL (`../noisemaker-hlsl`) and Godot
(`../noisemaker-godot`) ports: live procedural texture from the Polymorphic DSL, rendered
through a Python-built **GLSL TOP** network, tolerance-parity to the JS/WebGL2 reference.

**Architecture (see `../ARCHITECTURE.md`):** the seam is the **Render Graph JSON**
(`compileGraph(dsl) → {passes, programs, textures, renderSurface}`). Two producers: (a)
golden/offline — the *unchanged* reference JS via reused `tools/export-graph.mjs`; (b)
live/in-engine — a staged TD-Python DSL frontend (Phase 6). Both feed one consumer: the TD
**network builder** (`td/noisemaker/runtime/td_backend.py`), which translates the graph into a
network of GLSL TOPs that TouchDesigner cooks each frame.

**Key facts that shape the port:**
- TD's GLSL TOP is **OpenGL GLSL, bottom-left raster** = same as the reference WebGL2 backend →
  **port shaders directly from reference GLSL, no Y-flip** (verified at Task 2.3). This is why
  most shaders **auto-transpile** (`tools/convert-shaders.mjs`).
- TD `.toe`/`.tox` are binary → **don't author offline**; ship a bootstrap `.toe`, keep GLSL in
  on-disk `.frag`, build the network from Python at startup.
- TD is **not truly headless** but is fully scriptable on a logged-in GPU session; parity renders
  via `project.realTime=False` → `op.save(png)` → `project.quit`.
- Free **Non-Commercial** tier: 1280×1280 cap (parity is 256²), no watermark, but **first launch
  needs a one-time GUI license activation** — the only manual prerequisite.

**Reused engine-agnostic assets (copied, NOT re-authored):** `reference/01–10`,
`tools/export-graph.mjs`, `tools/convert-definitions.mjs` (OUT_DIR retargeted), `parity/compare.py`,
`parity/programs/*.dsl`, `parity/export-and-render.mjs`, `docs/GRAPH-JSON-SCHEMA.md`.

**Parity targets:** SSIM ≥ 0.98, max-abs-diff ≤ 1–2/255 (MoltenVK/Metal vs ANGLE/WebGL2).

---

## Phase 0 — Scaffold & reuse wiring  ✅ DONE

- [x] Project tree + `.gitignore`; `git init`.
- [x] Copy `reference/` (01–10, byte-identical to the sibling ports), `docs/GRAPH-JSON-SCHEMA.md`.
- [x] Copy reused tools (`export-graph.mjs`, `convert-definitions.mjs`, `package.json`) and parity
      assets (`compare.py`, `programs/*.dsl`, `export-and-render.mjs`).
- [x] Retarget `convert-definitions.mjs` OUT_DIR → `td/noisemaker/effects`.
- [x] **Verify** the golden producer runs in-repo: `export-graph.mjs --file parity/programs/solid.dsl`
      emits a schema-correct graph (effect pass + blit, `renderSurface:o0`, `phys_0`).

## Phase 1 — Generated assets  ✅ DONE

- [x] `convert-definitions.mjs` → **182** effect-definition JSONs (`td/noisemaker/effects/<ns>/*.json`),
      0 failures.
- [x] `convert-shaders.mjs` (NEW) → **247** TD `.frag` programs; **226 auto-transpiled**, **21 MRT
      flagged** (points/agents, 3D renderers, synth3d precompute — Phase 5.5).
- [x] 8 Tier-1 golden graph JSONs (`parity/out/*.graph.json`) + 8 golden PNGs (reference render,
      reused from the identical-DSL Godot port).

## Phase 2 — Bring-up: builder end-to-end  ✅ DONE

The runtime ran for the first time and was iterated to green. Riskiest-first; all gates passed.

- [x] Runtime core authored: `render_graph`, `graph_loader`, `dim` (reference/04 §9 exact),
      `engine_uniforms` (§10.1), `uniform_binder`, `td_backend`, `surface_manager`, `pipeline`,
      `nm_renderer`. Pure-Python core unit-smoke-tested under stock python3.
- [x] `td/parity_render_all.py` (batch renderer) + `td/build_parity_toe.py` (offline `.toe` author)
      + `parity/run.sh` (build → render → compare) + `parity/.venv` (numpy/pillow for `compare.py`).
- [x] **TouchDesigner license activated** (one-time, by the user) — bring-up then ran fully automated.
- [x] **Task 2.1 — GLSL TOP contract verified.** `TDOutputSwizzle`/`sTD2DInputs`/Vectors uniforms
      work as documented. **`TOUCH_START_COMMAND` does NOT exist in this build** — the startup hook
      is an **Execute DAT (`onStart`/`onCreate`) inside a `.toe`**, which we author offline via
      `toeexpand`/`toecollapse` (`td/build_parity_toe.py`). The runtime modules must fetch TD globals
      (`glslTOP`, `baseCOMP`, …) from the `td` module — they aren't injected into imported `.py`.
- [x] **Task 2.2 — Y-origin: NO FLIP (confirmed).** `gradient` matches the golden at SSIM 0.99999 —
      TD's GLSL TOP is OpenGL bottom-left, same as the reference WebGL2 backend. The core thesis holds.
- [x] **Task 2.3 — `solid` parity gate green** (SSIM 1.00000, max-diff 0). First gate passed.
- [x] **Task 2.4 — uniform feed fixed.** The GLSL TOP `vec` parameter is the SLOT COUNT — it must be
      set (`g.par.vec = N`) before `vecNname`/`vecNvalue*`; we now bind only the uniforms the shader
      declares. int/bool bind fine as floats — **no CHOP/Arrays or transpiler change needed.**

## Phase 3 — Full builder coverage  ⛔ gated on Phase 2

- [ ] 3.1 `dim`-driven per-TOP resolution + format across all texture specs (already wired; verify
      against `blur` pooled intermediates).
- [~] 3.2 Feedback TOP wiring — **intra-graph back-edges DONE** (`td_backend._detect_back_edges`:
      a texId read before it is written routes through a Feedback TOP; drives the golden frame
      count). Global-surface o0..o7 swap + state-surface cross-frame persist
      (reference/04 §10.2/§10.6/§10.7, `surface_manager`) still pending — for sims (Phase 5.5).
- [ ] 3.3 `td_backend` MRT: Render Select TOP per extra color buffer (draw_buffers>1).
- [ ] 3.4 `td_backend` points scatter (`drawMode:"points"`): Geometry COMP + GLSL MAT + Render TOP.
- [ ] 3.5 `pipeline` live time driving for animated effects (osc2d) + host `resize`.

## Phase 4 — Tier-1 effect parity  ✅ DONE — 8/8 PASS

All eight match the reference at **SSIM ≥ 0.99998, max-diff ≤ 1** via `parity/run.sh all`
(fully automated through the bootstrap `.toe`).
- [x] 4.1 `synth/noise` (PCG value/simplex; `NOISE_TYPE`/`LOOP_OFFSET` defines) — ssim 0.99998
- [x] 4.2 `synth/cell` 0.99999 · [x] 4.3 `synth/gradient` 0.99999 · [x] 4.4 `synth/shape` 0.99998
- [x] 4.5 `synth/osc2d` 0.99998 · [x] 4.6 `filter/blur` 0.99998 (2-pass; needed input extend =
      `hold` to match the reference's CLAMP_TO_EDGE — default was `zero`)
- [x] 4.7 `mixer/blendMode` 0.99999 (two-input)
- [x] **Milestone:** 8/8 Tier-1 parity-pass — **`parity/run.sh all` green.**

## Phase 5 — Expand coverage (templated)  ✅ 5.1–5.4 DONE — 71/71 single-pass PASS

Per-effect: `.frag` exists; parity-gate, fix any auto-transpile miss. `parity/stage_coverage.py`
reuses the sibling `noisemaker-godot` DSL+golden pairs (identical DSL + same reference renderer ⇒
byte-identical goldens); `parity/sweep.sh` renders all in TD and grades with a per-effect tolerance.
- [x] 5.1–5.4 — **71/71 single-pass** (`synth`/`filter`/`mixer`/`classicNoisedeck` + single-step
      `feedback`): 65 strict (SSIM ≥ 0.99998, max-diff ≤ 1) + 6 SSIM-gated discontinuity effects
      (`newton`/`shadow`/`edge`/`crt`/`uvRemap`/`distortion`, mirroring the godot tolerance table).
      Five builder/transpiler fixes found by gating: **(a)** GLSL TOP `inputfiltertype='nearest'`
      (reference samples surfaces NEAREST; fixed a 10-effect warp cluster); **(b)** boolean
      `#define` injection as `true`/`false` (strict `#version 460` rejects `if (1)` — `curl`);
      **(c)** 1×1 black Constant TOP for `'none'`/unbound inputs (`subdivide` sTD2DInputs); **(d)**
      transpiler sampler/output regex tolerates a trailing `// comment` (`feedback` black samplers);
      **(e)** back-edge → **Feedback TOP** wiring + N-frame cook (`feedback`). The harness now also
      surfaces GLSL compile errors via an Info DAT (`parity_render_all._shader_errors`).
- [x] 5.4b `channelCombine` (multi-input) added → **72/72 gateable PASS** (`parity/sweep.sh`).
- [~] 5.5a **Multi-frame feedback accumulation** — `cellularAutomata`, `reactionDiffusion`,
      `motionBlur` have goldens but are **deferred** (sweep `[DEFER]`). The golden accumulates over
      8 frames; TD's Feedback TOP latches only on a real engine frame tick (`absTime.frame`), which
      a synchronous `onStart` force-cook loop can't drive (stepping `root.time.frame` + force-cook
      is necessary but NOT sufficient — verified: frame advances, mean stays frame-0). Needs an
      **async realTime / Movie-File-Out frame loop**. The back-edge → Feedback TOP wiring is correct;
      `cellularAutomata`/`reactionDiffusion` additionally need the global state-surface self-loop
      (same-pass read+write of a `*state*` surface — `surface_manager`; my back-edge detector only
      catches cross-pass `j>i`). NB `reactionDiffusion` is cross-backend-divergent even in godot.
- [ ] 5.5b **The 21 MRT/points/3D programs** — transpiled but **unvalidatable locally**: godot has
      no goldens for them and `parity/export-and-render.mjs` fails here (`readback failed: FBO
      incomplete` — the headless WebGL2 float-FBO readback path is unavailable). Builder work
      (Render Select TOP per draw buffer; points scatter via Geometry COMP + GLSL MAT + Render TOP;
      3D volume atlas + raymarch + geoOut) is ready to do, but gating needs a working golden source.
- [x] Coverage tracked in README; per-effect tolerances + rationale live in `parity/sweep.sh`.

## Phase 6 — Live TD-Python DSL compiler  ✅ DONE — 94/95 corpus byte-clean graph-parity

Ported `reference/01–03` (+ expander/resources/04) to Python under `td/noisemaker/compiler/`,
**mirroring `noisemaker-hlsl/unity/com.noisemaker.hlsl/Compiler/` file-for-file** (~6.7k C# LOC):
`lang/{token,lexer,ast,parser,enums,enum_paths,effect_registry,diagnostics,validator,expander,
palette_expansion}` + `graph/{dim,resources}` + `dsl_compiler` (orchestrator). The C# typed model
(`UniformValue`/`ArgValue`/`Dim`/`OrderedMap`/`JsonValue`) collapses to native Python values + dicts;
AST nodes are plain dicts matching the reference JS objects; clone = `copy.deepcopy`.
- [x] **4 staged parity gates** vs the reference (`parity/compiler/check_{lex,parse,validate,graph}.py`
      + `tools/dump-{tokens,ast,validated}.mjs`): **lexer / parser / validator 95/95 byte-exact** vs
      reference `lex`/`parse`/`compile`; **graph 94/95 byte-clean** vs the `export-graph.mjs` oracle
      (the 1 skip `B5oBsA` references a nonexistent effect — the reference rejects it too).
- [x] Corpus = the **blaster** compositions (`parity/corpus/`, from `noisemaker-hlsl/parity/corpus`)
      + the 73 `parity/programs/`. Points/agent comps compile clean (WebGL2 graph = `drawMode:"points"`
      render passes — no compute/MRT fields trigger the staged path).
- [x] Two parity fixes beyond hlsl: define-suffix order keys off the **sorted global key** (not the
      define name — hlsl's re-sort is a latent bug its 12-prog corpus never hit); osc **object
      uniforms serialized** (hlsl stages them null).
- [ ] **NEXT:** wire `compile_graph(dsl, reg)` into `nm_renderer.set_dsl(src)` (live TD rendering from
      DSL source) + render real blaster comps in TD for renderer/shader-library parity.

---

## Self-review
- **Spec coverage:** runtime (ref 04)→Phase 2/3; shader translation (ref 07/08)→Phase 1/4/5; golden
  seam (ref 03/04 + tools)→Phase 0/1; live compiler (ref 01–03)→Phase 6; parity harness→Phase 2/4.
- **Test-first:** goldens (Phase 1) precede any candidate; every effect has a parity gate.
- **Riskiest-first:** TD integration brought up on `solid` (Phase 2) before any complex effect;
  MRT/points/feedback each get a dedicated task.
- **The one external blocker:** TD license activation — isolated to the Phase 2 gate; all authoring
  is complete and independent of it.
