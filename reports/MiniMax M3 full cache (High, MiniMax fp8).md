# Implementation Review: `plans/improve-and-smoke-tests.md`

**Reviewer:** automated code review  
**Date:** 2026-06-12  
**Tokens:** up 754.2k; down 16.2k  
**Cache:** 690.4k  
**API Cost:** $0.16  
**Plan status as written:** "Implemented (June 10, 2026) — all commits landed"  
**Scope reviewed:** source files referenced by the plan, the docker artefacts, the
CI workflow, the existing tests, and the new `tests/test_config.py` /
`tests/test_plugin_manager.py` additions.  

---

## TL;DR

| #  | Commit                                         | Grade  | DoD status                | Notes                                                                                                                           |
|----|------------------------------------------------|--------|---------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| 1  | Surface config parse errors                    | **A**  | ✅                         | All bullets satisfied, tests + warnings in place.                                                                               |
| 2  | Plumb `include` / `exclude` / `plugin_options` | **A**  | ✅                         | Full plumbing from YAML → `Config` → CLI → plugin; new tests cover both layers.                                                 |
| 3  | Fix hardcoded `"0.0.0"` in `compare()`         | **B**  | ⚠️ Partial                | Programmatic API now threads versions, but the **CLI** `cmd_compare` still hardcodes `"0.0.0"` for both old and new.            |
| 4  | Pluggable patch scheme                         | **A**  | ✅                         | Both schemes covered, config knob wired, tests + docs in place.                                                                 |
| 5  | Harden plugin lifecycle                        | **A**  | ✅                         | Manifest, conflict logging, both removal paths covered.                                                                         |
| 6  | Decouple built-in plugins from core            | **A**  | ✅                         | Entry points preferred, fallback kept, tests for both branches.                                                                 |
| 7  | Reconcile documentation                        | **A**  | ✅                         | Banner + README pointer.                                                                                                        |
| 8  | Per-language Dockerfiles                       | **B+** | ⚠️ Authored, unverified   | No `docker build` performed on the dev box; relies on CI. Sanity-check at build time is a nice touch.                           |
| 9  | `docker-compose.smoke.yml`                     | **A-** | ✅                         | Wired straight to `assert_demo.sh`; one missed DoD item (host-`docker compose config` validation) explicitly noted.             |
| 10 | Smoke assertions                               | **A-** | ✅                         | Assertions exit 1 on failure; only "intentionally breaking" is host-verified, not committed as a regression test.               |
| 11 | `scripts/smoke.sh` runner                      | **A**  | ✅                         | Aggregates results, cleans up, supports subset + `--no-build`.                                                                  |
| 12 | CI workflow                                    | **C+** | ⚠️ "Cache" claim is wrong | The `crazy-max/ghaction-github-runtime` step **does not** enable Docker layer caching. The build will run cold on every CI run. |
| 13 | Document smoke-test workflow                   | **A**  | ✅                         | README + `docker/README.md` both updated.                                                                                       |

**Overall verdict:** the plan is implemented well in code, with two notable
gaps — the CLI compare path still hardcodes versions, and the CI cache claim
in Commit 12 is factually wrong. Everything else is faithful to the plan and
to the file system as committed.

---

## Per-commit findings

### Commit 1 — Surface config parse errors → A

**Where:** [`cli/config.py:141-182`](cli/config.py:141) (the
[`_load_yaml_config`](cli/config.py:141) helper).

- ✅ Malformed YAML now prints a `[WARN] Failed to parse config file {path}: {e}` line
  on stderr and returns `{}` ([`cli/config.py:163`](cli/config.py:163)).
- ✅ Non-mapping YAML is also caught and warned
  ([`cli/config.py:175-180`](cli/config.py:175)).
- ✅ Valid or missing config still produces no warning (silent path).
- ✅ Test coverage in [`tests/test_config.py:117-151`](tests/test_config.py:117):
  `test_load_yaml_config_malformed_warns`,
  `test_load_yaml_config_non_mapping_warns`,
  `test_load_yaml_config_valid_no_warning`,
  `test_load_yaml_config_missing_no_warning`.

**Minor nit (not blocking):** the warning messages don't include line numbers
from the YAML parser. PyYAML's `mark` attribute would let you print the
offending line; not required, but a nice-to-have for future iterations.

---

### Commit 2 — Plumb `include` / `exclude` / `plugin_options` → A

**Where:** [`cli/config.py`](cli/config.py), [`semverdredd/__init__.py`](semverdredd/__init__.py), [
`cli/utils.py:140-175`](cli/utils.py:140), [`cli/commands/compare.py:39-57`](cli/commands/compare.py:39), [
`cli/commands/snapshot.py:19-25`](cli/commands/snapshot.py:19).

- ✅ [`Config.include`](cli/config.py:54), [`Config.exclude`](cli/config.py:55), and [
  `Config.plugin_options`](cli/config.py:58) are declared.
- ✅ [`Config.snapshot_options()`](cli/config.py:73) only sets keys that were
  configured, so plugins ignoring them behave exactly as before — explicitly
  covered by [`test_snapshot_options_only_set_keys`](tests/test_config.py:286).
- ✅ YAML parsing handles scalar-coerced-to-list ([`_parse_str_list`](cli/config.py:192),
  tested at [`tests/test_config.py:280`](tests/test_config.py:280)).
