# Snapshot Package — API Contract

The `snapshot` package is the **single source of truth** for API snapshot
formats, diff scoring, and the registry that ties them together.

## Quick Start

```python
from snapshot import (
    ChangeKind,        # NONE | PATCH | MINOR | BREAKING
    NormalizedSnapshot, # built-in snapshot format
    DiffResult,        # result of comparing two snapshots
    DiffScorer,        # ABC for custom diff logic
    SnapshotFormat,    # protocol every snapshot class must satisfy
    default_registry,  # UUID-based type registry (singleton)
    load_snapshot,     # load YAML file via registry
)
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
    MAJOR    = 3   # backward-compat alias for BREAKING
```

`ChangeType` is a deprecated alias for `ChangeKind` — both names are
re-exported from the package.

---

## SnapshotFormat Protocol

Every custom snapshot class **MUST** implement the following:

```python
from snapshot.protocols import SnapshotFormat

class MySnapshot:
    # ── Required class attribute ──────────────────────────────
    SNAPSHOT_TYPE_ID: str = "<your-uuid-here>"

    # ── Required property ─────────────────────────────────────
    @property
    def version(self) -> str: ...

    # ── Serialization ─────────────────────────────────────────
    def to_yaml(self) -> str: ...

    def to_dict(self) -> dict[str, Any]: ...

    # ── Deserialization (classmethods) ────────────────────────
    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MySnapshot": ...

    @classmethod
    def from_file(cls, path: Path | str) -> "MySnapshot": ...
```

### SNAPSHOT_TYPE_ID

Every snapshot format has a **UUID string** that uniquely identifies it.
This UUID is embedded in the YAML output as `snapshot_type_id` so the
registry knows which class to use for deserialization.

**Recommended UUID generation** (deterministic, collision-free):

```python
import uuid
MY_UUID = str(uuid.uuid5(
    uuid.NAMESPACE_URL,
    "semver-dredd:my-plugin:MySnapshot",
))
```

### YAML Format Requirement

The `to_yaml()` method **MUST** include `snapshot_type_id` as a top-level
field:

```yaml
snapshot_type_id: "d4e5f6a7-1234-5678-9abc-def012345678"
version: "1.0.0"
# ... rest of the snapshot data
```

---

## DiffScorer ABC

If the default diff logic doesn't suit your snapshot format, implement
a custom scorer:

```python
from snapshot.protocols import DiffScorer, DiffResult
from snapshot.change_kind import ChangeKind

class MyDiffScorer(DiffScorer):
    def diff(self, old: MySnapshot, new: MySnapshot) -> DiffResult:
        breaking = []
        added = []
        # ... your comparison logic ...
        if breaking:
            kind = ChangeKind.BREAKING
        elif added:
            kind = ChangeKind.MINOR
        else:
            kind = ChangeKind.NONE
        return DiffResult(
            change_kind=kind,
            breaking=tuple(breaking),
            added=tuple(added),
        )
```

---

## Snapshot Registry

The registry maps UUID strings → snapshot classes.  When loading a YAML
file, the registry reads `snapshot_type_id` and delegates to the matching
class's `from_yaml_str()`.

### Registering a custom type

```python
from snapshot.registry import default_registry

# At plugin startup (e.g., in LanguagePlugin.__init__)
default_registry.register(MySnapshot)
```

### Loading snapshots

```python
from snapshot import load_snapshot, load_snapshot_yaml

# From file — auto-detects type via UUID
snap = load_snapshot("baked.yaml")

# From string
snap = load_snapshot_yaml(yaml_content)
```

### Fallback behaviour

If `snapshot_type_id` is **absent** from the YAML (e.g., legacy v2 files),
the registry falls back to `NormalizedSnapshot`.  If the UUID is present
but **unknown**, a warning is logged and `NormalizedSnapshot` is used.

---

## Integrating with LanguagePlugin

Plugins expose custom snapshot formats and diff scorers via two optional
properties on `LanguagePlugin`:

```python
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

class MyPlugin(LanguagePlugin):
    @property
    def name(self) -> str:
        return "my-lang"

    def generate_snapshot(self, path, version, options=None) -> SnapshotResult:
        snap = MySnapshot(version=version, ...)
        return SnapshotResult(success=True, yaml_content=snap.to_yaml())

    @property
    def snapshot_format_class(self):
        return MySnapshot          # or None to use NormalizedSnapshot

    @property
    def diff_scorer(self):
        return MyDiffScorer()      # or None to use DefaultDiffScorer
```

When either property returns `None` (the default), the core engine uses
the built-in `NormalizedSnapshot` and `DefaultDiffScorer`.

---

## Module Layout

| Module                  | Contents                                                |
|-------------------------|---------------------------------------------------------|
| `snapshot.change_kind`  | `ChangeKind` enum (+ `ChangeType` alias)                |
| `snapshot.protocols`    | `SnapshotFormat` protocol, `DiffScorer` ABC, `DiffResult` |
| `snapshot.models`       | `NormalizedSnapshot`, `FunctionSignature`, `TypeDefinition`, `Parameter`, `Field`, `SnapshotDiff` |
| `snapshot.registry`     | `SnapshotRegistry`, `default_registry`, `load_snapshot`, `load_snapshot_yaml` |
