#!/bin/bash
# Demo script for Java language support
# This script demonstrates the semver-dredd workflow for Java projects

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
JAVAGEOM1="$SCRIPT_DIR/java/javageometry1"
JAVAGEOM2="$SCRIPT_DIR/java/javageometry2"
WORK_DIR=$(mktemp -d)

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    semver-dredd Java Demo${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "Working directory: ${YELLOW}$WORK_DIR${NC}"
echo ""

cd "$WORK_DIR"

# Ensure we can import from the project
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Check for Java
if ! command -v java &> /dev/null; then
    echo -e "${RED}Error: Java is not installed. Please install JDK 21+${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: Show Java source files${NC}"
echo ""
echo -e "${YELLOW}javageometry1/Point.java:${NC}"
echo "----------------------------------------"
cat "$JAVAGEOM1/Point.java"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}javageometry1/Geometry.java:${NC}"
echo "----------------------------------------"
cat "$JAVAGEOM1/Geometry.java"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}javageometry2/Point.java (with additions):${NC}"
echo "----------------------------------------"
cat "$JAVAGEOM2/Point.java"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}javageometry2/Geometry.java (with additions):${NC}"
echo "----------------------------------------"
cat "$JAVAGEOM2/Geometry.java"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 2: Generate API snapshot for javageometry1${NC}"
echo -e "Command: ${YELLOW}semver-dredd snapshot --plugin java --path ./example/java/javageometry1 --version 1.0.0${NC}"
echo ""
semver-dredd snapshot --plugin java --path "$JAVAGEOM1" --version 1.0.0 --out "$WORK_DIR/snapshot_preview.yaml"
echo -e "${YELLOW}snapshot_preview.yaml:${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/snapshot_preview.yaml"
echo "----------------------------------------"
echo ""

# Create VERSION file
echo "1.0.0" > "$WORK_DIR/VERSION"

echo -e "${GREEN}Step 3: Initialize project with semver-dredd (Java)${NC}"
echo -e "Command: ${YELLOW}semver-dredd init ./example/java/javageometry1 --plugin java --version 1.0.0${NC}"
echo ""
semver-dredd init "$JAVAGEOM1" --plugin java --version 1.0.0 --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
echo ""

echo -e "${GREEN}Step 4: Check status (no changes)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status ./example/java/javageometry1 --plugin java --details${NC}"
echo ""
semver-dredd status "$JAVAGEOM1" --plugin java --details --baked "$WORK_DIR/baked.yaml" --current-file "$WORK_DIR/current.yaml" --version-file "$WORK_DIR/VERSION" || true
echo ""

echo -e "${GREEN}Step 5: Check status with javageometry2 (against javageometry1 baseline)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status ./example/java/javageometry2 --plugin java --details${NC}"
echo ""
echo -e "${YELLOW}Changes in javageometry2:${NC}"
echo -e "  - Added Point.z field (3D coordinate)"
echo -e "  - Added Point.translate() method"
echo -e "  - Added Geometry.volume() static method"
echo ""
semver-dredd status "$JAVAGEOM2" --plugin java --details --baked "$WORK_DIR/baked.yaml" --current-file "$WORK_DIR/current.yaml" --version-file "$WORK_DIR/VERSION" || true
echo ""

echo -e "${GREEN}Step 6: Show suggested version in current.yaml${NC}"
echo -e "File: ${YELLOW}current.yaml${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/current.yaml"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 7: Bake the new version${NC}"
echo -e "Command: ${YELLOW}semver-dredd bake ./example/java/javageometry2 --plugin java${NC}"
echo ""
semver-dredd bake "$JAVAGEOM2" --plugin java --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
echo ""

echo -e "${GREEN}Step 8: Show new version${NC}"
echo -e "File: ${YELLOW}VERSION${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/VERSION"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Cleanup: Removing work directory${NC}"
rm -rf "$WORK_DIR"

echo ""
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    Demo Complete!${NC}"
echo -e "${BLUE}=================================================${NC}"
