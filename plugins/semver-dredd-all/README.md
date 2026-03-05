# semver-dredd-all

Meta-package that installs semver-dredd with all official language plugins.

## Installation

```bash
pip install semver-dredd-all
```

This will install:
- `semver-dredd` - Core library
- `python-3.10-dredd` - Python language plugin
- `go-1.20-dredd` - Go language plugin
- `java-1.8-dredd` - Java language plugin

## Usage

After installation, all plugins are automatically available:

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
