# semver-dredd — Architecture & Plugin Roadmap

## Executive Summary

semver-dredd is a **language-agnostic, snapshot-agnostic** tool for automatically
classifying API changes and suggesting the next semantic version.

The core package provides only three things:

1. **Version arithmetic** — parse, compare, and increment semantic versions
2. **Plugin infrastructure** — discover, load, and invoke language plugins
3. **CLI / programmatic shell** — drive the workflow from a terminal or Python code

Everything else — how to extract an API snapshot from source code, how to
represent that snapshot, and how to compare two snapshots — is delegated to
**plugins** and **snapshot types**.

---

## Design Principles

| Principle         | Implication                                                             |
|-------------------|-------------------------------------------------------------------------|
| Language-agnostic | The core never imports language-specific code                           |
| Snapshot-agnostic | The core never inspects the internal structure of a snapshot            |
| Diff-agnostic     | Diff logic lives on snapshot objects (`diff_against`), not in the core  |
| Open-closed       | New languages / snapshot formats can be added without touching the core |
| Composable        | Plugins may reuse predefined models or define entirely new ones         |
| Registry-driven   | YAML round-trips are dispatched by a UUID stored inside the YAML itself |

---

## Package Layout

```
semver-dredd/                       # core package
├── pyproject.toml
├── semverdredd/                    # core logic
│   ├── __init__.py                 # public API: compare(), compare_and_suggest(), exports
│   ├── plugin_base.py              # LanguagePlugin ABC + SnapshotResult
│   ├── plugin_manager.py           # discovery, loading, PluginInfo registry
│   ├── registry.py                 # UUID → snapshot class registry
│   ├── diff.py                     # DefaultDiffScorer + compare_snapshots()
│   ├── snapshot_io.py              # load_snapshot() / load_snapshot_yaml()
│   ├── version.py                  # Version parsing + increment
│   └── result.py                   # CompareResult, SuggestVersionResult (pure data)
├── snapshot/                       # snapshot type system
│   ├── __init__.py                 # re-exports for convenience
│   ├── change_kind.py              # ChangeKind enum (NONE/PATCH/MINOR/BREAKING)
│   ├── protocols.py                # SnapshotFormat, Comparable, DiffScorer, DiffResult
│   ├── models.py                   # NormalizedSnapshot (built-in cross-language format)
│   └── predefined/                 # reusable cross-language building blocks
│       ├── __init__.py
│       └── models.py               # Variable, Argument, Function, ClassField, ClassMethod
├── cli/
│   ├── __init__.py                 # CLI entry point + all command implementations
│   ├── __main__.py
│   └── config.py                   # .semver.yaml / .env / env-var loading
└── tests/

plugins/                            # official language plugins (each installable separately)
├── semver-dredd-python/
│   ├── pyproject.toml
│   └── semver_dredd_python/
│       ├── __init__.py
│       └── plugin.py               # PythonPlugin + PythonSnapshot + PythonArgument
├── semver-dredd-go/
│   ├── pyproject.toml
│   └── semver_dredd_go/
│       ├── __init__.py
│       ├── plugin.py               # GoPlugin
│       └── parser/                 # bundled Go AST parser source
│           ├── go.mod
│           ├── go.sum
│           └── main.go
├── semver-dredd-java/
│   ├── pyproject.toml
│   └── semver_dredd_java/
│       ├── __init__.py
│       ├── plugin.py               # JavaPlugin
│       └── parser/                 # bundled Java reflection parser
│           ├── main.java
│           └── lib/
│               └── snakeyaml-2.2.jar
└── semver-dredd-all/
    └── pyproject.toml              # meta-package: depends on core + all three plugins
```

---

## Core Subsystems

### 1. ChangeKind

A simple ordered enum in `snapshot/change_kind.py`:

```
NONE < PATCH < MINOR < BREAKING
```

The core uses this enum as the sole output of any diff operation.  It has no
knowledge of what caused the change.

### 2. Version

`semverdredd/version.py` provides:

- `Version.parse(string)` — parse `"1.2.3"` or `"1.2.20260305001"`
- `version.increment(change_kind)` — return the next version for a given change
- `generate_patch()` — produce a datestamp-based patch number (`YYYYMMDDZZZ`)

Patch numbers encode both a date and an intra-day increment, so the output is
always strictly monotonically increasing within a calendar day.

### 3. SnapshotFormat protocol

Every snapshot class — built-in or plugin-supplied — must satisfy the
`SnapshotFormat` protocol defined in `snapshot/protocols.py`:

```python
class SnapshotFormat(Protocol):
    SNAPSHOT_TYPE_ID: str        # UUID that identifies this format in YAML

    @property
    def version(self) -> str: ...

    def to_yaml(self) -> str: ...

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "SnapshotFormat": ...

    @classmethod
    def from_file(cls, path: Path | str) -> "SnapshotFormat": ...

    def to_dict(self) -> dict[str, Any]: ...
```

The `SNAPSHOT_TYPE_ID` is a **UUID string** (generated once and hardcoded).
It is embedded as `snapshot_type_id` in every serialized YAML file so the
registry can pick the correct deserializer when loading unknown files.

### 4. Comparable protocol

Diff logic lives **on the snapshot**, not in the core engine:

```python
class Comparable(Protocol):
    def diff_against(self, other: "Comparable") -> DiffResult: ...
```

The core engine calls `old_snapshot.diff_against(new_snapshot)` and receives a
`DiffResult(change_kind, breaking, added)`.  It never inspects the snapshot's
internal structure.

> ✅ `DiffScorer` (the older fallback interface) has been removed.  Every
> snapshot type **must** implement `Comparable` (`diff_against`).  Snapshots
> may raise `TypeError` when `other` is not of the expected type.

### 5. SnapshotRegistry

`semverdredd/registry.py` maps `UUID → snapshot class`:

```python
from semverdredd.registry import default_registry

# Register at startup (plugins do this automatically)
default_registry.register(MySnapshot)

# Load from file — the registry resolves the correct class automatically
snapshot = default_registry.load_file("baked.yaml")
```

Registration is **idempotent** and safe to call multiple times.  On import,
`semverdredd/__init__.py` calls `load_plugins()` which triggers registration
of all installed plugins' snapshot classes.

### 6. LanguagePlugin ABC

`semverdredd/plugin_base.py` defines the contract every plugin must implement:

```python
class LanguagePlugin(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique language identifier (e.g. 'python', 'go', 'java')."""

    @abstractmethod
    def generate_snapshot(
        self,
        path: str,
        version: str,
        options: dict[str, Any] | None = None,
    ) -> SnapshotResult:
        """Generate a YAML snapshot string for the given source path."""

    # --- optional hooks ---

    @property
    def snapshot_format_class(self) -> type[SnapshotFormat] | None:
        """Return a custom snapshot class, or None to use NormalizedSnapshot."""
        return None

    @property
    def diff_scorer(self) -> DiffScorer | None:
        """Return a custom DiffScorer, or None to use the default Comparable-based one."""
        return None
```

`generate_snapshot` returns a `SnapshotResult(success, yaml_content, error_message)`.
The YAML string is whatever the plugin's snapshot class produces; the core
never parses it directly.

### 7. PluginManager

`semverdredd/plugin_manager.py` handles discovery, loading, and access:

- Reads `semver_dredd.plugins` entry-point group (standard Python mechanism)
- Also scans `~/.semver-dredd/plugins/` for user-installed packages
- Falls back to direct imports for plugins present in the same environment
- On successful load, registers each plugin's `snapshot_format_class` in the
  `default_registry`

```python
from semverdredd.plugin_manager import get_plugin, list_plugins, get_plugin_manager

plugin = get_plugin("python")
result = plugin.generate_snapshot("./mypackage", "1.2.3")
```

---

## Snapshot Type System

### Built-in types

| Class                | Module                          | Description                                                                               |
|----------------------|---------------------------------|-------------------------------------------------------------------------------------------|
| `NormalizedSnapshot` | `snapshot/models.py`            | Cross-language snapshot using `FunctionSignature`, `TypeDefinition`, `Field`, `Parameter` |
| `Variable`           | `snapshot/predefined/models.py` | Named value with type and optional default                                                |
| `Argument`           | `snapshot/predefined/models.py` | Function argument (extends Variable)                                                      |
| `Function`           | `snapshot/predefined/models.py` | Callable: name + return type + arg list                                                   |
| `ClassField`         | `snapshot/predefined/models.py` | Class/struct field (extends Variable)                                                     |
| `ClassMethod`        | `snapshot/predefined/models.py` | Class method (extends Function)                                                           |

All built-in types are registered in `default_registry` automatically on import.

### Plugin-supplied types

A plugin may define entirely new snapshot classes (e.g. `PythonSnapshot` in the
Python plugin) as long as they satisfy `SnapshotFormat` + `Comparable`:

```python
class MySnapshot:
    SNAPSHOT_TYPE_ID = "..."   # hardcoded UUID

    @property
    def version(self) -> str:
        ...
    def to_yaml(self) -> str:
        ...
    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MySnapshot":
        ...
    @classmethod
    def from_file(cls, path: Path | str) -> "MySnapshot":
        ...
    def to_dict(self) -> dict[str, Any]:
        ...
    def diff_against(self, other: "MySnapshot") -> DiffResult:
        ...
```

The plugin registers the class via `snapshot_format_class`:

```python
class MyPlugin(LanguagePlugin):
    @property
    def snapshot_format_class(self) -> type:
        return MySnapshot
```

`PluginManager.load_plugins()` detects this and calls
`default_registry.register(MySnapshot)` automatically.

### YAML round-trip

Every YAML file produced by semver-dredd contains a `snapshot_type_id` field:

```yaml
snapshot_type_id: "d4e5f6a7-..."
version: "1.2.3"
# ... rest of snapshot ...
```

Loading is fully automatic:

```python
from semverdredd import load_snapshot

snap = load_snapshot("baked.yaml")  # returns the correct type
```

The registry dispatches to the correct `from_yaml_str` based on the UUID.
Unknown UUIDs fall back to `NormalizedSnapshot` for forward compatibility.

---

## Plugin Development Guide

### Minimal plugin

```python
# my_lang_plugin/plugin.py
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult

class MyLangPlugin(LanguagePlugin):

    @property
    def name(self) -> str:
        return "mylang"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "MyLang language support for semver-dredd"

    def generate_snapshot(self, path, version, options=None):
        # ... analyse source at `path`, produce YAML ...
        yaml_content = run_my_analyser(path, version)
        return SnapshotResult(success=True, yaml_content=yaml_content)
```

The plugin may return YAML that deserializes to any class registered in
the `default_registry` — including `NormalizedSnapshot` or a custom class.

### Using predefined models

```python
from snapshot.predefined import Function, Argument, ClassField, ClassMethod
from snapshot.models import (
    NormalizedSnapshot, FunctionSignature,
    Parameter, TypeDefinition, Field,
)

# Build a NormalizedSnapshot from parsed source
functions = {}
for fn in parsed_api.functions:
    params = tuple(Parameter(name=p.name, type=p.type) for p in fn.params)
    functions[fn.name] = FunctionSignature(name=fn.name, parameters=params)

snap = NormalizedSnapshot(version=version, functions=functions, types={})
return SnapshotResult(success=True, yaml_content=snap.to_yaml())
```

### Custom snapshot type

```python
import uuid, yaml
from snapshot.protocols import DiffResult
from snapshot.change_kind import ChangeKind

MY_SNAPSHOT_TYPE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "myvendor:MyLangSnapshot"))

class MyLangSnapshot:
    SNAPSHOT_TYPE_ID = MY_SNAPSHOT_TYPE_ID

    def __init__(self, version: str, symbols: dict):
        self._version = version
        self.symbols = symbols   # {name: type_str}

    @property
    def version(self) -> str:
        return self._version

    def to_dict(self):
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "version": self._version,
            "symbols": self.symbols,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MyLangSnapshot":
        data = yaml.safe_load(yaml_str)
        return cls(version=data["version"], symbols=data.get("symbols", {}))

    @classmethod
    def from_file(cls, path) -> "MyLangSnapshot":
        from pathlib import Path
        return cls.from_yaml_str(Path(path).read_text())

    # --- diff logic lives here, not in the core ---
    def diff_against(self, other: "MyLangSnapshot") -> DiffResult:
        old_symbols = set(self.symbols)
        new_symbols = set(other.symbols)

        removed = old_symbols - new_symbols
        added_set = new_symbols - old_symbols
        changed = {
            n for n in old_symbols & new_symbols
            if self.symbols[n] != other.symbols[n]
        }

        if removed or changed:
            return DiffResult(
                change_kind=ChangeKind.BREAKING,
                breaking=tuple(f"removed/changed: {n}" for n in removed | changed),
            )
        if added_set:
            return DiffResult(
                change_kind=ChangeKind.MINOR,
                added=tuple(f"added: {n}" for n in added_set),
            )
        return DiffResult(change_kind=ChangeKind.NONE)
```

Then expose it via the plugin:

```python
class MyLangPlugin(LanguagePlugin):
    @property
    def snapshot_format_class(self):
        return MyLangSnapshot

    def generate_snapshot(self, path, version, options=None):
        symbols = run_my_analyser(path)
        snap = MyLangSnapshot(version=version, symbols=symbols)
        return SnapshotResult(success=True, yaml_content=snap.to_yaml())
```

### Plugin package structure

