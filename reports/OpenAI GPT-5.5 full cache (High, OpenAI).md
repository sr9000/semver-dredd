# Implementation Review: Improve Plan and Include/Exclude Proposal

**Date:** 2026-06-12  
**Reviewer:** Kilo Code  
**Reviewed inputs:** [`plans/improve-and-smoke-tests.md`](../plans/improve-and-smoke-tests.md), [
`INCLUDE-EXCLUDE-PROPOSAL.md`](../INCLUDE-EXCLUDE-PROPOSAL.md)  
**Tokens:** up 2.4m; down 11.9k  
**Cache:** 2.2m  
**API Cost:** $4.11  

## Executive summary

**Overall implementation grade: A- / 90%**

The implementation is high quality and closely tracks the plan. Part A is substantially complete and well tested. Part B
is structurally complete, with host-level smoke assertions passing for python/go/java and Docker Compose syntax
validated. The only unverified items are the same ones the plan already calls out: Docker image builds/full compose runs
and live GitHub Actions results, because the local Docker daemon is unavailable.

**Proposal accuracy grade: A / 94%**

[`INCLUDE-EXCLUDE-PROPOSAL.md`](../INCLUDE-EXCLUDE-PROPOSAL.md) accurately marks what is implemented versus proposed.
The implemented status for config plumbing and plugin options is correct, and the proposed status for plugin-side
filtering, multi-document config, and the bundle plugin is correct.

## Verification performed

| Check                                                               |                                               Result |
|---------------------------------------------------------------------|-----------------------------------------------------:|
| Full unit suite: `poetry run pytest -q`                             |                              ✅ `219 passed in 0.90s` |
| Focused plan-related suite                                          |                              ✅ `104 passed in 0.24s` |
| Host smoke: `poetry run bash tests/smoke/assert_demo.sh python`     |                                               ✅ Pass |
| Host smoke: `poetry run bash tests/smoke/assert_demo.sh go`         |                                               ✅ Pass |
| Host smoke: `poetry run bash tests/smoke/assert_demo.sh java`       |                                               ✅ Pass |
| Compose schema: `docker compose -f docker-compose.smoke.yml config` |                                               ✅ Pass |
| Docker daemon availability                                          | ⚠️ Unavailable: client present, daemon not reachable |

## Plan implementation assessment

### Part A — Tool improvements

