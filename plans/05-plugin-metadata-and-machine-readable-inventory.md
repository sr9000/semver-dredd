# Plugin Metadata and Machine-Readable Inventory

## Motivation

Plugin discovery should be useful both to humans and automation. Core should be
able to ask plugins about optional capabilities without expanding the minimal
`LanguagePlugin` contract in a breaking way.

## Touched Files

- `semverdredd/plugin_base.py`
- `semverdredd/plugin_manager.py`
- `cli/commands/plugin.py`
- official plugin `plugin.py` files
- official plugin `README.md` files
- `HOWTO.md`
- `tests/test_plugin_manager.py`
- `tests/test_cli.py`

## Commit-Sized Steps

### 1. Add optional feature discovery

- Add a backward-compatible optional hook, for example `have(feature: str) ->
  bool` or a metadata property with feature flags.
- Ensure existing third-party plugins without the hook still work.
- Document that feature discovery is optional and not part of the minimal
  versioning contract.

Definition of Done:

- Tests cover plugins with and without the hook.
- Type hints remain Python 3.10-friendly.

### 2. Add structured plugin metadata

Metadata should be able to describe:

- plugin name;
- snapshot type ID/class if available;
- scope syntax;
- supported `plugin_options`;
- external tools/runtime requirements;
- feature flags;
- package/version/source if discoverable.

Definition of Done:

- Official plugins expose useful metadata.
- Missing metadata degrades gracefully for third-party plugins.

### 3. Add machine-readable plugin list/info output

- Add `semver-dredd plugin list --json` and `--yaml`.
- Add `semver-dredd plugin info NAME --json` and `--yaml`.
- Keep human-readable output as the default.
- Do not add `plugin scaffold`.

Definition of Done:

- Tests assert valid JSON/YAML shape and stable key names.
- Human-readable output still includes installed plugin names.

### 4. Document plugin inventory as a stable interface

- Update HOWTO with metadata examples for plugin authors.
- Update official plugin READMEs with scope and option metadata.
- Decide later whether a top-level `semver-dredd list` alias is worth adding;
  do not block this phase on the alias.

Definition of Done:

- Docs describe current command names and do not imply an unimplemented alias.