```
my-lang-1.0.0/                       # distribution name
├── pyproject.toml
└── my_lang_plugin/                   # importable package
    ├── __init__.py
    └── plugin.py
```

**`pyproject.toml`** must declare the entry-point:

```toml
[project]
name = "my-lang-1.0.0"
version = "1.0.0"
dependencies = ["semver-dredd>=0.1.0"]

[project.entry-points."semver_dredd.plugins"]
mylang = "my_lang_plugin.plugin:MyLangPlugin"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

### Distribution naming convention

Distribution (PyPI) names follow the scheme:

```
# (vendor-aware, supports multiple implementations):
<lang>-<lang_version>-<vendor>-<plugin_version>
# e.g.: python-3.10-dredd, go-1.20-dredd, java-1.8-dredd
```

> ✅ All official plugins have been renamed to follow this convention:
> `python-3.10-dredd`, `go-1.20-dredd`, `java-1.8-dredd`.
> Importable module names (`semver_dredd_python`, `semver_dredd_go`,
> `semver_dredd_java`) and entry-point keys (`python`, `go`, `java`) are
> unchanged for backward compatibility.

The importable module name and entry-point key defined in pyproject.toml.

---

## CLI Usage

```bash
# Initialise a project
semver-dredd init --plugin python ./mypackage

# Check current status against baked baseline
semver-dredd status --plugin go ./mypackage

# Compare two module versions explicitly
semver-dredd compare --plugin java ./v1 ./v2

# Bake current state as the new baseline
semver-dredd bake --plugin python ./mypackage

# One-off snapshot
semver-dredd snapshot --plugin python --path ./mypackage --version 1.2.3

# Plugin management
semver-dredd plugin list
semver-dredd plugin install ./plugins/semver-dredd-go
semver-dredd plugin install go-1.20-gogen-1.0.0      # from PyPI
semver-dredd plugin remove go
semver-dredd plugin info python

# Version utilities
semver-dredd bump --current 1.2.3 --change minor
semver-dredd patch

# Generate a full .semver.yaml template
semver-dredd template --out .semver.yaml
```

All commands that interact with snapshots accept `--baked` and `--version-file`
overrides so multiple modules can coexist in one repository.

### Configuration priority (lowest → highest)

```
.semver.yaml  <  .env file  <  environment variables  <  CLI flags
```

Key environment variables: `SEMVER_DREDD_PLUGIN`, `SEMVER_DREDD_ALLOW_BREAKING`,
`SEMVER_DREDD_COLOR`, `SEMVER_DREDD_BAKED_FILE`, `SEMVER_DREDD_CURRENT_FILE`,
`SEMVER_DREDD_VERSION_FILE`.

---

## Programmatic API

```python
from semverdredd import compare, compare_and_suggest, Version

# Simple comparison
result = compare("./v1", "./v2", plugin="python")
print(result.change_kind)   # ChangeKind.MINOR
print(result.diff.added)    # ("function foo",)

# With version suggestion
result = compare_and_suggest("./v1", "./v2", "1.2.3", plugin="go")
print(result.suggested_version)   # 1.3.20260305001

# Direct plugin access
from semverdredd import get_plugin, list_plugins

go = get_plugin("go")
r = go.generate_snapshot("./mypackage", "1.0.0")
print(r.yaml_content)

for info in list_plugins():
    print(f"{info.name}  v{info.plugin.version}  [{info.origin}]")

# Isolated registry (for testing / multi-tenant use)
from semverdredd import PluginManager

mgr = PluginManager(user_plugin_dir=None)
mgr.register(MyCustomPlugin())
snap_yaml = mgr.get("mylang").generate_snapshot("./src", "2.0.0").yaml_content

# Load a snapshot file (type resolved automatically by UUID)
from semverdredd import load_snapshot
snap = load_snapshot("baked.yaml")
diff = snap.diff_against(load_snapshot("current.yaml"))
```

---

## CI / Git Hook Integration

### GitHub Actions

```yaml
- name: Check API compatibility
  run: semver-dredd status --plugin python ./mypackage
  # exits 0 = no breaking changes
  # exits 10 = breaking changes detected (use --allow-breaking to downgrade to warning)
```

### Pre-push git hook (`.git/hooks/pre-push`)

```bash
#!/bin/bash
semver-dredd status --plugin go ./mypackage
if [ $? -eq 10 ]; then
  echo "Breaking API changes detected. Bump major version before pushing."
  exit 1
