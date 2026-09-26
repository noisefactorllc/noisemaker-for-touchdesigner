# noisemaker-for-touchdesigner: completion gaps

Current compatibility matrix: [compatibility report](COMPATIBILITY.md).

## 1. Scope and source revisions

Daily review: 2026-09-25. Current inspected source: [`de416d7606e231bf6e38027316269640a1d7d096`](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/commit/de416d7606e231bf6e38027316269640a1d7d096).
Full rendered parity remains **unverified**. No release approval or new closure follows from this review.
Current upstream discovery: `bbdeb56c4b75cf33379766c3e87b0f5a18bcbba8`. Published Noisemaker authority: `1.0.179`, source `fca611fd8f91424661d4e531d39313d24ea21134`, 210 effect IDs.
The observations below retain their original source and authority identities. They do not qualify later updates.
Current served kit: `0.1.23`, source `de416d7606e231bf6e38027316269640a1d7d096`. [Retrieved inventory and hashes](/Users/alex/.codex/automations/noisemaker-port-completion-audit/review-20260925-053200/current-served-inventories.json). Artifact identity does not establish host qualification.

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
`6c96151d72648f87e16e572428a98d1922b61136`; the candidate commits that record
this run (`94dbb373`, `184e1b6`) and this provenance add only documentation,
so the harness files, corpus, and `td/` sources are byte-identical across
base and candidate.

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
`touchdesigner-parity` profile) still requires the activated macOS host and
remains the open condition for closing the gap.

Native render check at source `5ba51bb3` (check `753f86fe`,
profile `touchdesigner-parity` v1, engine TouchDesigner 2025.32820): failed on
runner `native-spare` with `command_failed` and no command, stderr, or artifact
captured; the runner did not deliver per-case results for any of the three
required cases. These historical ledger rows remain the last recorded per-case
native verdicts: `adjust` PASS (max_abs_diff 1.000003695487976, ssim
0.9999804496765137, tol 2.001/0.98), `alphaMask` PASS (max_abs_diff
1.000003695487976, ssim 0.9999801516532898), `bitwise` PASS (max_abs_diff 0.0,
ssim 1.0) — all against goldens rendered from the reference engine under the
declared tolerances. The gap stays open on the missing current-source native
run, not on any recorded per-case failure.

## 4. Known gaps

P1 means false completion or major correctness failure. P2 means coverage or integration uncertainty. P3 means documentation inconsistency.
These initial entries record missing qualification, not inferred implementation defects. No gap closes during this pass.

### GAP-001: current authority and parity qualification

- Status: open. Priority: P2. Category: verification.
- Affected scope: td/noisemaker/, td/make_bootstrap.py, parity/, README.md, STATUS.md
- Expected behavior: Each supported claim has reproducible evidence tied to the port and authority revisions.
- Observed behavior: Compiler parity at the resolved authority revision is qualified (see the 2026-09-26 compiler gates in section 3): lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP / 0 DIFF / 0 STAGE / 0 ERR, definitions 210/210 byte-identical, 118 unit tests passing. The native render half (`adjust`, `alphaMask`, `bitwise` under the declared `touchdesigner-parity` profile) and the complete host workflow remain unqualified. The current official build is 2025.33230, newer than README qualification 2025.32820. [Official releases](https://derivative.ca/UserGuide/Release_Notes).
- Evidence: [Historical claim](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/STATUS.md) and the bounded checks in section 3.
- Next action: Run the native render gates in an activated host (`adjust`, `alphaMask`, `bitwise` under the declared `touchdesigner-parity` profile); compiler gates are complete per section 3. Preserve chaotic, timed, skipped, and platform-specific cases.
- Dependencies: Resolve immutable authority inputs before comparison. Retain historical goldens and their provenance.
- Acceptance criteria: Record every applicable case, parameter choice, exclusion, error, and tolerance. Pass the declared contract without silently reducing coverage.
- Required checks: Existing compiler and parity entry points from the README, with raw results and exact source hashes.
- Last verification: 2026-09-24. Full behavior qualification remains unverified.

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
- Observed behavior: Distribution metadata was inspected. Complete artifact reproduction, installation, upgrades, and removal remain unverified.
- Evidence: [Package instructions](https://github.com/noisefactorllc/noisemaker-for-touchdesigner/blob/66426bc41c2b85940322ae843ba04f41b7905ce4/README.md), exact-source CI in section 2, and recorded distribution observations in section 1.
- Next action: Load the served kit in an isolated activated project. Check source paths, TOP output, saved-project relocation, notices, and removal.
- Dependencies: Complete GAP-002 for the release candidate. Distinguish source CI from downstream publication and host qualification.
- Acceptance criteria: Match artifact bytes to the inventory. Check licenses and dependencies. Pass installation, example execution, upgrade, and removal.
- Required checks: Inspect required CI jobs at the exact source SHA. Count skips and verify actual render legs, not green summaries.
- Last verification: 2026-09-24. No package or release approval follows from this register.

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
| 2026-09-26 | `6c96151d72648f87e16e572428a98d1922b61136` | Recorded compiler-parity qualification at authority `2f47612c29045c1b91af94887a8ff20106e980ef`. GAP-001 remains open. | Linux compiler gates: lex/parse/validate 326/326, graph 325 PASS / 1 rejection-parity SKIP / 0 DIFF / 0 STAGE / 0 ERR; definitions 210/210 byte-identical; 118 unit tests. | Native render gates (`adjust`, `alphaMask`, `bitwise`), installed workflow, and platform qualification remain open. |
| 2026-09-24 | `66426bc41c2b85940322ae843ba04f41b7905ce4` | Created the requested six-section register and README link. No closures. | 76 Python unit tests passed. Native installation, activation, TOP rendering, saved projects, and accessibility were not exercised. | Full audit, current parity, installed workflows, platform qualification, and release readiness remain open. |

Native follow-up: `solid` was exact; `noise` differed by one byte maximum. Full current-authority qualification remains open.

Run ID: `20260924-remaining-gap-documents`.
[Operational evidence](/Users/alex/.codex/automations/noisemaker-port-completion-audit/evidence-20260924-remaining-gap-documents). Queue position and successful-audit timestamps remain unchanged by document creation.
