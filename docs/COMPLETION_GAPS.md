# noisemaker-for-touchdesigner: completion gaps

Current compatibility matrix: [compatibility report](COMPATIBILITY.md).

## 1. Scope and source revisions

Daily review: 2026-09-25. Current inspected source: [`de416d7606e231bf6e38027316269640a1d7d096`](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/commit/de416d7606e231bf6e38027316269640a1d7d096).
Full rendered parity remains **unverified**. No release approval or new closure follows from this review.
Current upstream discovery: `bbdeb56c4b75cf33379766c3e87b0f5a18bcbba8`. Published Noisemaker authority: `1.0.179`, source `fca611fd8f91424661d4e531d39313d24ea21134`, 210 effect IDs.
The observations below retain their original source and authority identities. They do not qualify later updates.
Current served kit: `0.1.23`, source `de416d7606e231bf6e38027316269640a1d7d096`. [Retrieved inventory and hashes](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-served-inventories.json). Artifact identity does not establish host qualification.
Served kit `0.1.26` at source `6c96151d72648f87e16e572428a98d1922b61136` was later byte-verified against its own served inventory and the source tree (2026-09-26, section 3). Artifact identity still does not establish host qualification.

### Earlier source observations

Date: 2026-09-24. Reviewed source: [`66426bc41c2b85940322ae843ba04f41b7905ce4`](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/commit/66426bc41c2b85940322ae843ba04f41b7905ce4).
Local HEAD matched remote `main` before checks. The operator requested missing registers for all remaining eligible ports in this run.
This is an initial register with bounded evidence, not a completed port audit or release approval.
No implementation, effect coverage, or parity checkpoint changed. Full audits remain in the existing rotation.

TouchDesigner Python compiler and native operator network. README requires an activated GPU desktop and identifies build 2025.32820 on Apple Silicon. [Contract](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md).

Latest status entry records upstream `5b81e04f8a4b53c2be43b8e328cee0c3365f352f`. Runtime and rendered evidence beyond that revision remain unverified.
Current Noisemaker upstream at discovery: `c9ee8a049b2b63cd300da67c01ee40baf29dc288`. Current CPU authority at discovery: `f2eb495d70abcb74e3632e7a652a4f83e4f3b11e`.
These heads identify review targets, not qualification results. No authority evidence was regenerated.

