# How to Write a semver-dredd Language Plugin

This guide walks you through creating a custom language plugin for
[semver-dredd](https://github.com/sr9000/semver-dredd). By the end, your
plugin will:

- Be discovered automatically via Python entry points
- Generate API snapshots from source code
- Support diff / semver bump detection via the core engine

The `javaparser-1.8-dredd` plugin is used as a concrete reference throughout.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Scaffold](#2-project-scaffold)
3. [Implement the Plugin Class](#3-implement-the-plugin-class)
4. [Define a Custom Snapshot Format](#4-define-a-custom-snapshot-format)
5. [Implement Serialization](#5-implement-serialization)
6. [Implement Diff (Comparable)](#6-implement-diff-comparable)
7. [Register via Entry Points](#7-register-via-entry-points)
8. [Package Data & External Parsers](#8-package-data--external-parsers)
9. [Testing](#9-testing)
10. [Checklist](#10-checklist)

---

## 1. Architecture Overview

```
┌──────────────────────┐
│  semver-dredd CLI     │
│  or programmatic API  │
└──────┬───────────────┘
       │  discovers via entry points
       ▼
┌──────────────────────┐      ┌────────────────────────┐
│   PluginManager      │─────►│  YourPlugin            │
│  (plugin_manager.py) │      │  (LanguagePlugin ABC)  │
└──────────────────────┘      └──────┬─────────────────┘
                                     │
                              generates snapshot
                                     │
                                     ▼
                              ┌──────────────────────┐
                              │  YourSnapshot         │
                              │  (SnapshotFormat +    │
                              │   Comparable)         │
                              └──────┬────────────────┘
                                     │
                              registered in
                                     │
                                     ▼
                              ┌──────────────────────┐
                              │  SnapshotRegistry     │
                              │  (by UUID)            │
                              └──────────────────────┘
```

**Key contracts:**

| Interface | Module | Purpose |
|-----------|--------|---------|
| `LanguagePlugin` (ABC) | `semverdredd.plugin_base` | The plugin itself — name, validation, snapshot generation |
| `SnapshotFormat` (Protocol) | `snapshot.protocols` | Serialization: `to_yaml`, `from_yaml_str`, `from_file`, `to_dict` |
| `Comparable` (Protocol) | `snapshot.protocols` | Self-diffing: `diff_against(other) → DiffResult` |
| `SnapshotRegistry` | `semverdredd.registry` | UUID-based type lookup for YAML deserialization |

---

## 2. Project Scaffold

Create your plugin as a standalone Python package:

```
plugins/my-lang-dredd/
├── pyproject.toml
├── README.md
└── semver_dredd_mylang/
    ├── __init__.py
    └── plugin.py
```

Minimal `__init__.py`:

```python
"""My language plugin for semver-dredd."""

from semver_dredd_mylang.plugin import MyLangPlugin

__all__ = ["MyLangPlugin"]
__version__ = "1.0.0"
```

---

## 3. Implement the Plugin Class

Subclass `LanguagePlugin` from `semverdredd.plugin_base`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult


class MyLangPlugin(LanguagePlugin):
    """My language support for semver-dredd."""

    @property
    def name(self) -> str:
        # Unique identifier used in CLI: --plugin mylang
        return "mylang"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes MyLang source code"

    @property
    def snapshot_format_class(self) -> type:
        """Return your custom snapshot class (or None for NormalizedSnapshot)."""
        return MyLangSnapshot

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate that the given path is suitable for analysis."""
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        if not p.is_dir():
            return False, f"Path must be a directory: {path}"
        source_files = list(p.rglob("*.mylang"))
        if not source_files:
            return False, f"No .mylang files found in: {path}"
        return True, ""

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate a YAML snapshot string.

        This is where your core logic lives. You can:
        - Parse source files directly in Python
        - Shell out to an external tool (compiler, AST parser)
        - Use a library binding

        The ``options`` dict carries framework- and user-provided hints.
        Keys you may receive (all optional — ignore what you don't use):
        - ``use_color`` (bool): set by the CLI for log styling
        - ``include`` / ``exclude`` (list): analysis scope from
          .semver.yaml; item syntax is up to your plugin
        - ``plugin_options`` (dict): free-form options from .semver.yaml,
          never validated by the framework

        Must return a SnapshotResult with success=True and yaml_content
        containing a valid YAML string, or success=False with an error_message.
        """
        try:
            snap = MyLangSnapshot(version=version, ...)
            return SnapshotResult(success=True, yaml_content=snap.to_yaml())
        except Exception as e:
            return SnapshotResult(
                success=False, yaml_content="", error_message=str(e)
            )
```

### Required properties/methods

| Member | Required | Description |
|--------|----------|-------------|
| `name` | **Yes** | Unique plugin identifier (used in `--plugin <name>`) |
| `generate_snapshot()` | **Yes** | Generates the snapshot YAML |
| `version` | No | Plugin version string (default: `"0.0.0"`) |
| `description` | No | Human-readable description |
| `display_name` | No | Pretty name (default: `name.capitalize()`) |
| `validate_path()` | No | Validate source path before analysis |
| `snapshot_format_class` | No | Custom snapshot class (default: `None` → NormalizedSnapshot) |

### Scope and options contract

The core framework does **not** interpret API scope. It only forwards values to
your plugin:

```python
options = options or {}
include = options.get("include", [])
exclude = options.get("exclude", [])
plugin_options = options.get("plugin_options", {})
```

Current core behavior requires `include` and `exclude` to be arrays and keeps
item shapes unchanged. Item syntax remains plugin-specific. A plugin may use strings,
objects, paths, package names, URL fragments, operation IDs, or any other shape
that is natural for its API surface.

Recommended semantics, where they make sense for your domain:

- empty `include` means “analyze the whole configured `path` API surface”;
- non-empty `include` is an allow-list;
- apply `exclude` after `include`;
- make `include` recursive by default;
- support explicit `*` in `exclude` if your users need “exclude nested members”;
- log invalid patterns and match-nothing patterns, with severity chosen by the
  plugin.

Example for a package-like domain:

```yaml
include:
  - api/v1
  - api/experimental
exclude:
  - api/v1/admin
  - api/experimental/*
```

Dot-separated strings such as `com.example.api` or `mypackage.core` are a good
convention for languages that naturally use them, but they are not a framework
requirement.

`plugin_options` is the plugin-specific escape hatch for compiler flags,
timeouts, parser tuning, classpaths, source levels, authentication settings, and
similar details. The framework never validates this dictionary. Prefer putting
semantic API-surface selection in `include` / `exclude`, not in
`plugin_options`.

### Planned optional feature discovery

The minimal versioning contract should remain `generate_snapshot()` plus a
snapshot that can diff itself. For future optional integrations, the planned
pre-1.0 direction is a feature-discovery method such as:

```python
plugin.have("feature name")
```

This is **not implemented yet**. The intent is to let core use optional plugin
capabilities, such as richer metadata or timestamps, without making those
capabilities mandatory for all plugins.

---

## 4. Define a Custom Snapshot Format

Every snapshot class needs:

1. A **UUID** (`SNAPSHOT_TYPE_ID`) — unique identifier for registry dispatch
2. Implementation of the **`SnapshotFormat`** protocol (serialization)
3. Implementation of the **`Comparable`** protocol (diffing)

### Generate a stable UUID

```python
import uuid

MY_SNAPSHOT_TYPE_ID = str(
    uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:plugin:mylang:MyLangSnapshot")
)
```

### Skeleton

```python
import uuid as _uuid
import yaml
from pathlib import Path
from typing import Any

from snapshot.predefined import (
    Argument,
    ClassField,
    ClassMethod,
    Function,
)

MY_SNAPSHOT_TYPE_ID = str(
    _uuid.uuid5(_uuid.NAMESPACE_URL, "semver-dredd:plugin:mylang:MyLangSnapshot")
)


class MyLangSnapshot:
    """Custom snapshot format for MyLang."""

    SNAPSHOT_TYPE_ID: str = MY_SNAPSHOT_TYPE_ID

    def __init__(
        self,
        version: str = "",
        source_kind: str = "directory",
        source_path: str = "",
        functions: dict[str, Function] | None = None,
        types: dict[str, tuple[list[ClassField], dict[str, ClassMethod]]] | None = None,
    ) -> None:
        self._version = version
        self.source_kind = source_kind
        self.source_path = source_path
        self.functions = functions or {}
        self.types = types or {}

    @property
    def version(self) -> str:
        return self._version

    # ... serialization and diff methods (see next sections)
```

### Using predefined components

The `snapshot.predefined` module provides reusable building blocks:

| Component | Description |
|-----------|-------------|
| `Variable` | Module-level variable/constant (name, type, default) |
| `Argument` | Function parameter (name, type, default) |
| `Function` | Standalone callable (name, result_type, args) |
| `ClassField` | Class field/attribute (name, type, default) |
| `ClassMethod` | Class method (name, result_type, args) |

These are immutable dataclasses with stable UUIDs, already registered in the
global registry on import. Use them to represent your API surface.

---

## 5. Implement Serialization

Your snapshot class must implement these methods:

```python
class MyLangSnapshot:
    # ...existing __init__...

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for YAML serialization."""
        functions = {
            name: {
                "result_type": f.result_type,
                "args": [
                    {"name": a.name, "type": a.type, "default": a.default}
                    for a in f.args
                ],
            }
            for name, f in self.functions.items()
        }
        types = {}
        for type_name, (fields, methods) in self.types.items():
            types[type_name] = {
                "fields": [
                    {"name": cf.name, "type": cf.type, "default": cf.default}
                    for cf in fields
                ],
                "methods": {
                    mname: {
                        "result_type": m.result_type,
                        "args": [
                            {"name": a.name, "type": a.type, "default": a.default}
                            for a in m.args
                        ],
                    }
                    for mname, m in methods.items()
                },
            }
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "schema_version": 3,
            "version": self._version,
            "language": "mylang",
            "source": {"kind": self.source_kind, "path": self.source_path},
            "api": {"functions": functions, "types": types},
        }

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MyLangSnapshot":
        """Deserialize from a YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "MyLangSnapshot":
        """Load from a file path."""
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "MyLangSnapshot":
        """Internal: build from parsed YAML dict."""
        source = data.get("source", {})
        api = data.get("api", {})

        functions = {
            name: Function(
                name=name,
                result_type=f.get("result_type", "void"),
                args=tuple(
                    Argument(
                        name=a.get("name", ""),
                        type=a.get("type", "unknown"),
                        default=a.get("default"),
                    )
                    for a in f.get("args", [])
                ),
            )
            for name, f in api.get("functions", {}).items()
        }

        types = {}
        for type_name, td in api.get("types", {}).items():
            fields = [
                ClassField(
                    name=fd.get("name", ""),
                    type=fd.get("type", "unknown"),
                    default=fd.get("default"),
                )
                for fd in td.get("fields", [])
            ]
            methods = {
                mname: ClassMethod(
                    name=mname,
                    result_type=m.get("result_type", "void"),
                    args=tuple(
                        Argument(
                            name=a.get("name", ""),
                            type=a.get("type", "unknown"),
                            default=a.get("default"),
                        )
                        for a in m.get("args", [])
                    ),
                )
                for mname, m in td.get("methods", {}).items()
            }
            types[type_name] = (fields, methods)

        return cls(
            version=data.get("version", ""),
            source_kind=source.get("kind", "directory"),
            source_path=source.get("path", ""),
            functions=functions,
            types=types,
        )
```

### YAML format requirements

Your YAML **must** include `snapshot_type_id` as a top-level field. This is
how the registry knows which class to use for deserialization:

```yaml
snapshot_type_id: "your-uuid-here"
schema_version: 3
version: "1.0.0"
language: mylang
source:
  kind: directory
  path: ./src
api:
  functions: { ... }
  types: { ... }
```

### Snapshot YAML quick reference

Plugin authors should not need to jump between documents for the core envelope.
Keep this shape in mind even when your domain does not have “functions” or
“types”:

```yaml
snapshot_type_id: "stable-plugin-snapshot-uuid"
schema_version: 3
version: "1.0.0"
language: mylang
source:
  kind: directory      # module | package | directory | file | URL | aggregate | ...
  path: ./src
api:
  # Domain-specific content. NormalizedSnapshot uses functions/types;
  # your plugin can use commands, endpoints, messages, dependencies, etc.
  functions: {}
  types: {}
```

For reusable code-like snapshots, the predefined component models serialize in
the same registry-friendly style:

```yaml
snapshot_type_id: "<FUNCTION_TYPE_ID>"
name: compute_area
result_type: float
args:
  - snapshot_type_id: "<ARGUMENT_TYPE_ID>"
    name: radius
    type: float
    default: null
```

See `docs/schema.md` and `snapshot/README.md` for the full schema reference.
Planned pre-1.0 snapshot evolution should also record plugin/generator
provenance so users can trace which plugin and config candidate created a
snapshot.

---

## 6. Implement Diff (Comparable)

The core engine calls `old_snapshot.diff_against(new_snapshot)` to detect
API changes. The easiest approach is to convert your snapshot to a
`NormalizedSnapshot` and delegate:

```python
class MyLangSnapshot:
    # ...existing code...

    def diff_against(self, other: "MyLangSnapshot"):
        """Compare self against other for API changes."""
        return _to_normalized(self).diff_against(_to_normalized(other))


def _to_normalized(snap: MyLangSnapshot):
    """Convert to NormalizedSnapshot for built-in diff logic."""
    from snapshot.models import (
        NormalizedSnapshot,
        FunctionSignature,
        TypeDefinition,
        Parameter,
        Field,
    )

    functions = {}
    for name, func in snap.functions.items():
        params = tuple(
            Parameter(name=a.name, type=a.type, optional=(a.default is not None))
            for a in func.args
        )
        functions[name] = FunctionSignature(name=name, parameters=params, returns=())

    types = {}
    for type_name, (fields_list, methods_dict) in snap.types.items():
        fields = tuple(Field(name=f.name, type=f.type) for f in fields_list)
        methods = {}
        for mname, method in methods_dict.items():
            mparams = tuple(
                Parameter(name=a.name, type=a.type, optional=(a.default is not None))
                for a in method.args
            )
            methods[mname] = FunctionSignature(
                name=mname, parameters=mparams, returns=()
            )
        types[type_name] = TypeDefinition(
            name=type_name, fields=fields, methods=methods
        )

    return NormalizedSnapshot(
        version=snap.version,
        language="mylang",
        functions=functions,
        types=types,
    )
```

**`DiffResult`** returned by `diff_against` has:

| Field | Type | Description |
|-------|------|-------------|
| `change_kind` | `ChangeKind` | `NONE`, `PATCH`, `MINOR`, or `BREAKING` |
| `breaking` | `tuple[str, ...]` | Human-readable descriptions of breaking changes |
| `added` | `tuple[str, ...]` | Human-readable descriptions of additions |

---

## 7. Register via Entry Points

The plugin manager discovers plugins via the `semver_dredd.plugins` entry
point group. Configure this in your `pyproject.toml`:

```toml
[project]
name = "my-lang-dredd"
version = "1.0.0"
description = "MyLang language plugin for semver-dredd"
requires-python = ">=3.10"
dependencies = [
    "semver-dredd>=0.1.0",
]

[project.entry-points."semver_dredd.plugins"]
mylang = "semver_dredd_mylang:MyLangPlugin"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

The entry point format is:

```
<plugin_name> = "<module_path>:<ClassName>"
```

- **`<plugin_name>`** — must match `LanguagePlugin.name` (used in `--plugin <name>`)
- **`<module_path>`** — dotted path to the module containing the class
- **`<ClassName>`** — the `LanguagePlugin` subclass

After `pip install ./plugins/my-lang-dredd`, the plugin will be automatically
discovered. No changes to semver-dredd core code are needed.

### Verifying discovery

```bash
# Install
pip install ./plugins/my-lang-dredd

# Check
semver-dredd plugin list
# Should show: mylang  1.0.0  entry_point  semver_dredd_mylang:MyLangPlugin
```

---

## 8. Package Data & External Parsers

If your plugin shells out to an external parser (like the Java plugins do),
bundle the parser sources and/or binaries using setuptools package data:

```toml
[tool.setuptools.package-data]
semver_dredd_mylang = [
    "parser/*.java",
    "parser/lib/*.jar",
]
```

Access bundled resources at runtime using `importlib.resources`:

```python
from importlib.resources import files

def _get_parser_dir():
    parser_pkg = files("semver_dredd_mylang").joinpath("parser")
    return Path(str(parser_pkg))
```

### Compile-on-the-fly pattern

The Java plugins compile their parser on first run:

```python
def _compile_parser(self, parser_dir, classpath):
    src = parser_dir / "Main.java"
    cls_file = parser_dir / "Main.class"
    # Skip if already compiled and up-to-date
    if cls_file.exists() and cls_file.stat().st_mtime >= src.stat().st_mtime:
        return True, ""
    # Compile
    subprocess.run(["javac", "-cp", classpath, str(src)], check=True, ...)
```

---

## 9. Testing

Write tests that verify:

1. **Snapshot generation** — given source files, the plugin produces valid YAML
2. **Round-trip** — `from_yaml_str(snap.to_yaml())` reconstructs the same data
3. **Diff detection** — comparing two snapshots yields correct `ChangeKind`
4. **Scope behavior** — empty include, include-only, exclude-only,
   include+exclude, invalid patterns, and match-nothing cases follow your
   documented semantics
5. **Option tolerance** — unknown `plugin_options` do not crash the plugin

Example test structure:

```python
def test_generate_snapshot():
    plugin = MyLangPlugin()
    result = plugin.generate_snapshot(
        path="./example/mylang/v1",
        version="1.0.0",
    )
    assert result.success
    assert "snapshot_type_id" in result.yaml_content

def test_round_trip():
    snap = MyLangSnapshot(version="1.0.0", functions={...}, types={...})
    yaml_str = snap.to_yaml()
    restored = MyLangSnapshot.from_yaml_str(yaml_str)
    assert restored.version == snap.version

def test_diff_breaking():
    old = MyLangSnapshot(version="1.0.0", functions={"foo": ...}, types={})
    new = MyLangSnapshot(version="2.0.0", functions={}, types={})  # removed foo
    result = old.diff_against(new)
    assert result.change_kind == ChangeKind.BREAKING

def test_diff_minor():
    old = MyLangSnapshot(version="1.0.0", functions={}, types={})
    new = MyLangSnapshot(version="1.1.0", functions={"bar": ...}, types={})
    result = old.diff_against(new)
    assert result.change_kind == ChangeKind.MINOR
```

---

## 10. Checklist

Before publishing your plugin, verify:

- [ ] **Plugin class** extends `LanguagePlugin` with required `name` and
      `generate_snapshot()`
- [ ] **Snapshot class** has `SNAPSHOT_TYPE_ID` (UUID string)
- [ ] **Snapshot class** implements `to_yaml()`, `from_yaml_str()`,
      `from_file()`, `to_dict()`
- [ ] **Snapshot class** implements `diff_against()` (Comparable protocol)
- [ ] **YAML output** includes `snapshot_type_id` as a top-level field
- [ ] **`pyproject.toml`** has entry point under `semver_dredd.plugins`
- [ ] **`snapshot_format_class`** property returns your custom snapshot class
- [ ] **`pip install`** works and `semver-dredd plugin list` shows the plugin
- [ ] **Tests** cover generation, round-trip, and diff scenarios
- [ ] **README** documents installation and usage
- [ ] **Plugin docs / `plugin info`** document include/exclude semantics,
      supported `plugin_options`, external tools, and known limitations
- [ ] **Scope tests** prove the documented include/exclude behavior

---

## Reference: Existing Plugins

| Plugin | Package | Plugin Name | Approach |
|--------|---------|-------------|----------|
| Python | `python-3.10-dredd` | `python` | Runtime import/introspection via `inspect` |
| Go | `go-1.20-dredd` | `go` | Bundled Go AST parser |
| Java (regex) | `java-1.8-dredd` | `java` | Regex-based Java parser |
| Java (AST) | `javaparser-1.8-dredd` | `javaparser` | JavaParser library |

Current status: these official plugins accept the `options` parameter, but do
not yet honor `include`, `exclude`, or most plugin-specific options during
analysis.

Planned official scope conventions:

| Plugin | Planned `include` / `exclude` unit |
|--------|------------------------------------|
| `python` | Python module/package names; recursive module discovery; respect `__all__`; ignore names starting `_` |
| `go` | Go import paths; package-level filtering; tests are never API surface |
| `java` | Java package prefixes |
| `javaparser` | Java package prefixes |

Study the `javaparser-1.8-dredd` plugin for a complete, well-documented
example of an entry-point-only plugin with an external parser.
