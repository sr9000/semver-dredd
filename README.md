# semver-dredd

Automatically increments semver number based on interface changes.

## Features

- **Multi-Language Support**: Pluggable architecture for Python, Go, and Java (more coming)
- **API Introspection**: Extracts public API surface from source code via language plugins
- **Change Detection**: Compares two versions of a module/package and classifies the change
  - **BREAKING**: Removed functions/classes/methods/fields, added required parameters
  - **MINOR**: New functions/classes/methods/fields, new optional parameters
  - **PATCH**: No API changes (implementation-only)
  - **NONE**: No changes detected at all
- **Version Management**: Semantic versioning with a date-based patch format (`YYYYMMDDZZZ`)
- **API Snapshots**: YAML-serialized API state with a UUID-based type registry
- **Plugin System**: Discover plugins via entry points, install third-party plugins
- **CLI & Programmatic API**: Use from the command line or import directly in Python

### Feature Status

This README documents both the **current shipped behavior** and the agreed
**pre-1.0 target behavior**. Current behavior is explicitly marked where a
feature is still planned.

| Area | Current status |
|------|----------------|
| Plugin discovery, snapshots, diffing, version suggestions | ✅ Implemented |
| `.semver.yaml` parsing and `.env`/environment/CLI precedence | ✅ Implemented |
| `include` / `exclude` / `plugin_options` forwarding to plugins | ✅ Implemented |
| Plugin-side `include` / `exclude` filtering | 🚧 Planned — official plugins receive these keys but do not honor them yet |
| Multi-document `.semver.yaml` fallback candidates | 🚧 Planned |
| Config remembered `source.path` and pathless `status` / `bake` | 🚧 Planned |
| Built-in aggregate `bundle` plugin | 🚧 Planned |

Detailed status and scope notes live in:

- [`INCLUDE-EXCLUDE-PROPOSAL.md`](INCLUDE-EXCLUDE-PROPOSAL.md)
- [`reports/include-exclude-status.md`](reports/include-exclude-status.md)
- [`reports/include-exclude-usability-and-implementation-plan.md`](reports/include-exclude-usability-and-implementation-plan.md)
- [`reports/complete-semver-tool-gap-report.md`](reports/complete-semver-tool-gap-report.md)

## Installation

```bash
# Core package
pip install semver-dredd

# Install language plugins (pick what you need)
pip install python-3.10-dredd
pip install go-1.20-dredd
pip install java-1.8-dredd
pip install javaparser-1.8-dredd

# Or install the core set of official plugins at once
# (current meta-package covers python/go/java; install javaparser separately)
pip install semver-dredd-all
```

### Development Install

```bash
# Core + all plugins (editable)
poetry install
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
pip install -e plugins/javaparser-1.8-dredd
```

## Quick Start

Current explicit workflow:

```bash
# List available language plugins
semver-dredd plugin list

# Initialize semver-dredd for a Python project
semver-dredd init mymodule --plugin python --version 1.0.0

# Check current API status against the baked baseline
semver-dredd status mymodule --plugin python --details

# Bake current API as the new baseline (after release)
semver-dredd bake mymodule --plugin python
```

Target pre-1.0 workflow (planned): `init` records plugin and source path in
`.semver.yaml`, so later commands can use config defaults:

```bash
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

`--plugin` should always take precedence over config. If a command-line plugin
differs from `.semver.yaml`, the CLI should continue with the explicit value and
log a warning.

Works the same way for Go and Java — just point to a directory and switch
the `--plugin` flag. The regex Java plugin is named `java`; the AST-based
JavaParser plugin is named `javaparser`.

```bash
# Go
semver-dredd init ./pkg/geometry --plugin go --version 1.0.0
semver-dredd status ./pkg/geometry --plugin go --details

# Java
semver-dredd init ./src/main/java --plugin java --version 1.0.0
semver-dredd status ./src/main/java --plugin java --details

