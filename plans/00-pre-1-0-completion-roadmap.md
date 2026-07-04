# Remaining pre-1.0 roadmap

Most phase plans in this directory have already shipped and were removed to keep
`plans/` focused on unfinished work only.

## Remaining goal

Finish the last release-hardening/documentation cleanup tasks without restating
already-implemented features as future work.

## Remaining items

- [x] Keep top-level docs (`README.md`, `HOWTO.md`, `USAGE.md`, `SCHEMA.md`) in
  sync with actual CLI/config/plugin behavior.
- [x] Keep plugin READMEs accurate about install steps, scope semantics, and CLI
  examples.
- [x] Decide explicitly whether to add a top-level `semver-dredd list` alias or
  leave plugin inspection under `semver-dredd plugin ...` only.
- [x] Keep smoke/tests/docs aligned whenever user-facing workflow examples change.

## Current status

Implemented already:

- config-driven command resolution and precedence
- multi-document config fallback
- shipped verbosity/logging surface
- official plugin `include` / `exclude` behavior
- plugin metadata and machine-readable inventory
- built-in `bundle` plugin

The remaining documentation hardening work tracked in
[`07-documentation-and-release-hardening.md`](07-documentation-and-release-hardening.md)
has now been reconciled with the shipped CLI/docs/examples. Keep future doc
changes tied to their corresponding feature/fix work so this roadmap does not
drift back out of sync.