Served kit `0.1.20` identifies source `66426bc41c2b85940322ae843ba04f41b7905ce4`. [Deployment metadata](https://kits.noisedeck.app/touchdesigner/0/deployment-meta.json). Inventory and compatibility metadata were retrieved. Artifact bytes and installation were not fully checked.

Only the gap document and README link are publication candidates. Their paths do not trigger the current workflows.
Publication uses a document-only commit on `main`. The containing commit identifies this document's publication revision.
Exact commit, remote document hashes, and downstream results are retained in the shared run record.

## 2. Completion claims

| Claim ID | Claim source | Claimed scope | Finding | Evidence |
|---|---|---|---|---|
| CLAIM-001 | [Source claim](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/STATUS.md) | Self-contained DSL rendering, 2D and 3D effects, simulations, and reusable TOP output. Historical shader and graph gates are separate evidence. | partial | 76 Python unit tests passed. Native installation, activation, TOP rendering, saved projects, and accessibility were not exercised. [Local evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-tests.json). |
| CLAIM-002 | [README workflow](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md) | Human usability: installation, first output, errors, and recovery | partial | Installed workflow observed on TD 2025.32820 (isolated Base COMP, documented example, TOP connect/resize, invalid-DSL recovery, save/reopen, cleanup — section 3); the documented connect example was corrected to the in-COMP form. 2025.33230 not exercised. GAP-002. |
| CLAIM-003 | [Official ecosystem documentation](https://derivative.ca/UserGuide/System_Requirements) | Ecosystem fit and supported versions | partial | Source entry points were examined. Installed integration and the supported-version matrix remain open. GAP-002. |
| CLAIM-004 | [Distribution description](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md) | Release readiness | partial | Artifact byte identity (852/852), notices, dependencies, and the installed kit legs (install, first result, relocation, version-delta upgrade from source history, reinstall-over, removal) qualified on TD 2025.32820 — section 3; GAP-003 is blocked on its declared GAP-002 dependency (the 2025.33230 leg). Not a release approval: GAP-002's 2025.33230 leg and the platform matrix remain open. |
| CLAIM-005 | [Exact-source Actions](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/actions?query=head_sha%3A66426bc41c2b85940322ae843ba04f41b7905ce4) | Exact-source automated evidence | supported | [Export kit](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/actions/runs/35955443239): `success`. This finding covers workflow status only. |

## 3. Methods and evidence

Review CI boundary: Exact-source runs: Export kit. A passing export dispatch does not qualify rendered parity. Current complete-render enforcement remains an open verification requirement. [Exact-source responses and workflows](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/noisemaker-for-touchdesigner-remote-evidence.json).

### Daily review, 2026-09-25

91 harness tests pass. The actual TouchDesigner process renders the current runtime: solid is byte-exact and noise differs by at most 1 in 38,396 channels against retained historical goldens. Both cases executed. This two-case result does not qualify the current authority, full fixture inventory, Windows, or installed workflows. TouchDesigner retains equal priority with every other port. [Raw evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-native-comparisons.json).
The review checked source changes, worker evidence, source-bound CI where present, and current served inventories. Full installed-host and platform qualification remains incomplete.

Environment: macOS 26.5, Darwin arm64. Source-file SHA-256 records bind the local checks to the reviewed revision.
[Source hashes](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/noisemaker-for-touchdesigner-source-hashes.json). [Remote evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/noisemaker-for-touchdesigner-remote.json).

Executed bounded command:

```sh
python3 -m unittest discover -s parity -p "test_*.py"
```

76 Python unit tests passed. Native installation, activation, TOP rendering, saved projects, and accessibility were not exercised. Command exit code: 0. [Local evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-tests.json).
Unit and harness checks do not measure rendered parity. No new image denominator or tolerance is inferred from these results.

Official reference: [TouchDesigner 2025 requirements, accessed 2026-09-24](https://derivative.ca/UserGuide/System_Requirements).
Historical denominators and tolerances remain in the original source documents. Their current-source validity remains an open verification task.

| Developer outcome | This pass | Required remaining check |
|---|---|---|
| Installation | Source instructions and package declarations inspected | Install the actual distribution in an isolated consumer. |
| First useful result | Two native 256×256 renders completed | Create an isolated Base COMP, execute the documented NMRenderer example, connect its TOP, resize, recover from invalid DSL, and reopen the project. |
| Normal host workflow | Not fully observed | Exercise ordinary parameters, external inputs, resize, state, and cleanup. |
| Error and recovery | Selected tests only where listed above | Fail through the installed public entry point, correct input, and render again. |
| Distribution | Metadata inspection only | Load the served kit in an isolated activated project. Check source paths, TOP output, saved-project relocation, notices, and removal. |
| Accessibility | Not observed | Check keyboard, focus, labels, and errors for provided interfaces. For a headless library, check CLI diagnostics instead. |

No global installation, user-project modification, manual deployment, or manual release occurred.
Native applications present on the machine are not evidence of a qualified host workflow.

Native follow-up used TouchDesigner 2025.32820 on Apple M4 macOS 26.5, with an isolated copy of the existing bootstrap and renderer.
Source `c5242301da6c6bb096f716623f92edf63a34f36b` differs from the inspected revision only in audit documents.
Both 256×256 probes rendered at time 0.25. `solid` matched its retained golden exactly; `noise` had maximum byte difference 1 across 38,396 channels.
These measurements do not independently qualify golden provenance or current-authority parity. Existing tolerances and goldens were unchanged.
The staged inventory contains 301 program fixtures: two executed and 299 unexecuted. Separate corpus and stateful coverage remain unqualified.
[Command and runtime evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native.json). [Input hashes](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native-input-hashes.json).
[Exact comparisons](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-native-comparisons.json). [Unexecuted fixture IDs](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents/touchdesigner-fixture-inventory.json).

### 2026-09-26 compiler-parity qualification (Linux runner)

Immutable authority inputs were resolved by checking out upstream
`noisefactorllc/noisemaker` at the port's current synced reference revision
`2f47612c29045c1b91af94887a8ff20106e980ef` (the revision named by port commit
`6c96151d72648f87e16e572428a98d1922b61136`) and running the declared compiler
gates against it with `NM_REFERENCE_ROOT` bound to that checkout. The
checkout is untracked (`upstream-noisemaker/`, gitignored); the pinned SHA
makes it reproducible. `node tools/convert-definitions.mjs` regenerated 210/210
effect JSON files with zero failures and produced no working-tree diff, so the
committed effect catalog is byte-identical to the authority revision. The
Python unit suite passed: 118 tests, 0 failures
(`./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"`,
Python 3.11.2, numpy 2.5.3, Pillow 12.3.0).

Compiler gates (default corpus = all DSL files in `parity/corpus` +
`parity/programs`, 326 files), reference oracle `2f47612c`:

| Gate | Result |
|---|---|
| `parity/compiler/check_lex.py` | 326/326 PASS |
| `parity/compiler/check_parse.py` | 326/326 PASS |
| `parity/compiler/check_validate.py` | 326/326 PASS |
| `parity/compiler/check_graph.py` | 325 PASS / 0 DIFF / 0 STAGE / 1 SKIP / 0 ERR (of 326) |

Exact commands and environment (working tree `main` at
`6c96151d72648f87e16e572428a98d1922b61136`, clean except the untracked
`upstream-noisemaker/` checkout and `parity/.venv/`):

```sh
NM_REFERENCE_ROOT=/workspace/repos/noisemaker-for-touchdesigner/upstream-noisemaker
git -C "$NM_REFERENCE_ROOT" rev-parse HEAD   # 2f47612c29045c1b91af94887a8ff20106e980ef
export NM_REFERENCE_ROOT
./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"
./parity/.venv/bin/python3 parity/compiler/check_lex.py
./parity/.venv/bin/python3 parity/compiler/check_parse.py
./parity/.venv/bin/python3 parity/compiler/check_validate.py
./parity/.venv/bin/python3 parity/compiler/check_graph.py
```

Each gate was invoked with no file arguments, so it used its full declared
default corpus: `parity/corpus/*.dsl` (25 files) + `parity/programs/*.dsl`
(301 files) = 326. Raw summary lines as emitted (exact byte strings):

```
=== lexer parity: 326/326 PASS ===
=== parser parity: 326/326 PASS ===
=== validator parity: 326/326 PASS ===
=== graph parity: 325 PASS / 0 DIFF / 0 STAGE / 1 SKIP / 0 ERR  (of 326) ===
```

All four gates exited 0. The gates ran at base revision
`6c96151d72648f87e16e572428a98d1922b61136`. `git diff 6c96151..40114b84 -- \
td/noisemaker parity/compiler` is empty: the port compiler sources and the
gate harness files are byte-identical from base through candidate tip
`40114b84`, so these results remain valid at the candidate. Later candidate
commits add only gap-record documentation plus the run-driver robustness fixes
`b502e32`/`c727965`/`40114b8` (`parity/run.sh`, `td/build_parity_toe.py`) —
neither file is part of the gated compiler or the gate harnesses. Those
fixes make `parity/run.sh` self-provisioning (portable TouchDesigner
discovery via `TD_APP`/`TD_BIN`/install roots, `parity/.venv` bootstrap,
`upstream-noisemaker/` reference fallback) because the native runner failed
identically at every tested SHA with `command_failed` and no diagnostics
(checks `753f86fe`, `3632a413`, `34156eb1`, `077a584e` at SHAs `5ba51bb3`,
`1a5c43e`, `c727965`, `40114b8`); with all repo-side early-exit paths
removed, the residual failure is attributable to the runner environment
(missing/failed TouchDesigner GUI-license session), which no repository
change can supply.

Scope note: commit `0628e9f` changes only `td/build_parity_toe.py`'s install
discovery (Windows `.exe` tool names, `TD_APP` pointing at the TD binary,
`~/Applications` bundles, searched-roots diagnostics) — on hosts where the
previous discovery already succeeded its behavior is unchanged. The standing
STATUS.md limitations (aperture-defocus wide-footprint blur not ported and
defocus-buffer normalization unresolved; the force-pushed, non-contiguous
upstream range `4891b9953f9f..2f47612c2904` audited via endpoint tree diff;
`projectPass()` `defines` coverage asserted via the byte-identical
`convert-definitions.mjs` gate rather than re-rendered) are pre-existing
recorded items: the defocus port and any TD-session re-render belong to the
separate implementation job and to this gap's unqualified native half, and
the upstream range audit is a recorded fact of upstream history. None are
regressions of the run-driver fix, and none are closed here.

Authority provenance: the reference checkout was fetched as a fresh clone of
`https://github.com/noisefactorllc/noisemaker.git` and pinned with
`git checkout 2f47612c29045c1b91af94887a8ff20106e980ef`, the revision named in
port commit `6c96151`'s message ("sync(reference): update to
noisemaker@2f47612c2904"). The checkout stays untracked and gitignored; the
clone URL plus pinned SHA make the oracle reproducible without vendoring it.

Harness-file SHA-256 at this revision: `parity/compiler/check_lex.py`
`ac8aa6ff580840a6403ab052eaa167ad6e428488c8cdcb86bd936d4e87ed22f3`,
`parity/compiler/check_parse.py`
`554d5e73c826aef5519aaf22f8d49b5d7f48ca5efd54c23108c6be1ba40cb633`,
`parity/compiler/check_validate.py`
`bfd01fcfa8fface8069f35fb05695d06072ffaa3fe3a00e4532be619d1ac60ec`,
`parity/compiler/check_graph.py`
`b1ce88fa64889aaa552b553b1810eff806dc31c96ef7a8409fa73b455c5183a6`.

The single graph SKIP is `parity/corpus/B5oBsA.dsl`, an intentionally invalid
program the reference oracle rejects (`ERR_COMPILATION_FAILED`) and the port
rejects as well — rejection parity, not a port defect. It is preserved here and
not reclassified.

Port file SHA-256 at this revision: `td/noisemaker/compiler/lang/lexer.py`
`d06460b5b3b8880eec7367ad71a014c336dddb8cc0e532e14e771a163ae588ab`,
`td/noisemaker/compiler/lang/parser.py`
`019db836ef868b788aeacf26b9b166488a033497c9c0a4f389188fdc17a7d782`,
`td/noisemaker/compiler/lang/validator.py`
`c1bbc8586430abb0f3b42187c2fc6bbcc155af4ddc5becb89ed53b1464d723c9`,
`td/noisemaker/compiler/dsl_compiler.py`
`c93ed547a03404dc9eb37223d87c3e4b5b4c4db8cd03adb6569d2b490befe22a`.

These results qualify the compiler half of GAP-001's required checks. The
native render half (`adjust`, `alphaMask`, `bitwise` under the declared
`touchdesigner-parity` profile) is qualified at the published candidate below.

Infrastructure observation (records no qualification, closure, or per-case
native result): the declared native check at source `5ba51bb3` (check
`753f86fe`, profile `touchdesigner-parity` v1, engine TouchDesigner 2025.32820)
did not complete — runner `native-spare` exited `command_failed` and returned
no command, stderr, artifact, or per-case result for `adjust`, `alphaMask`, or
`bitwise`. No current-source native verdict exists; the historical ledger rows
(`adjust` max_abs_diff 1.000003695487976 / ssim 0.9999804496765137,
`alphaMask` 1.000003695487976 / 0.9999801516532898, `bitwise` 0.0 / 1.0, all
within tol 2.001 / ssim 0.98) remain the last recorded per-case verdicts and
are unchanged by this observation. GAP-001 therefore stays fully open on both
required halves (compiler half qualified above; native half unqualified), and
the host-workflow items it depends on remain recorded as GAP-002/GAP-003. The
README qualification engine (2025.32820) versus the current official build
(2025.33230) remains the recorded version-matrix uncertainty; no claim about
the newer build is made.

### 2026-09-26 native render qualification at the published candidate

After the run-driver fixes above were published, the declared native check
re-ran successfully at source
`3b543dde9f25d35f30d9b3ee15869255f9e14b8f` (machine verification receipt,
`verified_at 2026-09-26T05:37:35.380Z`, review `01a1d4ac`): TouchDesigner
2025.32820, darwin arm64, GPU available, runtime binary
`/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner` (version from
installed bundle metadata). All three declared `touchdesigner-parity` cases
passed at the declared thresholds `max_abs_diff ≤ 2 / ssim ≥ 0.98`, each with
golden + candidate PNG artifacts and a per-case report, and every declared
command (runtime-version, setup, per-case golden renders, bootstrap, render,
per-case compares) exited 0 with no timeouts:

| Case | Verdict | Artifacts |
|---|---|---|
| `adjust` | passed | golden + candidate PNG, `adjust.report.json` |
| `alphaMask` | passed | golden + candidate PNG, `alphaMask.report.json` |
| `bitwise` | passed | golden + candidate PNG, `bitwise.report.json` |

Both halves of GAP-001's declared contract are now qualified: the compiler
gates above at authority `2f47612c2904` over the full 326-file default corpus
with the single documented rejection-parity SKIP, and the declared native
render cases above at the exact published candidate. GAP-001 closes on these
criteria with the scoping stated in the gap entry below; the earlier failed
native attempts (`753f86fe`, `3632a413`, `34156eb1`, `077a584e`) are retained
as the repair trail that produced the run-driver fixes
(`b502e32`/`c727965`/`40114b8`/`699f6d2`/`3b543dd`).

### 2026-09-26 served distribution artifact byte qualification (GAP-003, artifact half)

The served distribution artifact was reproduced and checked byte-for-byte
against its own published inventory. [Deployment
metadata](https://kits.noisedeck.app/touchdesigner/0/deployment-meta.json)
reports version `0.1.26`, `git_hash 6c96151d72648f87e16e572428a98d1922b61136`,
`date 1790392233`. The served inventory
[kit.json](https://kits.noisedeck.app/touchdesigner/0/kit.json) (SHA-256
`9a7092ce2548224cf0988e684817defaa890cf42604ca1236f987b76139ffdf5`, 178485
bytes) lists 852 files with per-file byte counts and SHA-256 hashes. All 852
files were fetched individually from
`https://kits.noisedeck.app/touchdesigner/0/<path>` and each matched its
inventory entry on both SHA-256 and byte count: 852/852, zero mismatches, zero
skips. Bytes per `estBytes` class also matched exactly (base 23,954; engine
2,377,207; shaders 1,441,251).

Inventory bytes were then reproduced from this repository at source
`6c96151d72648f87e16e572428a98d1922b61136` (via `git show <sha>:<path>`):

- All 549 non-shader, non-`compat.json` files are byte-identical to their
  sources: 546 `engine/noisemaker/*` files to `td/noisemaker/*`,
  `LICENSES/noisemaker-for-touchdesigner-LICENSE.txt` to `LICENSE` (SHA-256
  `e502d1baf14c5fde7a7476f8a860665352d31d26f75b7a6977943606c8b51259`),
  and `README.template.md`/`integrate.py` to `export-kit/kit/` (integrate.py
  SHA-256 `433eab0ab9af15d3225f8047ccd4630fc9129d2f771508e8e73d4fcc8fa45540`).
- All 301 `shaders/*` files are byte-identical to `td/noisemaker/shaders/`
  content.
- `compat.json` (SHA-256
  `b4c57ae75efeb357e22893f5261a02be95cd99cba86f51c9c00dab5637807ce5`) lists
  207 effect ids exactly equal to the effect definitions under
  `td/noisemaker/effects/` at that SHA (`namespace/func`), with `media`,
  `scope`, and `spectrum` excluded as declared in `export-kit/kit.config.json`;
  no missing and no extra ids.
- `td/noisemaker`, `export-kit/kit`, and `LICENSE` are byte-identical between
  `6c96151` and current `main` (`dbd98d8`), so the served bytes reproduce from
  the current default-branch tree.

Licenses and dependencies: the kit ships two notices — the port's MIT license
(byte-identical to the repo `LICENSE`) and the upstream Noisemaker MIT notice
(`LICENSES/noisemaker-MIT.txt`, "Copyright (c) 2017-2025 Noise Factor LLC").
An import scan over the served engine `.py` files finds only the Python
standard library, TouchDesigner's built-in `td` module, and `numpy` (a single
`import numpy` in `runtime/td_frame_export.py`; numpy ships inside
TouchDesigner), consistent with the README's no-third-party-dependency claim.

Required-check boundary: at source `6c96151d72648f87e16e572428a98d1922b61136`
the only exact-source workflow run is [Export kit
36213953378](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/actions/runs/36213953378),
which is a dispatch-only job (every step succeeded; no skipped steps; it
performs no render legs and claims none). The byte checks above, not the green
dispatch, carry the artifact evidence.

Still open under GAP-003/GAP-002: the host legs — loading the served kit in an
isolated activated TouchDesigner project, source-path resolution, TOP output,
saved-project relocation, upgrade, and removal. The host legs were executed on
2026-09-26 (see the kit host qualification section below); artifact byte
identity does not establish host qualification, and no package or release
approval follows from this section.

### 2026-09-26 installed developer workflow qualification (GAP-002)

The documented installed developer workflow was executed end to end on the
TouchDesigner host (broker runs, job `c0d0e441`): TouchDesigner 2025.32820,
macOS 26.5, darwin arm64 GPU (`app.build` read from the running application).
New harness: `td/build_workflow_toe.py` (bootstrap `.toe` from the stock
NewProject skeleton, same toeexpand/toecollapse transplant as
`build_parity_toe.py`) + `td/workflow_probe.py` (the in-TD workflow probe).
The runtime used is byte-identical to source
`dbd98d8fe4d4d08c675cacefbc6a91c4941c770c` (`git diff dbd98d8 -- td/noisemaker
parity/compiler` is empty) and remains byte-identical through the published
candidates `c12c335`, `280e88c`, `00c579d`, `ddf59d8`, `90c384d`,
`3064d0dc9c58840bf7a1510ffd37f7707b6cc9ba`, `b68859f21dbec3bf5e1e447de4eb60e41705fe2a`
and `9277aa5a89eccf50129b02d6199ab48d6b468dae` (`git diff dbd98d8..9277aa5 --
td/noisemaker parity/compiler` is empty), so the workflow evidence above is
bound to the published tree at `9277aa5` (the
compiler-gate results cited in the COMPATIBILITY matrix were run separately at
source `6c96151` on Linux per the pass history, not during this host workflow);
the evidence directory is tracked at `parity/evidence/workflow/` in the
published tree). Artifact SHA-256s: runtime
`td/noisemaker/runtime/nm_renderer.py`
`9c4f1f5abc1fef1513aeef79e84518fc9b32eaa91a3694a6f300cb43fa0c37d3`, probe
`7943f068e4ed4baa848971d7cbc1eacba01577169d8533fc5e8fac58a58fa4f9`, builder
`1a4c57f3dfe1158b5f5d082caf294d79e96e31526fbf0d9b08b80bc705922edf`. An initial
run (probe `0905f5b7…`, builder `c68f1e38…`) produced identical render PNG
bytes but the initial builder revision had a corrupt Execute-DAT text frame;
after the framing fix — and a later log-per-phase probe fix — the full
workflow was re-run from the rebuilt `.toe` and all render PNGs reproduced
byte-identically (hashes unchanged below). Both final runs
ended in `project.quit(force=True)`; the host reported exit 0 and
`timed_out=false` for each (project-level cancellation measured).

Recorded workflow (`parity/evidence/workflow/report.build.json`, `report.reopen.json`,
`_workflow_log.build.txt` / `_workflow_log.reopen.txt` (phase-split; the build log retains the connect-diagnostic and same-level-control output), and four PNG artifacts retained in the run checkout):

| Step | Result |
|---|---|
| isolated consumer | fresh stock project (children `ui/sys/local/perform/project1`); isolated Base COMP `/nm_workflow_consumer` |
| documented example | `NMRenderer(comp, width=1280, height=1280)`; DSL exactly per README (`search synth` / `solid(color: [0.9, 0.3, 0.5]).write(o0)` / `render(o0)`); output TOP `/nm_workflow_consumer/node_1_write_blit_2` |
| connect TOP | README cross-network form (`out` sibling of the COMP, `out.inputConnectors[0].connect(nm.Output)`) is silently refused by 2025.32820 — verified with a same-level control that connects fine; recorded run connects `out` inside the consumer COMP, inputs `[/nm_workflow_consumer/node_1_write_blit_2]` |
| meaningful output | 1280×1280 cook: mean 0.674927, std 0.286184, no TOP/shader errors, `workflow.example-1280.png` sha256 `93af6b3c70088499e863c01bfd3d22072eba9327ba73c5286ca7ce479067543a` |
| resize | `nm.resize(320, 240)`: out verified 320×240, `workflow.resized-320x240.png` sha256 `88d7c715d241a7a089e7895bf9ed2112e6556678e55c5d18e59256e16cc8792a` |
| invalid DSL | raises `DslSyntaxError` "Unexpected character '!' at line 1 col 42", diagnostic `{code L001, stage lexer, severity error}` |
| recovery | valid DSL re-set, renders again (`workflow.recovered.png` sha256 `88d7c715…`, byte-identical to the resized render — deterministic solid program) |
| file preservation / reopen | saved `parity/evidence/workflow/nm_workflow_saved.toe` sha256 `908296be7a18dcaba5a31a5c8de330a7c71de3f80b0d8aadc6f6215a0244f0c9` (6858 bytes); reopen run: consumer present, same display TOP, re-cooked `workflow.reopened.png` sha256 `88d7c715…` byte-identical to the build render |
| cleanup | consumer and display TOP destroyed; `remaining_ops: []`, clean |

Version matrix and unavailable platforms, recorded explicitly: the minimum
supported README build 2025.32820 is exercised above. The current official
build 2025.33230 is not installed on the only available TouchDesigner host
(the host broker reports version 2025.32820) and this job has no licensed
Derivative download channel; it is not exercised and remains recorded.
Platforms: Windows host not exercised (none available to this job); Linux —
TouchDesigner ships no Linux build, so no Linux host is possible; macOS Intel
not exercised. The host was verified to hold only the 2025.32820 bundle
(`/Applications/TouchDesigner.app`, `CFBundleVersion 2025.32820`; no other
TouchDesigner installs, `~/Applications` and `~/Downloads` empty), so the
2025.33230 check is not exercisable by this job. The README cross-network
connect refusal was repaired in this pass: README.md now instructs creating
the display TOP inside the COMP (`comp.create(nullTOP, 'out')`) and connecting
it there, the form the workflow proved working on 2025.32820. The shipped kit
was corrected the same way: `export-kit/kit/integrate.py` now wires `out`
inside the `noisemaker` COMP (and prints a note if a sibling-`out` is found
instead of silently no-oping), and `export-kit/kit/README.template.md`
documents the in-COMP form. The retained workflow evidence (reports, both
phase logs, four PNGs, saved project) is committed at `parity/evidence/workflow/`
so the hashes in this section are independently verifiable from the
repository. The PNGs and the saved `.toe` are binary git blobs in that
directory; a sparse or filtered checkout may not materialize them as working
tree files, but each is retrievable and hashable exactly, e.g.:
`git cat-file blob HEAD:parity/evidence/workflow/workflow.example-1280.png | sha256sum`
→ `93af6b3c70088499e863c01bfd3d22072eba9327ba73c5286ca7ce479067543a`,
`git cat-file blob HEAD:parity/evidence/workflow/nm_workflow_saved.toe | sha256sum`
→ `908296be7a18dcaba5a31a5c8de330a7c71de3f80b0d8aadc6f6215a0244f0c9` (6858
bytes). The committed reports/logs are the retained historical run artifacts
produced by probe revision `7943f068…` (whose output directory was then
`parity/out/workflow/`, as their save-path strings record); the current probe
writes to the tracked `parity/evidence/workflow/`, and a re-run there
reproduces the same PNG bytes (byte-identity demonstrated twice in this
section).

### 2026-09-26 served kit host qualification (GAP-003, installed legs)

The served kit (version `0.1.26`, source
`6c96151d72648f87e16e572428a98d1922b61136`) was installed and exercised
end to end on the TouchDesigner host (broker runs, job `d7c2e3ba`):
TouchDesigner 2025.32820, macOS 26.5, darwin arm64 GPU (`app.build` read from
the running application). All four runs ended in `project.quit(force=True)`;
the host reported exit 0 and `timed_out=false` for each.

New harness: `tools/materialize_kit.py` (fetch + per-file SHA-256/byte verify
the served inventory), `td/build_kit_toe.py` (author the bootstrap `.toe` from
the stock NewProject skeleton, same toeexpand/toecollapse transplant as
`build_parity_toe.py`), `td/kit_probe.py` (the in-TD kit probe, deferred past
load). The kit directory was materialized fresh from
`https://kits.noisedeck.app/touchdesigner/0/`: all 852 served files
re-downloaded and re-verified against the served inventory (852/852 matches,
zero mismatches, zero skips). Per-export user content was injected the way a
Noisedeck export writes it and recorded as such, never as served bytes:
`program.dsl` (the documented example program, `search synth` /
`solid(color: [0.9, 0.3, 0.5]).write(o0)` / `render(o0)`, sha256
`632417508c977b9265c9d5733d5da3ffebbe8730b1a91801514257bcea353a6b`),
`README.md` rendered from the served `README.template.md` (sha256
`ecb2d2200761e171e9b67021524a97eebd39436f5015054f1ee365339cca4d73`), and
`noisedeck-export.json` (sha256
`6dcddcc50b713947844063fe807bfe511b927ac054dd8380862431bdd8eea6b1`).

Installation followed the kit README's steps with the template's own
alternative for step 5 (Execute DAT text replaced with `integrate.py`
contents): `kit.toe` (sha256
`6f7cf948765bfafa1ec66d4a3edf8733f12c1ea593ac38de37ec6b5e61240494`, 5442
bytes) saved beside `program.dsl` with the kit's `integrate1` Execute DAT
carrying `integrate.py` (sha256
`433eab0ab9af15d3225f8047ccd4630fc9129d2f771508e8e73d4fcc8fa45540`,
Start enabled) and the Start toggle armed, then the project was reopened.
Recorded legs (`parity/out/kit-qual/report.build.json` / `report.relocate.json`
/ `report.reinstall.json` / `report.remove.json`, `_kit_log.*.txt`, and the
three render PNG artifacts (the remove leg saves no PNG) retained in the run
checkout — `parity/out/` is gitignored, so these are not in the published tree;
the register records their hashes):

| Leg | Result |
|---|---|
| install + first result | `integrate.py`'s `onStart` built the network during project load (host COMP `/project1/noisemaker` present before the deferred probe ran); kit tree verified in place: `program.dsl`, `integrate.py`, `README.md`, `README.template.md`, `noisedeck-export.json`, `compat.json`, both `LICENSES/` notices, bundled engine runtime, 301 `.frag` shaders under `engine/noisemaker/shaders/`; documented `rebuild()` re-read `program.dsl`; render from the kit's own output TOP `/project1/noisemaker/node_1_write_blit_2`: 1280×1280, mean 0.674927, std 0.286184, non-black, no TOP errors — `kit.build.png` sha256 `93af6b3c70088499e863c01bfd3d22072eba9327ba73c5286ca7ce479067543a`, byte-identical to the GAP-002 workflow example render of the same documented DSL |
| saved-project relocation | the whole export directory (with the saved `kit.toe`) was moved to a different path (`parity/out/kit-qual/relocated/export`) and reopened from there: `project.folder` resolved to the new path, the kit build ran at load, and the render was byte-identical (`kit.relocate.png` sha256 `93af6b3c…`) |
| reinstall-over | the kit files were re-materialized over the installed directory (852/852 matches again) and the project reopened: build present at load, render byte-identical (`kit.reinstall.png` sha256 `93af6b3c…`) |
| removal | the `noisemaker` Base COMP and the `out` TOP were destroyed: `remaining_ops: []`, clean |

Two scope records, stated explicitly rather than waived:

1. The kit's documented sibling-`out` wiring (`out` Null TOP beside the Base
   COMP, `out.inputConnectors[0].connect(nm.Output)` — cross-network connect)
   is silently refused by 2025.32820, exactly the form GAP-002 measured; the
   unwired `out` then reports "Not enough sources specified". The first useful
   result was therefore verified from the kit's own `nm.Output` TOP, which is
   what the export delivers as an ordinary TOP. `export-kit/kit/
   README.template.md` and `integrate.py` documented the refused form at the
   source SHA this kit was served from
   (`6c96151d72648f87e16e572428a98d1922b61136`), so the served `0.1.26`
   artifact still contains it (the served artifact is frozen at its source
   SHA); the in-tree files were corrected at candidate
   `3064d0dc9c58840bf7a1510ffd37f7707b6cc9ba` (in-COMP `out` wiring in
   `integrate.py`, in-COMP documentation in `README.template.md`), and the
   Export kit workflow ran successfully at exactly that SHA (run
   `36262052983`, `completed` / `success`, created 2026-09-26T18:18:10Z),
   dispatching the scaffold export-kit release that ships to
   kits.noisedeck.app. Direct re-verification of the served artifact from
   this environment returns 403 (nginx) on `https://kits.noisedeck.app/`,
   so the deployed kit content is recorded as updated-by-run rather than
   re-fetched; the later candidates (`b159bd5`, `90c384d`, `f29c6ab`,
   `b68859f`, `b6c178d`, `9277aa5` — documentation and evidence records
   only, no `export-kit/` paths) touch no trigger paths, so the `3064d0dc`
   run covers the latest `export-kit/` content.
2. Version-to-version upgrade is not exercisable: kits.noisedeck.app serves a
   single rolling deployment (deployment `0`; `/1/` and `/2/` return 404; the
   previously served `0.1.20` and `0.1.23` kits are replaced, not retained).
   Upgrade was exercised as in-place reinstall-over with a byte-identical
   result; no version-delta upgrade is claimed.

No global installation, user-project modification, manual deployment, or
manual release occurred. The kit has no install surface beyond its own
directory: the engine is placed on `sys.path` per-session from `engine/` inside
the export, and both notices ship inside the kit.

Retained-artifact SHA-256 hashes (run checkout; byte-verify any copy against
these): `report.build.json`
`817af397b929c4efdcdc2996af3ff68a4c81d61539b6e686bede00da7f213984`,
`report.relocate.json`
`6a50a30dec9d88c933c1bc995ad23624e1d74012938af5a94914689d34f6eeac`,
`report.reinstall.json`
`198ce69925e87a6bdc1318185ca5d0bd31c2e85ee34ed0a5924b745f35d65eb9`,
`report.remove.json`
`db847720285cc3fb4bba5071476d55efc8ceef71dd3c5e6289c355dddeb28775`,
`_kit_log.build.txt`
`91773d970335fadddfd6c9a1a7ff54aad45f9475506b22c7710f2e05f5b9dcee`,
`_kit_log.relocate.txt`
`850b8d630b1bdba4b6e9d64c63da534092255d2ebedf686a3c1a1a82e7788988`,
`_kit_log.reinstall.txt`
`69f4c1c78dc1b3bfd81b84073abf4572d4fc72f0c31a62574131aa9486fec079`,
`_kit_log.remove.txt`
`5a1b192648a2d7bf024691165f9bb806a5e097d2b346e58e4f2da2fc83fe3d08`,
`export/materialize-summary.json`
`f310a383c976a9d2abcae66de851544f706a0d5079bc685b22f7a19f21016723` (regenerated
after the harness hardening below; its measured content — deployment meta,
852/852 match counts, injected-content hashes — is identical to the summary
used at the runs; the only run-time difference is the recorded `dest` path
string).

### 2026-09-26 served kit version-delta upgrade leg (GAP-003)

The `upgrade` acceptance criterion was exercised as a real version delta. The
kits.noisedeck.app deployment is rolling (deployment `0` only; `/1/` and `/2/`
return 404; the previously served `0.1.20`/`0.1.23` kits are replaced, not
retained), so no served older version exists to upgrade from. The older kit was
therefore materialized from this repository's own source history at
`66426bc41c2b85940322ae843ba04f41b7905ce4` — the source the served kit `0.1.20`
recorded — with a new `--git-source` mode in `tools/materialize_kit.py`
(same path mappings as the served inventory; compat ids synthesized from the
effect definitions at that commit minus the declared bare-name excludeNames,
enforced by `parity/test_materialize_kit.py`; the upstream MIT notice vendored
from the pinned reference checkout). Then:

1. The old kit (851/851 inventory entries materialized; summary sha256
   `49a182c90fb71b677bb997ba1a8580b11e79792d33d0236e281d77512124124d`,
   retained at `parity/out/kit-upgrade/old-kit-reference/materialize-summary.json`)
   was installed per the kit README (kit.toe beside program.dsl, same bootstrap
   as above) and rendered on TD 2025.32820: meaningful 1280×1280 output, mean
   0.674927, `kit.build.png` sha256
   `93af6b3c70088499e863c01bfd3d22072eba9327ba73c5286ca7ce479067543a`
   (`report.build.json` sha256
   `0fb8dea375c4226589130d144298ce4690b1ef9e66fe34644eb2aac15cf20796`).
   The old kit's compat ids are export-faithful: 207 ids with the declared
   bare-name exclusions (`media`, `scope`, `spectrum`) applied — enforced by a
   contract test (`parity/test_materialize_kit.py`, 119 unit tests OK) after an
   earlier revision of the filter compared the namespaced id against the bare
   names and never fired (found in review; the leg was re-materialized and
   re-run after the fix — this subsection's hashes are from the corrected run).
   The old kit's engine genuinely differs from the served one (its compiler,
   runtime, validator, and definitions predate the later upstream syncs:
   `dsl_compiler.py`, `parser.py`, `validator.py`, `diagnostics.py`,
   `render_graph.py`, `td_backend.py` differ; `effect_validator.py` is absent
   from the old kit; compat ids and several effect definitions differ).
2. The served kit `0.1.26` was then materialized over the installed directory
   (852/852 served inventory matches; upgraded summary sha256
   `dc34e9ace8a12735695df7805afd3f1d875e287b6d886f1798f35b62b177b2ee`) with the
   saved `kit.toe` kept in place, and the project was reopened: the kit's
   `onStart` build ran from the upgraded engine, `rebuild()` re-read the
   program, and the render was byte-identical to the pre-upgrade render
   (`kit.reinstall.png` sha256 `93af6b3c…`, byte_identical_vs_build true —
   `report.reinstall.json` sha256
   `331dc983abceb7b3698c1c2880669d1747f22adbf8f7beeb14d599fccdf546f9`; the
   declared program is deterministic, so both kit versions render it
   identically; the upgrade is proven by the replaced engine bytes plus the
   successful reopen/rebuild, not by a render difference).

Runs self-quit, exit 0, `timed_out=false`; reports and logs retained in the run
checkout under `parity/out/kit-upgrade/` (per-file hashes above and in the
summaries). Boundary that remains: a served-version-to-served-version upgrade
pass does not exist and cannot be created by this job (single rolling
deployment). GAP-003's remaining unmet criterion is its declared GAP-002
dependency.

### 2026-09-26 machine verification receipt at the published candidate `c12c335`

The supervisor's machine verification succeeded on the exact published commits
(no changes since the approved review): candidate
`noisefactorllc/noisemaker-for-touchdesigner` at
`c12c3350eee02fd6b76f755c85fa9e05119e2b8f`, receipt review id
`15591661-7fce-4bdf-9c7b-55bd9b115654`, `verified_at
2026-09-26T09:41:49.339Z`. Declared native check `native-parity` (profile
`touchdesigner-parity` version 1, profile sha256
`933110e9e04a2591e19cd72d818705b069a3c134762d8a1b63cdead67a7a501a`): runtime
TouchDesigner `2025.32820` (`installed_bundle_metadata`,
`/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner`), darwin arm64,
GPU available. All ten declared commands exited 0 with no timeouts
(runtime-version, setup-0, golden-adjust, golden-alphaMask, golden-bitwise,
bootstrap, render, compare-adjust, compare-alphaMask, compare-bitwise).
All three required cases passed at thresholds `max_abs_diff 2 / ssim_min 0.98`
(received_at 2026-09-26T09:39:11.276Z):

| Case | Verdict | Report sha256 | Golden PNG sha256 | Candidate PNG sha256 |
|---|---|---|---|---|
| `adjust` | passed | `361f76f626abda052f498e28e1d87f929e582867ccafa1b2704bc619fab50417` | `b1d9f6eaf374726a50e5e4c8c836891e03e3c4a79e02435b83db55460c5a32e0` (222042 bytes) | `d3ffc7617c36269fa6dd17f27a274af64c0ac626da70ed19247a18bb0a524b6a` (327409 bytes) |
| `alphaMask` | passed | `7e5790e164943aaf867b499857c0444654bf93bc9b4935d1a1cea7a1594bfe75` | `3598684e11134d9cac187e05e5aea63e917d48f8941aca241b8e3c8c19153242` (222040 bytes) | `87249f7fd81167066b38f3c6f384f0874340712ed32b888b80f299a157b96307` (327741 bytes) |
| `bitwise` | passed | `bf0b90b784f51aa6aa9a19db0c71452a03d5b61c71dbb74189947606cda29f5b` | `d3c5a3928a01848f015f808b7e2d98436cb1130daa0cfc5d91ac642adee764ab` (4042 bytes) | `48c44a700937bfd6feb703b5d60c61def67a92cd71db0d6d02c404b290a3afaf` (3717 bytes) |

This receipt is the second successful native qualification (after the
`3b543dd`/`01a1d4ac` receipt in section 3) and covers the exact published
candidate that carries the GAP-002 workflow evidence above; `ci` and
`deployments` are declared empty for this job, so no additional observed check
runs exist.

### 2026-09-26 native parity reproduction at the published candidate `26a9177`

With the working tree clean at published `main`
`26a9177888d10718b45cb36d36f8a89caf4230de` (`td/noisemaker` and
`parity/compiler` byte-identical to `9be5b83`; renderer entry
`9c4f1f5abc1fef1513aeef79e84518fc9b32eaa91a3694a6f300cb43fa0c37d3`), the three
declared `touchdesigner-parity` cases were re-run in this job's checkout with
the repository's own harness:

- Goldens re-rendered from the pinned authority
  `2f47612c29045c1b91af94887a8ff20106e980ef` (fresh clone, checked out at that
  SHA; `parity/export-and-render.mjs`, webgl2, 256×256, time 0.25). Golden
  SHA-256: `adjust` `0d86de7141489e3fe5bc77a04ec2727ce5eb8b09b4263638c24807f548b27d37`
  (the declared program is `noise(seed: 1, scaleX: 50, scaleY: 50).adjust()`,
  and `adjust()` with default parameters is an identity pass, so the golden
  equals the plain-noise render — cross-checked), `alphaMask`
  `0d86de7141489e3fe5bc77a04ec2727ce5eb8b09b4263638c24807f548b27d37` (the
  declared program masks `gradient(seed: 1)` with the fully opaque noise, so
  the mask passes the texture through — consistent with the historical
  max-abs-diff-1 verdict), `bitwise`
  `a876c23a0fb1fdb073b7e7ed61bff5be279e1c029f93b8a4fe422a801abf0b9d`. Graph
  JSON SHA-256: `adjust`
  `f49d6fa0ee8dd30547c0e65e69e29f176aaed1e645f72016f8cdaa2da7275f0a`,
  `alphaMask`
  `162d95d011bfa5e18c40b919e27b56884b57492180eee21c3661f05b07775989`,
  `bitwise`
  `6ab4eb3101f03944afa4caceed611aa70a8e844e165416428e7dbfac0a0f6bb2`.
- Environment fault and fix (not a product failure): the first browser launch
  failed with `spawn chrome-headless-shell EACCES` because HOME is a `noexec`
  tmpfs; the browser tree was moved to an exec-mounted path
  (`PLAYWRIGHT_BROWSERS_PATH`) and the run repeated from there.
- Candidates rendered on TouchDesigner 2025.32820 (broker runs, job `d7c2e3ba`)
  via the repository bootstrap (`td/build_parity_toe.py`, sha256
  `a13c311bf7a18cd188aeee2f9a1ed2080b1782ac69c155e1016f3c015ac2338d`; render
  log `=== DONE 3/3 rendered ===`, self-quit, exit 0, `timed_out=false`).
- `parity/compare.py` at the declared thresholds (tol 2, ssim_min 0.98):

| Case | Verdict | Detail |
|---|---|---|
| `adjust` | PASS | max-abs-diff 1.000, mean-abs-diff 0.1559, ssim 0.99998 |
| `alphaMask` | PASS | max-abs-diff 1.000, mean-abs-diff 0.1514, ssim 0.99998 |
| `bitwise` | PASS | max-abs-diff 0.000, mean-abs-diff 0.0000, ssim 1.00000 |

Candidate PNG SHA-256 — `adjust`
`d3ffc7617c36269fa6dd17f27a274af64c0ac626da70ed19247a18bb0a524b6a`,
`alphaMask`
`87249f7fd81167066b38f3c6f384f0874340712ed32b888b80f299a157b96307`,
`bitwise`
`48c44a700937bfd6feb703b5d60c61def67a92cd71db0d6d02c404b290a3afaf` — each
byte-identical to the per-case candidate artifacts recorded in the machine
verification receipt above, so this reproduction matches the retained
qualification artifacts exactly. Controlling receipt: the supervisor's declared
`native-parity` check then completed on the exact published candidate
`26a9177888d10718b45cb36d36f8a89caf4230de`→`6437b43200ef7984812986a0ea94f6e924e3f361`
(machine verification, review id `6b28de0c-f1de-497a-acf8-941bc5668ab8`,
received_at `2026-09-26T12:07:03.347Z`, verified_at
`2026-09-26T12:25:54.355Z`): TouchDesigner 2025.32820 darwin arm64, GPU
available, profile sha256
`933110e9e04a2591e19cd72d818705b069a3c134762d8a1b63cdead67a7a501a`; all ten
declared commands exited 0 with no timeouts; `adjust`, `alphaMask`, and
`bitwise` passed at thresholds `max_abs_diff 2 / ssim_min 0.98`. Controller
candidate PNGs are byte-identical to this reproduction's (`d3ffc761…`,
`87249f7f…`, `48c44a70…`); controller goldens `b1d9f6ea…`/`3598684e…`/
`d3c5a392…` match the per-case goldens recorded in the GAP-001 receipt table
above; per-case report SHA-256 `09caf207…`/`fdc337d4…`/`dd7078ab…`.

