# Complete semver-dredd Tool Gap Report

**Date:** 2026-06-14  
**Scope:** repository state after the include/exclude investigation, plus the
requirements clarified in `reports/Answers semver-dredd.md`.

## Executive Summary

The provided answers are enough to define a coherent **pre-1.0 complete scope**
for semver-dredd.

The current repository already has the most important architectural foundation:

- a domain-agnostic `LanguagePlugin` contract;
- entry-point plugin discovery;
- custom snapshot classes dispatched by top-level `snapshot_type_id`;
- snapshot-owned diff logic through `Comparable.diff_against()`;
- CLI/programmatic snapshot generation and version suggestion;
- single-document `.semver.yaml` parsing;
- environment/config/CLI precedence for implemented fields;
- forwarding of `include`, `exclude`, and `plugin_options` into plugin
  `generate_snapshot(..., options=...)` calls.

The missing work is therefore not a rewrite of the core idea. It is mostly a
set of pre-1.0 productization gaps:

1. make the CLI config-driven enough for `init .`, then pathless `status` and
   `bake`;
2. implement multi-document config candidate resolution;
3. make official plugins honor their documented scope options;
4. add traceability and observability so users can understand selected config,
   selected plugin, and matched API surface;
5. add the built-in `bundle` plugin;
6. update docs/tests so planned behavior becomes executable and stable before
   1.0.

Until those items are implemented, README/HOWTO should continue to mark them as
planned rather than shipped.

## Current Implemented Foundation

### Core and Snapshot Architecture

Implemented today:

- `LanguagePlugin` is intentionally small: name, optional validation, snapshot
  generation, optional custom snapshot class.
- Snapshot loading is registry-based, keyed by top-level `snapshot_type_id`.
- Plugins can use `NormalizedSnapshot`, but are not forced to. Any snapshot that
  implements `SnapshotFormat` and `Comparable.diff_against()` can define its own
  domain model and compatibility rules.
- `DiffResult` is small and domain-agnostic: `change_kind`, `breaking`, and
  `added`.
- Programmatic `compare()` and `compare_and_suggest()` forward caller-provided
  `options` to plugins.

This already supports the desired long-term model where semver-dredd can handle
non-code API surfaces such as OpenAPI, protobuf, gRPC, CLI help output, or
aggregate bundles through plugins.

### Configuration Plumbing

Implemented today:

- `.semver.yaml`, `.env`, shell environment, and CLI arguments are merged with
  CLI at highest priority for implemented fields.
- The actual environment variable for plugin selection is
  `SEMVER_DREDD_PLUGIN`.
- `include`, `exclude`, and `plugin_options` are parsed by `cli/config.py` and
  forwarded through `args.snapshot_options` into CLI snapshot generation.
- `plugin_options` remains opaque to core.

Important current limitation:

- current `include` and `exclude` parsing coerces values to `list[str]`;
  target pre-1.0 behavior should only require those keys to be arrays and must
  allow plugin-specific item shapes, including object items.

### CLI and Plugin Baseline

Implemented today:

- `init`, `status`, `bake`, `compare`, `snapshot`, `bump`, `patch`, `template`,
  and `plugin` subcommands exist.
- `plugin list` and `plugin info` exist.
- Official plugins exist for Python, Go, regex Java, and JavaParser.
- Official plugins accept the `options` parameter.

Important current limitation:

- official plugins currently ignore `include`, `exclude`, and `plugin_options`
  for analysis behavior. This includes `python`, `go`, regex `java`, and
  `javaparser`.

## Gap 1 — Config-Driven CLI Workflow

### Target Behavior

The target first-run workflow is:

