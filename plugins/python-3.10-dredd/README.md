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
pip install ./plugins/python-3.10-dredd
```

## Usage

Once installed, the plugin is automatically discovered by semver-dredd:

```bash
# List plugins to verify installation
semver-dredd plugin list
semver-dredd plugin info python

# Generate a snapshot for an importable module/package
semver-dredd snapshot --plugin python --path mypackage --version 1.0.0

# Use with init/status/bake commands
semver-dredd init mypackage --plugin python --version 1.0.0
semver-dredd status mypackage --plugin python
semver-dredd bake mypackage --plugin python
```

For the Python plugin, `--path`/positional source values are importable module
or package names (for example `mypackage` or `mypackage.api`), not filesystem
globs.

If `.semver.yaml` already records `plugin: python` and `source.path`, follow-up
commands can often omit the explicit path/plugin:

```bash
semver-dredd status --details
semver-dredd bake
```

## How it works

This plugin uses Python's `inspect` module to introspect Python modules and extract:

- Public functions and their signatures
- Public classes, their methods, and fields
- Support for dataclasses, namedtuples, Pydantic models, and `__slots__`

## Scope: `include` / `exclude`

`include` and `exclude` items are module/package dotted names (not filesystem
globs), matched recursively (an item matches itself and any of its
dotted-prefix descendants):

```yaml
include: [mypackage.api]
exclude: [mypackage.api.internal]
```

- Empty `include` (or omitted) analyzes the whole configured module's API
  surface, exactly as without scope.
- A non-empty `include` switches to allow-list mode: only listed
  modules/submodules (and their descendants) are analyzed.
- `exclude` is applied after `include`.
- If the root module defines `__all__`, scope recursion is skipped entirely —
  only the names listed in `__all__` are analyzed, matching plain Python
  visibility rules. `include`/`exclude` do not apply in this mode.
- If `__all__` is absent, the plugin recursively discovers public (non
  `_`-prefixed) submodules and merges their public members into the
  snapshot. `include` matching nothing produces an empty snapshot API
  (logged as a warning) rather than falling back to no-scope behavior.

## Requirements

- Python 3.10+
- semver-dredd >= 0.1.0
