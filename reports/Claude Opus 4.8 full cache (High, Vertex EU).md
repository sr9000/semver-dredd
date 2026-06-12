# Implementation Review — `plans/improve-and-smoke-tests.md`

**Reviewer:** Kilo Code  
**Date:** June 12, 2026  
**Tokens:** up 1.1m; down 13.2k  
**Cache:** 1.1m  
**API Cost:** $2.92  
**Scope reviewed:** All 13 commits in the plan (Part A: tool improvements,
Part B: Docker Compose smoke tests) + the `INCLUDE-EXCLUDE-PROPOSAL.md` design
document.

**Verification method:** static reading of the affected source files, the test
suite, the Docker/CI assets, and a live test run:

```
poetry run pytest tests/ -q   →  219 passed in 0.89s
```

---

## 1. Executive Summary

| Area                                       | Grade  | One-line verdict                                                                                                |
|--------------------------------------------|--------|-----------------------------------------------------------------------------------------------------------------|
| Part A — tool improvements (commits 1–7)   | **A**  | Fully implemented, well-tested, backward-compatible.                                                            |
| Part B — smoke tests (commits 8–13)        | **A−** | Authored cleanly and honestly; Docker/CI paths not runtime-verified (no daemon), one network-dependency caveat. |
| Plan accuracy & honesty                    | **A**  | Every unchecked DoD box maps to a real "needs Docker/GitHub" gap — no overclaiming.                             |
| `INCLUDE-EXCLUDE-PROPOSAL.md` (design doc) | **A−** | Strong, coherent, status table matches the code; a few under-specified edge cases.                              |
| **Overall**                                | **A−** | High-quality, trustworthy delivery.                                                                             |

The plan is unusually honest: the only DoD checkboxes left unchecked are
exactly the four that require a running Docker daemon or a push to GitHub, and
each is explicitly annotated as such. Nothing claimed as done was found to be
missing.

---

## 2. Part A — Commit-by-Commit Findings

### Commit 1 — Surface config parse errors ✅ Verified

[`cli/config.py:141`](cli/config.py:141) `_load_yaml_config` now emits distinct
`[WARN]` messages on stderr for: missing PyYAML, `YAMLError`, `OSError`, and a
non-mapping document — instead of silently returning `{}`.
Tests: [`tests/test_config.py:117`](tests/test_config.py:117) cover
malformed / non-mapping / valid-no-warning / missing-no-warning. **DoD met.**

### Commit 2 — Plumb `include` / `exclude` / `plugin_options` ✅ Verified

`Config` exposes the three fields ([`cli/config.py:54`](cli/config.py:54)),
[`Config.snapshot_options()`](cli/config.py:73) only emits keys that are set
(so option-ignoring plugins are byte-for-byte unchanged), and
[`apply_config_defaults()`](cli/config.py:337) wires them onto the argparse
namespace. Options reach `generate_snapshot` in both the CLI path
([`cli/commands/snapshot.py:24`](cli/commands/snapshot.py:24),
[`cli/commands/compare.py:39`](cli/commands/compare.py:39)) and the
programmatic API. Tests: `TestScopeOptions` in
[`tests/test_config.py:249`](tests/test_config.py:249) plus
`test_options_reach_generate_snapshot_*` and `test_plugin_without_options_still_works`
in [`tests/test_plugin_manager.py:84`](tests/test_plugin_manager.py:84). **DoD met.**

### Commit 3 — Fix hardcoded `"0.0.0"` in `compare()` ✅ Verified (minor nuance)

[`semverdredd.compare()`](semverdredd/__init__.py:94) now takes
`old_version` / `new_version` and threads them into each snapshot;
[`compare_and_suggest()`](semverdredd/__init__.py:175) feeds the real current
version. Tests `test_compare_threads_explicit_versions` /
`test_compare_defaults_remain_000` confirm both behaviors.
**Nuance:** `compare_and_suggest` passes the *current* version for **both** old
and new snapshots (the post-bump version is unknown at snapshot time) — this is
acknowledged in an inline comment and is harmless because the version string
does not influence the API-surface diff. Separately, the CLI `compare` command
still hardcodes `"0.0.0"` for both sides; that was outside this commit's stated
scope (`semverdredd/__init__.py` only), so it is not a defect, but it leaves the
"meaningful versions" goal only partially realized at the CLI layer. **DoD met.**

### Commit 4 — Pluggable patch scheme ✅ Verified

[`semverdredd/version.py`](semverdredd/version.py:18) defines
`date` / `integer` schemes, validates unknown schemes (`_validate_scheme`),
and resets patch to `0` on major/minor in integer mode. Config parsing warns
and falls back to `date` on a bad value
([`cli/config.py:264`](cli/config.py:264)). README "Versioning Scheme" documents
the option with a behavior table. Tests: `test_version.py` covers both modes,
invalid-scheme errors, and config parsing. **DoD met.**

