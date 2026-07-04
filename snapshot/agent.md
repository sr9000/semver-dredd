# Agent Notes — `snapshot/` (protocols + default models)

Defines snapshot contracts, the default normalized model, and reusable component
dataclasses. Schemas: `SCHEMA.md`, `HOWTO.md`.

## Files

- `protocols.py` — universal contracts: `DiffResult`, `SnapshotFormat`, `Comparable`.
- `models.py` — `NormalizedSnapshot` + common function/type models.
- `change_kind.py` — `ChangeKind` (`NONE`, `PATCH`, `MINOR`, `BREAKING`).
- `predefined/` — reusable immutable models for plugins: `Variable`, `Argument`,
  `Function`, `ClassField`, `ClassMethod`.

## Invariants

- Core never assumes an API model; it only needs snapshots to deserialize and
  implement `diff_against()`.
- `NormalizedSnapshot` is a convenient default, not mandatory for plugins.
- Every snapshot format needs a stable UUID in `SNAPSHOT_TYPE_ID`, serialized as
  top-level `snapshot_type_id`.
- `DiffResult` stays minimal: core only depends on `change_kind`, `breaking`,
  `added`. Plugins may carry richer internal detail.

## Style

- Keep dataclasses immutable where practical.
- Serialization stays YAML-compatible and deterministic.
- Preserve back-compat for existing snapshot YAML fields when feasible.
- No plugin-specific behavior here — only generic reusable components.

## Scope

Do NOT implement `include`/`exclude` here — filtering is a plugin concern before
snapshots are produced. Any helper added must stay generic (e.g. option
normalization), not language-specific pattern matching.