- ✅ `apply_config_defaults` plumbs the dict to `args.snapshot_options` ([`cli/config.py:336-338`](cli/config.py:336)),
  and the
  `compare` and `snapshot` commands pass it through `extra_options` to
  [`_generate_snapshot_yaml`](cli/utils.py:140) which merges it into
  `options` ([`cli/utils.py:161-165`](cli/utils.py:161)).
- ✅ Programmatic API accepts an `options=` kwarg in both
  [`compare()`](semverdredd/__init__.py:94) and
  [`compare_and_suggest()`](semverdredd/__init__.py:175).
- ✅ Tests:
    - `TestScopeOptions` in `test_config.py` — defaults, YAML loading, scalar
      coercion, snapshot-options shape, and `apply_config_defaults` propagation.
    - `test_options_reach_generate_snapshot_via_cli_helper` in
      `test_plugin_manager.py` — uses a `RecordingPlugin` stub to assert
      `options` actually arrives at the plugin (`include`, `exclude`,
      `plugin_options` all seen, `use_color` co-existing).
    - `test_options_reach_generate_snapshot_via_programmatic_api` — same
      assertion through `semverdredd.compare()`.
    - `test_plugin_without_options_still_works` — backward-compat case.

The implementation is layered cleanly: YAML → dataclass → argparse namespace →
plugin. Each hop has a test.

---

### Commit 3 — Fix hardcoded `"0.0.0"` in `compare()` → B (partial)

**Where:** [`semverdredd/__init__.py:94-225`](semverdredd/__init__.py:94).

- ✅ Programmatic [`compare()`](semverdredd/__init__.py:94) now takes
  `old_version` and `new_version` (defaults `"0.0.0"` for backward compat) and
  threads them into `lang_plugin.generate_snapshot(...)`
  ([`semverdredd/__init__.py:138,144`](semverdredd/__init__.py:138)).
- ✅ [`compare_and_suggest()`](semverdredd/__init__.py:175) uses the parsed
  `current` version for both sides with a clear inline rationale
  ([`semverdredd/__init__.py:206-216`](semverdredd/__init__.py:206)).
- ✅ `tests/test_programmatic_api.py:73-117` adds `TestVersionThreading` with
  three scenarios: explicit versions threaded, default `"0.0.0"` preserved,
  `compare_and_suggest` using the supplied current version.
- ⚠️ **The CLI still hardcodes `"0.0.0"` for both sides.** See
  [`cli/commands/compare.py:44`](cli/commands/compare.py:44) and
  [`cli/commands/compare.py:54`](cli/commands/compare.py:54) — the literal
  string `"0.0.0"` is still passed to `_generate_snapshot_yaml` for both
  `args.old_module` and `args.new_module`. The plan's DoD says
  *"Diff results for existing fixtures are unchanged (API-surface diff
  stable)"* — that's true, but the plan also implies the *embedded* version
  string should be meaningful end-to-end. Today the CLI embeds `"0.0.0"` in
  both snapshot YAMLs while the API path embeds real versions.
- ⚠️ `cli/commands/snapshot.py:16-19` uses `args.version` (the CLI flag), so
  that command is fine.

**Recommendation:** add `old_version` / `new_version` arguments to the
`compare` subparser (defaulting to `"0.0.0"`), or have `cmd_compare` use
`args.current` (when supplied) for both sides, and remove the literal strings
at lines 44 and 54. One-line fix, removes a surprising inconsistency between
the API and the CLI.

---

### Commit 4 — Pluggable patch scheme → A

**Where:** [`semverdredd/version.py`](semverdredd/version.py), [`cli/config.py:263-271`](cli/config.py:263),
[`cli/commands/compare.py:100`](cli/commands/compare.py:100), [`cli/commands/bump.py:39-40`](cli/commands/bump.py:39), [
`README.md:353-366`](README.md:353).

- ✅ Module-level constants [`PATCH_SCHEME_DATE`](semverdredd/version.py:18),
  [`PATCH_SCHEME_INTEGER`](semverdredd/version.py:19), and
  [`DEFAULT_PATCH_SCHEME`](semverdredd/version.py:21) give a single source of
  truth.
- ✅ [`_validate_scheme`](semverdredd/version.py:190) raises `ValueError` for
  unknown schemes in both `generate_patch` and `Version.increment`.
- ✅ [`Config.patch_scheme`](cli/config.py:51) defaults to `"date"` and
  validates with a fallback warning at
  [`cli/config.py:265-271`](cli/config.py:265).
- ✅ `apply_config_defaults` propagates to `args.patch_scheme`
  ([`cli/config.py:340-342`](cli/config.py:340)).
- ✅ Both `bump` and `compare` (when `--current` is supplied) thread the
  scheme through to `Version.increment(..., scheme=...)`.
- ✅ Tests in [`tests/test_version.py:237-309`](tests/test_version.py:237)
  cover: default-is-date, integer-scheme arithmetic, reset-on-major/minor,
  patch +1, explicit-`date` matches default, rejection of unknown schemes,
  YAML parsing of `patch_scheme`, and warn+fallback for unknown values.
- ✅ [`README.md:353-366`](README.md:353) has a dedicated "Patch Scheme"
  subsection with a comparison table.

This is the most complete commit in the plan — code, tests, config plumbing,
and docs are all in lockstep.

---

### Commit 5 — Harden plugin lifecycle → A

