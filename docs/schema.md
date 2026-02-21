# semver-dredd Snapshot Schema

This document describes the YAML schema used by semver-dredd snapshots.

---

## Schema Versions

| Version | Status      | Description                                                     |
|---------|-------------|-----------------------------------------------------------------|
| v2      | Legacy      | Flat API items list; language-specific fields inline            |
| **v3**  | **Current** | Typed component model; `snapshot_type_id` for registry dispatch |

---

## Schema v3 — Common Envelope

Every v3 snapshot YAML starts with these top-level fields:

```yaml
snapshot_type_id: "<UUID>"   # required — identifies deserializer
schema_version: 3
version: "1.2.0"             # version of the analysed library
language: python             # or: go, java, ...
source:
  kind: module               # module | package | directory | file
  path: "/path/to/source"
api:
  # language-specific content (see below)
```

---

## Predefined Component UUIDs

All six predefined component models have deterministic UUIDs derived via:

```python
uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:predefined:<ClassName>")
```

| Model            | UUID seed                                |
|------------------|------------------------------------------|
| `Variable`       | `semver-dredd:predefined:Variable`       |
| `Argument`       | `semver-dredd:predefined:Argument`       |
| `PythonArgument` | `semver-dredd:predefined:PythonArgument` |
| `Function`       | `semver-dredd:predefined:Function`       |
| `ClassField`     | `semver-dredd:predefined:ClassField`     |
| `ClassMethod`    | `semver-dredd:predefined:ClassMethod`    |

Plugin snapshot UUIDs are derived similarly:

| Plugin snapshot  | UUID seed                                   |
|------------------|---------------------------------------------|
| `PythonSnapshot` | `semver-dredd:plugin:python:PythonSnapshot` |
| `GoSnapshot`     | `semver-dredd:plugin:go:GoSnapshot`         |
| `JavaSnapshot`   | `semver-dredd:plugin:java:JavaSnapshot`     |

---

## Python Plugin — `PythonSnapshot`

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: python
source:
  kind: module
  path: /path/to/mylib

api:

  # ── Module-level variables ─────────────────────────────────────────
  variables:
    MAX_RETRIES:
      type: int
      default: "3"

    TIMEOUT:
      type: float
      default: "30.0"

  # ── Top-level functions ────────────────────────────────────────────
  functions:
    compute_area:
      result_type: float
      args:
        - name: width
          type: float
          default: null
          position_only: false
          pos_and_named: true
          named_only: false
        - name: height
          type: float
          default: "1.0"
          position_only: false
          pos_and_named: true
          named_only: false

    greet:
      result_type: str
      args:
        - name: name
          type: str
          default: null
          position_only: false
          pos_and_named: true
          named_only: false
        - name: greeting
          type: str
          default: "'Hello'"
          position_only: false
          pos_and_named: false
          named_only: true

  # ── Classes / types ────────────────────────────────────────────────
  types:
    Circle:
      fields:
        - name: radius
          type: float
          default: null
        - name: color
          type: str
          default: "'red'"
      methods:
        __init__:
          result_type: unknown
          args:
            - name: self
              type: Circle
              default: null
              position_only: false
              pos_and_named: true
              named_only: false
            - name: radius
              type: float
              default: null
              position_only: false
              pos_and_named: true
              named_only: false
        area:
          result_type: float
          args:
            - name: self
              type: Circle
              default: null
              position_only: false
              pos_and_named: true
              named_only: false
```

### Python argument calling conventions

| Flag                  | Meaning              | Position in signature      |
|-----------------------|----------------------|----------------------------|
| `position_only: true` | Before `/`           | Only passable positionally |
| `pos_and_named: true` | Normal               | Passable both ways         |
| `named_only: true`    | After `*` or `*args` | Must use keyword syntax    |

Exactly one of the three flags should be `true` per argument.
`*args` and `**kwargs` variadic parameters are omitted.

---

## Go Plugin — `GoSnapshot`

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: go
source:
  kind: package
  path: ./pkg/geometry

api:
  functions:
    NewPoint:
      result_type: "*Point"
      args:
        - name: x
          type: float64
          default: null
        - name: "y"
          type: float64
          default: null

  types:
    Point:
      fields:
        - name: X
          type: float64
          default: null
        - name: "Y"
          type: float64
          default: null
      methods:
        Distance:
          result_type: float64
          args:
            - name: other
              type: "*Point"
              default: null
```

---

## Java Plugin — `JavaSnapshot`

```yaml
snapshot_type_id: "..."
schema_version: 3
version: "1.0.0"
language: java
source:
  kind: directory
  path: ./src/main/java

api:
  functions:
    MathUtils.add:
      result_type: int
      args:
        - name: a
          type: int
          default: null
        - name: b
          type: int
          default: null

  types:
    Point:
      fields:
        - name: x
          type: double
          default: null
        - name: "y"
          type: double
          default: null
      methods:
        distance:
          result_type: double
          args:
            - name: other
              type: Point
              default: null
```

---

## Predefined Component YAML (standalone)

Each predefined model can also be serialised standalone when used directly:

### `Variable` / `Argument` / `ClassField`

```yaml
snapshot_type_id: "..."     # UUID for Variable / Argument / ClassField
name: my_value
type: int
default: "42"
```

### `PythonArgument`

```yaml
snapshot_type_id: "..."
name: callback
type: Callable
default: null
position_only: false
pos_and_named: true
named_only: false
```

### `Function` / `ClassMethod`

```yaml
snapshot_type_id: "..."     # UUID for Function / ClassMethod
name: compute
result_type: float
args:
  - name: x
    type: float
    default: null
  - name: y
    type: float
    default: null
```

When `Function`/`ClassMethod` args contain `PythonArgument`s, the dict
includes an internal `_arg_kind: python` marker for deserialization.

---

## Change Kind Mapping

| `ChangeKind` | Semver bump | Meaning                            |
|--------------|-------------|------------------------------------|
| `NONE`       | none        | No public API changes              |
| `PATCH`      | patch       | Implementation only                |
| `MINOR`      | minor       | New backwards-compatible additions |
| `BREAKING`   | major       | Removals / incompatible changes    |

---

## Migration from Schema v2

Schema v2 files lack `snapshot_type_id`.  The registry falls back to
`NormalizedSnapshot` when this field is absent.

The Go and Java plugins automatically upgrade their parser output from
schema v2 to v3 via `_upgrade_legacy_yaml()` before returning the snapshot.