# JavaParser
semver-dredd init ./src/main/java --plugin javaparser --version 1.0.0
semver-dredd status ./src/main/java --plugin javaparser --details
```

## Managed Files

semver-dredd manages several files in your project:

| File           | Description                                                    |
|----------------|----------------------------------------------------------------|
| `.semver.yaml` | Configuration (plugin, policies, severity mapping, file paths) |
| `baked.yaml`   | Locked API snapshot — the release baseline                     |
| `current.yaml` | Current API snapshot with suggested next version               |
| `VERSION`      | Plain-text file with the current version string                |

## CLI Commands

### `init` — Initialize project

```bash
# Initialize with an explicit version and plugin
semver-dredd init ./src --plugin go --version 1.0.0
```

Creates `.semver.yaml`, `baked.yaml`, and `VERSION`.

Current implementation still defaults to the Python plugin when `--plugin` is
omitted. Target pre-1.0 behavior is to require `--plugin` for `init`, write the
plugin and analysed source path to `.semver.yaml`, allow `--version-file` to
choose the stored `VERSION` path, and allow plugins to initialize their own
`options` defaults.

### `status` — Check API changes

```bash
# Compare current code against the baked baseline
semver-dredd status mymodule --plugin python

# Show a detailed breakdown of breaking & added changes
semver-dredd status mymodule --details

# Allow breaking changes (exit 0 even on BREAKING)
semver-dredd status mymodule --allow-breaking

# Override the date used for patch version generation
semver-dredd status mymodule --date 2026-06-15
```

Updates `current.yaml` with the current API state and suggested version.

Target pre-1.0 behavior: when `.semver.yaml` contains `source.path`, `status`
can omit the positional path and use config. If a different source is needed,
use an explicit path override.

### `bake` — Lock current API as baseline

```bash
# Auto-compute version from detected changes
semver-dredd bake mymodule --plugin python

# Set an explicit version
semver-dredd bake mymodule --plugin python --version 2.0.0
```

Updates `baked.yaml` and `VERSION`.

Target pre-1.0 behavior: when `.semver.yaml` contains `source.path`, `bake` can
omit the positional path and use config.

### `compare` — Compare two modules directly

```bash
# Compare old vs new (Python modules by name)
semver-dredd compare old_module new_module

# Compare Go packages by path
semver-dredd compare ./v1/pkg ./v2/pkg --plugin go

# With detailed diff and version suggestion
semver-dredd compare old_module new_module --details --current 1.0.0

# Verbose output explaining what's being inspected
semver-dredd compare old_module new_module --verbose
```

### `snapshot` — Generate a standalone API snapshot

```bash
# Print snapshot YAML to stdout
semver-dredd snapshot --plugin python --path mymodule --version 1.0.0

# Write to a file
semver-dredd snapshot --plugin go --path ./pkg --version 1.0.0 --out snapshot.yaml
```

Target pre-1.0 behavior: `snapshot` may read plugin/path from `.semver.yaml` and
version from the configured `VERSION` file by default, while keeping explicit
flags as overrides.

### `bump` — Manually bump version

```bash
semver-dredd bump --current 1.0.0 --change minor
```

### `patch` — Generate patch version

```bash
# Generate a new patch number for today
semver-dredd patch

# Increment from an existing patch
semver-dredd patch --current 20260305001
```

### `template` — Generate configuration template

```bash
# Print comprehensive .semver.yaml template to stdout
semver-dredd template

# Save to file
semver-dredd template --out .semver.yaml
```

### `plugin` — Manage language plugins

```bash
# List all discovered plugins
semver-dredd plugin list

# Planned pre-1.0: machine-readable plugin inventory
semver-dredd plugin list --json
semver-dredd plugin list --yaml

# Show details about a plugin
semver-dredd plugin info python

# Install a plugin (anything pip accepts)
semver-dredd plugin install python-3.10-dredd

# Remove a plugin
semver-dredd plugin remove python
```

Installs are recorded in a manifest (`installed_plugins.json` in the user
plugin directory), so `plugin remove` deletes exactly what an install
created. Plugins installed by other means fall back to best-effort removal
with a clear warning.

## Python API

```python
from semverdredd import compare, compare_and_suggest, ChangeKind, Version

# Compare two Python modules and get a structured result
result = compare("mymodule.v1", "mymodule.v2", plugin="python")
print(result.change_kind)   # ChangeKind.MINOR
print(result.severity)      # "warn"
print(result.diff.added)    # ("function added: volume", ...)
print(result.diff.breaking) # ()

# With automatic version suggestion
result = compare_and_suggest(
    "mymodule.v1", "mymodule.v2",
    current_version="1.0.0",
    plugin="python",
)
print(result.suggested_version)  # 1.1.20260305001

# Works for Go / Java too — pass directory paths
result = compare("./v1/pkg", "./v2/pkg", plugin="go")