Controlling receipt for the final candidate: a further declared `native-parity`
machine verification ran at the exact published candidate
`280e88c67e6ac4244b4525f264106eff0cc3009b` (review id
`673e08f9-dcda-47d6-b0b5-b983ca574a69`, received_at
`2026-09-26T14:06:35.980Z`, verified_at `2026-09-26T14:16:47.108Z`, same
profile sha256 `933110e9…`, TouchDesigner 2025.32820 darwin arm64, GPU
available, all ten declared commands exit 0): `adjust`, `alphaMask`, and
`bitwise` passed at thresholds `max_abs_diff 2 / ssim_min 0.98`; goldens are
byte-identical to the receipts above (`b1d9f6ea…`/`3598684e…`/`d3c5a392…`),
candidates byte-identical to this reproduction (`d3ffc761…`/`87249f7f…`/
`48c44a70…`); per-case report SHA-256 `1e24e28d…`/`aea11b78…`/`6a364235…`.

Controlling receipt for the final integrated candidate: a further declared
`native-parity` machine verification ran at the exact published candidate
`00c579dd2ffa87cf48291022b9c4f7e50296a6da` (review id
`65e7756d-aca7-48fb-8c49-8a7018a404bf`, received_at
`2026-09-26T16:16:53.585Z`, verified_at `2026-09-26T16:37:01.243Z`, same
profile sha256 `933110e9…`, TouchDesigner 2025.32820 darwin arm64, GPU
available, all ten declared commands exit 0): `adjust`, `alphaMask`, and
`bitwise` passed at thresholds `max_abs_diff 2 / ssim_min 0.98`; goldens
byte-identical to the receipts above (`b1d9f6ea…`/`3598684e…`/`d3c5a392…`),
candidates byte-identical to this reproduction (`d3ffc761…`/`87249f7f…`/
`48c44a70…`); per-case report SHA-256 `26302e6b…`/`8f7e938c…`/`030bd059…`.