### Commit 5 — Harden plugin lifecycle ✅ Verified

[`cli/commands/plugin.py`](cli/commands/plugin.py:15) introduces an
`installed_plugins.json` manifest (`_record_installation` / `_load_manifest`),
and `plugin remove` consumes it, falling back to best-effort glob removal with a
clear "not tracked" warning and a non-zero exit when nothing is removable.
Registration conflicts are now loud: name conflicts `logger.warning`
([`plugin_manager.py:205`](semverdredd/plugin_manager.py:205)) and duplicate
`SNAPSHOT_TYPE_ID` warns ([`plugin_manager.py:172`](semverdredd/plugin_manager.py:172)).
Tests: `test_register_name_conflict_warns`, `test_duplicate_snapshot_type_id_warns`,
`TestPluginManifest` (roundtrip / remove / untracked). **DoD met.**

### Commit 6 — Decouple built-in plugins from core ✅ Verified

Entry-point discovery is the primary path; the hardcoded list is renamed
`_BUILTIN_FALLBACK_SPECS` and consulted only when an entry point did not already
register a name ([`plugin_manager.py:137`](semverdredd/plugin_manager.py:137)).
Tests: `test_entry_points_win_when_installed`,
`test_builtin_fallback_without_entry_points`. **DoD met.**

### Commit 7 — Reconcile documentation ✅ Verified

The proposal carries a per-feature status banner/table, and `README.md` has a
"Feature Status" section that points to it. Docs-only. **DoD met.**

---

## 3. Part B — Commit-by-Commit Findings

### Commit 8 — Per-language Dockerfiles ✅ Authored / ⚠ build not run

`docker/Dockerfile.{python,go,java,unit}` exist, use pinned slim/official bases
(`python:3.10-slim`, `golang:1.20-*`, `eclipse-temurin:21-jdk-jammy`), and each
ends with a `RUN semver-dredd plugin list | grep -q <name>` self-check so a
broken install fails the build. `.dockerignore` present.
**Honest gap:** the actual `docker build` is correctly left unchecked (no daemon
on the dev host). **Caveat:** the Java image `curl`s `snakeyaml-2.2.jar` and the
Go image pre-fetches modules at build time, so the builds are **not hermetic** —
they need network egress; an offline CI runner would fail the build (not just
the smoke run).

### Commit 9 — `docker-compose.smoke.yml` ✅ Verified (structure)

Four services (`python`/`go`/`java`/`unit`), repo mounted read-only, each runs
`tests/smoke/assert_demo.sh` (pytest for `unit`). The read-only mount is safe
because the demo writes to a `mktemp -d` work dir
([`example/demo_python.sh:18`](example/demo_python.sh:18)) and `unit` disables
the pytest cache. `config`-validation is correctly claimed (cannot re-verify
without the binary). **DoD met (structurally).**

### Commit 10 — Smoke assertions ✅ Verified (logic)

[`tests/smoke/assert_demo.sh`](tests/smoke/assert_demo.sh:1) runs the demo, then
asserts `geometry1→geometry2` prints `Change type: MINOR` (exit 0) and the
reverse prints `BREAKING` (exit 10), aggregating failures. Clear, exit-code
aware, tamper-detectable. **DoD met.**

### Commit 11 — `scripts/smoke.sh` runner ✅ Verified (logic)

[`scripts/smoke.sh`](scripts/smoke.sh:1) builds, runs each service with
`--abort-on-container-exit --exit-code-from`, aggregates a PASS/FAIL summary,
returns non-zero on any failure, supports a service subset and `--no-build`, and
cleans up with `compose down --remove-orphans` per service. **Honest gap:** full
run unchecked (no daemon). Aggregation/idempotency are sound by inspection.

### Commit 12 — CI workflow ✅ Verified (definition)

[`.github/workflows/smoke.yml`](.github/workflows/smoke.yml:1) triggers on
push (main/master) + PR, sets up buildx, enables GitHub Actions layer caching,
builds, then runs `scripts/smoke.sh --no-build`. Green/red runs honestly left
unchecked pending a push. **DoD met (definition).**

### Commit 13 — Document smoke-test workflow ✅ Verified

README "Smoke Tests (Docker Compose)" section + `docker/README.md` exist and
describe local usage and each image. **DoD met.**

---

## 4. Test Suite Health

`219 passed in 0.89s`. The new behavior is genuinely covered, not just asserted
in prose:

