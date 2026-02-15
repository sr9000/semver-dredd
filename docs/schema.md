# Snapshot Schema v2

This document defines the cross-language API snapshot format used by semver-dredd.

## Overview

A snapshot captures the **public API surface** of a codebase at a specific version. Snapshots are language-agnostic YAML files that can be compared to detect breaking changes, additions, and compute semantic version bumps.

## Schema Version History

| Version | Description                               |
|---------|-------------------------------------------|
| 1       | Initial Python-only format (implicit)     |
| 2       | Cross-language format with explicit types |

## Schema v2 Format

```yaml
schema_version: 2
version: "1.2.20260214001"
language: python|go|java
source:
  kind: module|package|directory
  path: "src/mylib"
api:
  functions:
    FunctionName:
      parameters:
        - name: paramName
          type: "int"
          optional: false
      returns:
        - name: ""
          type: "string"
          optional: false
  types:
    TypeName:
      fields:
        - name: fieldName
          type: "float64"
          optional: false
      methods:
        MethodName:
          parameters: [...]
          returns: [...]
```

## Field Definitions

### Root Level

| Field            | Type    | Required | Description                                |
|------------------|---------|----------|--------------------------------------------|
| `schema_version` | integer | Yes      | Schema version (currently `2`)             |
| `version`        | string  | Yes      | Semantic version string                    |
| `language`       | string  | Yes      | Source language: `python`, `go`, or `java` |
| `source`         | object  | No       | Information about what was analyzed        |
| `api`            | object  | Yes      | The API surface                            |

### Source Object

| Field  | Type   | Required | Description                                      |
|--------|--------|----------|--------------------------------------------------|
| `kind` | string | No       | Type of source: `module`, `package`, `directory` |
| `path` | string | No       | Path that was analyzed                           |

### API Object

| Field       | Type   | Required | Description                        |
|-------------|--------|----------|------------------------------------|
| `functions` | object | Yes      | Map of function name → signature   |
| `types`     | object | Yes      | Map of type name → type definition |

### Function/Method Signature

| Field        | Type  | Required | Description                               |
|--------------|-------|----------|-------------------------------------------|
| `parameters` | array | Yes      | List of parameters                        |
| `returns`    | array | No       | List of return values (omit if void/none) |

### Parameter/Return Object

| Field      | Type    | Required | Description                                       |
|------------|---------|----------|---------------------------------------------------|
| `name`     | string  | Yes      | Parameter name (empty string for unnamed returns) |
| `type`     | string  | Yes      | Type as string (language-specific)                |
| `optional` | boolean | Yes      | Whether the parameter is optional                 |

### Type Definition

| Field     | Type   | Required | Description                    |
|-----------|--------|----------|--------------------------------|
| `fields`  | array  | No       | List of public fields          |
| `methods` | object | No       | Map of method name → signature |

### Field Object

| Field      | Type    | Required | Description                                |
|------------|---------|----------|--------------------------------------------|
| `name`     | string  | Yes      | Field name                                 |
| `type`     | string  | Yes      | Type as string                             |
| `optional` | boolean | No       | Whether field is optional (default: false) |

## Language-Specific Notes

### Python

- **Functions**: Module-level callables (excluding `_` prefixed)
- **Types**: Classes (excluding `_` prefixed)
- **Fields**: Detected from dataclasses, namedtuples, pydantic models, `__slots__`
- **Methods**: Public methods (excluding `_` prefixed, except `__init__`)
- **Types**: May be `"unknown"` if not inferrable

Example:
```yaml
schema_version: 2
version: "1.0.0"
language: python
source:
  kind: module
  path: "mylib"
api:
  functions:
    calculate:
      parameters:
        - name: x
          type: "unknown"
          optional: false
        - name: y
          type: "unknown"
          optional: true
      returns: []
  types:
    Point:
      fields:
        - name: x
          type: "float"
        - name: y
          type: "float"
      methods:
        distance:
          parameters:
            - name: self
              type: "Point"
              optional: false
            - name: other
              type: "Point"
              optional: false
          returns: []
```

### Go

- **Functions**: Exported package-level functions (`ast.IsExported`)
- **Types**: Exported struct types
- **Fields**: Exported struct fields only
- **Methods**: Exported methods with receiver
- **Types**: Full Go type syntax (e.g., `*Point`, `[]int`, `map[string]int`)

Example:
```yaml
schema_version: 2
version: "1.0.0"
language: go
source:
  kind: package
  path: "./pkg/geometry"
api:
  functions:
    Area:
      parameters:
        - name: w
          type: int
          optional: false
        - name: h
          type: int
          optional: false
      returns:
        - name: ""
          type: int
          optional: false
  types:
    Point:
      fields:
        - name: X
          type: float64
        - name: Y
          type: float64
      methods:
        Distance:
          parameters:
            - name: other
              type: "*Point"
              optional: true
          returns:
            - name: ""
              type: float64
              optional: false
```

### Java

- **Functions**: Public static methods (keyed as `ClassName.methodName`)
- **Types**: Public classes, interfaces, records
- **Fields**: Public/protected fields
- **Methods**: Public/protected methods
- **Types**: Java type syntax (e.g., `int`, `String`, `List<String>`)

Example:
```yaml
schema_version: 2
version: "1.0.0"
language: java
source:
  kind: directory
  path: "./src/main/java"
api:
  functions:
    MathUtils.add:
      parameters:
        - name: a
          type: int
          optional: false
        - name: b
          type: int
          optional: false
      returns:
        - name: ""
          type: int
          optional: false
  types:
    Point:
      fields:
        - name: x
          type: double
        - name: y
          type: double
      methods:
        distance:
          parameters:
            - name: other
              type: Point
              optional: false
          returns:
            - name: ""
              type: double
              optional: false
```

## Optionality Semantics

The `optional` field has different meanings per language:

| Language | Optional means... |
|----------|-------------------|
| Python | Has a default value |
| Go | Pointer, slice, map, interface, or variadic |
| Java | Varargs parameter |

## Type Normalization

Types are stored as emitted by the language parser with minimal normalization:
- Whitespace is collapsed
- No cross-language type equivalence is attempted

Comparing types:
- Exact string match required
- Any type change is considered **breaking** by default

## Backward Compatibility

When loading a snapshot:
1. If `schema_version` is missing, assume v1
2. v1 snapshots are upgraded in-memory to v2 format
3. v1 had no `language` field; default to `python`
4. v1 had no `source` field; omit it
5. v1 parameters had no `type`; use `"unknown"`
