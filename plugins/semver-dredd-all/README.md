# semver-dredd-all

Meta-package that installs semver-dredd with all official language plugins.

## Installation

```bash
pip install semver-dredd-all
```

This will install:
- `semver-dredd` - Core library
- `semver-dredd-python` - Python language plugin
- `semver-dredd-go` - Go language plugin
- `semver-dredd-java` - Java language plugin

## Usage

After installation, all plugins are automatically available:

```bash
# List available plugins
semver-dredd plugin list

# Use with any supported language
semver-dredd snapshot --lang python --path ./mypackage --version 1.0.0
semver-dredd snapshot --lang go --path ./mygomodule --version 1.0.0
semver-dredd snapshot --lang java --path ./src/main/java --version 1.0.0
```

## Requirements

- Python 3.10+
- For Go plugin: Go 1.20+
- For Java plugin: JDK 11+