fi
```

### Exit codes

| Code | Meaning                                                  |
|------|----------------------------------------------------------|
| `0`  | Success / no breaking changes                            |
| `1`  | Error (bad arguments, plugin not found, parse failure)   |
| `10` | Breaking changes detected and `--allow-breaking` not set |

---

## Official Plugins

| Package                 | Language                          | Entry-point key | Snapshot class                                       |
|-------------------------|-----------------------------------|-----------------|------------------------------------------------------|
| `python-3.10-dredd`     | Python 3.x                        | `python`        | `PythonSnapshot` (custom; extends predefined models) |
| `go-1.20-dredd`         | Go (any version via `go run`)     | `go`            | `GoSnapshot` (custom; extends predefined models)     |
| `java-1.8-dredd`        | Java (any JDK via `javac`/`java`) | `java`          | `JavaSnapshot` (custom; extends predefined models)   |

The Python plugin goes beyond the basic interface:
- Defines `PythonArgument` (extends `Argument` with `position_only`,
  `pos_and_named`, `named_only` flags) — Python calling convention metadata
- Defines `PythonSnapshot` with full Python-specific diff logic
- Registers both types in `default_registry` on import

---

## Snapshot Type Registration Flow

```
pip install semver-dredd-python
         │
         ▼
entry-point registered:
  "semver_dredd.plugins" → "semver_dredd_python:PythonPlugin"

import semverdredd  (or first call to get_plugin / compare)
         │
         ▼
PluginManager.load_plugins()
  ├─ loads PythonPlugin via entry-point (direct import fallback in dev)
  ├─ reads PythonPlugin.snapshot_format_class → PythonSnapshot
  └─ default_registry.register(PythonSnapshot)

load_snapshot("baked.yaml")
         │
         ▼
SnapshotRegistry reads snapshot_type_id from YAML
  ├─ known UUID  → PythonSnapshot.from_yaml_str(...)
  └─ unknown UUID → NormalizedSnapshot.from_yaml_str(...)  (fallback)
```

---

## Pending Work

The following items are known deviations from the ideal final state.
They do not block current functionality but should be addressed over time.

### 1. Move `semverdredd/python_api.py` into the Python plugin

`semverdredd/python_api.py` (260 lines) contains `ModuleAPI`, `ClassAPI`, and
`APISignature` — Python-specific introspection helpers.  They belong in
`plugins/semver-dredd-python/`, not in the language-agnostic core.

**Action:** Move file → update imports → remove from core package.

### 2. Clean up `semverdredd/snapshot.py`

`semverdredd/snapshot.py` (235 lines) contains a legacy Python-centric
`APISnapshot` class that predates the `snapshot/` package.  The only survivor
still actively used by the CLI is `save_version_file`.

**Action:** Extract `save_version_file` to `semverdredd/version.py` or
`semverdredd/snapshot_io.py`, then delete the file.

### 3. Split `cli/__init__.py` into `cli/commands/`

At 1 257 lines `cli/__init__.py` is unwieldy.  Target structure:

```
cli/
├── __init__.py         # main() + argument parser wiring only
├── __main__.py
├── config.py
└── commands/
    ├── __init__.py
    ├── compare.py      # cmd_compare
    ├── status.py       # cmd_status
    ├── bake.py         # cmd_bake
    ├── init.py         # cmd_init
    ├── bump.py         # cmd_bump
    ├── patch.py        # cmd_patch
    ├── snapshot.py     # cmd_snapshot
    ├── template.py     # cmd_template
    └── plugin.py       # cmd_plugin_list/install/remove/info
```

**Action:** Extract command functions one file at a time; keep
`cli/__init__.py` as a thin wiring layer.

---

## Extension Points Summary

| Extension                 | How                                                                                                                                |
|---------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| New language              | Implement `LanguagePlugin`, publish package with `semver_dredd.plugins` entry-point                                                |
| Custom snapshot format    | Implement `SnapshotFormat` + `Comparable`; expose via `plugin.snapshot_format_class`                                               |
| Custom diff logic         | Implement `DiffScorer`; expose via `plugin.diff_scorer` (fallback for non-Comparable snapshots)                                    |
| Custom component types    | Extend `Variable`/`Argument`/`Function`/`ClassField`/`ClassMethod` from `snapshot.predefined`; register UUID in `default_registry` |
| Isolated programmatic use | Instantiate `PluginManager(user_plugin_dir=None)` and register plugins manually                                                    |

---

## References

- [Python Entry Points Specification](https://packaging.python.org/en/latest/specifications/entry-points/)
- [importlib.resources documentation](https://docs.python.org/3/library/importlib.resources.html)
- [semver specification](https://semver.org/)
- `snapshot/README.md` — snapshot type system contract documentation
- `docs/schema.md` — YAML snapshot file format specification
