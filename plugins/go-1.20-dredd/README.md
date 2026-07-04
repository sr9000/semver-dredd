# go-1.20-dredd

Go 1.20+ language plugin for semver-dredd.

## Installation

```bash
pip install go-1.20-dredd
```

Or install from local path (development):

```bash
pip install ./plugins/go-1.20-dredd
```

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
- **Go 1.20+** installed and available in PATH

## Usage

Once installed, the plugin is automatically discovered by semver-dredd:

```bash
# List plugins to verify installation
semver-dredd plugin list
semver-dredd plugin info go

# Generate snapshot for a Go package
semver-dredd snapshot --plugin go --path ./mypackage --version 1.0.0

# Or use the managed init/status/bake workflow
semver-dredd init ./mypackage --plugin go --version 1.0.0
semver-dredd status ./mypackage --plugin go --details
semver-dredd bake ./mypackage --plugin go
```

## How it works

This plugin bundles a Go parser that uses Go's `go/ast` package to extract:

- Public functions and their signatures
- Public types (structs) with exported fields
- Methods on public types
- Parameter types and return types

The parser is invoked via `go run .` from the bundled parser directory.

## Scope: `include` / `exclude`

`include` and `exclude` items are Go import paths **relative to the analyzed
root directory**, using `/` separators (Go import-path convention), matched
recursively:

```yaml
include: [sub]
exclude: [sub/internal]
```

- Empty `include` (or omitted) analyzes the whole package tree rooted at
  `--path`, exactly as without scope.
- The parser walks the root directory recursively; each subdirectory
  containing `.go` files is treated as its own package. The root package's
  functions/types are unprefixed (preserving pre-scope single-package
  behavior); nested packages are prefixed with their relative import path,
  e.g. `sub/Area` or `sub/internal/Helper`.
- `exclude` is applied after `include` and supports a trailing `*` for
  non-recursive (single import path level) exclusion, e.g. `sub/internal*`
  excludes only `sub/internal` itself, not further-nested packages under it.
- `_test.go` files and hidden/`vendor`/`testdata` directories are never part
  of the analyzed API surface.
- `include` matching no package produces an empty snapshot API (logged as a
  warning) rather than falling back to no-scope behavior.

