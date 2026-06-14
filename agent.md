# Agent Notes — semver-dredd Repository

Purpose: help agents navigate the repo without spending tokens rediscovering
architecture, workflows, and proposal scope.

## What this repo is

`semver-dredd` is a Python 3.10+ semantic-versioning tool. It generates API
snapshots through language plugins, diffs snapshots, classifies the change as
`NONE` / `PATCH` / `MINOR` / `BREAKING`, and suggests or writes versions.

Core principle: **plugins understand APIs; core understands mechanics**.

- Core does plugin discovery, config loading, snapshot I/O, diff delegation, CLI
  orchestration, and version math.
- Plugins parse a language/domain and produce a snapshot that can diff itself.
- Snapshot format dispatch is UUID-based via top-level `snapshot_type_id`.

## High-value docs before editing

- `README.md` — user-facing CLI/API overview and project structure.
- `HOWTO.md` — how to write plugins; best single source for plugin contract.
- `docs/schema.md` — snapshot YAML envelope and predefined component schemas.
- `INCLUDE-EXCLUDE-PROPOSAL.md` — proposed config/plugin API evolution.
- `reports/include-exclude-status.md` — verified implementation status.
- `reports/include-exclude-usability-and-implementation-plan.md` — usability
  review, open questions, and staged implementation plan.

## Directory-specific notes

- `semverdredd/agent.md` — core source code boundaries and invariants.
- `snapshot/agent.md` — snapshot protocols, normalized model, diff result.
- `plugins/agent.md` — plugin package layout and official plugin notes.
- `docker/agent.md` — smoke-test Docker images and Compose workflow.
- `example/agent.md` — demo fixtures/scripts used by smoke tests.

## Module layout quick map

- `cli/` — argparse CLI, config application, command implementations.
- `semverdredd/` — importable core API and plugin/snapshot registry mechanics.
- `snapshot/` — snapshot model/protocol package, intentionally separate.
- `plugins/` — separately installable language plugin packages.
- `example/` — Python/Go/Java demo inputs and demo scripts.
- `tests/` — unit + integration-style tests; smoke assertions in
  `tests/smoke/`.
- `docker/` + `docker-compose.smoke.yml` — isolated smoke-test services.

## Development commands

```bash
# Install core dev deps
poetry install --with dev

# Install official plugins editable, if needed for local plugin discovery
pip install -e plugins/python-3.10-dredd
pip install -e plugins/go-1.20-dredd
pip install -e plugins/java-1.8-dredd
pip install -e plugins/javaparser-1.8-dredd

# Run tests
poetry run pytest -v
poetry run pytest tests/test_config.py -v

# Run demos directly (requires relevant toolchains/plugins)
bash example/demo_python.sh
bash example/demo_go.sh
bash example/demo_java.sh

# Run smoke tests in Docker
bash scripts/smoke.sh
bash scripts/smoke.sh python unit
```

## Code style / conventions

- Python >= 3.10; use modern type hints (`dict[str, Any]`, `X | None`).
- Prefer `pathlib.Path` for filesystem paths.
- Core data structures often use `dataclass`; snapshot protocols use runtime
  `Protocol` checks.
- Keep `semverdredd/` mostly pure-data / core logic. Printing belongs in `cli/`.
- Plugins return `SnapshotResult`; do not raise for expected parser failures.
- Plugin options must be backward-compatible: unknown keys should be ignored.
- Avoid adding core assumptions about language API shape; custom snapshots own
  their own `diff_against()` behavior.

## Scope-related current status

`include`, `exclude`, and `plugin_options` are parsed and forwarded to plugins.
Official plugins currently do **not** implement filtering. Multi-document config
and the `bundle` plugin are still proposed.

If changing scope behavior, read these first:

1. `INCLUDE-EXCLUDE-PROPOSAL.md`
2. `reports/include-exclude-status.md`
3. `reports/include-exclude-usability-and-implementation-plan.md`
4. `plugins/agent.md`

Important usability caution: once official plugins start honoring
`include`/`exclude`, existing configs containing those keys may produce narrower
snapshots than before.
