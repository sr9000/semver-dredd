#!/usr/bin/env bash
# Full-featured config showcase for semver-dredd.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARTIFACT_DIR="$WORK_DIR/.artifacts"

if command -v poetry >/dev/null 2>&1; then
    POETRY_PY="$(cd "$PROJECT_ROOT" && poetry env info --executable)"

    run_sdd() {
        PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$POETRY_PY" -m cli "$@"
    }

    run_py() {
        PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$POETRY_PY" "$@"
    }
elif command -v semver-dredd >/dev/null 2>&1; then
    run_sdd() {
        semver-dredd "$@"
    }

    if command -v python3 >/dev/null 2>&1; then
        run_py() {
            python3 "$@"
        }
    else
        run_py() {
            python "$@"
        }
    fi
elif command -v python3 >/dev/null 2>&1; then
    run_sdd() {
        python3 -m cli "$@"
    }

    run_py() {
        python3 "$@"
    }
else
    run_sdd() {
        python -m cli "$@"
    }

    run_py() {
        python "$@"
    }
fi

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

PLUGIN_LIST_RAW="$(run_sdd plugin list --no-color 2>/dev/null || run_sdd plugin list 2>/dev/null || true)"

SHOWCASE_PLUGIN=""
SOURCE_OLD=""
SOURCE_NEW=""
SCOPE_PATH=""
SCOPE_INCLUDE=""
SCOPE_EXCLUDE=""
SCOPE_APPEND=""
SCOPE_EXPECT_DEFAULT=""
SCOPE_EXPECT_EXTRA=""

if grep -Eq '(^|[[:space:]])python([[:space:]]|$)' <<<"$PLUGIN_LIST_RAW"; then
    SHOWCASE_PLUGIN="python"
    SOURCE_OLD="example.py.pygeometry1"
    SOURCE_NEW="example.py.pygeometry2"
    SCOPE_PATH="$PROJECT_ROOT/tests/fixtures/python_scope/scopepkg"
    SCOPE_INCLUDE="scopepkg.pub"
    SCOPE_EXCLUDE="scopepkg.other"
    SCOPE_APPEND="scopepkg.nested"
    SCOPE_EXPECT_DEFAULT="included_func"
    SCOPE_EXPECT_EXTRA="nested_func"
elif grep -Eq '(^|[[:space:]])go([[:space:]]|$)' <<<"$PLUGIN_LIST_RAW" && command -v go >/dev/null 2>&1; then
    SHOWCASE_PLUGIN="go"
    SOURCE_OLD="$PROJECT_ROOT/example/go/gogeometry1"
    SOURCE_NEW="$PROJECT_ROOT/example/go/gogeometry2"
    SCOPE_PATH="$PROJECT_ROOT/tests/fixtures/go_scope"
    SCOPE_INCLUDE="sub"
    SCOPE_EXCLUDE="sub/internal*"
    SCOPE_APPEND="other"
    SCOPE_EXPECT_DEFAULT="sub/SubFunc"
    SCOPE_EXPECT_EXTRA="other/OtherFunc"
elif grep -Eq '(^|[[:space:]])java([[:space:]]|$)' <<<"$PLUGIN_LIST_RAW" \
    && command -v java >/dev/null 2>&1 \
    && command -v javac >/dev/null 2>&1; then
    SHOWCASE_PLUGIN="java"
    SOURCE_OLD="$PROJECT_ROOT/example/java/javageometry1"
    SOURCE_NEW="$PROJECT_ROOT/example/java/javageometry2"
    SCOPE_PATH="$PROJECT_ROOT/tests/fixtures/java_scope"
    SCOPE_INCLUDE="com.example.api"
    SCOPE_EXCLUDE="com.example.api.internal*"
    SCOPE_APPEND="com.example.other"
    SCOPE_EXPECT_DEFAULT="com.example.api.Included.includedMethod"
    SCOPE_EXPECT_EXTRA="com.example.other.Other.otherMethod"
else
    echo -e "${RED}Error: no suitable showcase plugin/runtime found (need python, go, or java).${NC}" >&2
    exit 1
fi

show_functions() {
    local snapshot_path="$1"
    run_py - "$snapshot_path" <<'PY'
import sys
import yaml

data = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8")) or {}
functions = sorted((data.get("api") or {}).get("functions", {}).keys())
print(",".join(functions))
PY
}

