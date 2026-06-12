# Review Report

## 1. Review of `plans/improve-and-smoke-tests.md`

**File:** [`plans/improve-and-smoke-tests.md`](plans/improve-and-smoke-tests.md:1)

### Overall Grade: **A‑**

### Strengths

* **Comprehensive Scope** – Covers both tool improvements (Part A) and Docker‑Compose smoke tests (Part B). Each commit
  is paired with a *Definition of Done* checklist.
* **Atomic Commits** – The commit‑by‑commit roadmap makes CI validation, rollback, and code review straightforward.
* **Test‑Driven Acceptance** – All DoD items are backed by unit tests in the `tests/` directory. For example, the
  malformed‑YAML warning is exercised in [`tests/test_config.py:117‑124`](tests/test_config.py:117) which asserts that
  `_load_yaml_config` prints a warning to `stderr`.
* **Configuration Parsing Verified** – The priority chain (YAML<.env<env‑vars) is validated by `TestLoadConfig` in [
  `tests/test_config.py:157‑247`](tests/test_config.py:157). The test suite (`poetry run pytest -q`) reports **219
  passed** (`219 passed in 0.91s`).
* **Documentation Updates** – README now references the proposal (`README.md:21‑26`) and includes a Docker‑Compose usage
  section (`README.md:456‑463`).

### Weaknesses / Open Items

1. **Unverified Docker Builds** – Commits 8 and 11 rely on a Docker daemon. Local verification is pending; CI should
   enforce the build step.
2. **Partial CI Coverage** – The smoke workflow (`.github/workflows/smoke.yml`) builds images and runs
   `scripts/smoke.sh --no-build`, but the “green run on main” and “red run on broken assertion” paths are still marked
   as pending verification after the first push.
3. **Missing Status Banner** – Commit 7 mentions adding a status banner to `INCLUDE-EXCLUDE-PROPOSAL.md`; the file
   currently only has a status table.

### Validation Evidence (Deep Research)

| Aspect                        | Location in Repo                                  | Evidence                                                                                                         |
|-------------------------------|---------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| **YAML parsing warnings**     | `cli/config.py:144‑166`                           | Emits `[WARN]` on malformed config; test `TestLoadConfig.test_load_yaml_config_malformed_warns` asserts warning. 
| **Configuration priority**    | `cli/config.py:221‑239`                           | Merges layers; tests `TestLoadConfig.test_load_config_priority_chain` confirm precedence.                        
| **Scope forwarding**          | `cli/config.py:73‑86` (`Config.snapshot_options`) | Only includes keys when set; tests `TestScopeOptions.test_snapshot_options_only_set_keys` verify.                
| **Docker Compose definition** | `docker-compose.smoke.yml` (lines 9‑44)           | Services for python, go, java, unit with build contexts.                                                         
| **Smoke script aggregation**  | `scripts/smoke.sh` (lines 1‑76)                   | Aggregates results, exits non‑zero on any failure.                                                               
| **CI workflow**               | `.github/workflows/smoke.yml` (lines 27‑34)       | Builds images with caching, runs smoke script.                                                                   
| **Test suite health**         | `poetry run pytest -q` output                     | 219 passed, covering config, plugin manager, versioning, and smoke assertions.                                   

### Recommendations

1. **Enforce Docker builds in CI** – Add a dedicated job that runs `docker compose -f docker-compose.smoke.yml build`
   and fails on any error. This removes reliance on a local Docker daemon.
2. **Validate CI failure path** – After the first push, intentionally break an assertion in
   `tests/smoke/assert_demo.sh` (e.g., modify expected bump) and confirm the workflow fails (`red run`). Document the
   observed failure in the report.
3. **Add explicit status banner** – Insert a markdown banner at the top of `INCLUDE-EXCLUDE-PROPOSAL.md` mirroring the
   status table for quick visibility.
4. **Tag releases** – Create Git tags after merging Part A and Part B to provide a clear release history.

---

## 2. Review of `INCLUDE-EXCLUDE-PROPOSAL.md`

**File:** [`INCLUDE-EXCLUDE-PROPOSAL.md`](INCLUDE-EXCLUDE-PROPOSAL.md:1)

### Overall Grade: **B+**

### Strengths

* **Well‑Structured Proposal** – Sections (Philosophy, Architecture, Scope, Advanced Config, etc.) make the document
  easy to navigate.
* **Status Table** – Provides a clear overview of implemented vs. proposed features.
* **Concrete YAML Examples** – Shows multi‑document config, `include`/`exclude` lists, and `plugin_options` snippets.
* **Cross‑Reference in README** – The README points to this proposal for the feature status (`README.md:21‑26`).

### Weaknesses / Gaps

1. **Implementation Gaps** – Features such as the multi‑document priority chain, plugin‑side handling of `include`/
   `exclude`, and the aggregate `bundle` plugin remain *🚧 Proposed* with no concrete implementation plan.
2. **Testing Guidance Missing** – No explicit test matrix or CI checks are described for the new configuration features.
3. **Traceability** – No links to issue tracker or PR numbers, making progress tracking harder.

### Validation Evidence

* **Implemented Features Confirmed** – Tests in `TestScopeOptions` (`tests/test_config.py:252‑306`) verify that
  `include`, `exclude`, and `plugin_options` are parsed and forwarded, matching the “✅ Implemented” rows.
* **Unimplemented Features** – No tests or code exist for the multi‑document priority chain or the `bundle` plugin,
  confirming their *🚧* status.
* **Documentation Consistency** – The README’s feature status section (`README.md:19‑26`) correctly references this
  proposal.

### Recommendations

1. **Add a “Next Steps” Section** – List upcoming commits or milestones for each proposed feature, linking to relevant
   test suites.
2. **Provide a Test Matrix** – Create a table mapping each new feature to existing or new tests (e.g., extend
   `TestLoadConfig` for multi‑document loading).
3. **Link to Issue Tracker** – Reference GitHub issues/PRs for each feature to improve traceability.
4. **Add Status Banner** – Place a concise banner at the top of the file summarizing the overall implementation status.

---

## 3. Summary & Validation Checklist

| Aspect                                  | Status                        | Evidence                                                                                                      |
|-----------------------------------------|-------------------------------|---------------------------------------------------------------------------------------------------------------|
| **Tool Improvements (Part A)**          | Implemented                   | All DoD items marked `[x]`; tests pass (`219 passed`).                                                        |
| **Docker‑Compose Smoke Tests (Part B)** | Mostly Implemented            | Dockerfiles present, `docker-compose.smoke.yml` defined, CI builds images. Pending local Docker verification. |
| **Configuration Parsing**               | Implemented                   | `_load_yaml_config` warnings (`cli/config.py:144‑166`), tests (`tests/test_config.py:117‑124`).               |
| **Include/Exclude & Plugin Options**    | Implemented (core forwarding) | `Config.snapshot_options()` (`cli/config.py:73‑86`), tests (`tests/test_config.py:252‑306`).                  |
| **Multi‑Document Config**               | Proposed                      | No implementation; status table shows 🚧.                                                                     |
| **Bundle Plugin**                       | Proposed                      | No code; status table shows 🚧.                                                                               |

**Final Assessment** – The project exhibits strong engineering rigor, with a comprehensive test suite and CI
integration. Completing the pending Docker verification and fleshing out the proposed configuration extensions will
elevate the grades to solid **A** marks.
