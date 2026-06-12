# ANSWER KEY — Task 2 (legacy/audit) — Whole-Repo Truth Audit & Repair

> **OPERATOR-ONLY.** This file lives on `master` and is deleted from the local
> checkout before any candidate run. It must never appear on `legacy/audit`
> or any `legacy/audit-<model>` branch.

Baseline: `legacy/audit` — single squashed commit `legacy: import` off the root
commit of `master`, full current master tree + `reports/TASK.md` + the 15
seeded discrepancies below. `poetry run pytest tests/ -q` reports **219 passed**
with all seeds in place (verified at seeding time).

Menu deviations from `benchmarks/task-2-hard-repo-audit.md` (the real repo has
no HOWTO exit-code table or version walkthrough; items were adapted, see the
updated benchmark doc):

- Item 6 moved from "HOWTO exit-code table" to README's Common CLI Options comment.
- Item 11's doc-side claim was planted as a new HOWTO §9 "CLI gating" bullet (12),
  and uses **12** while README's Exit Codes table and `cli/utils.py` keep 10.
- Item 13 weakened to a parameter-**type** drift (a true breaking removal in the
  fixture is pinned by `tests/test_cross_language.py`).
- Item 14 planted as a new HOWTO §9 "Trying it end-to-end" walkthrough.
- Item 5 planted in the Go section of `docs/schema.md` (`return_type`).

## Tier L — Local (weight ×1)

| # | Wrong side (fix here) | Truth anchor(s) | Contradiction | Intended repair |
|---|---|---|---|---|
| L1 | `docker/README.md` (images table) | `docker/Dockerfile.java:2` (`eclipse-temurin:21-jdk-jammy`); also `plans/improve-and-smoke-tests.md` base-images note | README table documents the Java base image as `eclipse-temurin:17-jdk-jammy` | Change table back to `21-jdk-jammy` |
| L2 | `plugins/go-1.20-dredd/README.md` (Requirements) | `docker/Dockerfile.go:23-25` (`go mod download` pre-fetch), `docker/README.md` design note "needs no network access" | README claims "**Network access at runtime** — parser downloads its Go module dependencies on every invocation" | Delete the network-access requirement bullet |
| L3 | `semverdredd/version.py` (`Version.increment` docstring) | Same file, lines 140-141: `MINOR` + integer scheme → `patch=0`; README Patch Scheme table | Docstring claims integer scheme "preserves the current patch number on minor bumps, reset only on major" | Restore "reset to 0 on major/minor" wording |
| L4 | `README.md` (Smoke Tests section) | `scripts/smoke.sh` flag parser (`--no-build`) | README documents `bash scripts/smoke.sh --skip-build`; no such flag exists (script treats it as a service name and fails) | Change to `--no-build` (or drop the lines) |
| L5 | `docs/schema.md` (Go Plugin snippet) | `snapshot/predefined/models.py` (`result_type`), every other snippet in the same file, real plugin output | Go example uses `return_type:` for `NewPoint` and `Distance` | Rename both back to `result_type:` |

## Tier C — Cross-file (weight ×3)

| # | Wrong side (fix here) | Truth anchor(s) | Contradiction | Intended repair |
|---|---|---|---|---|
| C6 | `README.md` Common CLI Options comment | `cli/utils.py:16` (`EXIT_BREAKING_CHANGES_DETECTED = 10`); README Exit Codes table (10) | `--disallow-breaking  # Fail on BREAKING changes (exit 2)` | Restore `(exit 10)` |
| C7 | `README.md` Configuration priority list | `cli/config.py` module docstring + merge order (env vars override `.env` override yaml); `tests/test_config.py::TestLoadConfig` | README lists env vars as LOWEST priority (yaml above them) | Restore order: `.semver.yaml` < `.env` < env vars < CLI |
| C8 | `INCLUDE-EXCLUDE-PROPOSAL.md` status table | `cli/config.py::_load_yaml_config` uses single-document `yaml.safe_load`; README Feature Status | "Multi-document priority chain — ✅ Implemented (documents walked top-to-bottom)" | Restore "🚧 Proposed — `.semver.yaml` is still single-document" |
| C9 | `snapshot/README.md` ChangeKind enum snippet | `snapshot/change_kind.py` (`PATCH = 1`, `MINOR = 2`) | README shows `MINOR = 1`, `PATCH = 2` (values swapped) | Restore PATCH=1 / MINOR=2 |
| C10 | `plans/improve-and-smoke-tests.md` Commit 3 DoD | `cli/commands/compare.py:44,54` still hardcodes `"0.0.0"` for both snapshots | New ticked DoD: "[x] The CLI `compare` command threads the real `--current` version into both generated snapshots (no more hardcoded \"0.0.0\")" | Untick / remove the claim (the CLI side was never done; Commit 3 covered only the programmatic API) |

