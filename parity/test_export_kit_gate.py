"""Tests for scripts/export-kit-gate.

The gate decides from `git ls-remote --tags` output whether a commit already
carries a kit-* tag. These tests drive the script through a fake `git` on
PATH, so no network and no real tags are involved. Exit codes: 0 proceed,
1 already released, 2 could not check.
"""

import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "export-kit-gate"
RESERVE = ROOT / "scripts" / "export-kit-reserve"

SHA = "a" * 40
OTHER = "b" * 40
TAG_OBJECT = "c" * 40
URL = "https://git.example.test/noisefactorllc/noisemaker-for-touchdesigner.git"

LIGHTWEIGHT_AT_SHA = [f"{SHA}\trefs/tags/kit-touchdesigner-v0.1.37"]
# An annotated tag: the direct entry is the tag object, the peeled entry
# carries the commit.
ANNOTATED_AT_SHA = [
    f"{TAG_OBJECT}\trefs/tags/kit-touchdesigner-v0.1.38",
    f"{SHA}\trefs/tags/kit-touchdesigner-v0.1.38^{{}}",
]
ANNOTATED_AT_OTHER = [
    f"{TAG_OBJECT}\trefs/tags/kit-touchdesigner-v0.1.38",
    f"{OTHER}\trefs/tags/kit-touchdesigner-v0.1.38^{{}}",
]
LIGHTWEIGHT_AT_OTHER = [f"{OTHER}\trefs/tags/kit-touchdesigner-v0.1.37"]
NON_KIT_TAG_AT_SHA = [f"{SHA}\trefs/tags/v1.2.3"]


def make_bindir(with_git=True):
    """A PATH-front directory whose `git` is fake; without git, only the
    external commands the gate needs before its git check (bash via env,
    dirname, tr) are present."""
    bindir = tempfile.mkdtemp()
    bindir = pathlib.Path(bindir) / "bin"
    bindir.mkdir(parents=True)
    for tool in ("bash", "dirname", "tr"):
        target = subprocess.run(
            ["which", tool], capture_output=True, text=True, check=True
        ).stdout.strip()
        (bindir / tool).write_text(f"#!/bin/sh\nexec {shlex.quote(target)} \"$@\"\n")
        (bindir / tool).chmod(0o755)
    if with_git:
        fake_git = bindir / "git"
        fake_git.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "remote" ]; then\n'
            '  printf "%s\\n" "$FAKE_ORIGIN_URL"\n'
            "  exit 0\n"
            "fi\n"
            'printf "%s" "$FAKE_LS_REMOTE"\n'
            'exit "$FAKE_GIT_RC"\n'
        )
        fake_git.chmod(0o755)
    return bindir


def run_gate(tags, sha=SHA, git_rc=0, url=URL, with_git=True):
    bindir = make_bindir(with_git)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_LS_REMOTE"] = "".join(line + "\n" for line in tags)
    env["FAKE_GIT_RC"] = str(git_rc)
    env["FAKE_ORIGIN_URL"] = URL
    argv = [str(GATE)] + ([sha] if sha is not None else []) + ([url] if url is not None else [])
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    finally:
        shutil.rmtree(bindir.parent, ignore_errors=True)