has_function() {
    local snapshot_path="$1"
    local symbol="$2"
    local names
    names="$(show_functions "$snapshot_path")"
    if grep -Fq "$symbol" <<<"$names"; then
        echo yes
    else
        echo no
    fi
}

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    semver-dredd Config Showcase${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "Working directory: ${YELLOW}$WORK_DIR${NC}"
echo ""

mkdir -p "$ARTIFACT_DIR"
cd "$WORK_DIR"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "SHOWCASE selected_plugin=$SHOWCASE_PLUGIN"

cat > "$WORK_DIR/.semver.showcase.yaml" <<EOF_CONFIG
schema_version: 1
source:
  path: $SOURCE_OLD
files:
  baked: .artifacts/baked.yaml
  current: .artifacts/current.yaml
  version: .artifacts/VERSION
policies:
  allow_breaking_changes: false
output:
  color: null
  severity_by_change:
    none: info
    patch: info
    minor: warn
    major: error
versioning:
  patch_scheme: integer
plugin_options:
  timeout_seconds: 30
---
plugin: does-not-exist
---
plugin: $SHOWCASE_PLUGIN
EOF_CONFIG

cat > "$WORK_DIR/.semver.scope.yaml" <<EOF_SCOPE
schema_version: 1
source:
  path: $SCOPE_PATH
files:
  version: .artifacts/VERSION
versioning:
  patch_scheme: integer
plugin_options:
  timeout_seconds: 30
---
plugin: missing-scope-plugin
include:
  - $SCOPE_INCLUDE
---
plugin: $SHOWCASE_PLUGIN
include:
  - $SCOPE_INCLUDE
exclude:
  - $SCOPE_EXCLUDE
EOF_SCOPE

cat > "$WORK_DIR/.env" <<EOF_ENV
SEMVER_DREDD_COLOR=false
SEMVER_DREDD_CURRENT_FILE=.artifacts/current.from-dotenv.yaml
SEMVER_DREDD_PATH=$SOURCE_NEW
EOF_ENV

echo -e "${GREEN}Step 1: List available plugins${NC}"
run_sdd plugin list
echo ""

echo -e "${GREEN}Step 2: Generate a comprehensive template${NC}"
run_sdd template --out "$WORK_DIR/template.generated.yaml"
sed -n '1,30p' "$WORK_DIR/template.generated.yaml"
echo "SHOWCASE template=$WORK_DIR/template.generated.yaml"
echo ""

echo -e "${GREEN}Step 3: Initialize a baseline using explicit CLI args and config-managed files${NC}"
(
    unset SEMVER_DREDD_PLUGIN SEMVER_DREDD_PATH
    run_sdd --config "$WORK_DIR/.semver.showcase.yaml" init "$SOURCE_OLD" --plugin "$SHOWCASE_PLUGIN" --version 1.0.0
)
echo "SHOWCASE init_baked=$ARTIFACT_DIR/baked.yaml"
echo "SHOWCASE init_version=$(cat "$ARTIFACT_DIR/VERSION")"
echo ""

echo -e "${GREEN}Step 4: Pathless status via config + .env override + candidate fallback${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    run_sdd -vv --config "$WORK_DIR/.semver.showcase.yaml" status --details --no-color
)
DOTENV_SUGGESTED="$(run_py - <<'PY'
import yaml
data = yaml.safe_load(open('.artifacts/current.from-dotenv.yaml', 'r', encoding='utf-8')) or {}
print(data.get('version', ''))
PY
)"
echo "SHOWCASE dotenv_suggested=$DOTENV_SUGGESTED"
echo ""

echo -e "${GREEN}Step 5: Real environment overrides beat .env${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    export SEMVER_DREDD_PATH="$SOURCE_OLD"
    export SEMVER_DREDD_CURRENT_FILE=.artifacts/current.from-env.yaml
    run_sdd --config "$WORK_DIR/.semver.showcase.yaml" status --no-color
)
ENV_SUGGESTED="$(run_py - <<'PY'
import yaml
data = yaml.safe_load(open('.artifacts/current.from-env.yaml', 'r', encoding='utf-8')) or {}
print(data.get('version', ''))
PY
)"
echo "SHOWCASE env_suggested=$ENV_SUGGESTED"
echo ""

echo -e "${GREEN}Step 6: Compare old vs new directly${NC}"
(
    unset SEMVER_DREDD_PLUGIN SEMVER_DREDD_PATH
    run_sdd compare "$SOURCE_OLD" "$SOURCE_NEW" --plugin "$SHOWCASE_PLUGIN" --details --current 1.0.0 --no-color
)
echo ""