- config: malformed-YAML warning, scope-option parsing/forwarding, patch-scheme parsing;
- version: both patch schemes + invalid-scheme errors;
- plugin manager: option forwarding, name/UUID conflict warnings, entry-point-vs-fallback discovery, manifest
  roundtrip/remove.

No skipped or xfailed tests of concern (only a conditional `pydantic` skip).

---

## 5. Issues & Recommendations (none blocking)

1. **CLI `compare` still uses `"0.0.0"`** for both snapshots while the
   programmatic `compare()` was upgraded. For consistency, consider threading
   `--current` (when supplied) into the snapshot versions, or document that the
   CLI compare is version-agnostic by design.
2. **`compare_and_suggest` new-version is the current version**, not the
   suggested one. Harmless today, but if a plugin ever embeds the version into
   its diff logic this becomes subtly wrong. A short note in the docstring (it
   already has one) is adequate; no code change required.
3. **Non-hermetic image builds** (Java `snakeyaml` download, Go module fetch).
   For reproducible/offline CI, consider vendoring the jar / `GOFLAGS=-mod=vendor`
   or a pre-warmed base image. The Go parser binary is already committed, which
   helps.
4. **Plan date header** says "June 10, 2026" while the proposal says
   "June 2026" — cosmetic.

---

## 6. `INCLUDE-EXCLUDE-PROPOSAL.md` — Proposal Review

**Grade: A−.** A well-structured, opinionated design document with a clear
governing principle ("Plugin Rules First" / framework handles mechanics, plugins
own understanding). The status table at the top is **accurate against the code**:

| Proposal claim                                              | Reality in repo                           | Accurate? |
|-------------------------------------------------------------|-------------------------------------------|-----------|
| `include`/`exclude` plumbing implemented (§3)               | Parsed + forwarded via `options`          | ✅ Yes     |
| `plugin_options` escape hatch implemented (§4)              | Forwarded opaquely                        | ✅ Yes     |
| Plugin-side `include`/`exclude` filtering = proposed (§3.1) | Bundled plugins do not filter             | ✅ Yes     |
| Multi-document priority chain = proposed (§2)               | Loader uses `yaml.safe_load` (single doc) | ✅ Yes     |
| `bundle` plugin = proposed (§6)                             | No bundle plugin under `plugins/`         | ✅ Yes     |
| Domain agnosticism already true (§5)                        | Matches current pluggable snapshot API    | ✅ Yes     |

### Strengths

- **Backward compatibility** is treated as a first-class rule (single-document
  files keep working; option-ignoring plugins unchanged) — and this is borne out
  in the implemented code.
- **Clear non-goals** (§7: no globbing in core, no API-surface heuristics, no
  cross-document inheritance) keep the framework's scope honest.
- The `bundle` design (§6) is pragmatic: blind `max(ChangeKind)` over tracked
  `VERSION` files, no compiler dependency, fits the polyglot pattern the project
  already recommends.

### Weaknesses / open questions to tighten before implementing

1. **Defaults-document ambiguity (§2.3):** "the first document with no `plugin`
   key is the defaults." A *single* document with no `plugin` key would then be
   defaults with **zero candidates**. The spec should state the fallback
   (e.g., implicit `plugin` from CLI/`--plugin`, or treat lone doc as a
   candidate). Rule 4 ("single-document = combined defaults + candidate") and
   Rule 1 can conflict for that exact case.
2. **`include` semantics are entirely plugin-defined (§3.1)** yet the doc also
   prescribes "recursive by default" and "do not follow imports." These are
   reasonable defaults but currently unenforceable by the framework, so two
   plugins may diverge. Consider a conformance note or a shared helper.
3. **`bundle` diff vs. the project's own date-patch scheme (§6.5):** comparing
   `YYYYMMDDZZZ` patches numerically still yields "PATCH changed," so it works —
   but the table implies clean semver triples. A sentence clarifying that only
   the *position* (major/minor/patch) that changed matters would remove doubt.
4. **Ordering contract for `bundle` (§6.6):** correctness depends on each
   surface's bump running *before* the bundle reads its `VERSION`. Worth
   elevating from a workflow example to an explicit precondition.

None of these block the proposal; they are refinements for whoever implements
the still-"proposed" sections.

---

## 7. Bottom Line

The plan was executed faithfully and conservatively. Part A is production-grade
and fully validated by a green 219-test suite. Part B is cleanly authored with
exemplary honesty about what could not be machine-verified locally (Docker
daemon / GitHub). The proposal is a solid, accurate design doc whose
"implemented vs proposed" labeling matches the codebase. Recommended follow-ups
are minor (CLI version threading, hermetic builds, a few proposal edge cases).

**Final grade: A− (excellent, trustworthy).**
