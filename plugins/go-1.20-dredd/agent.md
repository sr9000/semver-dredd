# Agent Notes — Go Plugin (`go-1.20-dredd`)

Plugin key: `go`  
Entry point: `semver_dredd_go:GoPlugin`  
Implementation: `semver_dredd_go/plugin.py`  
Bundled parser: `semver_dredd_go/parser/main.go`

## How it works

- Requires Go 1.20+ in `PATH`.
- `validate_path()` requires an existing directory containing `*.go` files.
- `generate_snapshot()` runs `go run . --dir <path> --version <version>` from
  the bundled parser directory.
- Parser output is upgraded/normalized into `GoSnapshot` with
  `snapshot_type_id`.
- Diffing converts `GoSnapshot` to `NormalizedSnapshot` and delegates.

## Package data

`pyproject.toml` includes parser package data:

- `parser/*.go`
- `parser/go.mod`
- `parser/go.sum`

## Commands

```bash
pip install -e plugins/go-1.20-dredd
semver-dredd snapshot --plugin go --path example/go/gogeometry1 --version 1.0.0
bash example/demo_go.sh
```

Docker smoke pre-downloads parser Go modules to avoid runtime network access.

## Scope-related notes

The plugin currently receives `options` but does not use `include`, `exclude`,
or `plugin_options`.

Go API scope is package-oriented. Prefer package directory or import-path
matching before considering symbol-level filtering. Any filtering likely needs
parser changes and tests at both Python wrapper and Go parser levels.

Open decisions before implementing:

- Should include/exclude match directories, import paths, files, exported
  symbols, or only package paths?
- Should `*_test.go` be excluded by default?
- Should analysis support a module root plus package include list rather than
  only one package directory?
