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

## Scope (implemented)

`include`/`exclude` items are module/package dotted names, matched recursively
against discovered submodule dotted names (`_matches_scope_item`). When the
root module defines `__all__`, scope recursion is skipped and only
`__all__`-listed names are used (matches plain Python visibility). Otherwise
`_discover_submodule_names()` walks public (non `_`-prefixed) submodules via
`pkgutil.walk_packages`, `_resolve_scan_targets()` applies include (allow-list)
then exclude, and `_build_snapshot()` merges member dicts across targets,
logging (and keeping the first occurrence of) any name collisions. No new
`plugin_options` were added — see README for the exact syntax and tests in
`tests/test_python_plugin_scope.py` / `tests/fixtures/python_scope/`.