```bash
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

Rules clarified by the user:

- `--plugin` is required for `init`.
- `init` writes the plugin and analyzed source path into `.semver.yaml`.
- Later `status` and `bake` can omit the path and plugin by using config.
- If the source path differs from the remembered path, use `--path`.
- `--plugin` always takes precedence over config and must warn when it differs.
- `snapshot` should read version from the configured `VERSION` file by default
  and read plugin/path from config, while explicit flags override.
- `init` should support a version-file path override so config can record where
  the version is stored.

### Current Gap

Current CLI still requires positional source arguments for `init`, `status`, and
`bake`, and `snapshot` requires explicit `--plugin`, `--path`, and `--version`.
Config is loaded before command-specific path/plugin resolution, so the CLI does
not yet have a unified command context that can answer:

- which config file is active;
- which source path is active;
- which plugin was selected and from which precedence layer;
- which version file should be read;
- which command-line value is overriding which config value.

### Required Work

1. Add a command-resolution layer after argument parsing.
2. Store `source.path` in config during `init`.
3. Make `status` and `bake` accept an omitted source when config provides one.
4. Add/standardize `--path` as the explicit source override for commands that
   can use config path defaults.
5. Make `snapshot` default plugin/path/version from config and `VERSION` file.
6. Emit warnings for plugin/path collisions where explicit values override
   config.
7. Add tests for current explicit workflow and planned config-driven workflow.

## Gap 2 — `--config` Modes and Precedence

### Target Behavior

Users should be able to select modes by config file:

```bash
semver-dredd status --config .semver.yaml
semver-dredd status --config .semver.dev.yaml
semver-dredd status --config .semver.my-custom_mode.yaml
```

Precedence must be:

```text
CMDARGs -> ENVs -> CONFIG
```

For scope overrides:

- `--include` and `--exclude` append to config arrays;
- collisions warn;
- `--override` makes command-line include/exclude replace config arrays.

### Current Gap

The current loader always targets the default config path and supports only the
implemented fields. There are no general `--config`, `--include`, `--exclude`,
or `--override` semantics for the main workflow.

### Required Work

1. Add global `--config` support before config loading.
2. Ensure `.env` and shell environment are merged after the selected config.
3. Add CLI include/exclude flags as advanced usage.
4. Implement append-vs-replace behavior and collision warnings.
5. Document mode-based workflows and test every precedence layer.

## Gap 3 — Multi-Document `.semver.yaml` Candidate Resolution

### Target Behavior

A multi-document config describes one API surface and ordered plugin fallback
candidates. Document order is meaningful.

Example:

```yaml
# shared defaults
source:
  path: ./src/main/java
files:
  version: VERSION
---
plugin: javaparser
include:
  - com.example.api
---
plugin: java
include:
  - com.example.api
```

Rules clarified by the user:

- one multi-doc file is one API surface;
- candidate order defines fallback order;
- plugins of the same language may produce compatible snapshots, but this is a
  recommendation, not a hard requirement;
- if a baseline was baked with one plugin and status/bake later uses another,
  best effort is acceptable, but conflicts/assumptions/ignored data must be
  logged;
- selected plugin source should be traced in snapshots;
- if no candidate validates, error output must list every attempted candidate
  and its failure reason;
- `--plugin` / `SEMVER_DREDD_PLUGIN` override should fail if the requested
  plugin is not present in any candidate document;
- merge rules:
  - missing fields are added;
  - existing objects are deep-merged;
  - arrays are merged;
  - scalars replace;
  - `null` overwrites shared defaults and removes candidate-specific values.

### Current Gap

`cli/config.py` currently uses single-document `yaml.safe_load()`. Config is
resolved before the command has enough context for candidate validation. This is
not enough for multi-doc candidate selection because selection depends on:

- selected source path;
- installed plugins;
- plugin `validate_path()` result;
- explicit plugin override from CLI/env.

### Required Work

1. Parse with `yaml.safe_load_all()`.
2. Represent raw config documents before merging.
3. Add a resolver that receives command context: source path, plugin override,
   selected config path, and environment values.
4. Implement documented merge semantics.
5. Validate candidates in order and record failure reasons.
6. Fail clearly when override plugin is absent from candidates.
7. Add trace output in logs and snapshots.
8. Preserve single-document compatibility.

## Gap 4 — Scope Model (`include` / `exclude`)

### Target Behavior

Core requirement:

- `include` and `exclude` are arrays.
- Item syntax is plugin-specific.
- Items may be strings or objects if a plugin supports them.
- Dot-separated strings are a recommendation where natural, not a universal
  requirement.

Recommended cross-plugin behavior:

- empty `include` means the whole configured `path` API surface;
- non-empty `include` means allow-list mode;
- `exclude` is applied after `include`;
- include is recursive by default;
- exclude may support `*` for explicit nested matching where meaningful;
- invalid patterns and match-nothing behavior are plugin-specific, with warning
  recommended.

Example:

```yaml
include:
  - api/v1
  - api/experimental
