#!/usr/bin/env bash
# Build and run all semver-dredd Docker Compose smoke tests.
#
# Usage:
#   bash scripts/smoke.sh             # run every service
#   bash scripts/smoke.sh python go   # run a subset
#
# Each service runs in isolation with --abort-on-container-exit and
# --exit-code-from, results are aggregated, and containers are cleaned up.
# Exits non-zero when any smoke test fails.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.smoke.yml"
COMPOSE=(docker compose -f "$COMPOSE_FILE")

SERVICES=("$@")
if [ ${#SERVICES[@]} -eq 0 ]; then
    SERVICES=(python go java unit)
fi

cd "$REPO_ROOT"

echo "==> Building smoke images: ${SERVICES[*]}"
if ! "${COMPOSE[@]}" build "${SERVICES[@]}"; then
    echo "==> Image build failed" >&2
    exit 1
fi

declare -A RESULTS
FAILED=0

for svc in "${SERVICES[@]}"; do
    echo ""
    echo "==> Running smoke test: $svc"
    if "${COMPOSE[@]}" up \
        --abort-on-container-exit \
        --exit-code-from "$svc" \
        "$svc"; then
        RESULTS[$svc]="PASS"
    else
        RESULTS[$svc]="FAIL"
        FAILED=1
    fi
    # Idempotent cleanup between runs
    "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1
done

echo ""
echo "==> Smoke test summary"
for svc in "${SERVICES[@]}"; do
    echo "    $svc: ${RESULTS[$svc]}"
done

if [ "$FAILED" -ne 0 ]; then
    echo "==> SMOKE TESTS FAILED" >&2
    exit 1
fi
echo "==> ALL SMOKE TESTS PASSED"
