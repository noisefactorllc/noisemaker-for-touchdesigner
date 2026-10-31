"""Map changed-file paths (NM_CHANGED_FILES) to the engine-free checks that exercise them.

Shared by scripts/test (the engine-free test entrypoint) and its unit tests, so the
selection logic that drives the changed-paths filter is itself covered by the suite
it filters. The module knows about two kinds of selection:

- find_relevant_test_modules: which parity/test_*.py modules to run for a set of
  changed paths. A changed shader program (td/noisemaker/shaders/**/*.frag or
  .vert) routes to the shader-contract suite, because no other module reads the
  converted programs.
- select_gate_programs: which DSL programs the compiler parity gates run for a
  set of changed paths.
"""
import glob
import os

SHADER_ROOT = 'td/noisemaker/shaders/'
SHADER_SUFFIXES = ('.frag', '.vert')
SHADER_CONTRACT_MODULE = 'test_shader_contract'
CORPUS_GLOBS = ('parity/corpus/*.dsl', 'parity/programs/*.dsl')


def find_relevant_test_modules(changed_files):
    """Map changed file paths to the test modules that exercise them.

    A module is relevant when:
      - the changed file IS that test module;
      - the changed file is a converted shader program (the shader-contract
        suite exercises every converted program's emitted contract);
      - its source names the changed full path, or its basename when the
        basename carries an extension (e.g. `attractor.json`, `agent.frag`);
      - its source names one of the changed file's two closest ancestor
        directories that contain a slash (e.g. `td/noisemaker/effects` — how a
        whole-tree definition validator exercises any *.json under it);
      - its source invokes the file's stem at a call site (`.` + stem + `(`),
        which is how a DSL/registry-driven test exercises an effect
        definition. A bare stem word without a call site (the word `text`,
        `media`) is a prose or variable-name collision and does not count.
    Extensionless basenames (e.g. `test` from `scripts/test`) match only as a
    full path, never as a bare word, and bare single-component roots (e.g.
    `td`) never match.
    """
    test_files = sorted(glob.glob('parity/test_*.py'))
    changed_modules = {os.path.splitext(os.path.basename(c))[0] for c in changed_files}
    relevant = set()
    for changed in changed_files:
        if changed.startswith(SHADER_ROOT) and changed.endswith(SHADER_SUFFIXES):
            relevant.add(SHADER_CONTRACT_MODULE)
    for test_file in test_files:
        module = os.path.splitext(os.path.basename(test_file))[0]
        if module in changed_modules:
            relevant.add(module)
            continue
        with open(test_file, 'r', encoding='utf-8') as fh:
            content = fh.read()
        for changed in changed_files:
            base = os.path.basename(changed)
            tokens = [changed]
            if '.' in base:
                tokens.append(base)
                tokens.append('.' + os.path.splitext(base)[0] + '(')
            parent = os.path.dirname(changed)
            if '/' in parent:
                tokens.append(parent)
                grandparent = os.path.dirname(parent)
                if '/' in grandparent:
                    tokens.append(grandparent)
            if any(t in content for t in tokens):
                relevant.add(module)
                break
    return sorted(relevant) if relevant else None


def select_gate_programs(changed_files):
    """Pick the DSL programs the compiler parity gates run for the changed paths.

    With no changed paths, or when a changed path is shared gate machinery (the
    compiler port, a gate script, a reference dump tool, or the gate runner
    itself), every corpus and programs DSL runs. Otherwise a changed .dsl
    program runs on itself and a changed effect definition (td/noisemaker/
    effects/*.json) selects the programs that call that effect. Other changed
    files (shaders, tests) exercise no DSL program, so nothing is selected and
    the gates are skipped.
    """
    corpus = []
    for pattern in CORPUS_GLOBS:
        corpus.extend(sorted(glob.glob(pattern)))
    if not changed_files or any(c.startswith('td/noisemaker/compiler/')
                                or c.startswith('parity/compiler/')
                                or c.startswith('tools/dump-')
                                or c == 'scripts/test'
                                for c in changed_files):
        return corpus
    selected = set()
    for c in changed_files:
        if c in corpus:
            selected.add(c)  # a changed .dsl program runs on itself
        if c.startswith('td/noisemaker/effects/') and c.endswith('.json'):
            stem = os.path.splitext(os.path.basename(c))[0]
            for f in corpus:
                with open(f, encoding='utf-8') as fh:
                    src = fh.read()
                if ('.' + stem + '(') in src or (stem + '(') in src:
                    selected.add(f)
    return sorted(selected)
