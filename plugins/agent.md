# Agent Notes — `plugins/`

Official language plugins as separately installable packages, each exposed via the
`semver_dredd.plugins` entry-point group.

## Packages (read each one's agent.md before editing parser behavior)

- `python-3.10-dredd/` — key `python`; runtime `inspect` introspection.
- `go-1.20-dredd/` — key `go`; bundled Go AST parser.
- `java-1.8-dredd/` — key `java`; bundled regex Java parser.
- `javaparser-1.8-dredd/` — key `javaparser`; bundled JavaParser AST parser;
  entry-point only, NOT in core fallback list.
- `semver-dredd-all/` — meta-package: core + official plugins.
- `semver-dredd-java/` — legacy remnant; verify before relying on it.

## Package pattern

```text
plugins/<name>/
├── pyproject.toml
├── README.md
└── semver_dredd_<lang>/
    ├── __init__.py
    ├── plugin.py
    └── parser/        # external-parser plugins only
```

```toml
[project.entry-points."semver_dredd.plugins"]
python = "semver_dredd_python:PythonPlugin"
```

## Commands

```bash
pip install -e plugins/python-3.10-dredd   # + go/java/javaparser
semver-dredd plugin list
semver-dredd plugin info python
semver-dredd snapshot --plugin python --path example.py.pygeometry1 --version 1.0.0
```

## Contracts

- Subclass `semverdredd.plugin_base.LanguagePlugin`.
- Required: `name`, `generate_snapshot()`.
- Optional: `version`, `description`, `validate_path()`, `snapshot_format_class`.
- `generate_snapshot()` returns `SnapshotResult`; never print/raise on expected
  parser failures.
- Custom snapshots implement `SnapshotFormat` + `Comparable` with stable
  `SNAPSHOT_TYPE_ID`.
- Bundle parser sources/libs via setuptools package data; locate with
  `importlib.resources.files()`.

## Scope

Core forwards these `options` keys: `use_color` (CLI hint), `include`, `exclude`
(opaque `list[Any]`), `plugin_options` (free-form dict). All four official
plugins (`python`, `go`, `java`, `javaparser`) now honor `include`/`exclude`;
each plugin's local `agent.md` and README document its exact item syntax
(module dotted names for Python, package prefixes for Java/JavaParser, import
paths for Go). Shared conventions: empty `include` means "analyze everything";
`exclude` applies after `include`; official plugins never use glob syntax; an
`include` that matches nothing yields an empty API (logged as a warning), not
a fallback to no-scope behavior.

