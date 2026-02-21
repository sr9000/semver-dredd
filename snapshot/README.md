# snapshot — Snapshot Data Models

This package defines the core data types for **semver-dredd** API snapshots.

## Quick Start

```python
from semverdredd import (
    # NONE | PATCH | MINOR | BREAKING
    # built-in snapshot format
    DiffResult,  # result of comparing two snapshots
    DiffScorer,  # ABC for custom diff logic
    SnapshotFormat,  # protocol every snapshot class must satisfy
    SnapshotRegistry,  # UUID-based type registry
    default_registry,  # registry singleton
    load_snapshot,  # load YAML file via registry
    load_snapshot_yaml,  # load YAML string via registry
)
from snapshot import NormalizedSnapshot, ChangeKind
```

---

## Architecture Overview

```
                          ┌──────────────┐
  YAML file  ──load──►    │   Registry   │  ──looks up UUID──►  SnapshotFormat class
                          │  (by UUID)   │                      ├─ from_yaml_str()
                          └──────────────┘                      ├─ from_file()
                                                                ├─ to_yaml()
                                                                ├─ to_dict()
                                                                └─ version (property)
                                                                        │
                                                                        ▼
                                                               ┌─────────────┐
                                                               │ DiffScorer  │
                                                               │   .diff()   │
                                                               └──────┬──────┘
                                                                      │
                                                                      ▼
                                                               DiffResult
                                                               ├─ change_kind: ChangeKind
                                                               ├─ breaking: tuple[str,…]
                                                               └─ added:    tuple[str,…]
```

---

## ChangeKind Enum

```python
class ChangeKind(Enum):
    NONE     = 0   # no API surface change
    PATCH    = 1   # implementation-only change
    MINOR    = 2   # new public functionality added
    BREAKING = 3   # existing public API removed / incompatible
```

---

## SnapshotFormat Protocol

Every custom snapshot class **MUST** implement the following:

```python
class MySnapshot:
    SNAPSHOT_TYPE_ID: str = "<your-uuid-here>"

    @property
    def version(self) -> str: ...

    def to_yaml(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MySnapshot": ...
    @classmethod
    def from_file(cls, path: Path | str) -> "MySnapshot": ...
```

### SNAPSHOT_TYPE_ID

Every snapshot format has a **UUID string** that uniquely identifies it.
This UUID is embedded in YAML as `snapshot_type_id` so the registry can
pick the correct deserializer.

```python
import uuid
MY_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:my-plugin:MySnapshot"))
```

### YAML must include `snapshot_type_id` as a top-level field.

---

## DiffScorer ABC

```python
from snapshot.protocols import DiffScorer, DiffResult
from snapshot import ChangeKind


class MyDiffScorer(DiffScorer):
    def diff(self, old, new) -> DiffResult:
        breaking, added = [], []
        # ... comparison logic ...
        kind = ChangeKind.BREAKING if breaking else (ChangeKind.MINOR if added else ChangeKind.NONE)
        return DiffResult(change_kind=kind, breaking=tuple(breaking), added=tuple(added))
```

---

## Snapshot Registry

```python
from semverdredd.registry import default_registry
default_registry.register(MySnapshot)

from semverdredd import load_snapshot, load_snapshot_yaml
snap = load_snapshot("baked.yaml")
snap = load_snapshot_yaml(yaml_content)
```

Fallback: if `snapshot_type_id` is absent, `NormalizedSnapshot` is used.

---

## Integrating with LanguagePlugin

```python
class MyPlugin(LanguagePlugin):
    @property
    def name(self) -> str: return "my-lang"

    def generate_snapshot(self, path, version, options=None) -> SnapshotResult:
        return SnapshotResult(success=True, yaml_content=MySnapshot(...).to_yaml())

    @property
    def snapshot_format_class(self): return MySnapshot  # or None

    @property
    def diff_scorer(self): return MyDiffScorer()  # or None
```

---

## Module Layout

