#!/usr/bin/env bash
# parity/pylib.sh — choose a python interpreter that has numpy + pillow.
#
# Every parity script needs numpy + pillow (compare.py, write-ledger.py, stage_coverage.py).
# A venv is only trustworthy when its interpreter actually runs AND imports them, and the
# ambient python3 is only trustworthy when it does the same. A PATH that lost a toolchain
# (an Xcode or Homebrew upgrade, a cleaned toolchain dir) used to leave every python call
# dead with no output, so the search spans common install locations, not just PATH.
#
# Usage:
#   if ! PY="$(bash "$HERE/pylib.sh" "$REPO")"; then exit 2; fi
#
# The chosen interpreter is printed on stdout; diagnostics go to stderr.
set -u
repo="${1:?usage: pylib.sh REPO}"
ok() { "$1" -c 'import numpy, PIL' >/dev/null 2>&1; }
CANDS=""
add() {
  case " $CANDS " in *" $1 "*) return 0 ;; esac
  [ -x "$1" ] && CANDS="$CANDS $1"
  return 0
}
add "$repo/parity/.venv/bin/python"
while IFS= read -r p; do add "$p"; done < <(type -a -p python3 2>/dev/null)
for c in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 \
         "${HOME:-/root}/homebrew/bin/python3"; do add "$c"; done
# A redirected HOME (a sandboxed runner, a service account) hides the real
# Homebrew prefix, so also probe the invoking user's actual home directory.
real_home="$(eval echo "~$(id -un 2>/dev/null)" 2>/dev/null)" || real_home=""
if [ -n "$real_home" ] && [ "$real_home" != "$HOME" ]; then
  add "$real_home/homebrew/bin/python3"
fi
for c in $CANDS; do
  if ok "$c"; then printf '%s\n' "$c"; exit 0; fi
done
# Nothing on the search list imports numpy + pillow. Rebuild the venv from each
# candidate that can create one with pip, and keep the first that ends up working.
for c in $CANDS; do
  "$c" -m venv "$repo/parity/.venv" >/dev/null 2>&1 || continue
  vp="$repo/parity/.venv/bin/python"
  if "$vp" -m pip install --quiet -r "$repo/requirements.txt" >/dev/null 2>&1 && ok "$vp"; then
    printf '%s\n' "$vp"; exit 0
  fi
  rm -rf "$repo/parity/.venv"
done
echo "no python interpreter with numpy and pillow found (searched:$CANDS)" >&2
exit 2
