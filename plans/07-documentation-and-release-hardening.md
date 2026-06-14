# Documentation and Release Hardening

## Motivation

The final pre-1.0 work is to make shipped behavior executable and documented,
while keeping planned behavior clearly marked until implemented. This phase
prevents docs, examples, and tests from drifting after the core feature phases.

## Touched Files

- `README.md`
- `HOWTO.md`
- `docs/schema.md`
- plugin `README.md` files
- `example/`
- `tests/`
- `scripts/smoke.sh`
- `docker/` files if smoke scenarios need updates; read `docker/agent.md` first
- `VERSION` only when preparing an actual release, not during planning

## Commit-Sized Steps

### 1. Synchronize user-facing workflow docs

- Update README with the shipped config-driven first-run workflow.
- Document explicit override behavior and warnings.
- Document `--config` modes and precedence.
- Keep any future-only behavior in a clearly labeled planned section.

Definition of Done:

- Every README command example is backed by a CLI test, smoke test, or demo.

### 2. Synchronize plugin author docs

- Update HOWTO with:
  - minimal plugin contract;
  - optional metadata/feature discovery;
  - scope array contract;
  - plugin-specific include/exclude ownership;
  - snapshot provenance expectations.

Definition of Done:

- HOWTO examples match actual plugin APIs and tests.

### 3. Finalize schema documentation

- Document the snapshot envelope including `snapshot_type_id` and generator
  provenance.
- Document compatibility behavior for older snapshots without provenance.
- Add bundle snapshot examples.

Definition of Done:

- Schema docs match serialized test fixtures.

### 4. Consolidate include/exclude scope documentation

The standalone `INCLUDE-EXCLUDE-PROPOSAL.md` has been removed; its resolved
decisions now live in `README.md`, `HOWTO.md`, and the plugin READMEs. This step
keeps those authoritative homes consistent.

- Ensure the scope contract (arrays of plugin-specific items; recursive
  `include`; `*` nested `exclude`; no globs in official plugins; empty-include
  semantics) is documented once in README/HOWTO and referenced elsewhere.
- Mark resolved decisions as implemented once shipped; keep future ideas in a
  clearly labeled planned section.
- Link to official plugin READMEs for exact per-plugin syntax.

Definition of Done:

- README, HOWTO, and plugin READMEs agree on scope semantics with no
  contradictions and no references to the removed proposal file.

### 5. Expand end-to-end and smoke coverage

- Add or update demos for config-driven Python workflow.
- Add smoke paths for bundle and plugin metadata where practical.
- Keep Go/Java smoke scenarios isolated behind required toolchain/plugin setup.

Definition of Done:

- `poetry run pytest -v` passes.
- Relevant smoke scripts pass in local/Docker environments.
- The repository can be handed to a user with docs that describe only working
  behavior as shipped.

### 6. Pre-1.0 release readiness review

- Audit all top-level config keys for stability.
- Audit warning/error messages for clarity and test coverage.
- Audit plugin READMEs for exact scope semantics.
- Audit old snapshot fixtures for backward compatibility.
- Decide whether to add the optional top-level `semver-dredd list` alias or
  defer it explicitly.

Definition of Done:

- A release checklist issue or final plan update identifies no remaining
  product blockers for the pre-1.0 complete scope.

## Milestones

Implementation-dependent decisions; tick as resolved and mirror in `00`:

- [ ] Final decision on the `semver-dredd list` alias (carried from `05`).
- [ ] Which previously-planned sections flip from "planned" to "shipped" in
  README/HOWTO and plugin READMEs.
- [ ] Schema docs verified against serialized fixtures (generator block + bundle
  examples).
- [ ] Smoke coverage decided for bundle and plugin metadata vs deferred behind
  toolchain setup.

