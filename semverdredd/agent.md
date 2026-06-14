# Agent Notes — `semverdredd/` (core library)

Importable core. Keep it **language-agnostic**.

## Files

- `__init__.py` — public API: `compare()`, `compare_and_suggest()`, plugin/
  snapshot/version re-exports. Does **not** eagerly load plugins (avoids circular
  imports); loading is lazy via `PluginManager.get/list_plugins()`.
- `plugin_base.py` — `LanguagePlugin`, `SnapshotResult` contracts.
- `plugin_manager.py` — discovery. Prefers entry points in `semver_dredd.plugins`;
  built-in fallback specs cover only repo-bundled `python`/`go`/`java` (NOT
  `javaparser`).
- `registry.py` — snapshot UUID registry; falls back to `NormalizedSnapshot` when
  `snapshot_type_id` is missing/unknown (back-compat).
- `snapshot_io.py` — snapshot I/O shim.
- `version.py` — version parse/increment; supports `date` (`YYYYMMDDZZZ`) and
  `integer` patch schemes.
- `diff.py` — diff delegation.

## Invariants

- Core does NOT understand functions/classes/endpoints; snapshot types do.
- Diff is delegated to `old.diff_against(new)` via the `Comparable` protocol.
- Plugin boundary: `generate_snapshot(path, version, options=None)`.
- `path` and `plugin_options` are opaque to core; default `validate_path()` only
  checks existence.
- Custom snapshot classes are registered by UUID via each plugin's
  `snapshot_format_class`.

## Style

- No CLI printing here — raise or return data; `cli/` handles output.
- Don't import plugin packages except through discovery.
- Preserve Python 3.10 compatibility; prefer small pure functions; no import-time
  side effects except idempotent built-in snapshot registration.

## Scope integration

- `compare()` already forwards `options` to plugins.
- CLI config plumbing lives in `cli/config.py`, not here.
- Multi-document `.semver.yaml` selection spans `cli/config.py`, `cli/__init__.py`,
  and plugin validation — don't bake CLI resolution into core unless exposed as a
  clean helper.
- A future core `bundle` plugin could live here (`bundle_plugin.py`) but must
  implement the normal `LanguagePlugin` + `SnapshotFormat`/`Comparable` contracts.
