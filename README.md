# semver-dredd

Automatically increments semver number based on interface changes.

## Features

- **API Introspection**: Extracts public API from Python modules (functions, classes, methods)
- **Change Detection**: Compares two module versions and detects the type of change
  - **MAJOR**: Breaking changes (removed functions/classes/methods/fields, added required parameters)
  - **MINOR**: New features (new functions/classes/methods/fields, new optional parameters)
  - **PATCH**: No API changes, only implementation changes
- **Field Detection**: Detects fields in structured types (dataclasses, named tuples, pydantic models, __slots__)
- **Version Management**: Handles semantic versioning with custom patch format
- **API Snapshots**: Save/load API state to track changes over time
- **CLI Tool**: Command-line interface for version management

## Installation

```bash
poetry install
```

## Quick Start

```bash
# Initialize semver-dredd for your project
semver-dredd init mymodule --version 1.0.0

# Check current API status against baked baseline
semver-dredd status mymodule --details

# Bake current API as new baseline (after release)
semver-dredd bake mymodule
```

## Files

semver-dredd manages several files in your project:

| File | Description |
|------|-------------|
| `.semver.yaml` | Configuration (policies, severity mapping) |
| `baked.yaml` | Locked API state with current version |
| `current.yaml` | Current API state with suggested next version |
| `VERSION` | Plain text file with current version string |

## Usage

### CLI Commands

#### `init` - Initialize project

```bash
# Initialize with default version (0.1.YYYYMMDD001)
semver-dredd init mymodule

# Initialize with explicit version
semver-dredd init mymodule --version 1.0.0
```

Creates:
- `.semver.yaml` - configuration file
- `baked.yaml` - initial API snapshot with version
- `VERSION` - version string file

#### `status` - Check API changes

```bash
# Check current module against baked baseline
semver-dredd status mymodule

# Show detailed diff (breaking vs. added changes)
semver-dredd status mymodule --details

# Allow breaking changes (don't fail on MAJOR)
semver-dredd status mymodule --allow-breaking
```

Updates `current.yaml` with current API and suggested version.

#### `bake` - Lock current API as baseline

```bash
# Auto-compute version based on detected changes
semver-dredd bake mymodule

# Explicit version
semver-dredd bake mymodule --version 2.0.0
```

Updates:
- `baked.yaml` - new API snapshot
- `VERSION` - new version string

#### `compare` - Compare two modules directly

```bash
# Compare old vs new module
semver-dredd compare old_module new_module

# With details
semver-dredd compare old_module new_module --details

# Verbose (explain inspection logic)
semver-dredd compare old_module new_module --verbose
```

#### `bump` - Manually bump version

```bash
semver-dredd bump --current 1.0.0 --change minor
```

#### `patch` - Generate patch version

```bash
semver-dredd patch
```

### Python API

```python
from semverdredd import detect_change, compare, compare_and_suggest, ChangeType, Version

# Compare two module versions
from example import pygeometry2
from example.py import pygeometry1

# Simple change detection
change = detect_change(pygeometry1, pygeometry2)
if change == ChangeType.MAJOR:
    print("Breaking change detected!")

# Structured result with diff details
result = compare(pygeometry1, pygeometry2)
print(result.change_type)  # ChangeType.MINOR
print(result.severity)  # "warn"
print(result.diff.added)  # ("function added: volume", ...)
print(result.diff.breaking)  # ()

# With version suggestion
result = compare_and_suggest(pygeometry1, pygeometry2, "1.0.0")
print(result.suggested_version)  # 1.1.20260214001
```

### API Snapshots (Programmatic)

```python
from semverdredd.snapshot import APISnapshot, save_version_file

# Create snapshot from module
from mymodule import api
snapshot = APISnapshot.from_module(api, "1.0.0")

# Save to file
snapshot.save("baked.yaml")

# Load and compare
loaded = APISnapshot.load("baked.yaml")
old_api = loaded.to_module_api()
```

## Configuration

semver-dredd supports multiple configuration sources with the following priority (lowest to highest):

1. **`.semver.yaml`** - Project configuration file (lowest priority)
2. **`.env`** - Environment file in project root
3. **Environment variables** - Real shell environment
4. **CLI arguments** - Command-line flags (highest priority)

> **Note**: This priority system only applies to CLI usage. Programmatic API calls ignore all config files and use only the arguments passed directly to functions.

### `.semver.yaml` file

