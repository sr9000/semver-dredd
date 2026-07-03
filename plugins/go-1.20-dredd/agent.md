# Agent Notes — Go Plugin (`go-1.20-dredd`)

Key `go` · entry `semver_dredd_go:GoPlugin` · impl `semver_dredd_go/plugin.py` ·
parser `semver_dredd_go/parser/main.go`.

## How it works

- Requires Go 1.20+ in `PATH`.
- `validate_path()` requires an existing dir containing `*.go` files.
- `generate_snapshot()` runs `go run . --dir <path> --version <version>` from the
  bundled parser dir.
- Output normalized into `GoSnapshot` (with `snapshot_type_id`); diffing converts
  to `NormalizedSnapshot` and delegates.
- Package data (`pyproject.toml`): `parser/*.go`, `parser/go.mod`, `parser/go.sum`.
- Docker smoke pre-downloads parser modules to avoid runtime network access.

## Commands

```bash
pip install -e plugins/go-1.20-dredd
semver-dredd snapshot --plugin go --path example/go/gogeometry1 --version 1.0.0
bash example/demo_go.sh
```

## Scope (implemented)

`main.go` now recursively walks the analyzed directory tree
(`parseDirTree` + `parseSinglePackageDir`); each subdirectory with `.go` files
is its own package. Root-package functions/types stay unprefixed (backward
compatible with the pre-scope single-package output); nested packages are
prefixed with their `/`-separated import path relative to the root (e.g.
`sub/Area`, `sub/internal/Helper`). `_test.go` files and hidden/`vendor`/
`testdata` dirs are always excluded from the walk. Python-side
`_filter_snapshot_scope()`/`_matches_import_path()` in `plugin.py` apply
include (allow-list, recursive) then exclude (supports trailing `*` for
non-recursive exclusion) against the prefixed names. See README and
`tests/test_go_plugin_scope.py` / `tests/fixtures/go_scope/`.

