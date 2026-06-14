# Agent Notes — `semverdredd/` Core Package

This directory is the importable core library. Keep it language-agnostic.

## Core responsibilities

- Public programmatic API in `__init__.py`:
  - `compare()`
  - `compare_and_suggest()`
  - plugin/snapshot/version re-exports
- Plugin contract in `plugin_base.py`:
  - `LanguagePlugin`
  - `SnapshotResult`
- Plugin discovery/registry in `plugin_manager.py`.
- Snapshot UUID registry in `registry.py`.
- Snapshot I/O shim in `snapshot_io.py`.
- Version parsing/incrementing in `version.py`.
- Diff delegation in `diff.py`.

## Architecture invariants

- Core does **not** understand functions/classes/endpoints/commands. Snapshot
  types do.
- Diffing is delegated to `old_snapshot.diff_against(new_snapshot)` via the
  `Comparable` protocol.
- `LanguagePlugin.generate_snapshot(path, version, options=None)` is the main
  plugin boundary.
- `path` is deliberately opaque to the framework. Default `validate_path()` only
  checks existence; plugins may interpret paths as modules, dirs, files, URLs,
  etc.
- `plugin_options` must remain opaque to core.
- Custom snapshot classes are discovered through each plugin's
  `snapshot_format_class` and registered by UUID.

## File notes

- `__init__.py` intentionally does **not** eagerly load plugins to avoid circular
  imports. Plugin loading is lazy via `PluginManager.get/list_plugins()`.
- `plugin_manager.py` prefers Python entry points under
  `semver_dredd.plugins`. Built-in fallback specs only cover repo-bundled
  official plugins for editable/dev checkouts (`python`, `go`, `java`), not
  `javaparser`.
- `registry.py` falls back to `NormalizedSnapshot` when `snapshot_type_id` is
  absent or unknown; this preserves older snapshot compatibility.
- `version.py` supports `date` patch scheme (`YYYYMMDDZZZ`) and conventional
  `integer` patch scheme.

## Style guidelines

- Keep this package mostly free of CLI printing. Use exceptions or return data;
  `cli/` handles user-facing output.
- Avoid importing plugin packages from core except through plugin discovery.
- Preserve Python 3.10 compatibility.
- Prefer clear, small pure functions. Avoid side effects at import time except
  idempotent built-in snapshot registration.

## Scope/proposal integration points

- Programmatic API already forwards `options` from `compare()` to plugins.
- CLI config plumbing lives in `cli/config.py`, not here.
- Multi-document `.semver.yaml` candidate selection likely needs coordination
  between `cli/config.py`, `cli/__init__.py`, and plugin validation; avoid
  putting CLI-specific resolution directly in `semverdredd/` unless exposed as
  a clean helper.
- A future core `bundle` plugin could live here as `bundle_plugin.py`, but it
  should still implement the normal `LanguagePlugin` and `SnapshotFormat`/
  `Comparable` contracts.
