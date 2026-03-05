# python-3.10-dredd

Python 3.10+ language plugin for semver-dredd.

> **Package renamed:** This package was formerly published as `semver-dredd-python`.
> The importable module name (`semver_dredd_python`) and the CLI plugin key (`python`) are unchanged.

## Installation

```bash
pip install python-3.10-dredd
```

Or install from local path (development):

```bash
pip install ./plugins/semver-dredd-python
```

## Usage

Once installed, the plugin is automatically discovered by semver-dredd:

```bash
# List plugins to verify installation
semver-dredd plugin list

# Generate snapshot for a Python package
semver-dredd snapshot --plugin python --path ./mypackage --version 1.0.0

# Use with init/status/bake commands
semver-dredd init ./mypackage
semver-dredd status ./mypackage
```

## How it works

This plugin uses Python's `inspect` module to introspect Python modules and extract:

- Public functions and their signatures
- Public classes, their methods, and fields
- Support for dataclasses, namedtuples, Pydantic models, and `__slots__`

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
