#!/bin/bash
# Demo script for Python language support
# This script demonstrates the semver-dredd workflow for Python modules

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEMO_DIR="$PROJECT_ROOT/example/py"
WORK_DIR=$(mktemp -d)

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

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    semver-dredd Python Demo${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "Working directory: ${YELLOW}$WORK_DIR${NC}"
echo ""

cd "$WORK_DIR"

# Ensure we can import from the project
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

echo -e "${GREEN}Step 1: Initialize project with pygeometry1${NC}"
echo -e "Command: ${YELLOW}semver-dredd init example.py.pygeometry1 --plugin python --version 1.0.0${NC}"
echo ""
run_sdd init example.py.pygeometry1 --plugin python --version 1.0.0 --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
echo ""

echo -e "${GREEN}Step 2: Show baked API snapshot${NC}"
echo -e "File: ${YELLOW}baked.yaml${NC}"
echo "----------------------------------------"
head -50 "$WORK_DIR/baked.yaml"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 3: Check status (no changes)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status example.py.pygeometry1 --details${NC}"
echo ""
run_sdd status example.py.pygeometry1 --details --baked "$WORK_DIR/baked.yaml" --current-file "$WORK_DIR/current.yaml" --version-file "$WORK_DIR/VERSION" || true
echo ""

echo -e "${GREEN}Step 4: Compare pygeometry1 vs pygeometry2 (minor changes)${NC}"
echo -e "Command: ${YELLOW}semver-dredd compare example.py.pygeometry1 example.py.pygeometry2 --details --current 1.0.0${NC}"
echo ""
echo -e "${YELLOW}pygeometry2 adds:${NC}"
echo -e "  - Point.z field (3D coordinate)"
echo -e "  - Point.translate() method"
echo -e "  - volume() function"
echo ""
run_sdd compare example.py.pygeometry1 example.py.pygeometry2 --details --current 1.0.0 || true
echo ""

echo -e "${GREEN}Step 5: Check status with pygeometry2 (against pygeometry1 baseline)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status example.py.pygeometry2 --details${NC}"
echo ""
run_sdd status example.py.pygeometry2 --details --baked "$WORK_DIR/baked.yaml" --current-file "$WORK_DIR/current.yaml" --version-file "$WORK_DIR/VERSION" || true
echo ""

echo -e "${GREEN}Step 6: Show suggested version in current.yaml${NC}"
echo -e "File: ${YELLOW}current.yaml${NC}"
echo "----------------------------------------"
head -50 "$WORK_DIR/current.yaml"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 7: Bake the new version${NC}"
echo -e "Command: ${YELLOW}semver-dredd bake example.py.pygeometry2${NC}"
echo ""
run_sdd bake example.py.pygeometry2 --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
echo ""

echo -e "${GREEN}Step 8: Show new version${NC}"
echo -e "File: ${YELLOW}VERSION${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/VERSION"
echo ""
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Cleanup: Removing work directory${NC}"
rm -rf "$WORK_DIR"

echo ""
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    Demo Complete!${NC}"
echo -e "${BLUE}=================================================${NC}"