| Module                    | Contents                                                         |
|---------------------------|------------------------------------------------------------------|
| `snapshot.change_kind`    | `ChangeKind` enum                                                |
| `semverdredd.protocols`   | `SnapshotFormat` protocol, `DiffScorer` ABC, `DiffResult`        |
| `semverdredd.models`      | `NormalizedSnapshot`, `FunctionSignature`, `TypeDefinition`, etc |
| `semverdredd.registry`    | `SnapshotRegistry`, `default_registry`, `load_snapshot`          |
| `semverdredd.xldiff`      | `DefaultDiffScorer`, `compare_snapshots`, `diff_snapshots`       |
| `semverdredd.plugin_base` | `LanguagePlugin`, `SnapshotResult`                               |

# snapshot — Snapshot Data Models

This package defines the core data types for **semver-dredd** API snapshots.

---

## Packages

| Package               | Contents                                                             |
|-----------------------|----------------------------------------------------------------------|
| `snapshot`            | Root protocols, change severity enum, top-level `NormalizedSnapshot` |
| `snapshot.predefined` | Ready-to-use component models (see below)                            |

---

## `snapshot.predefined` — Component Models

The predefined module provides six immutable dataclasses that represent the
building blocks of any language API.  Every class satisfies the
`SnapshotFormat` protocol and carries a stable **UUID** (`SNAPSHOT_TYPE_ID`)
so it can be stored and round-tripped through YAML via the `SnapshotRegistry`.

### Type IDs (UUID v5 under `uuid.NAMESPACE_URL`)

| Class            | UUID seed                                |
|------------------|------------------------------------------|
| `Variable`       | `semver-dredd:predefined:Variable`       |
| `Argument`       | `semver-dredd:predefined:Argument`       |
| `PythonArgument` | `semver-dredd:predefined:PythonArgument` |
| `Function`       | `semver-dredd:predefined:Function`       |
| `ClassField`     | `semver-dredd:predefined:ClassField`     |
| `ClassMethod`    | `semver-dredd:predefined:ClassMethod`    |

All six classes are **automatically registered** in the global
`default_registry` when `snapshot.predefined` is imported.

---

### `Variable`

A module-level variable or constant.

| Field     | Type          | Default     | Description            |
|-----------|---------------|-------------|------------------------|
| `name`    | `str`         | `""`        | Symbol name            |
| `type`    | `str`         | `"unknown"` | Type annotation string |
| `default` | `str \| None` | `None`      | Default value (repr)   |

```yaml
snapshot_type_id: <VARIABLE_TYPE_ID>
name: MAX_RETRIES
type: int
default: "3"
```

---

### `Argument`

A function/method argument — same fields as `Variable`.

| Field     | Type          | Default     | Description                    |
|-----------|---------------|-------------|--------------------------------|
| `name`    | `str`         | `""`        | Parameter name                 |
| `type`    | `str`         | `"unknown"` | Type annotation string         |
| `default` | `str \| None` | `None`      | Default value (repr) or `null` |

```yaml
snapshot_type_id: <ARGUMENT_TYPE_ID>
name: timeout
type: float
default: "30.0"
```

---

### `PythonArgument`

Python-specific argument with calling-convention metadata.
Extends `Argument` with three mutually-exclusive boolean flags.

| Field           | Type          | Default     | Description          |
|-----------------|---------------|-------------|----------------------|
| `name`          | `str`         | `""`        | Parameter name       |
| `type`          | `str`         | `"unknown"` | Type annotation      |
| `default`       | `str \| None` | `None`      | Default value (repr) |
| `position_only` | `bool`        | `False`     | Declared before `/`  |
| `pos_and_named` | `bool`        | `True`      | Normal parameter     |
| `named_only`    | `bool`        | `False`     | Declared after `*`   |

```yaml
snapshot_type_id: <PYTHON_ARGUMENT_TYPE_ID>
name: width
type: int
default: null
position_only: false
pos_and_named: true
named_only: false
```

---

### `Function`

A standalone callable (top-level function or static method).

| Field         | Type                                     | Default  | Description        |
|---------------|------------------------------------------|----------|--------------------|
| `name`        | `str`                                    | `""`     | Function name      |
| `result_type` | `str`                                    | `"void"` | Return type string |
| `args`        | `tuple[Argument \| PythonArgument, ...]` | `()`     | Parameter list     |

