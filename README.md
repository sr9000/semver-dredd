# semver-dredd

Automatically increments semver number based on interface changes.

## Features

- **API Introspection**: Extracts public API from Python modules (functions, classes, methods)
- **Change Detection**: Compares two module versions and detects the type of change
  - **MAJOR**: Breaking changes (removed functions/classes, added required parameters)
  - **MINOR**: New features (new functions/classes, new optional parameters)
  - **PATCH**: No API changes, only implementation changes
- **Version Management**: Handles semantic versioning with custom patch format
- **CLI Tool**: Command-line interface for version bumping

## Installation

```bash
poetry install
```

## Usage

### Python API

```python
from semverdredd import detect_change, ChangeType, Version

# Compare two module versions
from example import pygeometry1, pygeometry2

change = detect_change(pygeometry1, pygeometry2)
if change == ChangeType.MAJOR:
    print("Breaking change detected!")
elif change == ChangeType.MINOR:
    print("New features added.")
else:
    print("No API changes.")

# Version management
version = Version.parse("1.2.2026021400")
new_version = version.increment(change)
print(f"New version: {new_version}")  # e.g., "1.3.20260214001"
```

### CLI

```bash
# Compare two modules and suggest version bump
semver-dredd compare old_module new_module

# Bump version based on detected changes
semver-dredd bump --current 1.0.0 --change minor
```

## Configuration

semver-dredd can be configured via a `meta.yaml` file in the project root:

```yaml
schema_version: 1

policies:
  allow_breaking_changes: false  # Default policy for breaking changes

output:
  severity_by_change:
    none: info
    patch: info
    minor: warn
    major: error
```

### CLI Options

```bash
# Allow breaking changes (overrides meta.yaml default)
semver-dredd compare old_module new_module --allow-breaking

# Disallow breaking changes (overrides meta.yaml default)
semver-dredd compare old_module new_module --disallow-breaking

# Colored output (auto-detected, can be forced)
semver-dredd compare old_module new_module --color
semver-dredd compare old_module new_module --no-color
```

## Versioning Scheme

`semver-dredd` uses a specific versioning strategy:

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

## API Reference

### Core Classes

- `ChangeType` - Enum: NONE, PATCH, MINOR, MAJOR
- `APISignature` - Represents a function/method signature
- `ClassAPI` - Represents a class's public API
- `ModuleAPI` - Represents a module's public API
- `Version` - Semantic version with custom patch format

### Core Functions

- `detect_change(old_module, new_module)` - Detect change type between modules
- `compare_modules(old_api, new_api)` - Compare two ModuleAPI objects
- `compare_classes(old_api, new_api)` - Compare two ClassAPI objects
- `compare_signatures(old_sig, new_sig)` - Compare two APISignature objects

## Development

```bash
# Install with dev dependencies
poetry install --with dev

# Run tests
poetry run pytest -v

# Run specific test
poetry run pytest tests/test_semverdredd.py -v
```

## Project Structure

```
semver-dredd/
├── semverdredd/
│   ├── __init__.py   # Core API comparison logic
│   └── version.py    # Version class and utilities
├── cli/
│   └── __init__.py   # Command-line interface
├── example/
│   ├── pygeometry1/  # Example module v1
│   └── pygeometry2/  # Example module v2
└── tests/
    └── test_semverdredd.py
```

## License

MIT