# Optional: forward scope/options to the plugin and embed real versions
result = compare(
    "mymodule.v1", "mymodule.v2",
    plugin="python",
    options={"include": ["mymodule.core"], "plugin_options": {"x": 1}},
    old_version="1.0.0",
    new_version="1.1.0",
)
```

## Configuration

semver-dredd supports multiple configuration sources with the following
priority for implemented fields (lowest → highest):

1. **`.semver.yaml`** — Project configuration file
2. **`.env`** — Environment file in project root
3. **Environment variables** — Shell environment
4. **CLI arguments** — Command-line flags (highest priority)

> **Note**: The programmatic API (`compare`, `compare_and_suggest`) ignores
> all config files and uses only the arguments passed directly.

Target pre-1.0 precedence is intentionally the same, expressed as:

```text
CMDARGs -> ENVs -> CONFIG
```

Target pre-1.0 behavior also adds `--config` so workflows can select explicit
modes such as `.semver.yaml`, `.semver.dev.yaml`, or
`.semver.my-custom_mode.yaml`.

### `.semver.yaml`

```yaml
schema_version: 1

# Language plugin (python, go, java)
plugin: python

# Target pre-1.0: init records the analyzed source path here.
# Current status/bake still require a positional path unless otherwise supplied.
# source:
#   path: .

policies:
  allow_breaking_changes: false  # Fail on BREAKING by default

output:
  color: null  # null = auto-detect, true = always, false = never
  severity_by_change:
    none: info     # Green
    patch: info    # Green
    minor: warn    # Yellow
    major: error   # Red (becomes warn when --allow-breaking)

files:
  baked: baked.yaml
  current: current.yaml
  version: VERSION

versioning:
  patch_scheme: date  # "date" (YYYYMMDDZZZ, default) or "integer"

# Analysis scope — forwarded to the plugin via its options dict.
# Target pre-1.0 contract: include/exclude are arrays and each item is
# plugin-specific. Dot-separated strings are only a recommendation where
# natural for the language/domain.
include:
  - mypackage.core
exclude:
  - mypackage.core._private

# Free-form options forwarded to the plugin as-is (never validated
# by the framework)
plugin_options:
  timeout_seconds: 30
```

> Current implementation note: `include` and `exclude` are parsed as string
> lists today. The target pre-1.0 contract is broader: the keys must be arrays,
> but array items may be plugin-specific values or objects.

> The bundled python/go/java/javaparser plugins receive `include`/`exclude`/
> `plugin_options` but do not filter by them yet — see
> [`INCLUDE-EXCLUDE-PROPOSAL.md`](INCLUDE-EXCLUDE-PROPOSAL.md) for status.

### Multi-document config fallback (planned)

Target pre-1.0 behavior: one config file can describe one API surface with
ordered plugin candidates. The first viable candidate wins; `--plugin` or
`SEMVER_DREDD_PLUGIN` may force a candidate and fails if that plugin is absent
from the document list.

```yaml
# Shared defaults
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

Current implementation is still single-document only.

### `.env`

```bash
SEMVER_DREDD_ALLOW_BREAKING=true
SEMVER_DREDD_COLOR=false
SEMVER_DREDD_PLUGIN=go
SEMVER_DREDD_BAKED_FILE=api/baked.yaml
SEMVER_DREDD_CURRENT_FILE=api/current.yaml
SEMVER_DREDD_VERSION_FILE=api/VERSION
```

### Environment Variables

| Variable | Description | Values |
|----------|-------------|--------|
| `SEMVER_DREDD_ALLOW_BREAKING` | Allow breaking changes | `true` / `false` |
| `SEMVER_DREDD_COLOR` | Color output mode | `true` / `false` |
| `SEMVER_DREDD_PLUGIN` | Plugin override | `python`, `go`, `java`, `javaparser`, or any installed plugin |
| `SEMVER_DREDD_BAKED_FILE` | Path to baked.yaml | file path |
| `SEMVER_DREDD_CURRENT_FILE` | Path to current.yaml | file path |
| `SEMVER_DREDD_VERSION_FILE` | Path to VERSION file | file path |

### Common CLI Options

