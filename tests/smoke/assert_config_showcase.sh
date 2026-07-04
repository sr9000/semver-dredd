#!/usr/bin/env bash
# Smoke assertions for the comprehensive config showcase.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

OUT="$(bash "$PROJECT_ROOT/example/demo_config_showcase.sh" 2>&1)"
CODE=$?
echo "$OUT"

if [ "$CODE" -ne 0 ]; then
    echo "ASSERTION FAILED: demo_config_showcase.sh exited $CODE" >&2
    exit 1
fi

assert_contains() {
    local needle="$1"
    if ! grep -Fq "$needle" <<<"$OUT"; then
        echo "ASSERTION FAILED: expected showcase output to contain: $needle" >&2
        exit 1
    fi
}

assert_contains "SHOWCASE init_version=1.0.0"
assert_contains "SHOWCASE dotenv_suggested=1.1.0"
assert_contains "SHOWCASE env_suggested=1.0.1"
assert_contains "SHOWCASE scope_default_has_primary=yes"
assert_contains "SHOWCASE scope_append_has_extra=yes"
assert_contains "SHOWCASE scope_override_only_extra=yes"
assert_contains "SHOWCASE plugin_override_exit=1"
assert_contains "SHOWCASE bump_minor=1.1.0"
assert_contains "SHOWCASE patch_next=8"
assert_contains "SHOWCASE baked_version=1.1.0"

echo "=== [config] smoke OK ==="