```yaml
schema_version: 1

# Language (python, go, java)
language: python

policies:
  allow_breaking_changes: false  # Fail on MAJOR by default

output:
  color: null  # null = auto-detect, true = always, false = never
  severity_by_change:
    none: info     # Green
    patch: info    # Green
    minor: warn    # Yellow
    major: error   # Red (changes to warn when --allow-breaking)

files:
  baked: baked.yaml
  current: current.yaml
  version: VERSION
```

### `.env` file

```bash
# Override .semver.yaml values
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
| `SEMVER_DREDD_ALLOW_BREAKING` | Allow breaking changes | `true`, `false` |
| `SEMVER_DREDD_COLOR` | Color output mode | `true`, `false` |
| `SEMVER_DREDD_LANG` | Project language | `python`, `go`, `java` |
| `SEMVER_DREDD_BAKED_FILE` | Path to baked.yaml | File path |
| `SEMVER_DREDD_CURRENT_FILE` | Path to current.yaml | File path |
| `SEMVER_DREDD_VERSION_FILE` | Path to VERSION file | File path |

### CLI Options

```bash
# Breaking change control
--allow-breaking      # Allow MAJOR changes (exit 0)
--disallow-breaking   # Fail on MAJOR changes (exit 10)

# File paths
--baked PATH         # Custom baked.yaml path
--current-file PATH  # Custom current.yaml path
--version-file PATH  # Custom VERSION file path

# Output control
--details            # List added/removed/changed API items
--verbose            # Explain what parts of API are inspected
--color / --no-color # Control colored output (auto-detected)
```

### Generate Configuration Template

```bash
# Print comprehensive template to stdout
semver-dredd template

# Save to file
semver-dredd template --out .semver.yaml
```

## Versioning Scheme

| Component | Description | Example |
|-----------|-------------|---------|
| **Major** | Incremented on breaking API changes | `2.0.0` |
| **Minor** | Incremented on new features (backward compatible) | `1.3.0` |
| **Patch** | Format: `YYYYMMDDZZZ` | `20260214001` |

Patch format breakdown:
- `YYYY`: Current year (e.g., 2026)
- `MM`: Current month, zero-padded (e.g., 02)
- `DD`: Current day, zero-padded (e.g., 14)
- `ZZZ`: Daily increment, zero-padded (001-999)

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid input, import failure, etc.) |
| 10 | Breaking changes detected and not allowed |

## Typical Workflow

1. **Initialize** your project:
   ```bash
   semver-dredd init mymodule --version 1.0.0
   ```

2. **Develop** - make changes to your module

3. **Check status** before release:
   ```bash
   semver-dredd status mymodule --details
   ```

4. **Review** `current.yaml` for suggested version

5. **Bake** the new version when ready to release:
   ```bash
   semver-dredd bake mymodule
   ```

6. **Commit** updated `baked.yaml`, `VERSION`, and your code

## Development

```bash
# Install with dev dependencies
poetry install --with dev

# Run tests
poetry run pytest -v

# Run specific test
poetry run pytest tests/test_snapshot.py -v
```

## Project Structure

```
semver-dredd/
├── semverdredd/
│   ├── __init__.py   # Core API comparison logic
│   ├── version.py    # Version class and utilities
│   ├── result.py     # Structured result types
│   ├── diff.py       # API diff utilities
│   └── snapshot.py   # API snapshot serialization
├── cli/
│   └── __init__.py   # Command-line interface
├── example/
│   ├── pygeometry1/  # Example module v1
│   └── pygeometry2/  # Example module v2
└── tests/
    ├── test_semverdredd.py
    ├── test_version.py
    ├── test_cli.py
    ├── test_programmatic_api.py
    └── test_snapshot.py
```

## License

MIT

### Core Classes

- `ChangeType` - Enum: NONE, PATCH, MINOR, MAJOR
- `APISignature` - Represents a function/method signature
- `ClassAPI` - Represents a class's public API (methods + fields for structured types)
- `ModuleAPI` - Represents a module's public API
- `Version` - Semantic version with custom patch format

### Core Functions

- `detect_change(old_module, new_module)` - Detect change type between modules
- `compare_modules(old_api, new_api)` - Compare two ModuleAPI objects
- `compare_classes(old_api, new_api)` - Compare two ClassAPI objects
- `compare_signatures(old_sig, new_sig)` - Compare two APISignature objects

### Field Detection

semver-dredd detects fields in structured types:

- **Dataclasses**: Fields from `__dataclass_fields__`
- **Named Tuples**: Fields from `_fields`
- **Pydantic Models**: Fields from `__fields__` (v1) or `model_fields` (v2)
- **__slots__ Classes**: Fields from `__slots__`

Adding/removing fields in these types is treated as MINOR/MAJOR changes respectively.
