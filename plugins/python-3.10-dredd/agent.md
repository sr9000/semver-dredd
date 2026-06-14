# Agent Notes — Python Plugin (`python-3.10-dredd`)

Key `python` · entry `semver_dredd_python:PythonPlugin` · impl
`semver_dredd_python/plugin.py`.

## How it works

- Runtime import + `inspect` introspection; accepts module names or filesystem
  paths to a package/file. Directories require `__init__.py` (`validate_path()`).
- Builds `PythonSnapshot` (variables, functions, types); `PythonArgument` carries
  calling-convention flags. Diffing converts to `NormalizedSnapshot` and delegates.

## Implementation details

- `_import_module()` temporarily inserts a filesystem parent into `sys.path`.
- `_build_snapshot()` iterates `dir(module)`, skips `_`-prefixed names and imported
  objects (`obj.__module__ != module.__name__`).
- `__init__` is included; other private methods skipped.
- Variables are serialized but ignored by current normalized diff conversion.

## Commands

```bash
pip install -e plugins/python-3.10-dredd
semver-dredd snapshot --plugin python --path example.py.pygeometry1 --version 1.0.0
bash example/demo_python.sh
```

## Scope (not yet implemented)

Likely first target: match scope against module + fully-qualified object names;
preserve no-scope behavior; fail clearly when `include` matches nothing. Runtime
import has side-effect risk — do NOT add broader submodule importing without an
explicit option/product decision (e.g. `plugin_options.import_submodules`).
