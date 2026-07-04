# semver-dredd-all

Meta-package that installs `semver-dredd` plus the core set of official plugin
packages bundled by this repo.

## Installation

```bash
# Install all official plugins via the core package extra
pip install "semver-dredd[all]"

# Or install the meta-package directly
pip install semver-dredd-all
```

This installs:
- `semver-dredd` - Core library
- `python-3.10-dredd` - Python language plugin
- `go-1.20-dredd` - Go language plugin
- `java-1.8-dredd` - Java language plugin
- `javaparser-1.8-dredd` - JavaParser-based Java language plugin

## Usage

After installation, all included plugins are automatically available:

```bash
# List available plugins
semver-dredd plugin list
semver-dredd plugin info python

# Use with any supported language
semver-dredd snapshot --plugin python --path mypackage --version 1.0.0
semver-dredd snapshot --plugin go --path ./mygomodule --version 1.0.0
semver-dredd snapshot --plugin java --path ./src/main/java --version 1.0.0
```

Plugin inspection remains under the `plugin` command group; use
`semver-dredd plugin list` rather than a top-level `semver-dredd list` alias.

## Requirements

- Python 3.10+
- For Go plugin: Go 1.20+
- For Java plugin: JDK 1.8+
