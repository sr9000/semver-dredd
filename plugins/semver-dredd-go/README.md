# semver-dredd-go

Go language plugin for semver-dredd.

## Installation

```bash
pip install semver-dredd-go
```

Or install from local path (development):

```bash
pip install ./plugins/semver-dredd-go
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
semver-dredd snapshot --lang go --path ./mypackage --version 1.0.0
```

## How it works

This plugin bundles a Go parser that uses Go's `go/ast` package to extract:

- Public functions and their signatures
- Public types (structs) with exported fields
- Methods on public types
- Parameter types and return types

The parser is invoked via `go run .` from the bundled parser directory.