echo -e "${GREEN}Step 7: Snapshot with multi-document fallback and config scope${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    export SEMVER_DREDD_PATH="$SCOPE_PATH"
    run_sdd -vv --config "$WORK_DIR/.semver.scope.yaml" snapshot --version 1.0.0 --out "$WORK_DIR/scope-default.yaml" --no-color
)
DEFAULT_FUNCTIONS="$(show_functions "$WORK_DIR/scope-default.yaml")"
echo "SHOWCASE scope_default=$DEFAULT_FUNCTIONS"
echo ""

echo -e "${GREEN}Step 8: CLI --include appends to config scope${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    export SEMVER_DREDD_PATH="$SCOPE_PATH"
    run_sdd --config "$WORK_DIR/.semver.scope.yaml" snapshot --version 1.0.0 --include "$SCOPE_APPEND" --out "$WORK_DIR/scope-append.yaml" --no-color
)
APPEND_FUNCTIONS="$(show_functions "$WORK_DIR/scope-append.yaml")"
echo "SHOWCASE scope_append=$APPEND_FUNCTIONS"
echo ""

echo -e "${GREEN}Step 9: CLI --override replaces configured include/exclude${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    export SEMVER_DREDD_PATH="$SCOPE_PATH"
    run_sdd --config "$WORK_DIR/.semver.scope.yaml" snapshot --version 1.0.0 --include "$SCOPE_APPEND" --override --out "$WORK_DIR/scope-override.yaml" --no-color
)
OVERRIDE_FUNCTIONS="$(show_functions "$WORK_DIR/scope-override.yaml")"
echo "SHOWCASE scope_override=$OVERRIDE_FUNCTIONS"
echo "SHOWCASE scope_default_has_primary=$(has_function "$WORK_DIR/scope-default.yaml" "$SCOPE_EXPECT_DEFAULT")"
echo "SHOWCASE scope_append_has_extra=$(has_function "$WORK_DIR/scope-append.yaml" "$SCOPE_EXPECT_EXTRA")"
if [ "$OVERRIDE_FUNCTIONS" = "$SCOPE_EXPECT_EXTRA" ]; then
    echo "SHOWCASE scope_override_only_extra=yes"
else
    echo "SHOWCASE scope_override_only_extra=no"
fi
echo ""

echo -e "${GREEN}Step 10: Plugin override failure semantics${NC}"
set +e
PLUGIN_OVERRIDE_OUTPUT="$(
    unset SEMVER_DREDD_PATH
    export SEMVER_DREDD_PLUGIN=definitely-not-installed-demo-plugin
    run_sdd --config "$WORK_DIR/.semver.scope.yaml" snapshot --version 1.0.0 --out "$WORK_DIR/should-not-exist.yaml" --no-color 2>&1
)"
PLUGIN_OVERRIDE_CODE=$?
set -e
echo "$PLUGIN_OVERRIDE_OUTPUT"
echo "SHOWCASE plugin_override_exit=$PLUGIN_OVERRIDE_CODE"
echo ""

echo -e "${GREEN}Step 11: Version helpers use integer patch scheme from config${NC}"
BUMP_OUT="$(
    unset SEMVER_DREDD_PLUGIN SEMVER_DREDD_PATH
    run_sdd --config "$WORK_DIR/.semver.showcase.yaml" bump --current 1.0.0 --change minor | tail -1 | sed 's/^New: //'
)"
PATCH_OUT="$(
    unset SEMVER_DREDD_PLUGIN SEMVER_DREDD_PATH
    run_sdd --config "$WORK_DIR/.semver.showcase.yaml" patch --current 7 | tail -1
)"
echo "SHOWCASE bump_minor=$BUMP_OUT"
echo "SHOWCASE patch_next=$PATCH_OUT"
echo ""

echo -e "${GREEN}Step 12: Pathless bake uses resolved source path and managed files${NC}"
(
    unset SEMVER_DREDD_PLUGIN
    export SEMVER_DREDD_PATH="$SOURCE_NEW"
    run_sdd --config "$WORK_DIR/.semver.showcase.yaml" bake --no-color
)
echo "SHOWCASE baked_version=$(cat "$ARTIFACT_DIR/VERSION")"
echo ""

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}    Config Showcase Complete!${NC}"
echo -e "${BLUE}=================================================${NC}"
