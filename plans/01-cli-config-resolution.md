# CLI Config Resolution Foundation

## Motivation

Users should be able to initialize once and then run common commands without
repeating path/plugin/version details. This phase unlocks the target workflow and
creates the command-resolution layer that later multi-document candidate
selection depends on.

Target workflow:

```bash
semver-dredd init . --plugin python --version 1.0.0
semver-dredd status --details
semver-dredd bake
```

## Touched Files

- `cli/__main__.py`
- `cli/config.py`
- `cli/commands/init.py`
- `cli/commands/status.py`
- `cli/commands/bake.py`
- `cli/commands/snapshot.py`
- `cli/commands/compare.py` if shared resolution affects compare behavior
- `cli/utils.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `README.md`
- `HOWTO.md` only for current behavior notes if needed

## Commit-Sized Steps

### 1. Add global selected-config loading

- Add a global `--config PATH` argument parsed before normal config loading.
- Keep the default path as `.semver.yaml` when no flag is supplied.
- Make config loading report whether the file was absent, default-selected, or
  explicitly selected.
- Preserve current single-document behavior in this step.

Definition of Done:

- Tests prove `--config .semver.dev.yaml` is loaded instead of `.semver.yaml`.
- Tests prove missing default config is tolerated where current commands tolerate
  it, while missing explicit config gives a clear error.

### 2. Introduce a resolved command context

- Add an internal data object that answers:
  - active config path;
  - active source path and source layer;
  - active plugin and source layer;
  - active version file and source layer;
  - effective include/exclude/plugin options;
  - warnings caused by explicit overrides.
- Build this object after argparse and config/env loading but before command
  execution.
- Keep command handlers simple: they consume the resolved context instead of
  reimplementing precedence.

Definition of Done:

- Existing explicit CLI tests still pass.
- New tests assert precedence source labels for plugin/path/version-file values.

### 3. Store source path and version file during `init`

- Keep `--plugin` required for `init`.
- Write `plugin`, `source.path`, and `files.version` to `.semver.yaml`.
- Add or standardize `--version-file PATH` for config persistence.
- Preserve `--version` as the initial semantic version value written to the
  version file.

Definition of Done:

- `init . --plugin python --version 1.0.0` creates config with the analyzed path.
- `init . --plugin python --version-file pyproject-version.txt` records the
  custom version file.
- Tests assert no plugin auto-detection is introduced for `init`.

### 4. Make `status` and `bake` pathless when config provides a path

- Make the positional source optional for these commands.
- Add/standardize `--path` as the explicit source override.
- Warn if explicit path differs from `source.path` in config.
- Warn if explicit `--plugin` differs from config plugin.

Definition of Done:

- `semver-dredd status --details` and `semver-dredd bake` work after `init`.
- Explicit old-style invocations remain valid.
- Tests cover missing path with no config as a clear user-facing error.

### 5. Make `snapshot` config-driven

- Let `snapshot` default plugin/path from resolved config.
- Let `snapshot` read version from the resolved `files.version` path when
  `--version` is omitted.
- Preserve explicit flags as highest precedence and warn on collisions.

Definition of Done:

- Tests cover snapshot defaults from config + VERSION.
- Tests cover explicit `--version`, `--path`, and `--plugin` overriding config.

### 6. Add CLI include/exclude override semantics

- Add advanced `--include ITEM` and `--exclude ITEM` flags to relevant workflow
  commands.
- Default behavior: append CLI arrays to config arrays.
- Warn on duplicate/colliding values.
- Add `--override` so CLI include/exclude replace config arrays.

Definition of Done:

- Tests prove append behavior, duplicate warnings, and replacement behavior.
- Precedence remains `CMDARGs -> ENVs -> CONFIG`.