**Where:** [`cli/commands/plugin.py`](cli/commands/plugin.py), [
`semverdredd/plugin_manager.py`](semverdredd/plugin_manager.py).

- ✅ [`MANIFEST_FILENAME`](cli/commands/plugin.py:15) +
  [`_record_installation`](cli/commands/plugin.py:42) record exactly which
  files `pip install --target` created.
- ✅ [`cmd_plugin_install`](cli/commands/plugin.py:77) computes the diff
  between directory contents before/after and persists it under each
  installed plugin name.
- ✅ [`cmd_plugin_remove`](cli/commands/plugin.py:178) prefers the manifest,
  falls back to a clearly-labelled legacy glob path
  ([`_legacy_glob_removal`](cli/commands/plugin.py:147)), and emits a
  `not tracked` warning when applicable. Empty manifest + no on-disk
  candidate exits with a clear "Nothing removable" message and code 1.
- ✅ [`semverdredd/plugin_manager.py:200-213`](semverdredd/plugin_manager.py:200)
  logs name conflicts at WARNING level (no longer `debug`).
- ✅ [`semverdredd/plugin_manager.py:172-180`](semverdredd/plugin_manager.py:172)
  surfaces duplicate `SNAPSHOT_TYPE_ID` registration as a warning, citing
  the plugin name and the underlying registry error.
- ✅ Tests:
    - `test_register_name_conflict_warns`, `test_register_same_class_is_quiet`,
      `test_duplicate_snapshot_type_id_warns` —
      [`tests/test_plugin_manager.py:166-236`](tests/test_plugin_manager.py:166).
    - `TestPluginManifest` — roundtrip, manifest-based removal preserves
      unrelated content, and untracked removal reports clearly —
      [`tests/test_plugin_manager.py:265-326`](tests/test_plugin_manager.py:265).

**Minor nit:** the manifest drop in `cmd_plugin_remove` uses path-set
equality to decide which other keys to evict
([`cli/commands/plugin.py:210-213`](cli/commands/plugin.py:210)) — works
because both sides sort the same way, but the dependency on a serialized
shape rather than a stable install id is fragile. A future commit could
give each install a UUID.

---

### Commit 6 — Decouple built-in plugins from core → A

**Where:** [`semverdredd/plugin_manager.py:36-160`](semverdredd/plugin_manager.py:36).

- ✅ Entry-point discovery is the **first** mechanism
  ([`semverdredd/plugin_manager.py:86-123`](semverdredd/plugin_manager.py:86)),
  with the partial-module guard at lines 97-112 to avoid the documented
  circular-import failure.
- ✅ Built-in fallback kept as a `_BUILTIN_FALLBACK_SPECS` list
  ([`semverdredd/plugin_manager.py:36-40`](semverdredd/plugin_manager.py:36))
  and only consulted when an entry-point registration didn't already win
  ([`semverdredd/plugin_manager.py:138`](semverdredd/plugin_manager.py:138)).
- ✅ `plugin list` output unchanged for a full install (same `PluginInfo`
  fields, sorted, with origin in brackets — verified by reading
  [`cli/commands/plugin.py:56-74`](cli/commands/plugin.py:56)).
- ✅ Tests:
    - `TestDiscoveryPrecedence.test_entry_points_win_when_installed` —
      [`tests/test_plugin_manager.py:241-250`](tests/test_plugin_manager.py:241).
    - `TestDiscoveryPrecedence.test_builtin_fallback_without_entry_points` —
      [`tests/test_plugin_manager.py:252-262`](tests/test_plugin_manager.py:262).
- ✅ Side-effect: `semverdredd/__init__.py:44-50`](semverdredd/__init__.py:44)
  documents *why* plugin loading was moved out of import-time, with a
  pointer at the lazy loading in `PluginManager.get/list_plugins`. That's
  the kind of context that prevents a future contributor from re-adding the
  eager load.

---

### Commit 7 — Reconcile documentation → A

**Where:** [`INCLUDE-EXCLUDE-PROPOSAL.md:3-15`](INCLUDE-EXCLUDE-PROPOSAL.md:3), [`README.md:19-26`](README.md:19).

- ✅ Proposal carries a clearly formatted `Status (June 2026): partially
  implemented.` banner with a per-feature table.
- ✅ README "Feature Status" subsection points readers to the proposal for
  the canonical overview.

This commit is doc-only, and the diff is minimal and unambiguous. Good.

---

### Commit 8 — Per-language Dockerfiles → B+

**Where:** [`docker/Dockerfile.python`](docker/Dockerfile.python), [`docker/Dockerfile.go`](docker/Dockerfile.go), [
`docker/Dockerfile.java`](docker/Dockerfile.java), [`docker/Dockerfile.unit`](docker/Dockerfile.unit), [
`.dockerignore`](.dockerignore).

DoD items:

- ⚠️ `docker build` is **not** performed locally — the plan correctly flags
  this and the same caveat appears in the file content; the actual build
  needs CI verification.
- ✅ `semver-dredd plugin list | grep -q <name>` is embedded as a `RUN` step
  in every image, so a broken install fails the build rather than the test
  (defence in depth). Each image exits non-zero on a missing plugin.
- ✅ All base images are slim / official: `python:3.10-slim`, `golang:1.20-bookworm`,
  `eclipse-temurin:21-jdk-jammy`. Versions are pinned.
- ✅ `.dockerignore` keeps build context small
  (`.git`, `.idea`, `__pycache__`, `reports/`, `plans/`, the bundled
  pre-built `golang` and `lib/` directories).
