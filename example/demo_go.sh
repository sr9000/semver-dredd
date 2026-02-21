#!/bin/bash
# Demo script for Go language support
# This script demonstrates the semver-dredd workflow for Go packages

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
GO_PARSER="$PROJECT_ROOT/plugins/semver-dredd-go/semver_dredd_go/parser"
GOGEOM1="$SCRIPT_DIR/go/gogeometry1"
GOGEOM2="$SCRIPT_DIR/go/gogeometry2"
WORK_DIR=$(mktemp -d)

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    semver-dredd Go Demo${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "Working directory: ${YELLOW}$WORK_DIR${NC}"
echo ""

cd "$WORK_DIR"

# Ensure we can import from the project
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Check if Go parser is built
if [ ! -f "$GO_PARSER/golang" ]; then
    echo -e "${YELLOW}Building Go parser...${NC}"
    cd "$GO_PARSER"
    go build -o golang .
    cd "$WORK_DIR"
fi

echo -e "${GREEN}Step 1: Show Go source files${NC}"
echo ""
echo -e "${YELLOW}gogeometry1/geom.go:${NC}"
echo "----------------------------------------"
cat "$GOGEOM1/geom.go"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}gogeometry2/geom.go (with additions):${NC}"
echo "----------------------------------------"
cat "$GOGEOM2/geom.go"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 2: Generate API snapshot for gogeometry1${NC}"
echo -e "Command: ${YELLOW}go run ./parser/golang --dir ./example/go/gogeometry1 --version 1.0.0${NC}"
echo ""
"$GO_PARSER/golang" --dir "$GOGEOM1" --version 1.0.0 --out "$WORK_DIR/baked.yaml"
echo -e "${YELLOW}baked.yaml:${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/baked.yaml"
echo "----------------------------------------"
echo ""

# Create VERSION file
echo "1.0.0" > "$WORK_DIR/VERSION"

echo -e "${GREEN}Step 3: Initialize project with semver-dredd (Go)${NC}"
echo -e "Command: ${YELLOW}semver-dredd init ./example/go/gogeometry1 --plugin go --version 1.0.0${NC}"
echo ""
python -m cli init "$GOGEOM1" --plugin go --version 1.0.0 --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
echo ""

echo -e "${GREEN}Step 4: Check status (no changes)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status ./example/go/gogeometry1 --plugin go --details${NC}"
echo ""
cd "$WORK_DIR"
python -m cli status "$GOGEOM1" --plugin go --details || true
echo ""

echo -e "${GREEN}Step 5: Check status with gogeometry2 (against gogeometry1 baseline)${NC}"
echo -e "Command: ${YELLOW}semver-dredd status ./example/go/gogeometry2 --plugin go --details${NC}"
echo ""
echo -e "${YELLOW}Changes in gogeometry2:${NC}"
echo -e "  - Added Point.Z field (3D coordinate)"
echo -e "  - Added Point.Translate() method"
echo -e "  - Added Volume() function"
echo ""
python -m cli status "$GOGEOM2" --plugin go --details || true
echo ""

echo -e "${GREEN}Step 6: Show suggested version in current.yaml${NC}"
echo -e "File: ${YELLOW}current.yaml${NC}"
echo "----------------------------------------"
cat "$WORK_DIR/current.yaml"
echo "----------------------------------------"
echo ""

echo -e "${GREEN}Step 7: Bake the new version${NC}"
echo -e "Command: ${YELLOW}semver-dredd bake ./example/go/gogeometry2 --plugin go${NC}"
echo ""
python -m cli bake "$GOGEOM2" --plugin go --baked "$WORK_DIR/baked.yaml" --version-file "$WORK_DIR/VERSION"
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
