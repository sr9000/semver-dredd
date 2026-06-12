# ANSWER KEY — Task 1 (legacy/bughunting) — Seeded Bug Hunt & Fix

> **OPERATOR-ONLY.** This file lives on `master` and is deleted from the local
> checkout before any candidate run. It must never appear on `legacy/bughunting`
> or any `legacy/bughunting-<model>` branch.

Baseline: `legacy/bughunting` — single squashed commit `legacy: import` off the
root commit of `master`, full current master tree + `reports/TASK.md` + the 10
seeds below. `poetry run pytest tests/ -q` reports **219 passed** with all seeds
in place (verified at seeding time).

Menu deviations from `benchmarks/task-1-easy-bughunt.md` (originals were
covered by the unit suite and would have broken the green-suite invariant):

- Menu #5 (silent `patch_scheme` fallback) → replaced by **D5** (env-var mapping swap);
  the warning branch is covered by `tests/test_version.py::TestConfigPatchScheme`.
- Menu #7 (emit empty `include` key) → replaced by **D7** (`exclude` gated on `include`);
  `tests/test_config.py` asserts `snapshot_options() == {}` for empty config.
- Menu #8 (flip discovery precedence) → replaced by **D8** (force-reload reset no-op);
  `tests/test_plugin_manager.py::TestDiscoveryPrecedence` pins entry-point precedence.

## Easy tier (weight ×1 each)

| # | File:Line (seeded tree) | Defect | Why wrong | Intended fix |
|---|---|---|---|---|
| D1 | `tests/smoke/assert_demo.sh:62-64, 73-75` | Expected strings swapped: Step 2 (geometry1→2) greps `Change type: BREAKING`, Step 3 (geometry2→1) greps `Change type: MINOR` | Header comments (lines 7–8), demo sources, and `example/` fixtures establish 1→2 = MINOR (additions), 2→1 = BREAKING (removals) | Swap the greps back: Step 2 asserts `MINOR`, Step 3 asserts `BREAKING` (incl. fail messages) |
| D2 | `tests/smoke/assert_demo.sh:70-71` | Breaking-direction expected exit code changed `10` → `1` | `EXIT_BREAKING_CHANGES_DETECTED = 10` in `cli/utils.py`; `1` is the generic error code | Restore `-ne 10` / "expected 10" |
| D3 | `scripts/smoke.sh:58-60` | In the per-service failure branch `FAILED=1` was removed; `RESULTS[$svc]="FAIL"` is still recorded | Summary prints FAIL but the script exits 0 — a failed smoke service no longer fails the run/CI | Re-add `FAILED=1` in the `else` branch |

## Medium tier (weight ×2 each)

| # | File:Line | Defect | Why wrong | Intended fix |
|---|---|---|---|---|
| D4 | `cli/commands/compare.py:51-57` | `extra_options=snapshot_options` passed only to the OLD snapshot call; dropped from the NEW call | include/exclude/plugin_options from `.semver.yaml` scope only one side — silent asymmetric comparison (diff compares differently-scoped surfaces) | Pass `extra_options=snapshot_options` to both `_generate_snapshot_yaml` calls |
| D5 | `cli/config.py:27-28` (`ENV_VAR_MAPPING`) | `SEMVER_DREDD_CURRENT_FILE` maps to `("files", "version")` and `SEMVER_DREDD_VERSION_FILE` to `("files", "current")` — swapped | Setting `SEMVER_DREDD_CURRENT_FILE` silently changes the VERSION file path and vice versa; contradicts README "Environment Variables" table | Swap the mapping targets back (`current`→files.current, `version`→files.version) |
| D6 | `.github/workflows/smoke.yml:28-30` | `BUILDX_BAKE_GITHUB_ACTIONS_CACHE: "true"` env line deleted; the comment "Docker layer caching keeps repeat runs reasonable" and the `crazy-max/ghaction-github-runtime` step remain | Cache exposure step is wired but bake never uses the GHA cache — caching is silently dead, comment lies | Restore the env line under `COMPOSE_BAKE` |
| D7 | `cli/config.py:79-86` (`Config.snapshot_options`) | `exclude` emission nested inside `if self.include:` | A config with only `exclude:` set silently drops the exclusions — plugin analyzes excluded modules; contradicts docs (README config section, INCLUDE-EXCLUDE-PROPOSAL §3) | De-indent: `if self.exclude:` must be a sibling of `if self.include:` |

## Hard tier (weight ×4 each)

| # | File:Line | Defect | Why wrong | Intended fix |
|---|---|---|---|---|
| D8 | `semverdredd/plugin_manager.py:66-71` (`load_plugins` force-reset) | Reset filter keeps origins `("manual", "builtin", "entry_point", "user_dir")` — i.e. everything; "Reset on force reload" becomes a no-op | `load_plugins(force=True)` can no longer evict stale entry-point/user-dir registrations (e.g. after `plugin remove`/reinstall); removed or upgraded plugins keep their stale instances | Restore filter to keep only `("manual", "builtin")` |
| D9 | `cli/commands/plugin.py:209-212` (`cmd_plugin_remove`, manifest eviction) | Eviction filter replaced by key-prefix match: `if not k.startswith(plugin_name)` | Double-wrong: removing `java` also evicts the unrelated sibling `javaparser` manifest entry; AND other plugin names recorded by the same install (identical `paths`) are no longer evicted, leaving stale manifest entries pointing at deleted files | Restore paths-identity eviction: keep entries where `v.get("paths") != entry.get("paths")` |
| D10 | `docker/Dockerfile.java:31` | Build sanity check `grep -q java` → `grep -q dredd` | `semver-dredd plugin list` prints every plugin's description containing "dredd"; check passes even when the java plugin failed to install — vacuous | Restore `grep -q java` |

## Traps (must remain untouched — any reported "defect" here is a false positive)

- `semverdredd/version.py`
- `docker/README.md`

## Grading notes

- Scoring: found+fixed = full weight; found-only or silent-fix = half.
  Penalties: false positive −2, broken suite −5, missing `reports/report.md` −3.
  Max score = 3×1 + 4×2 + 3×4 = **23**.
- After applying each model's stash: `poetry run pytest tests/ -q` must still be 219 passed.
- D1+D2 live in adjacent lines; a single commit fixing both strings *and* the
  exit code should be credited as two finds but noted under commit hygiene.
- For D9, full credit requires restoring "evict exactly the keys of this
  installation" semantics (paths-identity or equivalent). A fix that only
  addresses the sibling-eviction symptom (e.g. exact-match `k == plugin_name`)
  stops evicting `javaparser` but leaves stale manifest entries for the other
  plugin names recorded by the same install — grade as half (found, fix
  incomplete) unless the report explicitly handles the multi-name case.