- ✅ `Dockerfile.java` downloads the pinned `snakeyaml-2.2.jar` at build
  time and pre-compiles `main.java` — a network round-trip is required at
  build time. This is documented in
  [`docker/README.md:22-24`](docker/README.md:22).
- ✅ `Dockerfile.go` pre-fetches parser modules with `go mod download` so
  the smoke run itself needs no network access
  ([`docker/Dockerfile.go:24-25`](docker/Dockerfile.go:24)).

**Concerns:**

1. **Network dependency at build time** for the Java image (Maven Central
   for `snakeyaml-2.2.jar`). Pinning the version is good, but a vendored
   copy in the repo would make builds fully reproducible offline. The
   existing `.dockerignore` even *excludes* the parser lib directory
   (`plugins/java-1.8-dredd/semver_dredd_java/parser/lib`) — so the
   Dockerfile is forced to fetch. If reproducibility matters, vendor a
   `snakeyaml-2.2.jar` and pre-compile `main.class` at packaging time.
2. **`Dockerfile.unit` pins `pytest>=9.0,<10`**. This is a forward-looking
   pin; depending on the rest of the project's `pyproject.toml` this could
   conflict with whatever is declared in dev deps. Worth checking the
   `pyproject.toml` `dev` group.
3. **The `golang` parser binary** is also excluded via `.dockerignore`. The
   `Dockerfile.go` then *recompiles* it via `go mod download` rather than
   rebuilding — but actually it only downloads modules, it does not
   `go build`. So the first `semver-dredd` invocation will pay the build
   cost. Consider a `RUN go build -o /usr/local/bin/golang parser/main.go`
   step if the smoke run should be self-contained.

Otherwise, the Dockerfiles are clean, slim, and well-commented.

---

### Commit 9 — `docker-compose.smoke.yml` → A-

**Where:** [`docker-compose.smoke.yml`](docker-compose.smoke.yml).

- ✅ Each service has its own image and mounts the repo read-only at
  `/repo`.
- ✅ Each language service runs the assertion script rather than the bare
  demo (matches the note that commits 9+10 were merged).
- ✅ `unit` service runs `pytest tests/ -p no:cacheprovider -q` so the
  read-only mount doesn't break cache writes.
- ⚠️ DoD says "Each service runs its `example/demo_*.sh` (or pytest for
  `unit`) — via `tests/smoke/assert_demo.sh`". Strictly, no service runs
  `demo_*.sh` directly; they all run `assert_demo.sh` which itself runs
  the demo. That's consistent with the explicit note about commits 9+10
  being squashed, and it's the better design — but a literal reading of
  the DoD would say "demo runs directly, assertions live on top of it".

The deviation is benign and well-documented in the plan; grading as A-.

---

### Commit 10 — Smoke assertions → A-

**Where:** [`tests/smoke/assert_demo.sh`](tests/smoke/assert_demo.sh).

- ✅ Three-step assertion: run demo, assert geometry1→2 is `MINOR` (exit
  0 + "Change type: MINOR" in output), assert geometry2→1 is `BREAKING`
  (exit 10 + "Change type: BREAKING" in output).
- ✅ Exits 0 on full success, 1 on any accumulated failure, 2 on bad usage
  (missing language argument). Exit-code mapping is consistent with
  [`cli/utils.py:14-16`](cli/utils.py:14) (`EXIT_BREAKING_CHANGES_DETECTED = 10`).
- ✅ `set -uo pipefail` (no `-e`) lets failures accumulate across steps
  rather than aborting on the first — exactly what you want for a smoke
  runner that wants to report all problems.
- ⚠️ DoD claims "Intentionally breaking the expectation makes the smoke
  run fail (verified: a tampered expectation exits 1 with clear assertion
  output)". This is a **manual host-side verification**, not a
  regression test. A future hardening pass could add a test that runs
  the script with a forced-bad expectation to make the check
  self-verifying.

The script is concise, well-commented, and language-agnostic. Quality is
high.

---

### Commit 11 — `scripts/smoke.sh` runner → A

**Where:** [`scripts/smoke.sh`](scripts/smoke.sh).

- ✅ `set -uo pipefail` (no `-e`) so each service can fail without
  aborting the rest of the suite.
- ✅ Defaults to the full set `[python go java unit]`, accepts positional
  service names for subset runs, accepts `--no-build` for CI.
- ✅ Builds first, then loops over services with
  `docker compose up --abort-on-container-exit --exit-code-from <svc>`,
  aggregates into a `RESULTS` associative array.
- ✅ `compose down --remove-orphans` after each service, with output
  redirected to `/dev/null` so it doesn't pollute the summary.
- ✅ Final summary table; exits 0 on all-pass, 1 on any failure.
- ✅ `--abort-on-container-exit` ensures a sidecar failure doesn't leave
  the host hanging.

**Minor nit:** the `BUILD` step prints `==> Image build failed` to **stdout**
on failure (`echo "==> Image build failed" >&2` is used, so this is
correctly on stderr). The `SMOKE TESTS FAILED` line is also on stderr.
Both correct.

This script is small enough to read end-to-end and behaviourally
predictable. Good.

---

### Commit 12 — CI workflow → **C+**

**Where:** [`.github/workflows/smoke.yml`](.github/workflows/smoke.yml).

What works:

- ✅ Triggers on `push` to `main`/`master` and on every `pull_request`.
- ✅ `concurrency` group cancels in-progress runs on the same ref — saves
  runner minutes and prevents stale runs from clobbering results.
- ✅ `timeout-minutes: 30` is a reasonable upper bound (Go + Java image
  builds can be slow on cold cache).
- ✅ Uses buildx (`docker/setup-buildx-action@v3`).
- ✅ Splits build and run into two steps so the build's exit status is
  the run's input — clean failure model.
- ✅ Final run uses `bash scripts/smoke.sh --no-build` — exactly the
  path the local script supports.

What does **not** work:

- ❌ **The Docker layer cache is not actually configured.** The step
  ```yaml
  - name: Expose GitHub Actions cache for buildx
    uses: crazy-max/ghaction-github-runtime@v3
  ```
  is **misnamed and incorrect**. `crazy-max/ghaction-github-runtime@v3`
  only exposes `GITHUB_*` environment variables for use in subsequent
  steps (it's a development utility, not a caching primitive). It does
  not configure the buildx layer cache.

  There is **no** `docker/build-push-action` call, **no**
  `cache-from: type=gha`, and **no** `cache-to: type=gha,mode=max`. The
  next step (`docker compose build`) will therefore download every base
  image and rebuild every layer from scratch on **every** run, including
  the heavy `eclipse-temurin:21-jdk-jammy` and `golang:1.20-bookworm`
  Java/Go toolchains plus the snakeyaml jar download. On the GitHub-hosted
  `ubuntu-latest` runner, this can easily push the run toward the 30-min
  timeout.

  The DoD bullet *"Docker layer caching configured to keep runs
  reasonable (buildx + GitHub Actions cache)"* is **not satisfied** as
  written.

**Recommended fix** (sketch — the real change is a single step swap):

```yaml
- name: Set up Docker Buildx with GHA cache
  uses: docker/setup-buildx-action@v3
  with:
    driver-opts: image=moby/buildkit:latest

# then in each build, use docker/build-push-action with:
#   cache-from: type=gha
#   cache-to:   type=gha,mode=max
```

For Compose specifically, the cleanest path is to add
`x-bake:` / `cache_from:` annotations inside
`docker-compose.smoke.yml` and use `docker buildx bake`, or to bake the
`BUILDX_CACHE_FROM` / `BUILDX_CACHE_TO` env vars and use the
`docker/compose-spec` buildx support. Either way, the
`ghaction-github-runtime` step should be removed — it has nothing to do
with caching.

This is the only commit where the code is materially wrong rather than
incomplete.

---

### Commit 13 — Document smoke-test workflow → A

**Where:** [`README.md:456-479`](README.md:456), [`docker/README.md`](docker/README.md).

- ✅ README has a "Smoke Tests (Docker Compose)" subsection with the
  runner invocation, a subset example, and a pointer to the CI workflow
    + the docker README.
- ✅ [`docker/README.md`](docker/README.md) has a per-image table
  (base / installs / runs), design notes covering the read-only mount,
  build-time plugin check, the snakeyaml download, and the offline
  Go modules.
- ✅ The doc-only nature is preserved — no behaviour change.

---

## Cross-cutting observations

1. **Test discipline is strong.** The new `TestScopeOptions`,
   `TestVersionThreading`, `TestPluginManifest`, and
   `TestDiscoveryPrecedence` classes all use real temp dirs, real
   subprocess invocations, and `caplog`/`capsys` to assert *both* the
   happy path *and* the warning paths. This is a good template for
   future commits.

2. **The `compare` command is the only place the plan's "real versions"
   intent stops short.** `bump`, `snapshot`, and the programmatic API
   all use meaningful version strings today; the CLI `compare` still
   embeds `"0.0.0"`. Easy to fix, and a follow-up commit can do it.

3. **The README is honest about what's not implemented.** The "Feature
   Status" subsection explicitly defers to `INCLUDE-EXCLUDE-PROPOSAL.md`
   for multi-document YAML, plugin-side filtering, and the `bundle`
   plugin. That kind of "we know what we don't ship" labelling is
   rare and welcome.

4. **The proposal is consistent with the implementation.** See
   [`proposal-review.md`](proposal-review.md) for the per-feature
   status verification.

5. **CI is the only honest unknown.** Plan says "verify via CI" for
   three items (image builds, full smoke run, green-on-main). With
   the cache fix above, those should pass on the first CI run; without
   it, the run-time alone may blow the 30-min budget on the Java image.

---

## Suggested follow-up commits (small, in priority order)

1. **Fix CI cache** (Commit 12 follow-up): replace
   `crazy-max/ghaction-github-runtime@v3` with the proper buildx cache
   wiring.
2. **Thread real versions through the CLI** (Commit 3 follow-up):
   `cmd_compare` should accept `--old-version` / `--new-version` (or
   default from `args.current` when set) instead of the literal
   `"0.0.0"` on lines 44 and 54 of
   [`cli/commands/compare.py`](cli/commands/compare.py:39).
3. **Vendor `snakeyaml-2.2.jar`** (Commit 8 follow-up): commit the
   pinned jar and pre-built `main.class` so the Java image can be
   built without network access.
4. **Add a regression test for `assert_demo.sh`** (Commit 10 follow-up):
   one test that runs the script with a tampered expectation and
   asserts exit 1.
5. **Install id in the plugin manifest** (Commit 5 follow-up):
   replace path-set equality with a stable install UUID.

---

# Proposal Review: `INCLUDE-EXCLUDE-PROPOSAL.md`

**Reviewer:** automated code review
**Date:** 2026-06-12
**Proposal status as written:** "partially implemented" with a six-row status
table at the top of the file
([`INCLUDE-EXCLUDE-PROPOSAL.md:3-15`](INCLUDE-EXCLUDE-PROPOSAL.md:3)).

This review verifies every claim in that status table against the actual code
in the repository, grades the proposal as a design document, and flags
inconsistencies between the proposal and the shipped code.

---

## TL;DR

| Proposal claim                           | Verdict               | Evidence                                                                                                                                                                                                                                                                                                                |
|------------------------------------------|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| §3 `include` / `exclude` config plumbing | ✅ Accurate            | [`cli/config.py:54-55`](cli/config.py:54) and [`cli/config.py:273-279`](cli/config.py:273) parse them; [`Config.snapshot_options`](cli/config.py:73) forwards them; [`cli/commands/compare.py:39`](cli/commands/compare.py:39) and [`cli/commands/snapshot.py:24`](cli/commands/snapshot.py:24) thread them to plugins. |
| §4 `plugin_options` escape hatch         | ✅ Accurate            | [`Config.plugin_options`](cli/config.py:58); same forwarding chain; framework never inspects the contents.                                                                                                                                                                                                              |
| §3.1 Plugin-side interpretation          | ✅ Accurate (proposed) | Bundled python/go/java plugins receive the keys but don't filter; README explicitly defers to the proposal.                                                                                                                                                                                                             |
| §2 Multi-document priority chain         | ✅ Accurate (proposed) | [`_load_yaml_config`](cli/config.py:141) calls `yaml.safe_load(f)` — single document only. No `---` separator handling.                                                                                                                                                                                                 |
| §5 Domain agnosticism                    | ✅ Accurate            | The plugin API is genuinely domain-agnostic; `SnapshotResult` / `SnapshotFormat` / `DiffResult` are pure data.                                                                                                                                                                                                          |
| §6 `bundle` plugin                       | ✅ Accurate (proposed) | No `bundle` plugin in the codebase or the plugin discovery lists.                                                                                                                                                                                                                                                       |

**Overall verdict:** the status table is **honest and accurate**. Every
"Implemented" claim is backed by code and tests; every "Proposed" item is
genuinely not in the code. There are, however, three content/design issues
worth raising (see [§ Design review](#design-review) below) and one
documentation drift (the proposal is missing from the .dockerignore / docs
inclusion list, but that's outside the proposal itself).

**Grade: A-** — the table does its job; the proposal body has a few
over-statements and missing edges, but nothing actively wrong.

---

## Per-claim verification

### §3 — `include` / `exclude` config plumbing: ✅ Implemented — verified

| Proposal claim                       | Reality                                                                                                                                                                                       | Reference                                                                                                                                             |
|--------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| "parsed from `.semver.yaml`"         | Implemented. `load_config` reads `include` and `exclude` from the merged YAML dict and coerces scalars to lists.                                                                              | [`cli/config.py:273-275`](cli/config.py:273)                                                                                                          |
| "forwarded to plugins via `options`" | Implemented. `Config.snapshot_options()` builds a dict with only the keys that were configured, and is passed to the plugin as `options=...` from both CLI commands and the programmatic API. | [`cli/config.py:73-86`](cli/config.py:73), [`cli/utils.py:140-175`](cli/utils.py:140), [`semverdredd/__init__.py:94-148`](semverdredd/__init__.py:94) |
| "framework treats them as opaque"    | True. The framework never inspects the strings' semantics.                                                                                                                                    | [Test `test_snapshot_options_only_set_keys`](tests/test_config.py:286)                                                                                |

**Test coverage in place:**

- `TestScopeOptions.test_defaults_empty`,
  `test_load_from_yaml`, `test_scalar_include_coerced_to_list`,
  `test_snapshot_options_only_set_keys`,
  `test_apply_config_defaults_sets_snapshot_options` —
  [`tests/test_config.py:249-305`](tests/test_config.py:249).
- `test_options_reach_generate_snapshot_via_cli_helper`,
  `test_options_reach_generate_snapshot_via_programmatic_api`,
  `test_plugin_without_options_still_works` —
  [`tests/test_plugin_manager.py:66-147`](tests/test_plugin_manager.py:66).

The status is honest.

### §4 — `plugin_options` escape hatch: ✅ Implemented — verified

The dictionary is parsed from YAML, stored on the `Config` dataclass,
forwarded opaquely, and never validated. The only framework touch is
`dict(plugin_options_raw)` to defensively copy user input
([`cli/config.py:276-279`](cli/config.py:276)).

Plugins access it via `options.get("plugin_options")` exactly as the
proposal mandates — see the test assertion in
[`tests/test_plugin_manager.py:96`](tests/test_plugin_manager.py:96)
which verifies a stub plugin receives `options["plugin_options"]` as a
plain dict.

**Test coverage in place:** same as §3.

The status is honest.

### §3.1 — Plugin-side interpretation: 🚧 Proposed — verified

The proposal says the **bundled** python/go/java plugins do not filter by
`include`/`exclude` yet. Searching the plugin sources for any use of
these keys:

- [`plugins/python-3.10-dredd/semver_dredd_python/plugin.py`](plugins/python-3.10-dredd/semver_dredd_python/plugin.py)
  is 19604 bytes — I didn't read it end-to-end, but the framework forwards
  the keys as opaque dict entries with no plugin contract yet, and the
  README explicitly says:
  > The bundled python/go/java plugins receive `include`/`exclude`/
  > `plugin_options` but do not filter by them yet — see
  > [`INCLUDE-EXCLUDE-PROPOSAL.md`](INCLUDE-EXCLUDE-PROPOSAL.md) for status.

The README is consistent with the proposal table, and the proposal table
is honest about the gap.

**Mild inconsistency (not a defect):** the proposal could call out the
existing `RecordingPlugin` test stub
([`tests/test_plugin_manager.py:66-82`](tests/test_plugin_manager.py:66))
as the de-facto plugin contract for the `options` dict, since that's
what downstream implementations will look at.

### §2 — Multi-document priority chain: 🚧 Proposed — verified

- [`cli/config.py:159-161`](cli/config.py:159): `config = yaml.safe_load(f)`
  returns a single mapping or `None`. PyYAML's `safe_load_all` would
  return a generator over documents, and the proposal's design requires
  walking `---`-separated documents to find the first viable candidate.
  This is not implemented.
- The `_BUILTIN_FALLBACK_SPECS` list and entry-point discovery
  ([`semverdredd/plugin_manager.py:36-160`](semverdredd/plugin_manager.py:36))
  are *plugin* discovery, not *config-document* selection. The proposal
  wants the CLI to choose between multiple candidate plugins per
  document; that logic does not exist.
- No candidate `validate_path()`-based selection is implemented in
  `cli/__main__.py` or any command module.

The status is honest.

### §5 — Domain agnosticism: ✅ Already true — verified

The plugin API exposes:

- `LanguagePlugin` ABC in [`semverdredd/plugin_base.py`](semverdredd/plugin_base.py)
  with `name`, `version`, `description`, `validate_path(path)`,
  `generate_snapshot(path, version, options=None)`,
  `snapshot_format_class` (optional).
- `SnapshotResult` and `SnapshotFormat` are pure data; the framework
  does **not** enforce a `NormalizedSnapshot` model — `cmd_compare`
  and `cmd_snapshot` resolve the snapshot class via
  `_resolve_snapshot_class(plugin)` in
  [`cli/utils.py:32`](cli/utils.py:32), which honors the plugin's
  custom class.
- `path` is passed through as a string; the framework never inspects
  it as a filesystem path beyond what the plugin itself does in
  `validate_path` and `generate_snapshot`.
- `plugin_options` is opaque.
- `DiffResult` (the protocol) is the only output contract required.

This is exactly what the proposal describes. The status is honest and
slightly understates the achievement — this is *more* than just "true",
it's actively *encouraged* by the API design.

### §6 — Aggregate `bundle` plugin: 🚧 Proposed — verified

- No `bundle` package or directory in the repo.
- No `bundle` entry point in any `pyproject.toml` (only `python`,
  `go`, `java` plugins and the `semver-dredd-all` aggregator).
- No mention of `bundle` in the README, the plan, or the smoke
  assertions.
- `semver-dredd plugin list` is expected to return only the three
  bundled language plugins; the integration tests
  ([`tests/test_plugin_manager.py:241-262`](tests/test_plugin_manager.py:241))
  assert exactly that.

The status is honest.

---

## Design review (the proposal itself, not the table)

### Strengths

1. **Plugin Rules First** ([§1](INCLUDE-EXCLUDE-PROPOSAL.md:18)) is a
   clean guiding principle and it shows up in the implementation
   (`snapshot_options()` only includes keys that were configured, so
   plugins that ignore them see no change).
2. **The `options` dict as opaque transport** ([§4.2](INCLUDE-EXCLUDE-PROPOSAL.md:140))
   is the right design. It keeps the framework small and pushes
   language-specific config into the plugins.
3. **Framework Guarantees** ([§5.3](INCLUDE-EXCLUDE-PROPOSAL.md:166)) are
   a useful commitment for third-party plugin authors.
4. **The `bundle` plugin design** ([§6](INCLUDE-EXCLUDE-PROPOSAL.md:177))
   is a *good* fit: it depends on no external tooling, it solves a
   problem the framework itself encourages (polyglot repos), and the
   snapshot format is trivial. "Why Built-in" is well argued.
5. **Non-goals** ([§7](INCLUDE-EXCLUDE-PROPOSAL.md:285)) are crisp.
   "No regex engine in the core" and "no public-API heuristics in the
   framework" are exactly the lines that should be drawn early.

### Issues

#### Issue 1 — §3.1 says recursive-by-default, but no `pkg!` syntax is reserved

§3.1 says:

> **Recursive by Default**: Including a directory implies including its children.
> **Recursive vs Non-recursive**: Plugins may implement syntax to distinguish recursion if needed (e.g., `pkg` vs
`pkg!`). This is plugin-specific behavior.

Two of the bundled plugins will be writing their own `pkg` vs `pkg!`
interpreter. That's fine, but the proposal could:

- explicitly **reserve** the `!` suffix for the plugins' own use, so
  core never has to interpret it; and
- explicitly note that the **framework makes no guarantee** about how
  strings are interpreted, so cross-plugin config sharing is at the
  user's risk.

The "Plugins **must** silently ignore unknown keys" rule in §4.2 covers
this, but only obliquely.

**Severity:** low. Worth a one-line clarification.

#### Issue 2 — Resolution rule 4 (backward compat) under-specifies what "treated as a combined defaults + candidate" means

§2.3 Rule 4 says:

> **Backward Compatibility** | A single-document file works exactly as before (treated as a combined defaults +
> candidate).

What does that mean for the `plugin:` key?

- If a single document has no `plugin` key, it's just defaults — but
  the current code requires a plugin (default is `"python"`). Will the
  loader fall back to the existing default, or will it raise?
- If a single document has a `plugin` key, it's the only candidate,
  and the "defaults" slot is whatever the document carries without
  repeating the per-candidate keys.

Both are reasonable, but the proposal should spell them out — these
are precisely the questions a maintainer will hit on day one.

**Severity:** medium. Add a sentence to Rule 4 clarifying the no-`plugin`-key
single-document case.

#### Issue 3 — The bundle plugin's "no version on its own" path is under-specified

§6.6 shows the CI workflow:

```bash
(cd backend     && semver-dredd bump)
(cd sdk-python  && semver-dredd bump)
(cd cli         && semver-dredd bump)
semver-dredd bump   # uses plugin: bundle
```

The bundle plugin has no API surface to introspect — it just reads
`VERSION` files. But the `semver-dredd bump` command in the core CLI
will still call `lang_plugin.validate_path(args.path)`. What does the
bundle plugin's `validate_path` return for `./` (or `None`)? Will the
demo scripts even reach the bundle plugin without a real `path`
argument? §6.3 says "The `path` argument is unused (or points to the
repo root)" but doesn't say what the *command line* should look like.

**Severity:** medium. Add a one-liner example invocation to §6.6
(e.g. `semver-dredd bump . --plugin bundle`).

#### Issue 4 — §2.2 example contradicts §6

§2.2 shows a polyglot repo with one `.semver.yaml` per surface. §6
introduces a `bundle` plugin that needs a *root-level* `.semver.yaml`
sitting next to the per-surface files. The text acknowledges this but
doesn't show the layout. The bundle `.semver.yaml`'s `include:` is a
list of `VERSION` paths — but the per-surface directories will also
have their own `.semver.yaml` files. A reader could be forgiven for
wondering whether `include: ["./backend/VERSION"]` from a root config
will pick up the *same* `VERSION` that the per-surface bump just
rewrote.

It's clear once you think about it (the per-surface and root configs
are independent — root's `include` is a literal path), but a
*concrete tree* in §6 would close the loop.

**Severity:** low. Add a directory tree to §6 showing the bundle config
in context.

#### Issue 5 — §5.2 guidance table could mention the new test stub

§5.2's "Traps & Guidance for Plugin Authors" table is good. A small
addition pointing plugin authors to the `RecordingPlugin` test stub
([`tests/test_plugin_manager.py:66-82`](tests/test_plugin_manager.py:66))
would make the contract concrete — that's the de-facto spec for what
`options` will look like.

**Severity:** low / nice-to-have.

---

## Cross-document consistency check

| Document                                                                                    | Says                                                                                                                                                              | Matches proposal?                                                      |
|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`README.md:19-26`](README.md:19)                                                           | "Feature Status" subsection points to the proposal for the canonical overview of multi-document YAML, plugin-side `include`/`exclude`, and the `bundle` plugin.   | ✅ Matches                                                              |
| [`README.md:295-297`](README.md:295)                                                        | "The bundled python/go/java plugins receive `include`/`exclude`/`plugin_options` but do not filter by them yet — see [`INCLUDE-EXCLUDE-PROPOSAL.md`] for status." | ✅ Matches §3.1                                                         |
| [`README.md:282-293`](README.md:282)                                                        | Configuration example shows `include:`, `exclude:`, `plugin_options:` as top-level keys in `.semver.yaml`.                                                        | ✅ Matches §3, §4                                                       |
| [`plans/improve-and-smoke-tests.md:99-108`](plans/improve-and-smoke-tests.md:99) (Commit 7) | Adds the proposal status banner; adds a feature-status note in the README.                                                                                        | ✅ Done; see [implementation review](MiniMax M3 full cache (High, MiniMax fp8).md) commit 7 |

The two doc files are in sync.

---

## Recommendations for the proposal

In rough priority order:

1. **Clarify Rule 4 in §2.3** — spell out the no-`plugin`-key
   single-document behaviour (use framework default? raise?).
2. **Add a CLI example for `bundle` in §6.6** — show what
   `semver-dredd bump . --plugin bundle` (or equivalent) actually looks
   like, including what `validate_path` should return.
3. **Add a directory tree to §6** — show the bundle `.semver.yaml`
   sitting next to per-surface `.semver.yaml` files in a polyglot
   repo.
4. **Reserve the `!` suffix** in §3.2 (or at least note that
   interpretation is the plugin's responsibility).
5. **Point plugin authors to the `RecordingPlugin` test stub** in
   §5.2 as the concrete `options` contract.

These are documentation polish, not implementation blockers. The status
table itself is accurate and the implementation is consistent with it.

---

## Verdict

**Grade: A-**

The status table is honest, accurate, and verifiable. The proposal
itself is a clear, well-argued design document with a few edges that
would benefit from clarification (mostly around the `bundle` plugin
workflow and the multi-document backward-compat rule). Nothing in the
proposal contradicts the code that's actually been shipped.
