"""Cross-language API diff engine for semver-dredd.

This module compares two NormalizedSnapshots and produces a detailed diff
that explains what changed and whether changes are breaking or additive.

Works with snapshots from any supported language (Python, Go, Java).
Comparison logic lives on the snapshot element types themselves via the
:class:`~snapshot.protocols.Comparable` protocol — this module only
orchestrates the top-level collections.
"""

from __future__ import annotations

from snapshot import NormalizedSnapshot
from snapshot.change_kind import ChangeKind
from snapshot.protocols import DiffResult, DiffScorer


def diff_snapshots(old: NormalizedSnapshot, new: NormalizedSnapshot) -> DiffResult:
    """Compare two snapshots and return a DiffResult.

    Top-level added/removed items are detected here; per-element comparison
    is delegated to each element's :meth:`~snapshot.protocols.Comparable.diff_against`
    method so the logic stays close to the type that owns it.
    """
    breaking: list[str] = []
    added: list[str] = []

    # --- Functions ---
    old_fns, new_fns = old.functions, new.functions

    for name in sorted(set(old_fns) - set(new_fns)):
        breaking.append(f"function removed: {name}")

    for name in sorted(set(new_fns) - set(old_fns)):
        added.append(f"function added: {name}")

    for name in sorted(set(old_fns) & set(new_fns)):
        result = old_fns[name].diff_against(new_fns[name])
        breaking.extend(f"function {name}: {b}" for b in result.breaking)
        added.extend(f"function {name}: {a}" for a in result.added)

    # --- Types ---
    old_types, new_types = old.types, new.types

    for name in sorted(set(old_types) - set(new_types)):
        breaking.append(f"type removed: {name}")

    for name in sorted(set(new_types) - set(old_types)):
        added.append(f"type added: {name}")

    for name in sorted(set(old_types) & set(new_types)):
        result = old_types[name].diff_against(new_types[name])
        breaking.extend(f"type {name}: {b}" for b in result.breaking)
        added.extend(f"type {name}: {a}" for a in result.added)

    if breaking:
        change = ChangeKind.BREAKING
    elif added:
        change = ChangeKind.MINOR
    else:
        change = ChangeKind.NONE

    return DiffResult(
        change_kind=change,
        breaking=tuple(breaking),
        added=tuple(added),
    )


def compare_snapshots(
    old: NormalizedSnapshot,
    new: NormalizedSnapshot,
) -> DiffResult:
    """Compare two snapshots and return a DiffResult."""
    return diff_snapshots(old, new)


def compare_snapshot_files(
    old_path: str,
    new_path: str,
) -> DiffResult:
    """Compare two snapshot files."""
    from semverdredd import load_snapshot

    old = load_snapshot(old_path)
    new = load_snapshot(new_path)
    return compare_snapshots(old, new)


# ---------------------------------------------------------------------------
# Default diff scorer
# ---------------------------------------------------------------------------


class DefaultDiffScorer(DiffScorer):
    """Default diff scorer wrapping ``diff_snapshots``."""

    def diff(self, old: NormalizedSnapshot, new: NormalizedSnapshot) -> DiffResult:
        return diff_snapshots(old, new)
