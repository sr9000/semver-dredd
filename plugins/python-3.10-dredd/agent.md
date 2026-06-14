# Agent Notes — Python Plugin (`python-3.10-dredd`)

Plugin key: `python`  
Entry point: `semver_dredd_python:PythonPlugin`  
Implementation: `semver_dredd_python/plugin.py`

## How it works

- Uses runtime import + `inspect` introspection.
- Accepts Python module names or filesystem paths to a package/file.
- For directories, `validate_path()` requires `__init__.py`.
- Builds a custom `PythonSnapshot` with variables, functions, and types.
- Uses `PythonArgument` to capture Python calling convention flags.
- Diffing converts `PythonSnapshot` to `NormalizedSnapshot` and delegates.

## Important implementation details

- `_import_module()` temporarily inserts a filesystem parent into `sys.path` for
  path-based imports.
- `_build_snapshot()` iterates `dir(module)`, skips names starting with `_`, and
  skips imported objects where `obj.__module__ != module.__name__`.
- `__init__` methods are included; other private methods are skipped.
- Variables are serialized but current normalized diff conversion ignores
  variables.

## Commands

```bash
pip install -e plugins/python-3.10-dredd
semver-dredd plugin list
semver-dredd snapshot --plugin python --path example.py.pygeometry1 --version 1.0.0
bash example/demo_python.sh
```

## Scope-related notes

The plugin currently receives `options` but does not use `include`, `exclude`,
or `plugin_options`.

Likely first implementation target:

- match scope against module names and fully-qualified object names;
- preserve current behavior when no scope is configured;
- fail clearly when `include` is non-empty and matches nothing;
- consider a future `plugin_options.import_submodules` if users expect package
  includes to scan submodules not imported by `__init__.py`.

Runtime import has side-effect risk. Do not add broader submodule importing
without an explicit option or product decision.
