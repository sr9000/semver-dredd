# semver-dredd-all

Meta-package that installs `semver-dredd` plus the core set of official plugin
packages bundled by this repo.

## Installation

```bash
pip install semver-dredd-all
```

This currently installs:
- `semver-dredd` - Core library
- `python-3.10-dredd` - Python language plugin
- `go-1.20-dredd` - Go language plugin
- `java-1.8-dredd` - Java language plugin

It does **not** currently include `javaparser-1.8-dredd`; install that package
separately when you want the AST-based Java parser.

## Usage

After installation, all included plugins are automatically available:

```bash
# List available plugins
semver-dredd plugin list

# Use with any supported language
semver-dredd snapshot --plugin python --path ./mypackage --version 1.0.0
semver-dredd snapshot --plugin go --path ./mygomodule --version 1.0.0
semver-dredd snapshot --plugin java --path ./src/main/java --version 1.0.0
```

## Requirements

- Python 3.10+
- For Go plugin: Go 1.20+
- For Java plugin: JDK 1.8+
