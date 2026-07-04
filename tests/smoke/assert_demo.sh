#!/usr/bin/env bash
# Smoke assertions for semver-dredd language demos.
#
# Usage: assert_demo.sh <python|go|java>
#
# 1. Runs the language demo end-to-end (exercises init/status/bake).
# 2. Asserts that geometry1 -> geometry2 is classified as MINOR.
# 3. Asserts that geometry2 -> geometry1 (removed API) is BREAKING.
#
# Exits 0 only when every expectation holds.

set -uo pipefail

LANG_NAME="${1:?usage: assert_demo.sh <python|go|java>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if command -v poetry >/dev/null 2>&1; then
    POETRY_PY="$(cd "$PROJECT_ROOT" && poetry env info --executable)"

    run_sdd() {
        PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$POETRY_PY" -m cli "$@"
    }
elif command -v semver-dredd >/dev/null 2>&1; then
    run_sdd() {
        semver-dredd "$@"
    }
elif command -v python3 >/dev/null 2>&1; then
    run_sdd() {
        PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m cli "$@"
    }
else
    run_sdd() {
        PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python -m cli "$@"
    }
fi

case "$LANG_NAME" in
    python)
        PLUGIN="python"
        OLD="example.py.pygeometry1"
        NEW="example.py.pygeometry2"
        ;;
    go)
        PLUGIN="go"
        OLD="$PROJECT_ROOT/example/go/gogeometry1"
        NEW="$PROJECT_ROOT/example/go/gogeometry2"
        ;;
    java)
        PLUGIN="java"
        OLD="$PROJECT_ROOT/example/java/javageometry1"
        NEW="$PROJECT_ROOT/example/java/javageometry2"
        ;;
    *)
        echo "Unknown language: $LANG_NAME (expected python, go, or java)" >&2
        exit 2
        ;;
esac

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

FAILURES=0

fail() {
    echo "ASSERTION FAILED: $1" >&2
    FAILURES=$((FAILURES + 1))
}

echo "=== [$LANG_NAME] Step 1/3: run demo script ==="
if ! bash "$PROJECT_ROOT/example/demo_${LANG_NAME}.sh"; then
    fail "demo_${LANG_NAME}.sh exited non-zero"
fi

echo "=== [$LANG_NAME] Step 2/3: assert geometry1 -> geometry2 is MINOR ==="
MINOR_OUT="$(run_sdd compare "$OLD" "$NEW" --plugin "$PLUGIN" --no-color 2>&1)"
MINOR_CODE=$?
echo "$MINOR_OUT"
if [ "$MINOR_CODE" -ne 0 ]; then
    fail "compare (minor direction) exited $MINOR_CODE, expected 0"
fi
if ! echo "$MINOR_OUT" | grep -q "Change type: MINOR"; then
    fail "expected 'Change type: MINOR' in compare output"
fi

echo "=== [$LANG_NAME] Step 3/3: assert geometry2 -> geometry1 is BREAKING ==="
BREAKING_OUT="$(run_sdd compare "$NEW" "$OLD" --plugin "$PLUGIN" --no-color 2>&1)"
BREAKING_CODE=$?
echo "$BREAKING_OUT"
if [ "$BREAKING_CODE" -ne 10 ]; then
    fail "compare (breaking direction) exited $BREAKING_CODE, expected 10"
fi
if ! echo "$BREAKING_OUT" | grep -q "Change type: BREAKING"; then
    fail "expected 'Change type: BREAKING' in compare output"
fi

if [ "$LANG_NAME" = "python" ]; then
    echo "=== [python] Step 4/4: run config showcase smoke assertions ==="
    if ! bash "$PROJECT_ROOT/tests/smoke/assert_config_showcase.sh"; then
        fail "assert_config_showcase.sh exited non-zero"
    fi
fi

if [ "$FAILURES" -ne 0 ]; then
    echo "=== [$LANG_NAME] smoke FAILED: $FAILURES assertion(s) ===" >&2
    exit 1
fi

echo "=== [$LANG_NAME] smoke OK ==="
