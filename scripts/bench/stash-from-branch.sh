#!/usr/bin/env bash
# stash-from-branch.sh — capture everything a model changed on its run branch
# as a single NAMED STASH on top of the benchmark baseline.
#
# Works with the squashed-baseline layout: every bench branch is exactly
#   <root commit> ── <single baseline commit (scaffolding + seeded defects)>
# and each model works on a copy of that branch, committing freely.
# The model's whole contribution is therefore `git diff <baseline> <model-branch>`.
#
# Usage:
#   bash scripts/bench/stash-from-branch.sh <baseline-branch> <model-branch> <stash-name>
# Example:
#   bash scripts/bench/stash-from-branch.sh bench/easy-v1 bench/easy-v1-kimi kimi-k2.6
#
# Result: `git stash list` gains an entry "On bench/easy-v1: <stash-name>".
# A grader can later inspect it with:
#   git checkout <baseline-branch>
#   git stash apply "stash^{/<stash-name>}"
# and reset between models with:
#   git checkout -- . && git clean -fd

set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <baseline-branch> <model-branch> <stash-name>" >&2
    exit 2
fi

BASE="$1"
BRANCH="$2"
NAME="$3"

# Refuse to run on a dirty tree — we are about to checkout and apply patches.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: working tree is dirty; commit or stash your own changes first." >&2
    exit 1
fi

PATCH="$(mktemp "/tmp/bench-${NAME//\//_}.XXXX.patch")"
trap 'rm -f "$PATCH"' EXIT

git diff --binary "$BASE" "$BRANCH" > "$PATCH"

if [ ! -s "$PATCH" ]; then
    echo "WARNING: no difference between $BASE and $BRANCH — nothing to stash." >&2
    exit 1
fi

git checkout --quiet "$BASE"
git apply --whitespace=nowarn "$PATCH"
git stash push --include-untracked -m "$NAME" >/dev/null

echo "OK: stash '$NAME' created (diff $BASE..$BRANCH, $(git stash list | head -1))"
