# java-1.8-dredd

Java 1.8+ language plugin for semver-dredd.

> **Package renamed:** This package was formerly published as `semver-dredd-java`.
> The importable module name (`semver_dredd_java`) and the CLI plugin key (`java`) are unchanged.

## Installation

```bash
pip install java-1.8-dredd
```

Or install from local path (development):

```bash
pip install ./plugins/java-1.8-dredd
```

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
- **JDK 1.8+** installed (both `javac` and `java` must be in PATH)

## Usage

Once installed, the plugin is automatically discovered by semver-dredd:

```bash
# List plugins to verify installation
semver-dredd plugin list
semver-dredd plugin info java

# Generate snapshot for a Java source directory
semver-dredd snapshot --plugin java --path ./src/main/java --version 1.0.0

# Or use the managed init/status/bake workflow
semver-dredd init ./src/main/java --plugin java --version 1.0.0
semver-dredd status ./src/main/java --plugin java --details
semver-dredd bake ./src/main/java --plugin java
```

## How it works

This plugin bundles a simple Java parser that uses regex-based extraction to identify:

- Public classes and interfaces
- Public/protected fields with types
- Public/protected methods with signatures
- Public static methods are also exposed as package-level functions

The parser is compiled on-the-fly using `javac` and runs with the bundled SnakeYAML library.

**Note**: This is a simple regex-based parser suitable for straightforward Java code.
For complex codebases, a proper Java AST parser (like JavaParser) would be recommended.

## Scope: `include` / `exclude`

`include` and `exclude` items are Java package prefixes (not glob syntax),
matched recursively against the fully package-qualified class/function names
the parser produces:

```yaml
include: [com.example.api]
exclude: [com.example.api.internal]
```

- Empty `include` (or omitted) analyzes the whole parsed public API under
  `--path`, exactly as without scope.
- A non-empty `include` switches to allow-list mode: only classes/functions
  under the listed package prefixes (and nested sub-packages) are kept.
- `exclude` is applied after `include` and supports a trailing `*` for
  non-recursive (single package level) exclusion, e.g.
  `com.example.api.internal*` excludes only that exact package, not deeper
  nested packages under it.
- `include` matching nothing produces an empty snapshot API (logged as a
  warning) rather than falling back to no-scope behavior.

