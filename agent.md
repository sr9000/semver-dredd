# Agent Notes — semver-dredd (repo root)

Navigate the repo without rediscovering architecture/workflow each time.

## What it is

Python 3.10+ semantic-versioning tool. Language plugins generate API snapshots;
core diffs them, classifies the change `NONE`/`PATCH`/`MINOR`/`BREAKING`, and
suggests/writes versions.

**Plugins understand APIs; core understands mechanics.**
- Core: plugin discovery, config, snapshot I/O, diff delegation, CLI, version math.
- Plugin: parses a language and emits a self-diffing snapshot.
- Snapshot dispatch is UUID-based via top-level `snapshot_type_id`.

## Workflow rules (must follow)

- Treat long tasks as a sequence of single-commit patches; keep repo **green**
  (tools run, tests pass) after each.
- **NEVER commit to master.** If on master, auto-checkout a new branch first.
- Branch = short task title. Commit msg: `feat/fix(branch-name): brief description`.
- User merges the branch manually after completion.
- Per-step cycle: confirm green → implement → write use-case tests (no trivial
  tests; often extend existing cases) → pre-commit gates (lint/format, full test
  suite, git hooks).

### Commit-splitting policy (enforced)

- Do **not** batch a whole multi-step plan into one uncommitted working tree.
- After each completed plan step (or tightly coupled 1-3 step slice), create a
  commit before moving on.
- Every commit must be independently meaningful and keep the repository green.
- If work is already accumulated, stop and split it into logical commits using
  `git add -p` / file-level staging before proceeding.
- Before final handoff, branch must contain a clean, reviewable commit series
  matching the executed plan steps.

## Planning

Plans live in `plans/`. Split a feature into enumerated files
`##-feature-title.md`, each describing one business-level change as commit-sized
steps with: **Motivation**, **Touched files**, **Definition of Done** (validating
use-case). Mark implementation-dependent parts as milestones and update as you go.

## Module map

- `cli/` — argparse CLI, config application, command implementations.
- `semverdredd/` — importable core API, plugin/snapshot registry mechanics.
- `snapshot/` — snapshot model/protocol package (kept separate).
- `plugins/` — separately installable language plugin packages.
- `example/` — Python/Go/Java demo inputs + demo scripts.
- `tests/` — unit/integration tests; smoke assertions in `tests/smoke/`.
- `docker/` + `docker-compose.smoke.yml` — isolated smoke services.

## Per-directory agent.md

`semverdredd/`, `snapshot/`, `plugins/`, `docker/`, `example/` each have an
`agent.md` with local invariants — read before editing that area.

## Docs to read before editing

- `README.md` — CLI/API overview, project structure.
- `HOWTO.md` — plugin authoring; best source for the plugin contract.
- `docs/schema.md` — snapshot YAML envelope + component schemas.
- `plans/` — pre-1.0 completion roadmap and per-phase plans (config/plugin API
  evolution, scope model, bundle plugin, observability).

## Dev commands

```bash
poetry install --with dev
pip install -e plugins/python-3.10-dredd   # + go/java/javaparser as needed
poetry run pytest -v
bash example/demo_python.sh                # go/java need toolchains+plugins
bash scripts/smoke.sh [python unit ...]    # Docker smoke
```

**git log — always use non-interactive mode** to avoid blocking on a pager:

```bash
git --no-pager log                            # suppress pager entirely
git --no-pager log --oneline --decorate -n 8  # uasge example
```

## Conventions

- Python ≥3.10 modern hints (`dict[str, Any]`, `X | None`); prefer `pathlib.Path`.
- `dataclass` for data; runtime `Protocol` for snapshot contracts.
- Keep `semverdredd/` pure logic — printing belongs in `cli/`.
- Plugins return `SnapshotResult`; don't raise/print on expected parser failures.
- Plugin options stay backward-compatible: ignore unknown keys.
- No core assumptions about language API shape; snapshots own `diff_against()`.

## Scope status

`include`/`exclude`/`plugin_options` are parsed and forwarded but **no official
plugin honors filtering yet**. Multi-document config and the `bundle` plugin are
still planned. Before changing scope behavior, read the `plans/` roadmap and
`plugins/agent.md`. Caution: once plugins honor `include`/`exclude`, existing
configs with those keys will yield narrower snapshots.