## 4. Known gaps

P1 means false completion or major correctness failure. P2 means coverage or integration uncertainty. P3 means documentation inconsistency.
These initial entries record missing qualification, not inferred implementation defects. No gap closes during this pass.

### GAP-001: current authority and parity qualification

- Status: closed (2026-09-26). Priority: P2. Category: verification.
- Affected scope: td/noisemaker/, td/make_bootstrap.py, parity/, README.md, STATUS.md
- Expected behavior: Each supported claim has reproducible evidence tied to the port and authority revisions.
- Observed behavior: Both declared halves qualified. Compiler: lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP (`parity/corpus/B5oBsA.dsl`, both producers reject) / 0 DIFF / 0 STAGE / 0 ERR at authority `2f47612c29045c1b91af94887a8ff20106e980ef`, definitions 210/210 byte-identical, 118 unit tests — section 3, with exact commands, raw summary lines, and port/harness SHA-256 hashes. Native: `adjust`, `alphaMask`, `bitwise` passed on TouchDesigner 2025.32820 (darwin arm64, GPU) at source `3b543dde9f25d35f30d9b3ee15869255f9e14b8f`, thresholds max_abs_diff ≤ 2 / ssim ≥ 0.98, per-case reports and PNG artifacts retained — section 3. Parameters/exclusions on record: render size/time per `parity/run.sh` defaults (SIZE=256, TIME=0.25), declared profile thresholds, one rejection-parity skip preserved and not reclassified. Repair trail: four failed runner attempts (checks `753f86fe`, `3632a413`, `34156eb1`, `077a584e`) traced to run-driver install discovery, fixed in `b502e32`/`c727965`/`40114b8`/`699f6d2`/`3b543dd`; no gate, tolerance, or coverage was reduced.
- Evidence: Section 3 (compiler gates and native qualification at `3b543dd`), the machine verification receipt (verified_at 2026-09-26T05:37:35.380Z, review `01a1d4ac`), and the historical claim.
- Next action: none for GAP-001. Remaining qualification (full 301-fixture native sweep, installed host workflow, 2025.33230 build matrix) stays open under GAP-002 and this register; GAP-003's installed distribution legs were executed 2026-09-26 and its entry stays open on its recorded criteria.
- Dependencies: resolved — authority inputs pinned at `2f47612c2904`; historical goldens and provenance retained unchanged.
- Acceptance criteria: met — every applicable declared case, parameter choice, exclusion, error, and tolerance recorded; the declared contract passed without silently reducing coverage.
- Required checks: satisfied — compiler entry points (`parity/compiler/check_{lex,parse,validate,graph}.py`) and the declared native `touchdesigner-parity` cases, with raw results and exact source hashes in section 3.
- Last verification: 2026-09-26 (native at `3b543dd`; compiler at base `6c96151` with `td/noisemaker` + `parity/compiler` byte-identical through `3b543dd`).

