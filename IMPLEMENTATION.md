# Implementation Plan

## Current Status

### ✅ Implemented

#### Core API Comparison (`semverdredd/__init__.py`)
- `ChangeType` enum (NONE, PATCH, MINOR, MAJOR)
- `APISignature` - extracts function/method signatures
- `ClassAPI` - extracts class public API
- `ModuleAPI` - extracts module public API
- `compare_signatures()` - compares two signatures
- `compare_classes()` - compares two class APIs
- `compare_modules()` - compares two module APIs
- `detect_change()` - detects change type between two modules

#### Version Management (`semverdredd/version.py`)
- `Version` dataclass with parse/str/compare operations
- `Version.increment()` - increment based on ChangeType
- `Version.patch_date` - extract date from YYYYMMDDZZZ patch
- `Version.patch_increment` - extract daily increment (ZZZ)
- `generate_patch()` - generate patch in YYYYMMDDZZZ format

#### CLI Tool (`cli/__init__.py`)
- `compare` command - compare two modules, detect change type
- `bump` command - bump version based on change type
- `patch` command - generate new patch version number
- Module import from path or dotted name

### Test Coverage (64 tests)
- `tests/test_semverdredd.py` - 20 tests for API comparison
- `tests/test_version.py` - 32 tests for Version class
- `tests/test_cli.py` - 12 tests for CLI commands

## Architecture

```
semver-dredd/
├── semverdredd/
│   ├── __init__.py      # Core API comparison logic ✅
│   └── version.py       # Version class and patch generator ✅
├── cli/
│   └── __init__.py      # Command-line interface ✅
├── example/
│   ├── pygeometry1/     # Test module v1 (base)
│   └── pygeometry2/     # Test module v2 (extended)
└── tests/
    ├── test_semverdredd.py  # API comparison tests ✅
    ├── test_version.py      # Version tests ✅
    └── test_cli.py          # CLI tests ✅
```

## Usage Examples

### Python API
```python
from semverdredd import detect_change, ChangeType, Version
from example import pygeometry1, pygeometry2

# Detect change type
change = detect_change(pygeometry1, pygeometry2)
print(f"Change: {change.name}")  # MINOR

# Version management
version = Version.parse("1.2.20260213001")
new_version = version.increment(change)
print(f"New: {new_version}")  # 1.3.20260214001
```

### CLI
```bash
# Compare modules
poetry run python -m cli compare example.pygeometry1 example.pygeometry2

# Bump version
poetry run python -m cli bump -c 1.0.0 -t minor

# Generate patch
poetry run python -m cli patch
```

## Test Results
```
64 passed in 0.07s
```
