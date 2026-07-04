# semver-dredd

Semantic-versioning workflow for public APIs.

`semver-dredd` compares a saved API snapshot with the current source tree,
classifies the change as `NONE`, `PATCH`, `MINOR`, or `BREAKING`, and helps you
write or suggest the next version.

## What it is

- **Core engine** for snapshot loading, diffing, version math, and config
  resolution.
- **Plugin-based API inspection** for different languages and source models.
- **CLI workflow** for initializing a project, checking API drift, baking a new
  release baseline, generating standalone snapshots, and inspecting plugins.
- **Programmatic Python API** for direct use in tests, release automation, or
  custom tooling.

Officially documented plugin keys:

- `python`
- `go`
- `java`
- `javaparser`
- `bundle` (built into core for VERSION-file dependency bundles)

## What it does

semver-dredd supports:

- config-driven workflows via `.semver.yaml`
- `.env` / environment / CLI override precedence
- multi-document config candidate fallback
- plugin-specific `include` / `exclude` scope forwarding
- machine-readable plugin inventory via `plugin list --json|--yaml`
- plugin metadata and generator provenance in plugin snapshots
- pathless `status`, `bake`, and `snapshot` when `source.path` is configured

## Install

```bash
# Core package
pip install semver-dredd

# Install the plugins you want
pip install python-3.10-dredd
pip install go-1.20-dredd
pip install java-1.8-dredd
pip install javaparser-1.8-dredd

# Or install the official meta-package
# (includes python/go/java; install javaparser separately)
pip install semver-dredd-all
```

Development install:

```bash
poetry install --with dev
poetry run pip install -e plugins/python-3.10-dredd
poetry run pip install -e plugins/go-1.20-dredd
poetry run pip install -e plugins/java-1.8-dredd
poetry run pip install -e plugins/javaparser-1.8-dredd
```

## Run it

Typical first-run workflow:

```bash
semver-dredd plugin list
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

Plugin inspection lives under the `plugin` command group. The supported
inventory command is `semver-dredd plugin list` (there is no top-level
`semver-dredd list` alias).

The important workflow rule is:

- `init` requires an explicit `--plugin`
- later commands can use `.semver.yaml` defaults
- CLI arguments override environment, which overrides config

Language examples:

```bash
# Python
semver-dredd init mypackage --plugin python --version 1.0.0
semver-dredd status --details

# Go
semver-dredd init ./pkg/api --plugin go --version 1.0.0
semver-dredd status ./pkg/api --plugin go --details

# Java (regex parser)
semver-dredd init ./src/main/java --plugin java --version 1.0.0

# JavaParser (AST parser)
semver-dredd init ./src/main/java --plugin javaparser --version 1.0.0
```

For full command reference and common workflows, see [`USAGE.md`](USAGE.md).

## Configuration

The main project config is `.semver.yaml`.

- Generate a commented template with `semver-dredd template`
- See a full, worked example in
  [`example/semver_showcase.yaml`](example/semver_showcase.yaml)
- See the config/schema reference in [`SCHEMA.md`](SCHEMA.md)
- Environment variables (`SEMVER_DREDD_*`) and the full precedence order
  (config < `.env` < environment < CLI) are documented in
  [`USAGE.md`](USAGE.md)

Managed files typically include:

| File | Purpose |
|------|---------|
| `.semver.yaml` | project configuration |
| `baked.yaml` | release baseline snapshot |
| `current.yaml` | latest generated snapshot |
| `VERSION` | current version string |

## Extend or patch it

- Plugin authoring guide: [`HOWTO.md`](HOWTO.md)
- Snapshot/config schema reference: [`SCHEMA.md`](SCHEMA.md)
- Example plugins: [`plugins/`](plugins/)
- Demos and example configs: [`example/`](example/)

Useful development commands:

```bash
poetry run pytest -v
poetry run python -m cli --help
bash example/demo_python.sh
bash scripts/smoke.sh python unit
```

## Programmatic API

```python
from semverdredd import compare_and_suggest

result, suggested = compare_and_suggest(
    "old_module",
    "new_module",
    plugin_name="python",
    current_version="1.2.0",
)

print(result.change_kind.name)
print(suggested)
```

The CLI/docs cover the primary user workflow; the importable API is best suited
for automation and tests.
