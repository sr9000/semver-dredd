# Plan: Improve semver-dredd & Add Docker Compose Smoke Tests

**Date:** June 10, 2026
**Status:** Proposed
**Scope:** Tool improvements + containerized smoke tests

This plan is organized as a **commit-by-commit roadmap**. Each step is a single,
self-contained commit with an explicit **Definition of Done (DoD)** that must be
satisfied before moving to the next step.

---

## Part A — Tool Improvements

### Commit 1 — Surface config parse errors

**Change:** In `cli/config.py`, stop swallowing exceptions in `_load_yaml_config`;
emit a warning when `.semver.yaml` fails to parse instead of silently returning `{}`.

**DoD:**
- [x] Malformed `.semver.yaml` produces a visible warning on stderr.
- [x] Valid/missing config still returns a `Config` with no warning.
- [x] New unit test in `tests/test_config.py` covers the malformed-file path.
- [x] `pytest tests/test_config.py` passes; no regression in existing tests.

---

### Commit 2 — Plumb `include` / `exclude` / `plugin_options`

**Change:** Parse `include`, `exclude`, and `plugin_options` from `.semver.yaml`
(`cli/config.py`) and forward them via `generate_snapshot(..., options=...)` from
the command modules and `semverdredd/__init__.py` (currently always `None`).

**DoD:**
- [x] `Config` exposes `include`, `exclude`, `plugin_options`.
- [x] `options` dict reaches `LanguagePlugin.generate_snapshot` (verified by a
      stub plugin in tests).
- [x] Plugins ignoring these keys behave exactly as before (backward compatible).
- [x] New tests in `tests/test_config.py` + `tests/test_plugin_manager.py` pass.

---

### Commit 3 — Fix hardcoded `"0.0.0"` in `compare()`

**Change:** Thread real version strings through `compare()` /
`compare_and_suggest()` in `semverdredd/__init__.py` instead of generating both
snapshots with `"0.0.0"`.

**DoD:**
- [x] `compare()` passes meaningful versions to `generate_snapshot`.
- [x] Diff results for existing fixtures are unchanged (API-surface diff stable).
- [x] `tests/test_programmatic_api.py` updated and passing.

---

### Commit 4 — Pluggable patch scheme

**Change:** Add `versioning.patch_scheme: date|integer` config option, implemented
in `semverdredd/version.py`, defaulting to `date` (current behavior).

**DoD:**
- [x] `integer` mode produces conventional incrementing patch numbers.
- [x] `date` mode is unchanged and remains the default.
- [x] `tests/test_version.py` covers both modes.
- [x] README "Versioning Scheme" section documents the option.

---

### Commit 5 — Harden plugin lifecycle

**Change:** Replace best-effort glob removal in `cli/commands/plugin.py` with an
installed-plugin manifest; log UUID/registration conflicts loudly in
`plugin_manager.py` (raise/warn instead of `debug`).

**DoD:**
- [x] `plugin install` records installed plugins in a manifest file.
- [x] `plugin remove` uses the manifest; reports clearly when nothing removable.
- [x] Duplicate `SNAPSHOT_TYPE_ID` across plugins produces a visible warning.
- [x] `tests/test_plugin_manager.py` covers conflict + remove paths.

---

### Commit 6 — Decouple built-in plugins from core

**Change:** Prefer entry-point discovery over the hardcoded `_builtin_specs` list
in `plugin_manager.py`; keep the list only as an editable-install fallback.

**DoD:**
- [ ] With plugins pip-installed, discovery works with no reference to the
      hardcoded list.
- [ ] Editable/dev installs still discover python/go/java via fallback.
- [ ] `semver-dredd plugin list` output unchanged for a full install.
- [ ] `tests/test_plugin_manager.py` passes.

---

### Commit 7 — Reconcile documentation

**Change:** Add a "Status: proposed / not yet shipped" banner to
`INCLUDE-EXCLUDE-PROPOSAL.md`; add a feature-status note in `README.md`.

**DoD:**
- [ ] Proposal clearly marks which features are implemented vs. proposed.
- [ ] README points readers to the current feature status.
- [ ] No code changes; docs only.

---

## Part B — Docker Compose Smoke Tests

### Commit 8 — Per-language Dockerfiles

**Change:** Add a `docker/` directory with `Dockerfile.python` (3.10),
`Dockerfile.go` (Go 1.20 + Python), `Dockerfile.java` (JDK + Python), and
`Dockerfile.unit` (pytest runner). Each installs core + the relevant plugin.

**DoD:**
- [ ] Each image builds successfully (`docker build`).
- [ ] `semver-dredd plugin list` inside each image shows the expected plugin.
- [ ] Images are slim (use `-slim`/official bases) and pin versions.

---

### Commit 9 — `docker-compose.smoke.yml`

**Change:** Add `docker-compose.smoke.yml` at repo root with one service per
Dockerfile: `python`, `go`, `java`, `unit`. Each mounts the repo read-only and
runs its target command, exiting non-zero on failure.

**DoD:**
- [ ] `docker compose -f docker-compose.smoke.yml config` validates.
- [ ] Each service runs its `example/demo_*.sh` (or pytest for `unit`).
- [ ] A failing demo causes the service to exit non-zero.

---

### Commit 10 — Smoke assertions

**Change:** Add `tests/smoke/assert_demo.sh` (or extend demos) asserting that
pygeometry1→2 yields `MINOR` and a removed-API fixture yields `BREAKING`, so demos
verify outcomes rather than only printing.

**DoD:**
- [ ] Assertion script exits 0 on expected bump, non-zero otherwise.
- [ ] Wired into each language demo / compose service.
- [ ] Intentionally breaking the expectation makes the smoke run fail.

---

### Commit 11 — `scripts/smoke.sh` runner

**Change:** Add `scripts/smoke.sh` that builds and runs each compose service with
`--abort-on-container-exit --exit-code-from <svc>`, aggregating results.

**DoD:**
- [ ] `bash scripts/smoke.sh` runs all services and returns aggregate exit code.
- [ ] Non-zero exit when any language smoke test fails.
- [ ] Script is idempotent and cleans up containers.

---

### Commit 12 — CI workflow

**Change:** Add `.github/workflows/smoke.yml` invoking `scripts/smoke.sh` on
push and pull_request.

**DoD:**
- [ ] Workflow triggers on push/PR.
- [ ] Green run on `main`; red run when a smoke assertion is broken.
- [ ] Docker layer caching configured to keep runs reasonable.

---

### Commit 13 — Document smoke-test workflow

**Change:** Document the smoke-test flow in `README.md` (Development section) and
add a short `docker/README.md`.

**DoD:**
- [ ] README explains how to run smoke tests locally.
- [ ] `docker/README.md` describes each image and its purpose.
- [ ] Docs-only commit; no behavior change.

---

## Open Questions (to confirm before/at kickoff)

1. Implement both Part A and Part B now, or Part B first (self-contained)?
2. Which Part A commits are in scope — all 7, or quick wins (1–3) only?
3. CI target — GitHub Actions assumed; confirm.
4. Base images — `python:3.10-slim`, `golang:1.20`, `eclipse-temurin` JDK OK?
