# How to write a semver-dredd plugin

This guide is the plugin-author deep dive for `semver-dredd`.

Use it when you need to understand:

- what interface a plugin must implement
- which concepts the core framework expects
- where official examples live
- how plugin packages should be installed and discovered

The official plugins under [`plugins/`](plugins/) are the best concrete
examples:

- [`plugins/python-3.10-dredd/README.md`](plugins/python-3.10-dredd/README.md)
- [`plugins/go-1.20-dredd/README.md`](plugins/go-1.20-dredd/README.md)
- [`plugins/java-1.8-dredd/README.md`](plugins/java-1.8-dredd/README.md)
- [`plugins/javaparser-1.8-dredd/README.md`](plugins/javaparser-1.8-dredd/README.md)

## 1. Architecture

```text
CLI / programmatic API
        |
        v
  PluginManager  ---- discovers plugins via entry points / builtins
        |
        v
  LanguagePlugin ---- generates a snapshot YAML string
        |
        v
 SnapshotFormat + Comparable ---- serialize + diff themselves
        |
        v
   semver-dredd core ---- classifies changes and suggests versions
```

The core/framework boundary is strict:

- **core owns mechanics**: config, plugin discovery, snapshot loading, version
  math, CLI orchestration
- **plugins own API meaning**: parsing, scope semantics, snapshot shape, diffing

## 2. Plugin package shape

Typical package layout:

```text
plugins/my-lang-dredd/
├── pyproject.toml
├── README.md
└── semver_dredd_mylang/
    ├── __init__.py
    └── plugin.py
```

Register the plugin with an entry point:

```toml
[project.entry-points."semver_dredd.plugins"]
mylang = "semver_dredd_mylang:MyLangPlugin"
```

Once installed, it appears in:

```bash
semver-dredd plugin list
semver-dredd plugin info mylang
```

Plugin discovery and inspection are intentionally exposed through the `plugin`
command group; semver-dredd does not currently provide a separate top-level
`semver-dredd list` alias.

## 3. Required interface

Subclass `LanguagePlugin` from `semverdredd.plugin_base`.

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

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
        return "Analyzes MyLang source code"

    @property
    def snapshot_format_class(self) -> type | None:
        return MyLangSnapshot

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        return True, ""

    def generate_snapshot(
        self, path: str, version: str, options: dict[str, Any] | None = None
    ) -> SnapshotResult:
        try:
            snap = MyLangSnapshot(version=version)
            return SnapshotResult(success=True, yaml_content=snap.to_yaml())
        except Exception as exc:
            return SnapshotResult(
                success=False,
                yaml_content="",
                error_message=str(exc),
            )
```

Required pieces:

| Member | Required | Notes |
|--------|----------|-------|
| `name` | yes | CLI plugin key |
| `generate_snapshot()` | yes | must return `SnapshotResult` |
| `version` | no | defaults to `0.0.0` |
| `description` | no | human-facing summary |
| `display_name` | no | defaults from `name` |
| `validate_path()` | no | preflight validation |
| `snapshot_format_class` | no | `None` means `NormalizedSnapshot` |
| `metadata` | no | plugin inventory details |
| `have(feature)` | no | optional feature discovery helper |

## 4. Snapshot contracts and concepts

Your snapshot type must satisfy both framework protocols:

- `SnapshotFormat`: `to_yaml`, `to_dict`, `from_yaml_str`, `from_file`, and a
  `version` property
- `Comparable`: `diff_against(other) -> DiffResult`

Important concepts:

### `SnapshotResult`

This is the return type from `generate_snapshot()`.

- `success=True` with `yaml_content` for a usable snapshot
- `success=False` with `error_message` for expected parser/tool failures

Plugins should not print or raise for routine analysis failures when a clean
error result is sufficient.

### `snapshot_type_id`

Plugin-specific snapshots should serialize a stable top-level UUID string as
`snapshot_type_id`. The registry uses it to choose the correct deserializer.

### `metadata`

Plugins may expose structured metadata consumed by `plugin list/info`.
Useful fields include:

- scope syntax description
- supported plugin options
- runtime requirements
- feature flags

### `have(feature)`

Optional helper for feature discovery. This is already shipped, not planned.
It is useful when a plugin wants to expose lightweight capability checks without
forcing callers to parse free-form metadata.

## 5. Scope, include/exclude, and plugin options

The core framework forwards scope and plugin tuning but does not interpret them.

Your plugin may receive these optional keys in `options`:

- `include`: opaque `list[Any]`
- `exclude`: opaque `list[Any]`
- `plugin_options`: free-form `dict[str, Any]`
- `use_color`: CLI hint only

Core rules:

- `include` / `exclude` must be arrays in config
- item shapes are preserved exactly, including objects
- `plugin_options` is never validated by core
- CLI `--include` / `--exclude` append to config arrays unless `--override` is used

Recommended scope behavior, when it fits your domain:

- empty `include` means “analyze the whole configured source”
- non-empty `include` acts as an allow-list
- `exclude` applies after `include`
- log invalid or match-nothing patterns clearly

Official plugin scope semantics today:

| Plugin | Scope item meaning |
|--------|--------------------|
| `python` | dotted module/package names |
| `go` | relative import paths under the analyzed root |
| `java` | package prefixes |
| `javaparser` | package prefixes |
| `bundle` | paths to VERSION files in `include[]` |

## 6. Schema and serialization guidance

Use [`SCHEMA.md`](SCHEMA.md) for the authoritative snapshot and config reference.

Important nuance:

- plugin-specific snapshots currently serialize a v3-style envelope with
  `snapshot_type_id`
- the built-in `NormalizedSnapshot` remains a separate schema-version-2 default
  model

Do not flatten those two ideas together in plugin docs or tests.

## 7. Examples to follow

Use the official plugins as reference implementations:

- Python plugin: runtime inspection, dotted-name scope
- Go plugin: bundled parser binary, import-path scope
- Java plugin: regex parser, package-prefix scope
- JavaParser plugin: AST parser, package-prefix scope
- Bundle plugin: built into core, dependency VERSION-file snapshots

The repo also contains config and workflow references:

- [`example/semver_showcase.yaml`](example/semver_showcase.yaml)
- [`example/demo_config_showcase.sh`](example/demo_config_showcase.sh)

## 8. Installation expectations

Plugins are supposed to be installed like normal Python packages.

Examples:

```bash
pip install python-3.10-dredd
pip install ./plugins/my-lang-dredd
poetry run pip install -e plugins/my-lang-dredd
```

After installation, discovery is automatic through entry points.

If your plugin needs external tools, document them in your plugin README and, if
possible, expose them in `metadata["runtime_requirements"]`.

## 9. Plugin README checklist

Each plugin README should be verbose enough to answer:

- how to install it
- which CLI key it registers
- what `--path` means for that language
- what `include` / `exclude` items look like
- whether extra toolchains are required
- at least one real `snapshot` example
- at least one `init` / `status` example when the workflow is supported

## 10. Validation checklist

Before calling a plugin done:

- `semver-dredd plugin list` shows it
- `semver-dredd plugin info <name>` is accurate
- a real `snapshot` command succeeds
- snapshots round-trip through the registry
- `diff_against()` classifies changes correctly
- README examples match actual CLI behavior
