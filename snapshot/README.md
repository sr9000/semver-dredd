# Snapshot API — Contract Documentation

The snapshot system is the **single source of truth** for API snapshot
formats, diff scoring, and the registry that ties them together.

All canonical implementations live in the `semverdredd` package.

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
  YAML file  ──load──►   │   Registry   │  ──looks up UUID──►  SnapshotFormat class
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

| Module                    | Contents                                                        |
|---------------------------|-----------------------------------------------------------------|
| `snapshot.change_kind` | `ChangeKind` enum                                               |
| `semverdredd.protocols`   | `SnapshotFormat` protocol, `DiffScorer` ABC, `DiffResult`       |
| `semverdredd.models`      | `NormalizedSnapshot`, `FunctionSignature`, `TypeDefinition`, etc |
| `semverdredd.registry`    | `SnapshotRegistry`, `default_registry`, `load_snapshot`         |
| `semverdredd.xldiff`      | `DefaultDiffScorer`, `compare_snapshots`, `diff_snapshots`      |
| `semverdredd.plugin_base` | `LanguagePlugin`, `SnapshotResult`                              |
