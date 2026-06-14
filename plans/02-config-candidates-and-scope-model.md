# Config Candidates and Scope Model

## Motivation

The project needs stable config semantics before official plugins rely on
include/exclude and before multi-document fallback becomes user-visible. This
phase changes config parsing from a single resolved document into raw documents
plus a resolver that can validate plugin candidates in command context.

## Touched Files

- `cli/config.py`
- `cli/__main__.py`
- `cli/utils.py`
- `semverdredd/plugin_manager.py`
- `semverdredd/plugin_base.py` if validation typing changes are needed
- `tests/test_config.py`
- `tests/test_cli.py`
- `tests/test_plugin_manager.py` if candidate validation touches discovery
- `README.md`
- `INCLUDE-EXCLUDE-PROPOSAL.md`

## Commit-Sized Steps

### 1. Preserve plugin-specific scope item shapes

- Change the config model for `include` and `exclude` from `list[str]` to
  `list[Any]`.
- Validate only that top-level values are arrays.
- Stop coercing items to strings.
- Keep `plugin_options` opaque.

Definition of Done:

- Tests prove strings, numbers, and object items are preserved exactly.
- Tests prove non-array `include`/`exclude` fails with a helpful error.
- Existing option forwarding tests still pass.

### 2. Parse raw multi-document configs

- Replace single-document `yaml.safe_load()` with `yaml.safe_load_all()`.
- Represent documents before merge as raw config documents with index/source
  metadata.
- Keep a one-document file semantically equivalent to current config.

Definition of Done:

- Tests prove one-document configs load as before.
- Tests prove document order is preserved for multi-doc files.

### 3. Implement documented merge semantics

Merge shared defaults and candidate documents with these rules:

- missing fields are added;
- objects are deep-merged;
- arrays are merged;
- scalars replace;
- `null` removes/overwrites inherited values.

Definition of Done:

- Table-driven tests cover nested objects, arrays, scalars, and null removals.
- Merge behavior is isolated enough to test without invoking the CLI.

### 4. Add candidate resolver in command context

- Feed the resolver selected config path, resolved source path, plugin override
  from CLI/env, and installed plugins.
- Validate candidates in order using plugin availability and `validate_path()`.
- Record every candidate attempt and failure reason.
- Preserve best-effort compatibility when later comparing snapshots produced by
  different plugins, but surface assumptions through the logging layer in phase 3.

Definition of Done:

- Tests cover first-valid candidate selection.
- Tests cover all-candidates-fail output listing every attempted candidate.
- Tests cover absent plugin entries and plugin validation failures separately.

### 5. Implement plugin override rules for candidates

- If `--plugin` or `SEMVER_DREDD_PLUGIN` is set, select only a candidate whose
  document names that plugin.
- If the requested plugin is not present in any candidate document, fail clearly.
- Preserve precedence: CLI plugin override beats environment override, which
  beats config candidate order.

Definition of Done:

- Tests cover CLI override, environment override, absent override plugin, and
  override candidate validation failure.

### 6. Document mode and candidate workflows

- Document `--config .semver.dev.yaml` and similar mode workflows.
- Document one API surface per multi-doc file.
- Document candidate fallback order and override failure semantics.

Definition of Done:

- README/HOWTO/proposal docs agree on shipped config behavior.
- Planned-only claims are removed only after tests prove behavior.
