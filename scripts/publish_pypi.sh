#!/usr/bin/env bash
# Build, verify, and optionally publish semver-dredd distributions to PyPI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_ROOT="${DIST_ROOT:-$REPO_ROOT/dist/pypi-publish}"

CHECK_ONLY=0
SKIP_CORE=0
SKIP_PLUGINS=0
SKIP_META=0
START_FROM=""
STARTED=1
TWINE_ARGS=()

usage() {
    cat <<'EOF'
Usage:
  bash scripts/publish_pypi.sh [options]

Options:
  --check-only                 Build + twine-check, but do not upload
  --skip-core                  Skip publishing the core semver-dredd package
  --skip-plugins               Skip publishing official plugin packages
  --skip-meta                  Skip publishing semver-dredd-all
  --start-from NAME            Resume from a specific package label
  --skip-existing              Pass through to twine upload --skip-existing
  --verbose                    Pass through to twine upload --verbose
  --twine-arg ARG              Pass a raw extra argument to twine upload
  --repository NAME            Pass through to twine upload --repository
  --repository-url URL         Pass through to twine upload --repository-url
  -h, --help                   Show this help

Environment:
  TWINE_USERNAME / TWINE_PASSWORD or a configured ~/.pypirc are used by twine.

Default publish order:
  1. Official plugin packages used by extras
  2. Core package (semver-dredd)
  3. Meta-package (semver-dredd-all)

Package labels for --start-from:
  python-3.10-dredd, go-1.20-dredd, java-1.8-dredd,
  javaparser-1.8-dredd, semver-dredd, semver-dredd-all
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check-only)
            CHECK_ONLY=1
            ;;
        --skip-core)
            SKIP_CORE=1
            ;;
        --skip-plugins)
            SKIP_PLUGINS=1
            ;;
        --skip-meta)
            SKIP_META=1
            ;;
        --start-from)
            if [ $# -lt 2 ]; then
                echo "Missing value for $1" >&2
                usage >&2
                exit 1
            fi
            START_FROM="$2"
            STARTED=0
            shift
            ;;
        --skip-existing|--verbose)
            TWINE_ARGS+=("$1")
            ;;
        --twine-arg)
            if [ $# -lt 2 ]; then
                echo "Missing value for $1" >&2
                usage >&2
                exit 1
            fi
            TWINE_ARGS+=("$2")
            shift
            ;;
        --repository|--repository-url)
            if [ $# -lt 2 ]; then
                echo "Missing value for $1" >&2
                usage >&2
                exit 1
            fi
            TWINE_ARGS+=("$1" "$2")
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

cd "$REPO_ROOT"

ensure_poetry_module() {
    local module_name="$1"
    local package_name="$2"

    if poetry run python - <<PY >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec(${module_name@Q}) else 1)
PY
    then
        return
    fi

    echo "==> Installing missing Poetry tool dependency: $package_name"
    poetry run python -m pip install --disable-pip-version-check "$package_name"
}

build_package() {
    local label="$1"
    local source_dir="$2"
    local outdir="$DIST_ROOT/$label"

    rm -rf "$outdir"
    mkdir -p "$outdir"

    echo "==> Building $label from $source_dir"
    poetry run python -m build "$source_dir" --outdir "$outdir"

    echo "==> Running twine check for $label"
    poetry run python -m twine check "$outdir"/*
}

should_process_package() {
    local label="$1"

    if [ "$STARTED" -eq 1 ]; then
        return 0
    fi

    if [ "$label" = "$START_FROM" ]; then
        STARTED=1
        return 0
    fi

    echo "==> Skipping $label until --start-from $START_FROM"
    return 1
}

process_package() {
    local label="$1"
    local source_dir="$2"

    if ! should_process_package "$label"; then
        return
    fi

    build_package "$label" "$source_dir"
    upload_package "$label"
}

upload_package() {
    local label="$1"
    local outdir="$DIST_ROOT/$label"

    if [ "$CHECK_ONLY" -eq 1 ]; then
        echo "==> Check-only mode: skipping upload for $label"
        return
    fi

    echo "==> Uploading $label"
    poetry run python -m twine upload "${TWINE_ARGS[@]}" "$outdir"/*
}

ensure_poetry_module build build
ensure_poetry_module twine twine

mkdir -p "$DIST_ROOT"

PLUGIN_DIRS=(
    "python-3.10-dredd:plugins/python-3.10-dredd"
    "go-1.20-dredd:plugins/go-1.20-dredd"
    "java-1.8-dredd:plugins/java-1.8-dredd"
    "javaparser-1.8-dredd:plugins/javaparser-1.8-dredd"
)

if [ "$SKIP_PLUGINS" -eq 0 ]; then
    for entry in "${PLUGIN_DIRS[@]}"; do
        IFS=":" read -r label source_dir <<<"$entry"
        process_package "$label" "$source_dir"
    done
fi

if [ "$SKIP_CORE" -eq 0 ]; then
    process_package "semver-dredd" "."
fi

if [ "$SKIP_META" -eq 0 ]; then
    process_package "semver-dredd-all" "plugins/semver-dredd-all"
fi

if [ "$STARTED" -eq 0 ]; then
    echo "Unknown package label for --start-from: $START_FROM" >&2
    exit 1
fi

echo "==> Publish flow complete"