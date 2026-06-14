# Agent Notes — `plugins/`

Official language plugins live here as separately installable Python packages.
Each package exposes a plugin through the `semver_dredd.plugins` entry-point
group.

## Official packages

- `python-3.10-dredd/` — plugin key `python`; runtime introspection using
  Python `inspect`.
- `go-1.20-dredd/` — plugin key `go`; shells out to bundled Go AST parser.
- `java-1.8-dredd/` — plugin key `java`; shells out to bundled regex Java
  parser.
- `javaparser-1.8-dredd/` — plugin key `javaparser`; shells out to bundled
  JavaParser AST parser; entry-point only, not part of core fallback list.
- `semver-dredd-all/` — meta-package installing core + official plugins.
- `semver-dredd-java/` — legacy/compatibility remnants; check carefully before
  editing or relying on it.

## Plugin package pattern

Typical layout:

```text
plugins/<name>/
├── pyproject.toml
├── README.md
└── semver_dredd_<lang>/
    ├── __init__.py
    ├── plugin.py
    └── parser/        # for external parser plugins
```

Entry point example:

```toml
[project.entry-points."semver_dredd.plugins"]
python = "semver_dredd_python:PythonPlugin"
```

## Development commands

```bash
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
pip install -e plugins/javaparser-1.8-dredd

semver-dredd plugin list
semver-dredd plugin info python
semver-dredd snapshot --plugin python --path example.py.pygeometry1 --version 1.0.0
```

## Code style / contracts

- Every plugin subclasses `semverdredd.plugin_base.LanguagePlugin`.
- Required: `name` and `generate_snapshot()`.
- Optional but commonly used: `version`, `description`, `validate_path()`,
  `snapshot_format_class`.
- `generate_snapshot()` should return `SnapshotResult`, not print or raise for
  expected parser failures.
- Custom snapshots must implement `SnapshotFormat` + `Comparable` and include
  stable `SNAPSHOT_TYPE_ID`.
- Parser plugins should bundle parser sources/libs through setuptools package
  data and locate them with `importlib.resources.files()`.

## Scope-related notes

Core currently forwards these keys in the plugin `options` dict:

- `use_color` — CLI styling hint.
- `include` — list of opaque strings from config.
- `exclude` — list of opaque strings from config.
- `plugin_options` — free-form plugin options dict.

As of this note, official plugins receive but do not honor `include`/`exclude`.
If implementing filtering, preserve no-scope behavior exactly and add tests for
empty include/exclude, include-only, exclude-only, include+exclude, and
include-matches-nothing.

Read per-plugin notes before editing parser behavior:

- `plugins/python-3.10-dredd/agent.md`
- `plugins/go-1.20-dredd/agent.md`
- `plugins/java-1.8-dredd/agent.md`
- `plugins/javaparser-1.8-dredd/agent.md`
- `plugins/semver-dredd-all/agent.md`
