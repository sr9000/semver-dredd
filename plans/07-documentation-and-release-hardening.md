# Documentation and release hardening

This plan now tracks only work that may still remain after the major feature
phases shipped.

## Scope of this plan

- keep docs truthful about shipped behavior
- keep examples and smoke paths aligned with the CLI
- close any last release-readiness documentation gaps

## Remaining questions / tasks

### 1. Final CLI surface review

- [x] Keep plugin inspection under `semver-dredd plugin ...`; do **not** add a
  top-level `semver-dredd list` alias.
- [x] Keep `--help` output, README examples, and `USAGE.md` examples aligned.

### 2. Schema and example drift prevention

- [x] Re-verify `SCHEMA.md` against serialized fixtures whenever snapshot models change.
- [x] Re-verify `example/semver_showcase.yaml` when config keys or precedence rules change.

### 3. Plugin documentation drift prevention

- [x] Re-check official plugin READMEs whenever scope semantics or runtime requirements change.
- [x] Keep the meta-package README explicit about which plugins it actually installs.

### 4. Release gates

- [x] Ensure user-facing examples are backed by tests, demos, or smoke coverage.
- [x] Keep the repo handoff-ready: docs should describe only working behavior.

## Status after this pass

- CLI/help/docs now consistently document `semver-dredd plugin list` as the
  supported plugin inventory command.
- `SCHEMA.md` and `example/semver_showcase.yaml` explicitly call out CLI-only
  precedence, scope append/override behavior, and the documentary status of
  `output.severity_by_change`.
- Official plugin READMEs and the meta-package README were rechecked against the
  shipped workflow and runtime expectations.
