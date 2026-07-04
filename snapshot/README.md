# snapshot — Snapshot Data Models

This package defines the core data types for **semver-dredd** API snapshots.

## Quick Start

```python
from snapshot import (
    ChangeKind,           # NONE | PATCH | MINOR | BREAKING
    NormalizedSnapshot,   # built-in language-agnostic snapshot format
    DiffResult,           # result of comparing two snapshots
    SnapshotFormat,       # protocol every snapshot class must satisfy
    Comparable,           # protocol for self-diffing snapshots
    SnapshotRegistry,     # UUID-based type registry
    default_registry,     # registry singleton
    load_snapshot,        # load YAML file via registry
    load_snapshot_yaml,   # load YAML string via registry
)
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
                                                               implements Comparable
                                                                        │
                                                                        ▼
                                                               old.diff_against(new)
                                                                        │
                                                                        ▼
                                                               DiffResult
                                                               ├─ change_kind: ChangeKind
                                                               ├─ breaking: tuple[str, …]
                                                               └─ added:    tuple[str, …]
```

Every snapshot class must implement both `SnapshotFormat` (marshalling) and
`Comparable` (self-diffing). There is no separate scorer object — comparison
logic lives on the snapshot type itself.

---

## Packages

| Package               | Contents                                                             |
|-----------------------|----------------------------------------------------------------------|
| `snapshot`            | Change severity enum, protocols, `NormalizedSnapshot`, re-exports    |
| `snapshot.predefined` | Reusable component models for plugin snapshots (see below)           |

---

## `ChangeKind` Enum

```python
class ChangeKind(Enum):
    NONE     = 0   # no API surface change
    PATCH    = 1   # implementation-only change
    MINOR    = 2   # new public functionality added
    BREAKING = 3   # existing public API removed / incompatible
```

---

## `SnapshotFormat` Protocol

Every custom snapshot class **must** implement:

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

### `SNAPSHOT_TYPE_ID`

Every snapshot format has a **UUID string** that uniquely identifies it.
This UUID is embedded in YAML as `snapshot_type_id` so the registry can
pick the correct deserializer.

```python
import uuid
MY_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:my-plugin:MySnapshot"))
```

### YAML must include `snapshot_type_id` as a top-level field.

---

## `Comparable` Protocol

Every snapshot class must also implement `Comparable` so the core engine
can diff two snapshots without knowing their internal structure:

```python
class Comparable(Protocol):
    def diff_against(self, other: "Comparable") -> DiffResult: ...
```

The engine calls `old_snapshot.diff_against(new_snapshot)` exclusively.

---

## `DiffResult`

```python
@dataclass(frozen=True)
class DiffResult:
    change_kind: ChangeKind
    breaking: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool: ...
```

---

## Snapshot Registry

```python
from semverdredd.registry import default_registry

# Register a custom snapshot class
default_registry.register(MySnapshot)

# Load YAML — the registry picks the right class based on snapshot_type_id
from semverdredd import load_snapshot, load_snapshot_yaml
snap = load_snapshot("baked.yaml")
snap = load_snapshot_yaml(yaml_content)
```

Fallback: if `snapshot_type_id` is absent, `NormalizedSnapshot` is used.

---

## Integrating with `LanguagePlugin`

```python
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

class MyPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "my-lang"

    def generate_snapshot(self, path, version, options=None) -> SnapshotResult:
        snap = MySnapshot(...)
        return SnapshotResult(success=True, yaml_content=snap.to_yaml())

    @property
    def snapshot_format_class(self):
        return MySnapshot  # or None to use NormalizedSnapshot
```

The plugin's `snapshot_format_class` tells the CLI which class to use for
deserialization and diffing. If `None`, the built-in `NormalizedSnapshot`
is used.

---

## Module Layout

| Module                    | Contents                                                          |
|---------------------------|-------------------------------------------------------------------|
| `snapshot.change_kind`    | `ChangeKind` enum                                                 |
| `snapshot.protocols`      | `SnapshotFormat` protocol, `Comparable` protocol, `DiffResult`    |
| `snapshot.models`         | `NormalizedSnapshot`, `FunctionSignature`, `TypeDefinition`, etc.  |
| `snapshot.predefined`     | `Variable`, `Argument`, `Function`, `ClassField`, `ClassMethod`   |
| `semverdredd.registry`    | `SnapshotRegistry`, `default_registry`, `load_snapshot`           |
| `semverdredd.diff`        | `diff_snapshots`, `compare_snapshots`, `DefaultDiffScorer`        |
| `semverdredd.plugin_base` | `LanguagePlugin` ABC, `SnapshotResult`                            |

---

## `NormalizedSnapshot`

`NormalizedSnapshot` is the generic language-agnostic snapshot format used
when no plugin-specific format is available. It stores functions and types
indexed by name.

UUID seed: `semver-dredd:NormalizedSnapshot`

Key fields:

| Field            | Type                              | Description                    |
|------------------|-----------------------------------|--------------------------------|
| `schema_version` | `int`                             | Schema version (`2`) |
| `version`        | `str`                             | Version string                 |
| `language`       | `str`                             | Language identifier             |
| `source_kind`    | `str`                             | `"module"`, `"package"`, etc.  |
| `source_path`    | `str`                             | Path or module name            |
| `functions`      | `dict[str, FunctionSignature]`    | Top-level functions            |
| `types`          | `dict[str, TypeDefinition]`       | Types (classes, structs, etc.) |

Implements `SnapshotFormat` and `Comparable` (via `diff_against`).

---

## `snapshot.predefined` — Component Models

The predefined module provides five immutable dataclasses that represent the
building blocks of any language API. Every class carries a stable **UUID**
(`SNAPSHOT_TYPE_ID`) so it can be stored and round-tripped through YAML via
the `SnapshotRegistry`.

### Type IDs (UUID v5 under `uuid.NAMESPACE_URL`)

| Class        | UUID seed                            |
|--------------|--------------------------------------|
| `Variable`   | `semver-dredd:predefined:Variable`   |
| `Argument`   | `semver-dredd:predefined:Argument`   |
| `Function`   | `semver-dredd:predefined:Function`   |
| `ClassField` | `semver-dredd:predefined:ClassField` |
| `ClassMethod`| `semver-dredd:predefined:ClassMethod`|

All five classes are **automatically registered** in the global
`default_registry` when `snapshot.predefined` is imported.

> **Note**: Language-specific argument types (e.g. `PythonArgument`) live in
> their respective plugin packages, not here.

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

A function/method argument — extends `Variable` (same fields).

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

### `Function`

A standalone callable (top-level function or static method).

| Field         | Type                  | Default  | Description        |
|---------------|-----------------------|----------|--------------------|
| `name`        | `str`                 | `""`     | Function name      |
| `result_type` | `str`                 | `"void"` | Return type string |
| `args`        | `tuple[Argument, …]`  | `()`     | Parameter list     |

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

| Field         | Type                  | Default  | Description        |
|---------------|-----------------------|----------|--------------------|
| `name`        | `str`                 | `""`     | Method name        |
| `result_type` | `str`                 | `"void"` | Return type string |
| `args`        | `tuple[Argument, …]`  | `()`     | Parameter list     |

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

## Auto-registration

Importing `snapshot.predefined` automatically registers all five predefined
model classes in the global `semverdredd.registry.default_registry`.

```python
from snapshot.predefined import Variable, Function, ClassField
# ↑ side-effect: all five classes are registered in default_registry
```

You can inspect what is registered:

```python
from semverdredd.registry import default_registry
print(default_registry.registered_ids())
```
