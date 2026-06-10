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

Everything documented in this README is implemented. Larger configuration and
plugin-API evolutions (multi-document `.semver.yaml`, plugin-side
`include`/`exclude` filtering, the aggregate `bundle` plugin) are tracked in
[`INCLUDE-EXCLUDE-PROPOSAL.md`](INCLUDE-EXCLUDE-PROPOSAL.md), which carries a
per-feature implemented/proposed status table.

## Installation

```bash
# Core package
pip install semver-dredd

# Install language plugins (pick what you need)
pip install python-3.10-dredd
pip install go-1.20-dredd
pip install java-1.8-dredd

# Or install everything at once
pip install semver-dredd-all
```

### Development Install

```bash
# Core + all plugins (editable)
poetry install
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
```

## Quick Start

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

Works the same way for Go and Java — just point to a directory and switch
the `--plugin` flag:

```bash
# Go
semver-dredd init ./pkg/geometry --plugin go --version 1.0.0
semver-dredd status ./pkg/geometry --plugin go --details

# Java
semver-dredd init ./src/main/java --plugin java --version 1.0.0
semver-dredd status ./src/main/java --plugin java --details
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
# Initialize with default version (0.1.YYYYMMDD001)
semver-dredd init mymodule

# Initialize with an explicit version and plugin
semver-dredd init ./src --plugin go --version 1.0.0
```

Creates `.semver.yaml`, `baked.yaml`, and `VERSION`.

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

### `bake` — Lock current API as baseline

```bash
# Auto-compute version from detected changes
semver-dredd bake mymodule --plugin python

# Set an explicit version
semver-dredd bake mymodule --plugin python --version 2.0.0
```

Updates `baked.yaml` and `VERSION`.

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

# Show details about a plugin
semver-dredd plugin info python

# Install a plugin (anything pip accepts)
semver-dredd plugin install python-3.10-dredd

# Remove a plugin
semver-dredd plugin remove python
```

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
```

## Configuration

semver-dredd supports multiple configuration sources with the following
priority (lowest → highest):

1. **`.semver.yaml`** — Project configuration file
2. **`.env`** — Environment file in project root
3. **Environment variables** — Shell environment
4. **CLI arguments** — Command-line flags (highest priority)

> **Note**: The programmatic API (`compare`, `compare_and_suggest`) ignores
> all config files and uses only the arguments passed directly.

### `.semver.yaml`

```yaml
schema_version: 1

# Language plugin (python, go, java)
plugin: python

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
```

### `.env`

```bash
SEMVER_DREDD_ALLOW_BREAKING=true
SEMVER_DREDD_COLOR=false
SEMVER_DREDD_LANG=go
SEMVER_DREDD_BAKED_FILE=api/baked.yaml
SEMVER_DREDD_CURRENT_FILE=api/current.yaml
SEMVER_DREDD_VERSION_FILE=api/VERSION
```

### Environment Variables

| Variable | Description | Values |
|----------|-------------|--------|
| `SEMVER_DREDD_ALLOW_BREAKING` | Allow breaking changes | `true` / `false` |
| `SEMVER_DREDD_COLOR` | Color output mode | `true` / `false` |
| `SEMVER_DREDD_LANG` | Language plugin | `python`, `go`, `java` |
| `SEMVER_DREDD_BAKED_FILE` | Path to baked.yaml | file path |
| `SEMVER_DREDD_CURRENT_FILE` | Path to current.yaml | file path |
| `SEMVER_DREDD_VERSION_FILE` | Path to VERSION file | file path |

### Common CLI Options

```bash
# Breaking-change control
--allow-breaking        # Allow BREAKING changes (exit 0)
--disallow-breaking     # Fail on BREAKING changes (exit 10)

# File paths
--baked PATH            # Custom baked.yaml path
--current-file PATH     # Custom current.yaml path
--version-file PATH     # Custom VERSION file path

# Output control
--details               # List added / breaking API items
--verbose               # Explain what parts of the API are inspected
--color / --no-color    # Force or disable colored output
```

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

## Language Plugins

semver-dredd uses a plugin system to support multiple languages.
Each plugin is a separate pip-installable package.

| Plugin | Package             | Requires                           |
|--------|---------------------|------------------------------------|
| Python | `python-3.10-dredd` | Python ≥ 3.10                      |
| Go     | `go-1.20-dredd`     | Go ≥ 1.20                          |
| Java   | `java-1.8-dredd`    | JDK ≥ 1.8 (for the bundled parser) |

Plugins are discovered via the `semver_dredd.plugins` entry-point group.

### Plugin API

Every plugin extends `LanguagePlugin` and provides:

| Method / Property                  | Description                                               |
|------------------------------------|-----------------------------------------------------------|
| `name`                             | Unique identifier (`"python"`, `"go"`, `"java"`)          |
| `version`                          | Plugin version string                                     |
| `description`                      | Human-readable description                                |
| `validate_path(path)`              | Check if a path is valid for this language                |
| `generate_snapshot(path, version)` | Produce a YAML snapshot string                            |
| `snapshot_format_class`            | *(optional)* Custom snapshot type with its own diff logic |

## Development

```bash
# Install core + dev dependencies
poetry install --with dev

# Install all language plugins (editable)
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd

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
│   └── semver-dredd-all/   # Meta-package installing all plugins
├── example/
│   ├── demo_python.sh      # End-to-end Python demo
│   ├── demo_go.sh          # End-to-end Go demo
│   └── demo_java.sh        # End-to-end Java demo
└── tests/
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
