#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${WORK_DIR:-$(pwd)}"
WHEELHOUSE="${WHEELHOUSE:-$WORK_DIR/dist/package-wheelhouse}"

if [ ! -f "$WORK_DIR/pyproject.toml" ]; then
    echo "Expected repo root at WORK_DIR=$WORK_DIR" >&2
    exit 1
fi

mkdir -p "$WHEELHOUSE"
rm -f "$WHEELHOUSE"/*

echo "==> Building core and plugin distributions into $WHEELHOUSE"
python -m build --outdir "$WHEELHOUSE" "$WORK_DIR"
for pkg in \
    "$WORK_DIR/plugins/python-3.10-dredd" \
    "$WORK_DIR/plugins/go-1.20-dredd" \
    "$WORK_DIR/plugins/java-1.8-dredd" \
    "$WORK_DIR/plugins/javaparser-1.8-dredd" \
    "$WORK_DIR/plugins/semver-dredd-all"
do
    python -m build --outdir "$WHEELHOUSE" "$pkg"
done

echo "==> Running twine check"
python -m twine check "$WHEELHOUSE"/*

run_case() {
    local name="$1"
    local spec="$2"
    local expected_csv="$3"
    local venv_dir
    venv_dir="$(mktemp -d /tmp/semver-dredd-${name}.XXXXXX)"

    echo "==> Running install case: $name ($spec)"
    python -m venv --system-site-packages "$venv_dir"
    # shellcheck disable=SC1090
    source "$venv_dir/bin/activate"
    python -m pip install --upgrade pip >/dev/null
    python -m pip install --no-index --find-links "$WHEELHOUSE" "$spec"
    semver-dredd plugin list --json > "$venv_dir/plugins.json"

    EXPECTED_PLUGINS="$expected_csv" CASE_NAME="$name" PLUGIN_JSON="$venv_dir/plugins.json" python - <<'PY'
import json
import os
import sys
from pathlib import Path

payload = json.loads(Path(os.environ["PLUGIN_JSON"]).read_text())
actual = {item["name"] for item in payload}
expected = {
    name.strip()
    for name in os.environ["EXPECTED_PLUGINS"].split(",")
    if name.strip()
}

if actual != expected:
    print(f"[{os.environ['CASE_NAME']}] expected: {sorted(expected)}")
    print(f"[{os.environ['CASE_NAME']}] actual:   {sorted(actual)}")
    sys.exit(1)

origins = {item["name"]: item.get("origin", "") for item in payload}
if origins.get("bundle") != "builtin":
    print(
        f"[{os.environ['CASE_NAME']}] expected bundle origin 'builtin', got "
        f"{origins.get('bundle')!r}"
    )
    sys.exit(1)

unexpected_origins = {
    name: origin
    for name, origin in origins.items()
    if name != "bundle" and origin != "entry_point"
}
if unexpected_origins:
    print(
        f"[{os.environ['CASE_NAME']}] expected non-bundle plugins from entry points, got "
        f"{unexpected_origins}"
    )
    sys.exit(1)

print(f"[{os.environ['CASE_NAME']}] OK -> {sorted(actual)}")
PY

    deactivate
    rm -rf "$venv_dir"
}

run_case tool-only semver-dredd bundle
run_case tool-plus-python "semver-dredd[python]" bundle,python
run_case tool-plus-go-java-javaparser "semver-dredd[go,java,javaparser]" bundle,go,java,javaparser
run_case tool-plus-all "semver-dredd[all]" bundle,go,java,javaparser,python

echo "==> Package install checks passed"