exclude:
  - api/v1/admin
  - api/experimental/*
```

### Current Gap

Core currently forwards scope values, but official plugins ignore them. Also,
the current config parser narrows arrays to strings, which is stricter than the
pre-1.0 target.

### Required Work

1. Change config model to allow `list[Any]` for `include` and `exclude` while
   still validating that the top-level values are arrays.
2. Update tests that currently expect string coercion.
3. Implement official plugin semantics and docs.
4. Add CLI and plugin logs for matched/ignored patterns at the appropriate
   verbosity level.

## Gap 5 — Official Plugin Scope Behavior

### Python Plugin

Target behavior:

- `include` matches module/package names only, not filesystem paths.
- Entities starting with `_` are ignored.
- Respect `__all__` when present.
- If `__all__` is missing, recursively scan module files/subfolders, import
  collected module paths separately, introspect each, merge results, and log
  collisions.
- Do not add `plugin_options.import_submodules` or `static_analysis`; recursion
  and analysis method are part of the plugin’s nature.

Current gap:

- the plugin imports one module and introspects visible members;
- it does not recursively discover unimported submodules;
- it does not use include/exclude;
- collision handling for recursively merged modules does not exist.

### Java and JavaParser Plugins

Target behavior:

- `include` matches Java package prefixes;
- regex Java and JavaParser are separate plugins;
- neither is a universal default except as selected by config/candidate order;
- classpath/source-level settings remain plugin-specific `plugin_options` and
  are orthogonal to scope.

Current gap:

- both plugins ignore include/exclude;
- parser output and snapshot generation need package-prefix filtering;
- plugin docs and `plugin info` do not describe supported scope syntax.

### Go Plugin

Target behavior:

- `include` matches Go import paths;
- package-level filtering is enough;
- tests are never API surface;
- `--path` is a root; the plugin resolves include/exclude relative to it.

Current gap:

- the Go parser is invoked for a directory without include/exclude filtering;
- package-root-plus-include-list analysis is not implemented;
- test exclusion policy should be explicit and tested.

## Gap 6 — Observability Instead of `doctor`

### Target Behavior

No `doctor` command is desired. Logging/verbosity should expose what happened:

| Level | Meaning |
|-------|---------|
| default | errors and warnings only |
| `-v` | info-level, O(1) logs once per tool call |
| `-vv` | debug-level, O(n) logs for every candidate/plugin/include/API member |
| `-vvv` | debug-level plus explicit argument/config dump |

### Current Gap

Current CLI has limited command-specific verbosity, including `compare
--verbose`, but not a uniform global verbosity model.

### Required Work

1. Add a global counted verbosity flag.
2. Replace ad-hoc verbose behavior with structured logging helpers.
3. Define log events for config selection, plugin selection, scope matching,
   candidate fallback, snapshot compatibility assumptions, and bundle
   dependency decreases.
4. Ensure logs do not become O(n) unless `-vv` or above.

## Gap 7 — Plugin Metadata, Feature Discovery, and Machine-Readable Listing

### Target Behavior

- No `plugin scaffold` command.
- Official plugins are both working implementations and examples.
- Add optional plugin feature discovery, e.g. `plugin.have("feature name")`, so
  core can use optional plugin capabilities without making them part of the
  minimal versioning contract.
- Plugins should document include/exclude semantics in plugin info.
- Plugin listing should enumerate installed plugins; `--json` or `--yaml`
  should provide machine-readable descriptions.
- A future `semver-dredd list` alias may expose plugin inventory more directly.

### Current Gap

- `plugin list` and `plugin info` exist, but plugin metadata is minimal.
- No feature discovery hook exists.
- No machine-readable plugin listing is documented as a stable interface.

### Required Work

1. Extend the plugin API with optional feature discovery while preserving
   compatibility for existing plugins.
2. Add structured plugin metadata: scope syntax, supported options, snapshot
   type, external tools, feature flags.
3. Add `--json` / `--yaml` output for plugin list/info.
4. Update HOWTO and plugin README files.

## Gap 8 — Built-In `bundle` Plugin

### Target Behavior

`bundle` is a built-in plugin that tracks other `VERSION` files through
`include`.

Configuration:

```yaml
plugin: bundle
include:
  - ./backend/VERSION
  - ./sdk-python/VERSION
  - ./cli/VERSION
```

Rules clarified by the user:

- use `include` for VERSION file paths;
- do not use a dependency map in `plugin_options` as the primary interface;
- no globs;
- dependency/member names are derived by the plugin as fully qualified names;
- missing VERSION file is a hard error;
- added dependency is `MINOR`;
- removed dependency is `BREAKING`;
- version decreases are meaningful and must warn:
  - patch decrease → `PATCH`;
  - minor decrease → `BREAKING`;
  - major decrease → `BREAKING`;
- snapshots should store dependency paths as well as names.

### Current Gap

No `bundle` plugin exists. There is also no built-in core plugin entry point.

### Required Work

1. Add `BundlePlugin` and `BundleSnapshot`.
2. Register `bundle` through core package entry points or a clearly documented
   built-in fallback path.
3. Implement VERSION file reading and dependency identity derivation.
4. Store dependency name, path, and version in snapshots.
5. Implement diff rules including decreases and warnings.
6. Add tests for added/removed/up/down/no-change dependencies.
7. Document bundle workflow after config-driven pathless commands exist.

## Gap 9 — Snapshot Traceability

### Target Behavior

Snapshots should trace plugin source/selection, especially when multi-document
fallback is possible. At minimum, snapshots should make it possible to answer:

- which plugin generated this snapshot;
- which plugin version generated it;
- whether it came from an entry point, built-in fallback, or another source;
- which config candidate was selected if relevant.

### Current Gap

Snapshots have language/source/API fields, but plugin-selection provenance is
not uniformly represented as a stable schema element.

### Required Work

1. Define a stable `plugin` or `generator` metadata block in snapshot examples
   and schema docs.
2. Update official snapshots.
3. Ensure older snapshots remain loadable.
4. Include plugin mismatch/compatibility assumptions in logs.

## Gap 10 — Documentation and Tests

### Documentation Gaps

Current docs need to keep a strict distinction between implemented behavior and
target behavior. The following docs should remain synchronized:

- `README.md` — user-facing current/target workflow;
- `HOWTO.md` — plugin author contract and scope semantics;
- `INCLUDE-EXCLUDE-PROPOSAL.md` — proposal/status and resolved decisions;
- `docs/schema.md` — snapshot envelope and traceability;
- plugin README files — exact include/exclude and plugin_options behavior.

### Test Gaps

Missing tests should cover:

- multi-doc parsing and candidate fallback;
- config/env/CLI precedence, including `SEMVER_DREDD_PLUGIN`;
- config-driven pathless `status` and `bake`;
- `snapshot` defaults from config and VERSION;
- include/exclude array validation with non-string items preserved;
- official plugin scope behavior;
- verbosity levels;
- plugin metadata JSON/YAML output;
- bundle plugin diff matrix;
- snapshot plugin provenance.

## Suggested Implementation Order

1. **CLI resolution foundation**: `--config`, `source.path`, pathless
   `status`/`bake`, snapshot defaults, precedence warnings.
2. **Config model update**: raw documents, `safe_load_all()`, merge semantics,
   `list[Any]` include/exclude.
3. **Observability**: global `-v/-vv/-vvv` logging before complex fallback/scope
   behavior lands.
4. **Python scope filtering**: fastest official plugin path to usable scoped
   analysis.
5. **Java/JavaParser and Go scope filtering**: package-prefix/import-path
   semantics with tests.
6. **Plugin metadata and machine-readable listing**.
7. **Snapshot traceability**.
8. **Bundle plugin**.
9. **Docs/schema/plugin README synchronization**.

## Remaining Open Details

The user answers are enough for complete product scope. Remaining choices are
implementation details, not product blockers:

- exact internal shape of raw/resolved config classes;
- exact snapshot metadata key names for plugin provenance;
- exact structured logging implementation;
- exact plugin metadata schema for JSON/YAML output;
- exact FQN derivation algorithm for bundle dependencies;
- whether `semver-dredd list` is added as a top-level alias or plugin listing
  remains under `semver-dredd plugin list` with machine-readable flags.

## Conclusion

semver-dredd is already architecturally aligned with the desired complete tool:
the framework delegates API understanding and diff semantics to plugins, while
core owns orchestration, config, snapshots, and version math.

The project is still `0.x.x`, so the remaining behavior changes can be made
directly without compatibility shims. The most important discipline before 1.0
is to stabilize the top-level config keys outside `plugin_options`, implement
the official plugin behaviors those keys imply, and keep docs explicit about
what is shipped versus planned.
