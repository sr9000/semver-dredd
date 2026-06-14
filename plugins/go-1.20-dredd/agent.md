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

## Scope (not yet implemented)

Go API scope is package-oriented; prefer package-dir / import-path matching before
symbol-level filtering. Filtering needs changes + tests at both Python wrapper and
Go parser levels. Open decisions: match dirs vs import paths vs files vs exported
symbols? exclude `*_test.go` by default? support module-root + package include
list vs single package dir?
