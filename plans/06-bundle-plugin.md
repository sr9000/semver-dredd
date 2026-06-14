# Built-In Bundle Plugin

## Motivation

The built-in `bundle` plugin lets semver-dredd track an aggregate API surface
made of other `VERSION` files. It validates semver movement across components
without requiring a language parser.

Example config:

```yaml
plugin: bundle
include:
  - ./backend/VERSION
  - ./sdk-python/VERSION
  - ./cli/VERSION
```

## Touched Files

- `semverdredd/plugin_manager.py`
- `semverdredd/plugin_base.py` if built-in source metadata needs support
- new built-in plugin module, likely under `semverdredd/` or a clearly named
  core subpackage
- `snapshot/` or plugin-local snapshot model files, depending on chosen layout
- `cli/config.py` only if bundle needs path resolution support beyond existing
  include forwarding
- `tests/test_plugin_manager.py`
- new bundle plugin tests
- `README.md`
- `HOWTO.md`
- `docs/schema.md`

## Commit-Sized Steps

### 1. Decide and document built-in registration path

- Register `bundle` through package entry points or a documented built-in
  fallback in plugin discovery. Note the existing machinery in
  `semverdredd/plugin_manager.py`: discovery uses the entry-point group
  `semver_dredd.plugins`, and there is already a `_BUILTIN_FALLBACK_SPECS` list
  plus an `origin="builtin"` registration path and a `PluginInfo.origin` field
  (`entry_point|user_dir|builtin|manual`). The current fallback only triggers
  when a bundled plugin *package* is importable but lacks dist metadata, so
  `bundle` (which ships inside core, not as a separate package) likely needs an
  always-on built-in registration rather than reusing that import-guarded list.
- Ensure built-in discovery reports source as `builtin` (matching the existing
  `PluginInfo.origin` value) for snapshot provenance.
- Avoid special-casing bundle behavior elsewhere in core.

Definition of Done:

- `semver-dredd plugin list` shows `bundle` without installing an external
  plugin package.
- Tests cover coexistence with entry-point plugins.

### 2. Add `BundlePlugin` snapshot generation

- Read dependency VERSION file paths from `include`.
- Reject globs and missing files as hard errors.
- Derive fully qualified dependency/member names deterministically.
- Store dependency name, path, and parsed version in snapshots.

Definition of Done:

- Tests cover valid includes, missing file errors, glob rejection, and stable
  name/path/version serialization.

### 3. Add `BundleSnapshot.diff_against()`

Implement the diff matrix:

- added dependency -> `MINOR`;
- removed dependency -> `BREAKING`;
- patch increase -> `PATCH`;
- minor increase -> `MINOR`;
- major increase -> `BREAKING`;
- patch decrease -> `PATCH` plus warning;
- minor decrease -> `BREAKING` plus warning;
- major decrease -> `BREAKING` plus warning;
- no change -> `NONE`.

Definition of Done:

- Table-driven tests cover added, removed, up, down, and no-change dependencies.
- Decrease warnings are emitted through the observability layer.

### 4. Integrate bundle with config-driven workflows

- Ensure pathless `status`, `bake`, and `snapshot` work with `plugin: bundle`.
- Ensure include paths resolve predictably relative to selected config/source
  context.
- Document bundle after config-driven pathless commands are shipped.

Definition of Done:

- End-to-end CLI tests cover bundle init/status/bake or equivalent configured
  workflow.