## Tier G — Global (weight ×6) — long-context discriminators

| # | Wrong side(s) (fix here) | Truth anchor(s) | Contradiction | Intended repair |
|---|---|---|---|---|
| G11 | `tests/smoke/assert_demo.sh:70-71` (expects exit **12**) AND `HOWTO.md` §9 bullet 4 ("exits with code `12`") | `cli/utils.py:16` (=10), README Exit Codes table (=10), README `--disallow-breaking` comment (=10) | Two sources agree on the wrong value 12; only code + README are authoritative | Change both 12s back to 10. G-credit requires naming `cli/utils.py` as authoritative AND fixing at least one wrong file; full credit = both |
| G12 | `plugins/python-3.10-dredd/pyproject.toml` entry point key `python3 = "semver_dredd_python:PythonPlugin"` | HOWTO §7 rule "entry point name must match `LanguagePlugin.name`"; `PythonPlugin.name == "python"`; `semverdredd/plugin_manager.py::_BUILTIN_FALLBACK_SPECS` ("python"); `docker/Dockerfile.python` grep check | Entry point renamed to `python3` while the whole chain expects `python` | Rename key back to `python` |
| G13 | `tests/fixtures/go/v2_minor.yaml` (Volume param `d: type: int`) | `example/go/gogeometry2/geom.go` (`Volume(width, height, depth float64)`); fixture's own w/h params (float64); `tests/test_cross_language.py` treats v2 as the additive mirror | Fixture encodes a signature drift (`int`) vs the Go source it mirrors | Restore `type: float64` |
| G14 | `HOWTO.md` §9 "Trying it end-to-end" walkthrough | `semverdredd/version.py` (integer scheme: minor bump → patch `0`); README Patch Scheme table; `cli/config.py` patch_scheme plumbing | Walkthrough's `.semver.yaml` sets `patch_scheme: integer` but shows `bump --current 1.2.3 --change minor` → `1.3.20260610001` (a date-scheme patch); truth is `1.3.0` | Fix the shown output to `1.3.0` (or change the config snippet to `date`) — wrong side is the walkthrough output |
| G15 | `example/demo_java.sh` Step 2 echoed command (`--options timeout_seconds=30`) AND `plugins/java-1.8-dredd/README.md` ("Parser options can be passed inline with the `--options` flag") | `cli/__init__.py` snapshot/compare parsers define no `--options` flag; real mechanism is config-driven `plugin_options` in `.semver.yaml` (README config section, `cli/config.py::snapshot_options`) | Both files document a nonexistent CLI flag | Remove `--options ...` from the demo echo and the README paragraph (optionally pointing at `plugin_options`) |

## Genuine pre-existing (unseeded) discrepancies — NOT false positives

Score as tier C if a model finds and proves these (per §5.4 of the benchmark doc):

- `README.md` `.env` example + env-var table list `SEMVER_DREDD_LANG`, but
  `cli/config.py::ENV_VAR_MAPPING` only knows `SEMVER_DREDD_PLUGIN` — the
  documented variable is silently ignored.
- `tests/fixtures/go/v2_minor.yaml` `Translate` takes `(dx, dy)` while
  `example/go/gogeometry2/geom.go` `Translate` takes `(dx, dy, dz)` (pre-existing
  fixture/source drift adjacent to G13).
- `HOWTO.md` Reference table says the Go plugin uses the "`go doc` CLI tool";
  the plugin actually ships a `go/ast`-based parser binary (`go run .`), per
  `plugins/go-1.20-dredd/README.md`.

## Grading notes

- Scoring: found + correct side + fixed = full weight (L 1, C 3, G 6);
  found+fixed with wrong-side verdict = half; found-not-fixed = half.
  Penalties: false positive −2, suite broken −6, no report −5. Max = **50**.
- G-tier credit additionally requires the report to name the authoritative file
  and at least one wrong file.
- After applying each stash: `poetry run pytest tests/ -q` must still pass
  (219; G13's correct repair keeps the suite green).
- Watch wrong-side picks on C8/C10 (a model might "implement" the claim or
  edit code instead of the docs) and on G11 (changing `cli/utils.py` to 12
  is a wrong-side fix → half weight at most, and breaks tests → −6).
