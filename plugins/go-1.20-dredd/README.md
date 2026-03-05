# go-1.20-dredd

Go 1.20+ language plugin for semver-dredd.

> **Package renamed:** This package was formerly published as `semver-dredd-go`.
> The importable module name (`semver_dredd_go`) and the CLI plugin key (`go`) are unchanged.

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

# Generate snapshot for a Go package
semver-dredd snapshot --plugin go --path ./mypackage --version 1.0.0
```

## How it works

This plugin bundles a Go parser that uses Go's `go/ast` package to extract:

- Public functions and their signatures
- Public types (structs) with exported fields
- Methods on public types
- Parameter types and return types

The parser is invoked via `go run .` from the bundled parser directory.