```bash
# Breaking-change control
--allow-breaking        # Allow BREAKING changes (exit 0)
--disallow-breaking     # Fail on BREAKING changes (exit 10)

# File paths
--config PATH           # Planned: select .semver.yaml mode/config file
--path PATH             # Planned: override configured source.path
--baked PATH            # Custom baked.yaml path
--current-file PATH     # Custom current.yaml path
--version-file PATH     # Custom VERSION file path

# Scope overrides (planned advanced usage)
--include VALUE         # Append to configured include array
--exclude VALUE         # Append to configured exclude array
--override              # Replace configured include/exclude with CLI values

# Output control
--details               # List added / breaking API items
--verbose               # Explain what parts of the API are inspected
--color / --no-color    # Force or disable colored output
```

Target pre-1.0 logging replaces ad-hoc verbosity with counted global levels:

| Option | Intended output |
|--------|-----------------|
| default | errors and warnings |
| `-v` | info-level, O(1) logs once per tool call |
| `-vv` | debug-level, O(n) logs for candidates, scope matches, and API members |
| `-vvv` | debug-level plus explicit argument/config dump |

## Versioning Scheme

| Component | Description | Example |
|-----------|-------------|---------|
| **Major** | Incremented on breaking API changes | `2.0.0` |
| **Minor** | Incremented on new features (backward compatible) | `1.3.0` |
| **Patch** | Date-based format: `YYYYMMDDZZZ` (default) | `20260305001` |

Patch format breakdown:
- `YYYY` — year
- `MM` — month (zero-padded)
- `DD` — day (zero-padded)
- `ZZZ` — daily increment (001 – 999)

### Patch Scheme

The patch component is pluggable via `versioning.patch_scheme` in `.semver.yaml`:

```yaml
versioning:
  patch_scheme: date     # default — YYYYMMDDZZZ
  # patch_scheme: integer  # conventional incrementing patch: 0, 1, 2, ...
```

| Scheme | Patch bump | Major/minor bump |
|--------|-----------|------------------|
| `date` (default) | New `YYYYMMDDZZZ` value (daily counter) | Fresh `YYYYMMDD001` |
| `integer` | `patch + 1` | Patch resets to `0` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid input, import failure, plugin not found, etc.) |
| 10 | Breaking changes detected and not allowed |

## Typical Workflow

Current explicit workflow:

1. **Initialize** your project:
   ```bash
   semver-dredd init mymodule --plugin python --version 1.0.0
   ```

2. **Develop** — make changes to your module / package.

3. **Check status** before release:
   ```bash
   semver-dredd status mymodule --plugin python --details
   ```

4. **Review** `current.yaml` for the suggested version.

5. **Bake** the new version when ready to release:
   ```bash
   semver-dredd bake mymodule --plugin python
   ```

6. **Commit** the updated `baked.yaml`, `VERSION`, and your code.

Target pre-1.0 config-driven workflow:

```bash
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

## Language Plugins

semver-dredd uses a plugin system to support multiple languages.
Each plugin is a separate pip-installable package.

| Plugin | Package                  | Requires                                  |
|--------|--------------------------|-------------------------------------------|
| Python | `python-3.10-dredd`      | Python ≥ 3.10                             |
| Go     | `go-1.20-dredd`          | Go ≥ 1.20                                 |
| Java   | `java-1.8-dredd`         | JDK ≥ 1.8 (for the bundled parser)        |
| JavaParser | `javaparser-1.8-dredd` | JDK + JavaParser-based parser tooling |

Planned official scope semantics:

| Plugin | Planned `include` meaning | Notes |
|--------|---------------------------|-------|
| `python` | Python module/package names | Recursive module discovery; respect `__all__`; ignore names starting `_` |
| `go` | Go import paths | Package-level filtering; test files are never API surface |
| `java` | Java package prefixes | Regex parser implementation |
| `javaparser` | Java package prefixes | AST-based implementation |

Plugins are discovered via the `semver_dredd.plugins` entry-point group.

### Plugin API

Every plugin extends `LanguagePlugin` and provides:

| Method / Property                                 | Description                                               |
|---------------------------------------------------|-----------------------------------------------------------|
| `name`                                            | Unique identifier (`"python"`, `"go"`, `"java"`, etc.)     |
| `version`                                         | Plugin version string                                     |
| `description`                                     | Human-readable description                                |
| `validate_path(path)`                             | Check if a path is valid for this language/domain         |
| `generate_snapshot(path, version, options=None)`  | Produce a YAML snapshot string; receives forwarded scope/options |
| `snapshot_format_class`                           | *(optional)* Custom snapshot type with its own diff logic |

Planned pre-1.0 plugin metadata improvements include optional feature discovery
(for example `plugin.have("feature name")`) and machine-readable plugin
descriptions for supported scope syntax and `plugin_options`.

## Development

```bash
# Install core + dev dependencies
poetry install --with dev

