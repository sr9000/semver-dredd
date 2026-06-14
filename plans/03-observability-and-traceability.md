# Observability and Snapshot Traceability

## Motivation

The desired tool does not need a `doctor` command. Users should understand what
happened through consistent verbosity and stable snapshot provenance. This phase
should land before deep fallback/scope behavior becomes complex.

## Touched Files

- `cli/__init__.py` — global flags and `main()` live here; `cli/__main__.py` is
  only an 8-line shim.
- `cli/utils.py`
- `cli/commands/*.py`
- `semverdredd/plugin_manager.py` — already uses `logging` and already tracks
  plugin origin via `PluginInfo.origin` (`entry_point|user_dir|builtin|manual`)
  and `PluginInfo.entry_point`; reuse these for provenance instead of inventing
  new tracking.
- `semverdredd/snapshot_io.py`
- `snapshot/models.py` — despite the "backward-compatibility shim" docstring this
  file holds the real `NormalizedSnapshot` implementation (there is no
  `semverdredd/models.py`); edit it here.
- `snapshot/predefined/models.py`
- `docs/schema.md`
- `tests/test_cli.py`
- `tests/test_snapshot.py`
- `tests/test_pluggable_snapshot_diff.py`

## Commit-Sized Steps

### 1. Add a global counted verbosity flag

- Add global `-v`/`-vv`/`-vvv` support. Caution: `-v` is currently registered as
  the short alias of `init`'s `--version` (`init_parser.add_argument("--version",
  "-v", ...)`). Resolve this collision deliberately — e.g. drop the `-v` alias
  from `init --version`, or attach counted verbosity only to the top-level parser
  before the subcommand — and cover the chosen behavior with tests.
- Define level behavior:
  - default: errors and warnings only;
  - `-v`: info-level, O(1) logs once per tool call;
  - `-vv`: debug-level, O(n) logs for candidates/plugins/include/API members;
  - `-vvv`: debug-level plus explicit argument/config dump.
- Avoid O(n) logs below `-vv`.

Definition of Done:

- Tests assert representative messages appear at the expected verbosity and are
  absent below that level.
- Existing `compare --verbose` behavior is either preserved through compatibility
  or migrated with tests.

### 2. Centralize CLI log event helpers

- Add helpers for warnings/info/debug instead of direct command printing.
- Emit structured events for:
  - config selection;
  - command context resolution;
  - plugin selection;
  - candidate fallback;
  - scope matching summary;
  - snapshot compatibility assumptions;
  - bundle dependency decreases later in phase 6.

Definition of Done:

- Command tests can assert warnings without depending on unrelated output.
- Core modules still do not print directly.

### 3. Define stable snapshot generator metadata

- Add a `generator` metadata block to new snapshots with at least:
  - plugin name;
  - plugin package/version when discoverable;
  - plugin source: entry point, built-in fallback, or other;
  - selected config path and candidate index when relevant.
- Keep older snapshots loadable when the block is absent.

Definition of Done:

- Snapshot schema docs define the generator block.
- Tests prove new snapshots include provenance.
- Tests prove old fixture snapshots still load and diff.

### 4. Surface plugin mismatch assumptions

- When a baseline and current snapshot have different generator/plugin metadata,
  log the compatibility assumption before delegating diff logic.
- Do not block comparison solely because plugins differ; snapshot classes still
  own compatibility.

Definition of Done:

- Tests cover same-plugin quiet behavior and different-plugin warning behavior.
- Logs include enough information to identify both generators.