```yaml
snapshot_type_id: <FUNCTION_TYPE_ID>
name: compute_area
result_type: float
args:
  - name: width
    type: float
    default: null
  - name: height
    type: float
    default: null
```

---

### `ClassField`

A public field (attribute/slot) of a class or struct — same shape as `Variable`.

| Field     | Type          | Default     | Description          |
|-----------|---------------|-------------|----------------------|
| `name`    | `str`         | `""`        | Field name           |
| `type`    | `str`         | `"unknown"` | Type annotation      |
| `default` | `str \| None` | `None`      | Default value (repr) |

```yaml
snapshot_type_id: <CLASS_FIELD_TYPE_ID>
name: radius
type: float
default: null
```

---

### `ClassMethod`

A public method of a class — same shape as `Function`.

| Field         | Type                                     | Default  | Description        |
|---------------|------------------------------------------|----------|--------------------|
| `name`        | `str`                                    | `""`     | Method name        |
| `result_type` | `str`                                    | `"void"` | Return type string |
| `args`        | `tuple[Argument \| PythonArgument, ...]` | `()`     | Parameter list     |

```yaml
snapshot_type_id: <CLASS_METHOD_TYPE_ID>
name: distance
result_type: float
args:
  - name: other
    type: Point
    default: null
```

---

## `change_kind.py` — Change Severity

```python
class ChangeKind(Enum):
    NONE     # No API changes
    PATCH    # Implementation-only changes
    MINOR    # Backwards-compatible additions
    BREAKING # Breaking changes
```

---

## `protocols.py` — Core Protocols

### `SnapshotFormat`

Every snapshot class must implement:

```python
class SnapshotFormat(Protocol):
    SNAPSHOT_TYPE_ID: str            # Stable UUID string
    version: str                     # Snapshot schema version
    def to_yaml(self) -> str: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> Self: ...
    @classmethod
    def from_file(cls, path) -> Self: ...
```

### `DiffScorer`

```python
class DiffScorer(Protocol):
    def diff(self, old: Any, new: Any) -> DiffResult: ...
```

### `DiffResult`

```python
@dataclass
class DiffResult:
    change_kind: ChangeKind
    added: list[str]
    removed: list[str]
    changed: list[str]
```

---

## `models.py` — `NormalizedSnapshot`

`NormalizedSnapshot` is the generic language-agnostic snapshot format used
when no plugin-specific format is available.  It stores a flat list of API
items indexed by string key.

UUID seed: `semver-dredd:NormalizedSnapshot`

---

## Auto-registration

Importing `snapshot.predefined` automatically registers all six predefined
model classes in the global `semverdredd.registry.default_registry`.

```python
from snapshot.predefined import Variable, Function, ClassField
# ↑ side-effect: all six classes are registered in default_registry
```

You can inspect what is registered:

```python
from semverdredd.registry import default_registry
print(default_registry.registered_ids())
```

---

## SnapshotFormat Protocol

Every custom snapshot class **MUST** implement:

```python
class MySnapshot:
    SNAPSHOT_TYPE_ID: str = "<your-uuid-here>"

    @property
    def version(self) -> str: ...

    def to_yaml(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MySnapshot": ...
    @classmethod
    def from_file(cls, path: Path | str) -> "MySnapshot": ...
```

The UUID must be embedded in the YAML as `snapshot_type_id` so the registry
can pick the correct deserializer when loading.

```python
import uuid
MY_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:my-plugin:MySnapshot"))
```

---

## Integrating with LanguagePlugin

```python
class MyPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "my-lang"

    def generate_snapshot(self, path, version, options=None) -> SnapshotResult:
        return SnapshotResult(success=True, yaml_content=MySnapshot(...).to_yaml())

    @property
    def snapshot_format_class(self):
        return MySnapshot  # or None to use NormalizedSnapshot

    @property
    def diff_scorer(self):
        return MyDiffScorer()  # or None to use DefaultDiffScorer
```