| Commit                                             | Grade | Assessment                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|----------------------------------------------------|------:|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 — Surface config parse errors                    |     A | Implemented in [`cli.config._load_yaml_config()`](../cli/config.py:141). Malformed YAML, read errors, missing PyYAML, and non-mapping files produce clear warnings or safe fallback. Tests cover malformed, missing, valid, and non-mapping paths in [`tests/test_config.py`](../tests/test_config.py:117).                                                                                                                                                                                                                   |
| 2 — Plumb include/exclude/plugin_options           |    A- | Implemented through [`cli.config.Config`](../cli/config.py:32), [`cli.config.Config.snapshot_options()`](../cli/config.py:73), and [`cli.utils._generate_snapshot_yaml()`](../cli/utils.py:140). CLI command modules pass these options through. Programmatic API forwarding is tested in [`tests/test_plugin_manager.py`](../tests/test_plugin_manager.py:113). Minor caveat: unsupported shapes are silently ignored rather than warned, but that is acceptable for an opaque/options-first design.                         |
| 3 — Fix hardcoded versions in programmatic compare |    A- | Implemented in [`semverdredd.compare()`](../semverdredd/__init__.py:94) with explicit `old_version` and `new_version`. [`semverdredd.compare_and_suggest()`](../semverdredd/__init__.py:175) threads the current version into both snapshots because the future version is not yet known. Tests verify version forwarding in [`tests/test_programmatic_api.py`](../tests/test_programmatic_api.py:73). CLI `compare` still snapshots with `0.0.0`, but the plan scoped this change to the programmatic API.                   |
| 4 — Pluggable patch scheme                         |     A | Implemented cleanly in [`semverdredd.version.Version.increment()`](../semverdredd/version.py:102) and [`semverdredd.version.generate_patch()`](../semverdredd/version.py:197). Config parsing is in [`cli.config.load_config()`](../cli/config.py:262), and commands consume `patch_scheme`. Tests cover date/default, integer, and invalid values in [`tests/test_version.py`](../tests/test_version.py:237).                                                                                                                |
| 5 — Harden plugin lifecycle                        |    B+ | Conflict warnings are visible in [`semverdredd.plugin_manager.PluginManager.register()`](../semverdredd/plugin_manager.py:190) and snapshot UUID conflicts are warned in [`semverdredd.plugin_manager.PluginManager.load_plugins()`](../semverdredd/plugin_manager.py:61). Manifest install/remove is implemented in [`cli/commands/plugin.py`](../cli/commands/plugin.py). Caveat: manifest recording is based on newly-created top-level paths, so reinstall/upgrade cases can leave modified pre-existing files untracked. |
| 6 — Decouple built-in plugins from core            |    A- | Entry points are preferred in [`semverdredd.plugin_manager.PluginManager.load_plugins()`](../semverdredd/plugin_manager.py:83), with a fallback list only for editable/dev installs at [`semverdredd.plugin_manager._BUILTIN_FALLBACK_SPECS`](../semverdredd/plugin_manager.py:36). Tests verify entry-point and fallback behavior in [`tests/test_plugin_manager.py`](../tests/test_plugin_manager.py:238).                                                                                                                  |
| 7 — Reconcile documentation                        |     A | [`README.md`](../README.md:19) now points to feature status and [`INCLUDE-EXCLUDE-PROPOSAL.md`](../INCLUDE-EXCLUDE-PROPOSAL.md:3) includes a per-feature status table. The status table is consistent with actual implementation.                                                                                                                                                                                                                                                                                             |

**Part A grade: A- / 91%**

### Part B — Docker Compose smoke tests

| Commit                       |                                       Grade | Assessment                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|------------------------------|--------------------------------------------:|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 8 — Per-language Dockerfiles |        A- structurally / unverified runtime | The four Dockerfiles exist and are appropriately slim/pinned: [`docker/Dockerfile.python`](../docker/Dockerfile.python), [`docker/Dockerfile.go`](../docker/Dockerfile.go), [`docker/Dockerfile.java`](../docker/Dockerfile.java), and [`docker/Dockerfile.unit`](../docker/Dockerfile.unit). Each includes a build-time `semver-dredd plugin list` check. Full image builds could not be run locally because Docker daemon is unavailable, matching the plan's open DoD note.                                                |
| 9 — Compose smoke file       |                                           A | [`docker-compose.smoke.yml`](../docker-compose.smoke.yml) defines python/go/java/unit services, read-only repo mounts, and non-zero command behavior. `docker compose -f docker-compose.smoke.yml config` validates successfully.                                                                                                                                                                                                                                                                                             |
| 10 — Smoke assertions        |                                          B+ | [`tests/smoke/assert_demo.sh`](../tests/smoke/assert_demo.sh) runs demos and asserts MINOR and BREAKING classifications. Host python/go/java smoke checks passed. Caveat: the assertions validate classification, not the specific API additions/removals. The Java parser output currently reports only `Point.z` as the minor addition in the demo path, while the demo text mentions `Point.translate()` and `Geometry.volume()` too. Classification remains correct, but the smoke could miss partial parser regressions. |
| 11 — Smoke runner            | A- structurally / unverified Docker runtime | [`scripts/smoke.sh`](../scripts/smoke.sh) builds services, runs each with `--abort-on-container-exit` and `--exit-code-from`, aggregates failures, supports subsets and `--no-build`, and cleans up with `compose down --remove-orphans`. Full Docker run is unverified due missing daemon.                                                                                                                                                                                                                                   |
| 12 — CI workflow             |         A- structurally / unverified remote | [`smoke.yml`](../.github/workflows/smoke.yml) triggers on push/PR, builds with Buildx/cache-oriented settings, then runs [`scripts/smoke.sh`](../scripts/smoke.sh) with `--no-build`. Live green/red GitHub runs remain unverified, as documented in the plan.                                                                                                                                                                                                                                                                |
| 13 — Smoke docs              |                                           A | [`README.md`](../README.md:456) and [`docker/README.md`](../docker/README.md) document local smoke usage and image purposes.                                                                                                                                                                                                                                                                                                                                                                                                  |

