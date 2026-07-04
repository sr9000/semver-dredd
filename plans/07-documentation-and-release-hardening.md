# Documentation and release hardening

This plan now tracks only work that may still remain after the major feature
phases shipped.

## Scope of this plan

- keep docs truthful about shipped behavior
- keep examples and smoke paths aligned with the CLI
- close any last release-readiness documentation gaps

## Remaining questions / tasks

### 1. Final CLI surface review

- [ ] Decide whether a top-level `semver-dredd list` alias should exist.
- [ ] Keep `--help` output, README examples, and `USAGE.md` examples aligned.

### 2. Schema and example drift prevention

- [ ] Re-verify `SCHEMA.md` against serialized fixtures whenever snapshot models change.
- [ ] Re-verify `example/semver_showcase.yaml` when config keys or precedence rules change.

### 3. Plugin documentation drift prevention

- [ ] Re-check official plugin READMEs whenever scope semantics or runtime requirements change.
- [ ] Keep the meta-package README explicit about which plugins it actually installs.

### 4. Release gates

- [ ] Ensure user-facing examples are backed by tests, demos, or smoke coverage.
- [ ] Keep the repo handoff-ready: docs should describe only working behavior.
