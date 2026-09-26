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
| CLAIM-002 | [README workflow](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md) | Human usability: installation, first output, errors, and recovery | unverified | The complete installed workflow was not observed during this register pass. GAP-002. |
| CLAIM-003 | [Official ecosystem documentation](https://derivative.ca/UserGuide/System_Requirements) | Ecosystem fit and supported versions | partial | Source entry points were examined. Installed integration and the supported-version matrix remain open. GAP-002. |
| CLAIM-004 | [Distribution description](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md) | Release readiness | unverified | Metadata and CI alone do not qualify the actual installed artifact. GAP-003. |
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
saved-project relocation, upgrade, and removal. Artifact byte identity does
not establish host qualification, and no package or release approval follows
from this section.

## 4. Known gaps

P1 means false completion or major correctness failure. P2 means coverage or integration uncertainty. P3 means documentation inconsistency.
These initial entries record missing qualification, not inferred implementation defects. No gap closes during this pass.

### GAP-001: current authority and parity qualification

- Status: closed (2026-09-26). Priority: P2. Category: verification.
- Affected scope: td/noisemaker/, td/make_bootstrap.py, parity/, README.md, STATUS.md
- Expected behavior: Each supported claim has reproducible evidence tied to the port and authority revisions.
- Observed behavior: Both declared halves qualified. Compiler: lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP (`parity/corpus/B5oBsA.dsl`, both producers reject) / 0 DIFF / 0 STAGE / 0 ERR at authority `2f47612c29045c1b91af94887a8ff20106e980ef`, definitions 210/210 byte-identical, 118 unit tests — section 3, with exact commands, raw summary lines, and port/harness SHA-256 hashes. Native: `adjust`, `alphaMask`, `bitwise` passed on TouchDesigner 2025.32820 (darwin arm64, GPU) at source `3b543dde9f25d35f30d9b3ee15869255f9e14b8f`, thresholds max_abs_diff ≤ 2 / ssim ≥ 0.98, per-case reports and PNG artifacts retained — section 3. Parameters/exclusions on record: render size/time per `parity/run.sh` defaults (SIZE=256, TIME=0.25), declared profile thresholds, one rejection-parity skip preserved and not reclassified. Repair trail: four failed runner attempts (checks `753f86fe`, `3632a413`, `34156eb1`, `077a584e`) traced to run-driver install discovery, fixed in `b502e32`/`c727965`/`40114b8`/`699f6d2`/`3b543dd`; no gate, tolerance, or coverage was reduced.
- Evidence: Section 3 (compiler gates and native qualification at `3b543dd`), the machine verification receipt (verified_at 2026-09-26T05:37:35.380Z, review `01a1d4ac`), and the historical claim.
- Next action: none for GAP-001. Remaining qualification (full 301-fixture native sweep, installed host workflow, 2025.33230 build matrix, distribution) stays open under GAP-002/GAP-003 and this register.
- Dependencies: resolved — authority inputs pinned at `2f47612c2904`; historical goldens and provenance retained unchanged.
- Acceptance criteria: met — every applicable declared case, parameter choice, exclusion, error, and tolerance recorded; the declared contract passed without silently reducing coverage.
- Required checks: satisfied — compiler entry points (`parity/compiler/check_{lex,parse,validate,graph}.py`) and the declared native `touchdesigner-parity` cases, with raw results and exact source hashes in section 3.
- Last verification: 2026-09-26 (native at `3b543dd`; compiler at base `6c96151` with `td/noisemaker` + `parity/compiler` byte-identical through `3b543dd`).

### GAP-002: installed developer workflow qualification

- Status: open. Priority: P2. Category: usability.
- Affected scope: Public API, README examples, supported host versions, and lifecycle behavior.
- Expected behavior: Developers can install, produce useful output, integrate it, diagnose errors, recover, and remove the package.
- Observed behavior: This pass did not observe the complete installed workflow or supported-platform matrix.
- Evidence: [README](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md), [ecosystem reference](https://derivative.ca/UserGuide/System_Requirements), and section 3.
- Next action: Create an isolated Base COMP, execute the documented NMRenderer example, connect its TOP, resize, recover from invalid DSL, and reopen the project.
- Dependencies: Use an isolated consumer and the intended host version. Identify any required GPU, license, or external input before testing.
- Acceptance criteria: Retain the installed artifact hash, interaction steps, meaningful output, recovery result, and cleanup result.
- Required checks: Test minimum and current supported versions. Measure cancellation and file preservation where relevant. Record unavailable platforms explicitly.
- Last verification: 2026-09-24. Source inspection does not close this gap.

### GAP-003: distribution and release qualification

- Status: open. Priority: P2. Category: release.
- Affected scope: Distribution artifact, dependency metadata, notices, platform promises, and release evidence.
- Expected behavior: The delivered artifact contains required files and supports its documented installation and first useful result.
- Observed behavior: Distribution metadata was inspected. The served artifact (`0.1.26`, source `6c96151d72648f87e16e572428a98d1922b61136`) was byte-matched file-by-file to its served inventory (852/852 SHA-256, zero mismatches or skips), reproduced from the source tree, and its license notices and dependency surface were checked — section 3, 2026-09-26. Installation, example execution, saved-project relocation, upgrade, and removal remain unverified.
- Evidence: [Package instructions](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md), [served inventory](https://kits.noisedeck.app/touchdesigner/0/kit.json), exact-source CI in section 2/3, and recorded distribution observations in section 1.
- Next action: Load the served kit in an isolated activated project. Check source paths, TOP output, saved-project relocation, notices, and removal. Blocked by the same activated-host requirement as GAP-002.
- Dependencies: Complete GAP-002 for the release candidate. Distinguish source CI from downstream publication and host qualification.
- Acceptance criteria: Match artifact bytes to the inventory (met for artifact `0.1.26` — section 3). Check licenses and dependencies (met — two notices, stdlib + `td` + bundled numpy). Pass installation, example execution, upgrade, and removal (still open).
- Required checks: Inspect required CI jobs at the exact source SHA (done — Export kit 36213953378 is dispatch-only, no skips, no render legs). Count skips and verify actual render legs, not green summaries (render legs were never claimed by that workflow; artifact bytes verified directly).
- Last verification: 2026-09-26 (artifact byte/license/dependency half only). No package or release approval follows from this register.

## 5. Ordered next actions

Current first action: Resolve immutable current authority inputs, then use the existing build_parity_toe.py and native TouchDesigner capture entry points for every tracked fixture. Require no missing or skipped cases. Next install the delivered component in a fresh project, check TOP output, parameters, cook failure and recovery, and record the unsupported host/version matrix.
Subsequent historical actions remain dependent on that evidence. No implementation is authorized by this audit.

1. Resolve authority revisions and retained evidence for GAP-001. Preserve all previous comparisons and exclusions.
2. Run the bounded installed workflow for GAP-002. Record output, errors, recovery, host version, and resource cleanup.
3. Execute the declared parity cases for GAP-001. Keep compilation, structure, rendered pixels, and platform qualification separate.
4. Qualify the actual distribution for GAP-003 after the workflow passes. Verify exact-source CI and required artifact contents.
5. Update this register with measured results. Close entries only when their acceptance criteria pass.

Implementation changes belong to the separate implementation job. This register does not authorize further effect ports or checkpoint advancement.

## 6. Pass history

2026-09-25 daily review at `de416d7606e231bf6e38027316269640a1d7d096`: source freshness and bounded evidence reviewed. Open qualification limits retained. [Retained review evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-native-comparisons.json). No new closure claimed.

| Date | Source SHA | Changes | Tested scope | Remaining limits |
|---|---|---|---|---|
| 2026-09-26 | `dbd98d8fe4d4d08c675cacefbc6a91c4941c770c` | GAP-003 artifact half recorded: served kit `0.1.26` (source `6c96151d`) byte-matched to its served inventory 852/852, reproduced from source, licenses and dependencies checked; GAP-003 stays open. | 852/852 per-file SHA-256 matches against kits.noisedeck.app; 549 engine/license/readme files byte-identical to `git show 6c96151`, 301 shaders byte-identical, compat.json ids exact (207, media/scope/spectrum excluded); Export kit 36213953378 (dispatch-only, no skips). | Installed host legs (load in activated project, TOP output, relocation, upgrade, removal) remain open and blocked by GAP-002; no release approval. |
| 2026-09-26 | `3b543dde9f25d35f30d9b3ee15869255f9e14b8f` | GAP-001 closed: native `touchdesigner-parity` cases passed at the published candidate; run-driver robustness fixes published along the way. | Native: `adjust`/`alphaMask`/`bitwise` passed on TD 2025.32820 darwin/arm64 at thresholds 2/0.98 (machine verification receipt). Compiler gates unchanged (td/noisemaker + parity/compiler byte-identical to base `6c96151`). | Full 301-fixture native sweep, installed host workflow, 2025.33230 matrix, and distribution remain open (GAP-002/GAP-003). |
| 2026-09-26 | `6c96151d72648f87e16e572428a98d1922b61136` | Recorded compiler-parity qualification at authority `2f47612c29045c1b91af94887a8ff20106e980ef`. GAP-001 remains open. | Linux compiler gates: lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP / 0 DIFF / 0 STAGE / 0 ERR; definitions 210/210 byte-identical; 118 unit tests. | Native render gates (`adjust`, `alphaMask`, `bitwise`), installed workflow, and platform qualification remain open. |
| 2026-09-24 | `66426bc41c2b85940322ae843ba04f41b7905ce4` | Created the requested six-section register and README link. No closures. | 76 Python unit tests passed. Native installation, activation, TOP rendering, saved projects, and accessibility were not exercised. | Full audit, current parity, installed workflows, platform qualification, and release readiness remain open. |

Native follow-up: `solid` was exact; `noise` differed by one byte maximum. Full current-authority qualification remains open.

Run ID: `20260924-remaining-gap-documents`.
[Operational evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents). Queue position and successful-audit timestamps remain unchanged by document creation.