# Install all language plugins (editable)
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
pip install -e plugins/javaparser-1.8-dredd

# Run tests
poetry run pytest -v

# Run a specific test file
poetry run pytest tests/test_snapshot.py -v
```

### Demo Scripts

```bash
# Python workflow demo
bash example/demo_python.sh

# Go workflow demo (requires Go 1.20+)
bash example/demo_go.sh

# Java workflow demo (requires JDK 21+)
bash example/demo_java.sh
```

### Smoke Tests (Docker Compose)

Containerized end-to-end tests that run each language demo with outcome
assertions (geometry1 → geometry2 must be `MINOR`, the reverse must be
`BREAKING`) plus the full pytest suite. No local Go/JDK needed — each
language runs in its own image (see [`docker/README.md`](docker/README.md)).

```bash
# Build and run all smoke tests (python, go, java, unit)
bash scripts/smoke.sh

# Run a subset
bash scripts/smoke.sh python unit
```

Assertions live in `tests/smoke/assert_demo.sh` and can also run directly on
the host when the relevant toolchains are installed:

```bash
bash tests/smoke/assert_demo.sh python
```

CI runs the same suite on every push and pull request
(`.github/workflows/smoke.yml`).

## Project Structure

```
semver-dredd/
├── pyproject.toml          # Core package config
├── semverdredd/            # Core library
│   ├── __init__.py         # Public API (compare, compare_and_suggest, …)
│   ├── version.py          # Version class and utilities
│   ├── result.py           # CompareResult, SuggestVersionResult
│   ├── diff.py             # Default diff scorer
│   ├── plugin_base.py      # LanguagePlugin ABC, SnapshotResult
│   ├── plugin_manager.py   # Plugin discovery & registry
│   ├── registry.py         # UUID-based snapshot type registry
│   └── snapshot_io.py      # Snapshot load/save helpers
├── snapshot/               # Snapshot data models & protocols
│   ├── change_kind.py      # ChangeKind enum (NONE, PATCH, MINOR, BREAKING)
│   ├── models.py           # NormalizedSnapshot (built-in format)
│   ├── protocols.py        # SnapshotFormat, Comparable, DiffResult
│   └── predefined/         # Reusable component models for plugins
├── cli/                    # Command-line interface
│   ├── __init__.py         # Argument parser & main()
│   ├── config.py           # Config loading (.semver.yaml, .env, env vars)
│   ├── utils.py            # Shared CLI helpers
│   └── commands/           # One module per subcommand
├── plugins/
│   ├── python-3.10-dredd/  # Python plugin (introspection-based)
│   ├── go-1.20-dredd/      # Go plugin (bundled AST parser)
│   ├── java-1.8-dredd/     # Java plugin (bundled source parser)
│   ├── javaparser-1.8-dredd/ # Java plugin (JavaParser-based AST parser)
│   └── semver-dredd-all/   # Meta-package installing all plugins
├── docs/                   # Snapshot schema and design documentation
├── reports/                # Investigation/status/gap reports
├── example/
│   ├── demo_python.sh      # End-to-end Python demo
│   ├── demo_go.sh          # End-to-end Go demo
│   └── demo_java.sh        # End-to-end Java demo
├── docker/                 # Smoke-test images (see docker/README.md)
│   ├── Dockerfile.python
│   ├── Dockerfile.go
│   ├── Dockerfile.java
│   └── Dockerfile.unit
├── docker-compose.smoke.yml # Smoke-test services (python/go/java/unit)
├── scripts/
│   └── smoke.sh            # Build + run all smoke tests, aggregate results
├── .github/workflows/
│   └── smoke.yml           # CI: smoke tests on push/PR
└── tests/
    ├── smoke/
    │   └── assert_demo.sh  # Demo outcome assertions (MINOR / BREAKING)
    ├── test_cli.py
    ├── test_config.py
    ├── test_cross_language.py
    ├── test_fields_detection.py
    ├── test_pluggable_snapshot_diff.py
    ├── test_plugin_manager.py
    ├── test_programmatic_api.py
    ├── test_semverdredd.py
    ├── test_snapshot.py
    └── test_version.py
```

## License

MIT