**Part B grade: B+ / 88%** — Mostly complete, but final confidence depends on Docker daemon/CI verification.

## Proposal review

[`INCLUDE-EXCLUDE-PROPOSAL.md`](../INCLUDE-EXCLUDE-PROPOSAL.md) is clear and mostly accurate.

### Accurate implemented/proposed split

- `include` / `exclude` config plumbing is implemented: parsed by [`cli.config.load_config()`](../cli/config.py:203),
  exposed by [`cli.config.Config`](../cli/config.py:32), and forwarded via [
  `cli.config.Config.snapshot_options()`](../cli/config.py:73).
- `plugin_options` is implemented as an opaque dictionary and forwarded to plugins.
- Plugin-side interpretation of `include` / `exclude` remains proposed. Search confirms the bundled plugin
  `generate_snapshot` methods accept `options` but do not inspect those keys.
- Multi-document `.semver.yaml` remains proposed; [`cli.config._load_yaml_config()`](../cli/config.py:141) still uses
  single-document YAML loading.
- The aggregate `bundle` plugin remains proposed; no such plugin is present.

### Proposal quality notes

- The document does a good job preventing user confusion by placing status at the top.
- The philosophy of keeping core agnostic and making plugins own filtering semantics matches the implementation.
- The bundle plugin design is coherent, but should remain explicitly non-shipped until there is a real implementation
  and tests.
- One nuance: the repository also contains a `javaparser` plugin package, and it likewise does not interpret `include` /
  `exclude`. The status table mentions python/go/java only; that is acceptable if `javaparser` is considered
  experimental, but a future status table could include it for completeness.

## Key risks and recommended follow-ups

1. **Run full Docker smoke in CI before claiming Part B fully complete.**  
   The local environment cannot connect to a Docker daemon, so the unchecked Docker/CI DoD items are real. Push/PR
   validation should be treated as the release gate.

2. **Strengthen smoke assertions to check representative diff details.**  
   Classification-only assertions are valuable, but they can miss parser regressions that still leave the severity at
   MINOR/BREAKING. Add checks for at least one expected function/method/field per language in [
   `tests/smoke/assert_demo.sh`](../tests/smoke/assert_demo.sh:55).

3. **Improve plugin install manifest robustness for upgrades.**  
   [`cli.commands.plugin.cmd_plugin_install()`](../cli/commands/plugin.py:77) records only paths newly created by pip
   install. Reinstalling or upgrading a plugin can modify existing paths without tracking them. Consider deriving
   installed files from package metadata or recording the complete top-level set associated with newly available
   distributions.

4. **Consider warning for invalid include/exclude/plugin_options shapes.**  
   Current behavior silently coerces scalar scope values and silently drops unsupported structures. That is
   backward-compatible, but warnings would make configuration mistakes easier to diagnose.

5. **Optional: make `snapshot` use config plugin defaults.**  
   The `snapshot` subcommand currently requires `--plugin` in [`cli/__init__.py`](../cli/__init__.py:320), so
   `.semver.yaml` cannot supply the plugin for that command. This is not a plan violation, but it is inconsistent with
   the rest of the CLI config behavior.

## Final grade

| Area                            |                  Grade |
|---------------------------------|-----------------------:|
| Correctness against plan        |                     A- |
| Test coverage                   |                     A- |
| Documentation/proposal accuracy |                      A |
| Docker/CI confidence            | B until CI is observed |
| Maintainability                 |                     A- |

**Final result: A- / 90%.** The implementation is good enough to accept with follow-up items, provided Docker/CI
validation is completed before release or before marking the remaining Part B DoD checkboxes as done.
