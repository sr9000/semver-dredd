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
pip install ./plugins/semver-dredd-java
```

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
- **JDK 11+** installed (both `javac` and `java` must be in PATH)

## Usage

Once installed, the plugin is automatically discovered by semver-dredd:

```bash
# List plugins to verify installation
semver-dredd plugin list

# Generate snapshot for a Java source directory
semver-dredd snapshot --plugin java --path ./src/main/java --version 1.0.0
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
