"""The 2.x branch's workflow contract.

The test jobs run on every push to ``2.x``, and every release, notice or
dispatch job runs only for ``main``. A job runs only for ``main`` when its
condition names ``refs/heads/main`` or a ``workflow_run`` head branch of
``main``, or when every trigger of its workflow is a ``schedule`` (which runs
only from the default branch) or a ``push`` or ``workflow_run`` filtered to
``main`` alone.

A workflow that holds both kinds of job is checked job by job: its test jobs
admit ``refs/heads/2.x``, and its release jobs run only for ``main`` by their
condition. The workflows are read as text, because the engine-free suite has
no YAML parser.
"""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

# Workflows whose jobs are test jobs, and must run on every 2.x push.
TEST_WORKFLOWS = ["tests.yml"]
# Workflows that hold both kinds of job: (test jobs, release jobs). The test
# jobs admit refs/heads/2.x; the release, notice or dispatch jobs run only for
# main by their condition.
MIXED_WORKFLOWS = {
    "export-kit.yml": (["parity"], ["dispatch"]),
}

MAIN_ONLY_CONDITIONS = (
    re.compile(r"github\.ref\s*==\s*'refs/heads/main'"),
    re.compile(r"github\.event\.workflow_run\.head_branch\s*==\s*'main'"),
)


def _lines(name):
    lines = []
    for raw in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines():
        raw = re.sub(r"\s+#[^'\"]*$", "", raw)
        if raw.strip() and not raw.lstrip().startswith("#"):
            lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    return lines


def _children(lines, start, indent):
    """Return (key, value, index) for each key one level below lines[start]."""
    found = []
    child = None
    for index in range(start + 1, len(lines)):
        depth, text = lines[index]
        if depth <= indent:
            break
        if child is None:
            child = depth
        if depth == child and not text.startswith("- "):
            key, _, value = text.partition(":")
            found.append((key.strip().strip("'\""), value.strip(), index))
    return found


def _block(lines, index):
    """The scalar at lines[index]: inline, or a folded or literal block."""
    depth, text = lines[index]
    value = text.partition(":")[2].strip()
    if value[:1] not in (">", "|"):
        return value
    parts = []
    for later in range(index + 1, len(lines)):
        if lines[later][0] <= depth:
            break
        parts.append(lines[later][1])
    return " ".join(parts)


def _top(lines, key):
    for index, (depth, text) in enumerate(lines):
        if depth == 0 and text.partition(":")[0].strip().strip("'\"") == key:
            return index
    raise AssertionError(f"no top-level {key!r}")


def triggers(name):
    """Map each trigger to its branch filter (None when it has none)."""
    lines = _lines(name)
    start = _top(lines, "on")
    result = {}
    for event, value, index in _children(lines, start, 0):
        branches = None
        for key, inline, child in _children(lines, index, lines[index][0]):
            if key != "branches":
                continue
            if inline.startswith("["):
                branches = [b.strip().strip("'\"") for b in inline.strip("[]").split(",") if b.strip()]
            else:
                branches = []
                for later in range(child + 1, len(lines)):
                    depth, text = lines[later]
                    if depth <= lines[child][0] and not text.startswith("- "):
                        break
                    if text.startswith("- "):
                        branches.append(text[2:].strip().strip("'\""))
        result[event] = branches
    return result


def jobs(name):
    """Map each job to its condition ('' when it has none)."""
    lines = _lines(name)
    start = _top(lines, "jobs")
    result = {}
    for job, _, index in _children(lines, start, 0):
        condition = ""
        for key, _, child in _children(lines, index, lines[index][0]):
            if key == "if":
                condition = _block(lines, child)
        result[job] = condition
    return result


def condition_runs_only_for_main(condition):
    # A condition with an alternative can hold outside main.
    return "||" not in condition and any(pattern.search(condition) for pattern in MAIN_ONLY_CONDITIONS)


def runs_only_for_main(name, condition):
    # A condition with an alternative can hold outside main, so only the
    # triggers can make such a job main-only.
    if condition_runs_only_for_main(condition):
        return True
    for event, branches in triggers(name).items():
        if event == "schedule":
            continue
        if event in ("push", "workflow_run") and branches == ["main"]:
            continue
        return False
    return True


def admits_2x(condition):
    return "refs/heads/main" not in condition or "refs/heads/2.x" in condition


class WorkflowContractTests(unittest.TestCase):

    def test_the_test_jobs_run_on_every_2x_push(self):
        for name in TEST_WORKFLOWS:
            with self.subTest(workflow=name):
                found = triggers(name)
                # A push trigger with no branch filter runs on every branch.
                self.assertTrue("push" in found and (found["push"] is None or "2.x" in found["push"]),
                                f"{name} does not run on a 2.x push")
                for job, condition in jobs(name).items():
                    self.assertTrue(admits_2x(condition), f"{name} job {job} runs only for main: {condition}")

    def test_every_job_of_a_mixed_workflow_is_a_test_job_or_a_release_job(self):
        for name, (test_jobs, release_jobs) in MIXED_WORKFLOWS.items():
            with self.subTest(workflow=name):
                self.assertEqual(sorted(jobs(name)), sorted(test_jobs + release_jobs),
                                 f"{name} has a job that is neither a listed test job nor a listed release job")

    def test_the_test_jobs_of_a_mixed_workflow_admit_2x(self):
        for name, (test_jobs, _) in MIXED_WORKFLOWS.items():
            found = jobs(name)
            for job in test_jobs:
                with self.subTest(workflow=name, job=job):
                    self.assertIn(job, found, f"{name} has no job {job}")
                    self.assertTrue(admits_2x(found[job]), f"{name} job {job} runs only for main: {found[job]}")

    def test_every_release_notice_or_dispatch_job_runs_only_for_main(self):
        for name, (_, release_jobs) in MIXED_WORKFLOWS.items():
            found = jobs(name)
            for job in release_jobs:
                with self.subTest(workflow=name, job=job):
                    self.assertIn(job, found, f"{name} has no job {job}")
                    self.assertTrue(condition_runs_only_for_main(found[job]),
                                    f"{name} job {job} can run outside main: {found[job]}")
                    self.assertTrue(runs_only_for_main(name, found[job]), f"{name} job {job} can run outside main")

    def test_the_contract_reader_finds_every_workflow_trigger_and_job(self):
        for name in TEST_WORKFLOWS + list(MIXED_WORKFLOWS):
            with self.subTest(workflow=name):
                self.assertTrue(triggers(name), f"no triggers read from {name}")
                self.assertTrue(jobs(name), f"no jobs read from {name}")
        self.assertIn("parity", jobs("export-kit.yml"))
        self.assertIn("dispatch", jobs("export-kit.yml"))
        self.assertIn("push", triggers("tests.yml"))
        self.assertIn("schedule", triggers("export-kit.yml"))


if __name__ == "__main__":
    unittest.main()