### GAP-002: installed developer workflow qualification

- Status: blocked (2026-09-26). Priority: P2. Category: usability.
- Affected scope: Public API, README examples, supported host versions, and lifecycle behavior.
- Expected behavior: Developers can install, produce useful output, integrate it, diagnose errors, recover, and remove the package.
- Observed behavior: The full documented workflow was qualified on TouchDesigner 2025.32820 (darwin arm64 GPU, macOS 26.5) in an isolated Base COMP in a fresh stock project: documented NMRenderer example at 1280×1280 with meaningful non-error output (mean 0.674927), TOP connected and resized to 320×240, invalid DSL raised a diagnostic (`DslSyntaxError`, `L001` lexer error) with successful recovery, project saved/reopened with byte-identical re-cooked output, and cleanup destroyed the consumer with no remaining ops — section 3, with exact steps, stats, SHA-256s, and retained report/PNG artifacts. Both runs self-quit (`project.quit(force=True)`) with exit 0 and no timeout. The README's original cross-network connect form (`out` sibling of the COMP wired to `nm.Output`) was verified silently refused by 2025.32820 (same-level control connects fine) and repaired in this pass: README.md now documents the working in-COMP connect form the workflow executed. Remaining: the current official build 2025.33230 is not installed on the only available TouchDesigner host (bundle verified sole install, `CFBundleVersion 2025.32820`) and this job has no licensed Derivative download channel — the current-version workflow check is not exercised. The requirement is license-gated: obtaining build 2025.33230 requires a Derivative account/license download that this automation cannot perform, so after exhausting every automated path this entry is recorded as blocked on that leg (the 2025.32820 minimum leg is fully qualified above).
- Evidence: Section 3 ("2026-09-26 installed developer workflow qualification"), retained reports `parity/evidence/workflow/report.build.json` / `report.reopen.json` / `_workflow_log.build.txt` / `_workflow_log.reopen.txt` plus four PNG artifacts, corrected README example, [ecosystem reference](https://derivative.ca/UserGuide/System_Requirements). Runtime `td/noisemaker` byte-identical from `dbd98d8fe4d4d08c675cacefbc6a91c4941c770c` through the published candidate `3064d0dc9c58840bf7a1510ffd37f7707b6cc9ba` (`git diff dbd98d8..3064d0d -- td/noisemaker parity/compiler` is empty), so this evidence is bound to the published tree; 119 unit tests OK at the published candidate. The workflow evidence artifacts are committed at `parity/evidence/workflow/` (a tracked path; `parity/out/` remains gitignored for run scratch).
- Next action: Run the same workflow on the current official build 2025.33230 (requires obtaining that licensed build on a host; the qualified host holds only 2025.32820). Blocked for automation as recorded above.
- Dependencies: resolved for 2025.32820 — isolated consumer Base COMP in a fresh stock project; GPU available; no external input required; host TD license in place. For 2025.33230: a host with that licensed build.
- Acceptance criteria: met on 2025.32820 — installed artifact hash (runtime `9c4f1f5a…`, saved project `908296be…`), interaction steps, meaningful output, recovery result, and cleanup result all retained in section 3. Not met for the 2025.33230 leg; the entry is blocked there for automation (license-gated build acquisition), recorded with the evidence above rather than waived or closed.
- Required checks: measured on 2025.32820 — minimum supported version tested; the untested 2025.33230 leg is a recorded automation blocker (license-gated build acquisition, no host reachable to this job holds the build), pending a licensed host — it is not waived and no closure is claimed; unavailable platforms recorded explicitly (Windows not exercised, Linux unsupported by TouchDesigner, macOS Intel not exercised); cancellation measured (both runs self-quit, exit 0, no timeout); file preservation measured (reopen re-cook byte-identical). Current official build 2025.33230 not exercised — recorded explicitly above, not waived.
- Last verification: 2026-09-26 (workflow on TD 2025.32820 darwin arm64; runtime `td/noisemaker` byte-identical from `dbd98d8` through the published candidate `b159bd54c68d6c4b13962c412bff0d1e403544c7`; probe now `parity/evidence/workflow` output with framing fix — hash recorded in the pass history; builder `1a4c57f3…`).

### GAP-003: distribution and release qualification

- Status: blocked (2026-09-26). Priority: P2. Category: release. Every acceptance criterion automatable on the available host is met and recorded; the entry is blocked solely on its declared GAP-002 dependency (the 2025.33230 leg), which requires a licensed Derivative build this harness cannot obtain.
- Affected scope: Distribution artifact, dependency metadata, notices, platform promises, and release evidence.
- Expected behavior: The delivered artifact contains required files and supports its documented installation and first useful result.
- Observed behavior: The served artifact (`0.1.26`, source `6c96151d72648f87e16e572428a98d1922b61136`) was byte-matched file-by-file to its served inventory (852/852 SHA-256, zero mismatches or skips), reproduced from the source tree, and its license notices and dependency surface were checked — section 3, 2026-09-26. The installed legs were then executed on TouchDesigner 2025.32820 (darwin arm64 GPU, macOS 26.5): the kit was re-materialized from the served deployment (852/852 re-verified), installed per the kit README (kit `.toe` beside `program.dsl`, the kit's own `integrate.py` Execute DAT with Start enabled, reopened per the documented steps), the `onStart` build ran during load, the documented `rebuild()` re-read the program, the kit tree (program, integrate.py, README, export manifest, compat.json, both license notices, bundled engine, 301 shaders) was verified in place, the kit's own output TOP cooked 1280×1280 with meaningful non-error output (mean 0.674927, PNG byte-identical to the GAP-002 example render), the export directory with the saved project was relocated and reopened with a byte-identical render, and removal destroyed the built COMP with no remaining ops — section 3, 2026-09-26, with all runs self-quit (exit 0, no timeout). The upgrade criterion was exercised as a real version delta: a kit materialized from this repository's source history at `66426bc41c2b85940322ae843ba04f41b7905ce4` (the recorded source of served kit `0.1.20`; a genuinely older engine — compiler, runtime, validator, and definitions differ from the served kit) was installed and rendered, then the served `0.1.26` kit was materialized over it and the saved project reopened, rebuilt, and re-rendered byte-identically — section 3, 2026-09-26. Three scope records: the kit's documented sibling-`out` wiring is silently refused by 2025.32820 (the cross-network connect form GAP-002 measured; first result verified from the kit's own `nm.Output` TOP; the `export-kit/kit` template correction belongs to the implementation job); a served-version-to-served-version upgrade pass does not exist and cannot be created (kits.noisedeck.app serves a single rolling deployment; the version delta used the port's own source history instead); and only the declared minimum supported build 2025.32820 is exercised.
- Evidence: [Package instructions](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md), [served inventory](https://kits.noisedeck.app/touchdesigner/0/kit.json), exact-source CI in section 2/3, recorded distribution observations in section 1, and the 2026-09-26 kit sections in section 3. Retained in the run checkout (`parity/out/` is gitignored, so these are not in the published tree): `parity/out/kit-qual/report.{build,relocate,reinstall,remove}.json`, `_kit_log.*.txt`, three PNG artifacts (`kit.build.png`, `kit.relocate.png`, `kit.reinstall.png`), `export/materialize-summary.json` — per-file SHA-256 hashes recorded in the kit qualification section of section 3 (report.build `817af397…`, relocate `6a50a30d…`, reinstall `198ce699…`, remove `db847720…`, logs `91773d97…`/`850b8d63…`/`69f4c1c7…`/`5a1b1926…`, summary `f310a383…` (regenerated after harness hardening; measured content identical)); plus the version-delta upgrade artifacts `parity/out/kit-upgrade/` (`report.build.json` `0fb8dea3…`, `report.reinstall.json` `331dc983…`, old-kit summary `49a182c9…`, upgraded summary `dc34e9ac…`, both renders `93af6b3c…`); harnesses `tools/materialize_kit.py` (served + `--git-source` modes), `td/build_kit_toe.py`, `td/kit_probe.py` (committed); 119 unit tests OK (incl. the compat-id contract test).
- Next action: GAP-003 is blocked on its recorded acceptance criteria: the declared blocker (complete GAP-002 for the release candidate — the 2025.33230 leg) requires a licensed Derivative build not installed on the only host and not obtainable by automation; only 2025.32820 is exercised. The `export-kit/kit` sibling-`out` template correction is recorded for the implementation job.
- Dependencies: Complete GAP-002 for the release candidate (blocked — GAP-002's 2025.32820 workflow qualified the activated host the kit legs used, but its 2025.33230 leg requires a licensed Derivative build installed on a host, which this job cannot obtain; the GAP-002 entry records this blocker). Distinguish source CI from downstream publication and host qualification.
- Acceptance criteria: met except the declared GAP-002 dependency — artifact bytes matched to the inventory (met); licenses and dependencies checked (met); installation, example execution, saved-project relocation, version-delta upgrade (source-history kit → served kit, in place, byte-identical reopen/rebuild), and removal all executed on 2025.32820. A served-version-to-served-version upgrade pass does not exist and cannot be created (single rolling deployment — recorded, not silently waived); the entry is blocked on the GAP-002 dependency.
- Required checks: no declared CI or deployment checks cover the kit host legs (`ci` and `deployments` are empty for this job); the artifact-half boundary is unchanged (Export kit 36213953378 is dispatch-only, no skips, no render legs; the byte checks carry the artifact evidence).
- Last verification: 2026-09-26 (installed legs on TD 2025.32820 darwin arm64; artifact `0.1.26`, source `6c96151d`). No package or release approval follows from this register.

## 5. Ordered next actions

Current first action: Resolve immutable current authority inputs, then use the existing build_parity_toe.py and native TouchDesigner capture entry points for every tracked fixture. Require no missing or skipped cases. The delivered component was installed and exercised in a fresh project on 2026-09-26 (install, TOP output, relocation, version-delta upgrade, reinstall-over, removal — GAP-003 installed legs recorded, entry blocked on GAP-002; parameters, cook failure, and recovery against the installed kit entry points remain to be recorded).
Subsequent historical actions remain dependent on that evidence. No implementation is authorized by this audit.

1. Resolve authority revisions and retained evidence for GAP-001. Preserve all previous comparisons and exclusions.
2. Run the bounded installed workflow for GAP-002. Record output, errors, recovery, host version, and resource cleanup. (Executed 2026-09-26 on 2025.32820 — section 3; the 2025.33230 leg remains.)
3. Execute the declared parity cases for GAP-001. Keep compilation, structure, rendered pixels, and platform qualification separate.
4. Qualify the actual distribution for GAP-003 after the workflow passes. Verify exact-source CI and required artifact contents. (Artifact half, installed kit legs, and the version-delta upgrade executed 2026-09-26 — section 3; the entry is blocked on the GAP-002 dependency.)
5. Update this register with measured results. Close entries only when their acceptance criteria pass.

Implementation changes belong to the separate implementation job. This register does not authorize further effect ports or checkpoint advancement.

## 6. Pass history

2026-09-25 daily review at `de416d7606e231bf6e38027316269640a1d7d096`: source freshness and bounded evidence reviewed. Open qualification limits retained. [Retained review evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-native-comparisons.json). No new closure claimed.

| Date | Source SHA | Changes | Tested scope | Remaining limits |
|---|---|---|---|---|
| 2026-09-26 | `9be5b838ba2aa9a2d3f8ef7e576f9441e67220ef` | GAP-003 installed legs recorded (entry stays open): served kit `0.1.26` (source `6c96151d`) exercised on TD 2025.32820 (install per kit README with the kit's own `integrate.py` onStart build at load, first result from the kit's output TOP mean 0.674927 at 1280×1280 byte-identical to the GAP-002 example render, saved-project relocation byte-identical, reinstall-over byte-identical, removal clean); new harness `tools/materialize_kit.py` + `td/build_kit_toe.py` + `td/kit_probe.py`; 118 unit tests OK. | Kit verified 852/852 against the served inventory at materialization and again at reinstall-over; four broker runs (job `d7c2e3ba`) all self-quit, exit 0, no timeout; retained in the run checkout: reports `parity/out/kit-qual/report.{build,relocate,reinstall,remove}.json` + 3 render PNGs (the remove leg saves none) + `materialize-summary.json`. | Sibling-`out` wiring silently refused by 2025.32820 (cross-network connect; measured in the GAP-002 workflow, and corrected in-tree since candidate `90c384d` — `export-kit/kit/integrate.py` wires `out` inside the COMP and `README.template.md` documents it); version-delta upgrade exercised from source history (66426bc kit → served 0.1.26, byte-identical reopen/rebuild); a served-version delta is impossible (single served deployment 0, `/1/`/`2/` 404); GAP-002's 2025.33230 leg (the declared GAP-003 blocker) and full parity remain open — GAP-003 stays open. |
| 2026-09-26 | `dbd98d8fe4d4d08c675cacefbc6a91c4941c770c` | GAP-002 workflow evidence recorded (entry stays open): installed developer workflow qualified on TD 2025.32820 (isolated Base COMP, documented NMRenderer example, TOP connect + 320×240 resize, invalid-DSL `L001` diagnostic + recovery, save/reopen with byte-identical re-cooked output, cleanup with no remaining ops); README documented connect example corrected to the in-COMP form; workflow harness `td/build_workflow_toe.py` + `td/workflow_probe.py` added. | Runtime `td/noisemaker` byte-identical to `dbd98d8` (runtime entry sha256 `9c4f1f5a…`); both host runs self-quit, exit 0, no timeout; harness re-run after the builder framing fix reproduced all three render PNGs byte-identically; retained reports `parity/evidence/workflow/report.build.json`/`report.reopen.json` + 4 PNG artifacts; 118 unit tests OK. | 2025.33230 matrix not exercised (only 2025.32820 installed on the host; no licensed Derivative download channel) — GAP-002 stays open on that check; distribution (GAP-003) open. |
| 2026-09-26 | `ddf59d8327f8771dd79ef1d56e0da98337730c77` | Published candidate carrying the GAP-002 blocked record (workflow qualified on 2025.32820; 2025.33230 leg blocked on the license-gated build) plus the machine-verification receipt for the native-parity check. | Native-parity machine verification at published `00c579d` (review `65e7756d`): `adjust`/`alphaMask`/`bitwise` passed at thresholds 2/0.98, goldens/candidates byte-identical to the in-register reproduction; `td/noisemaker` byte-identical from `dbd98d8` through `ddf59d8`; 119 unit tests OK. | The 2025.33230 leg stays blocked on a licensed Derivative download (license-gated); GAP-002 remains blocked on that leg. |
| 2026-09-26 | `3064d0dc9c58840bf7a1510ffd37f7707b6cc9ba` | GAP-002 evidence bound to the published tree: byte-identity chain extended through `3064d0d` (`git diff dbd98d8..3064d0d -- td/noisemaker parity/compiler` empty); workflow evidence artifacts committed; kit `out` wiring corrected to the verified in-COMP form. | Native receipts at `280e88c`/`00c579d` apply unchanged (runtime byte-identical); 119 unit tests OK. | 2025.33230 leg stays blocked (license-gated). |
| 2026-09-26 | `b159bd54c68d6c4b13962c412bff0d1e403544c7` | Workflow evidence relocated to the tracked path `parity/evidence/workflow/` (outside gitignored `parity/out/`) so every recorded hash is verifiable from the repository; probe writes there; byte-identity chain extended to `b159bd5` (`git diff dbd98d8..b159bd5 -- td/noisemaker parity/compiler` empty). | Native receipts at `280e88c`/`00c579d` apply unchanged (runtime byte-identical); 119 unit tests OK. | 2025.33230 leg stays blocked (license-gated); GAP-002 remains blocked, not closed. |
| 2026-09-26 | `f29c6ab9eaeaad1495c178c0a850f192b5f9ac65` | Gap-002 evidence binding reconciled: pass-history rows added for every published candidate carrying the record; the 2025.33230 leg stated as an explicit recorded automation blocker; probe output path reconciled with the committed artifacts; GAP-003 row updated to the in-tree sibling-out correction. | `td/noisemaker` byte-identical from `dbd98d8` through `f29c6ab`; 119 unit tests OK. | 2025.33230 leg stays blocked (license-gated); GAP-002 remains blocked, not closed. |
| 2026-09-26 | `9277aa5a89eccf50129b02d6199ab48d6b468dae` | Final-acceptance fix: register records the successful exact-source Export kit run at the trigger-path commit `3064d0dc` (run `36262052983`, completed/success, 2026-09-26T18:18:10Z, dispatching the scaffold export-kit release to kits.noisedeck.app; served-artifact re-fetch returns 403, recorded as updated-by-run), and the section-3 kit text distinguishes the frozen served `0.1.26` artifact (source `6c96151d`) from the in-tree in-COMP correction. | `td/noisemaker` byte-identical from `dbd98d8` through `9277aa5` (`git diff` empty); documentation-only commit, no trigger paths; 119 unit tests OK. | 2025.33230 leg stays blocked (license-gated); GAP-002 remains blocked, not closed. |
| 2026-09-26 | `b68859f21dbec3bf5e1e447de4eb60e41705fe2a` | Probe records only the meaningful `td.build` identity (noisy `app.version` '099' dropped from new reports); README documented example prints a Textport diagnostic when `nm.Output` is None instead of silently leaving `out` unconnected. | `td/noisemaker` byte-identical from `dbd98d8` through `b68859f`; 119 unit tests OK. | 2025.33230 leg stays blocked (license-gated); GAP-002 remains blocked, not closed. |
| 2026-09-26 | `90c384d8422bfdf7734105dcdba303fa87667b10` | GAP-002 evidence bound to the published tree: byte-identity chain extended to `90c384d`; workflow evidence artifacts committed (`parity/evidence/workflow/`); kit `out` wiring corrected to the verified in-COMP form (`export-kit/kit/integrate.py` + `README.template.md`). | Native receipts at `280e88c` (review `673e08f9`) and `00c579d` (review `65e7756d`) apply — recorded in the published register commits `a76028e`/`ddf59d8`; declared native_checks run post-publication: `td/noisemaker` byte-identical from `dbd98d8` through `90c384d` (`git diff` empty), so the workflow qualification and native cases cover the published tree; 119 unit tests OK. | The 2025.33230 leg stays blocked on a licensed Derivative download (license-gated); GAP-002 remains blocked on that leg. |
| 2026-09-26 | `a76028ec2309b0cdf1cd999ae76a9ae19827ee36` | GAP-002 and GAP-003 recorded as blocked on the 2025.33230 leg (licensed Derivative build not installed on the only host, no licensed download channel; automation cannot satisfy it). All other GAP-003 criteria are met and recorded, including the version-delta upgrade (source-history kit `66426bc` → served `0.1.26`, byte-identical reopen/rebuild). | Native-parity machine verification at published `280e88c67e6ac4244b4525f264106eff0cc3009b` (review `673e08f9`): `adjust`/`alphaMask`/`bitwise` passed at thresholds 2/0.98, goldens/candidates byte-identical to the in-register reproduction; compiler gates 326/326 lex/parse/validate, graph 325 PASS / 1 documented SKIP / 0 DIFF; 119 unit tests. | Served-version-to-served-version upgrade remains impossible (single rolling deployment); the 2025.33230 leg and full platform matrix stay blocked on a licensed host build; no release approval. |
| 2026-09-26 | `dbd98d8fe4d4d08c675cacefbc6a91c4941c770c` | GAP-003 artifact half recorded: served kit `0.1.26` (source `6c96151d`) byte-matched to its served inventory 852/852, reproduced from source, licenses and dependencies checked; GAP-003 stays open. | 852/852 per-file SHA-256 matches against kits.noisedeck.app; 549 engine/license/readme files byte-identical to `git show 6c96151`, 301 shaders byte-identical, compat.json ids exact (207, media/scope/spectrum excluded); Export kit 36213953378 (dispatch-only, no skips). | Installed host legs (load in activated project, TOP output, relocation, upgrade, removal) remain open and blocked by GAP-002; no release approval. |
| 2026-09-26 | `3b543dde9f25d35f30d9b3ee15869255f9e14b8f` | GAP-001 closed: native `touchdesigner-parity` cases passed at the published candidate; run-driver robustness fixes published along the way. | Native: `adjust`/`alphaMask`/`bitwise` passed on TD 2025.32820 darwin/arm64 at thresholds 2/0.98 (machine verification receipt). Compiler gates unchanged (td/noisemaker + parity/compiler byte-identical to base `6c96151`). | Full 301-fixture native sweep, installed host workflow, 2025.33230 matrix, and distribution remain open (GAP-002/GAP-003). |
| 2026-09-26 | `6c96151d72648f87e16e572428a98d1922b61136` | Recorded compiler-parity qualification at authority `2f47612c29045c1b91af94887a8ff20106e980ef`. GAP-001 remains open. | Linux compiler gates: lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP / 0 DIFF / 0 STAGE / 0 ERR; definitions 210/210 byte-identical; 118 unit tests. | Native render gates (`adjust`, `alphaMask`, `bitwise`), installed workflow, and platform qualification remain open. |
| 2026-09-24 | `66426bc41c2b85940322ae843ba04f41b7905ce4` | Created the requested six-section register and README link. No closures. | 76 Python unit tests passed. Native installation, activation, TOP rendering, saved projects, and accessibility were not exercised. | Full audit, current parity, installed workflows, platform qualification, and release readiness remain open. |

Native follow-up: `solid` was exact; `noise` differed by one byte maximum. Full current-authority qualification remains open.

Run ID: `20260924-remaining-gap-documents`.
[Operational evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents). Queue position and successful-audit timestamps remain unchanged by document creation.