class ExportKitGateTests(unittest.TestCase):
    def test_script_is_executable_with_shebang(self):
        self.assertTrue(os.access(GATE, os.X_OK), "scripts/export-kit-gate must be executable")
        self.assertTrue(GATE.read_text().startswith("#!"))

    def test_no_tags_proceeds(self):
        self.assertEqual(run_gate([]).returncode, 0)

    def test_lightweight_tag_at_sha_is_released(self):
        self.assertEqual(run_gate(LIGHTWEIGHT_AT_SHA).returncode, 1)

    def test_annotated_tag_at_sha_is_released(self):
        self.assertEqual(run_gate(ANNOTATED_AT_SHA).returncode, 1)

    def test_annotated_tag_at_other_commit_proceeds(self):
        self.assertEqual(run_gate(ANNOTATED_AT_OTHER).returncode, 0)

    def test_lightweight_tag_at_other_commit_proceeds(self):
        self.assertEqual(run_gate(LIGHTWEIGHT_AT_OTHER).returncode, 0)

    def test_non_kit_tag_at_sha_proceeds(self):
        self.assertEqual(run_gate(NON_KIT_TAG_AT_SHA).returncode, 0)

    def test_uppercase_sha_is_normalized(self):
        self.assertEqual(run_gate(LIGHTWEIGHT_AT_SHA, sha=SHA.upper()).returncode, 1)

    def test_short_sha_is_refused(self):
        self.assertEqual(run_gate([], sha=SHA[:12]).returncode, 2)

    def test_explicit_empty_sha_is_refused(self):
        result = run_gate(LIGHTWEIGHT_AT_SHA, sha="")
        self.assertEqual(result.returncode, 2)

    def test_origin_fallback_supplies_the_url(self):
        # The fake git answers `remote get-url origin`; reaching exit 1 (and
        # not the no-origin exit 2) proves the fallback URL was used.
        self.assertEqual(run_gate(LIGHTWEIGHT_AT_SHA, url=None).returncode, 1)

    def test_missing_git_fails_closed(self):
        result = run_gate(LIGHTWEIGHT_AT_SHA, with_git=False)
        self.assertEqual(result.returncode, 2)

    def test_ls_remote_failure_fails_closed(self):
        self.assertEqual(run_gate(LIGHTWEIGHT_AT_SHA, git_rc=128).returncode, 2)


class ExportKitReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name)
        self.state = self.directory / "reservation"
        self.calls = self.directory / "calls"
        fake_gh = self.directory / "gh"
        fake_gh.write_text("""#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_CALLS"
case "$*" in
  *'-X POST'*)
    if [ "$FAKE_POST_MODE" = fail ]; then exit 1; fi
    if [ -f "$FAKE_STATE" ]; then exit 1; fi
    printf '%s' "$FAKE_SHA" > "$FAKE_STATE"
    if [ "$FAKE_POST_MODE" = write_then_fail ]; then exit 1; fi
    printf '%s\\n' "$FAKE_SHA"
    ;;
  *)
    if [ -f "$FAKE_STATE" ]; then cat "$FAKE_STATE"; else exit 1; fi
    ;;
esac
""")
        fake_gh.chmod(0o755)

    def run_reserve(self, *, sha=SHA, repo="noisefactorllc/noisemaker-for-touchdesigner",
                    post_mode="normal"):
        env = {**os.environ,
               "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
               "GITHUB_SHA": sha, "GITHUB_REPOSITORY": repo,
               "FAKE_SHA": sha, "FAKE_STATE": str(self.state),
               "FAKE_CALLS": str(self.calls), "FAKE_POST_MODE": post_mode}
        return subprocess.run([str(RESERVE)], capture_output=True, text=True,
                              env=env)

    def test_new_sha_is_reserved_once(self):
        result = self.run_reserve()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state.read_text(), SHA)
        self.assertIn(f"refs/tags/export-kit-pending-{SHA}", self.calls.read_text())
        self.assertEqual(self.run_reserve().returncode, 1)

    def test_ambiguous_create_with_existing_exact_ref_skips_dispatch(self):
        result = self.run_reserve(post_mode="write_then_fail")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_create_failure_without_ref_fails_closed(self):
        result = self.run_reserve(post_mode="fail")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_existing_ref_at_wrong_sha_fails_closed(self):
        self.state.write_text(OTHER)
        result = self.run_reserve()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_invalid_source_context_never_calls_api(self):
        for sha, repo in (("abc", "noisefactorllc/noisemaker-for-touchdesigner"),
                          (SHA, "other/repo")):
            with self.subTest(sha=sha, repo=repo):
                result = self.run_reserve(sha=sha, repo=repo)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
