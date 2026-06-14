# Agent Notes — `snapshot/` Package

This package defines snapshot protocols, default normalized snapshot models, and
predefined reusable API component dataclasses.

## Responsibilities

- `protocols.py` defines the universal contracts:
  - `DiffResult`
  - `SnapshotFormat`
  - `Comparable`
- `models.py` defines `NormalizedSnapshot` and common function/type models.
- `change_kind.py` defines `ChangeKind` (`NONE`, `PATCH`, `MINOR`, `BREAKING`).
- `predefined/` contains reusable immutable component models used by plugins:
  `Variable`, `Argument`, `Function`, `ClassField`, `ClassMethod`.

## Design principles

- The core engine never assumes a specific API model; it only requires
  snapshots to deserialize and implement `diff_against()`.
- `NormalizedSnapshot` is a convenience/default, not a mandatory plugin format.
- Every snapshot format should include a stable UUID string in
  `SNAPSHOT_TYPE_ID` and serialize it as top-level `snapshot_type_id`.
- `DiffResult` is intentionally small. Plugins may add richer internal details,
  but core only depends on `change_kind`, `breaking`, and `added`.

## Style guidelines

- Keep dataclasses immutable where practical.
- Keep serialization YAML-compatible and deterministic.
- Preserve backward compatibility for existing snapshot YAML fields when
  feasible.
- Avoid plugin-specific behavior here unless it is a generic reusable component.

## Scope-related notes

`include` / `exclude` should not be implemented in this package. Filtering is a
plugin concern before snapshots are produced. If adding helpers, keep them
generic (for example, option normalization), not language-specific pattern
matching.

For snapshot schemas, see `docs/schema.md` and `HOWTO.md`.
