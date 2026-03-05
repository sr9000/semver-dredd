"""Cross-language API diff engine for semver-dredd.

The engine is intentionally structure-agnostic: it knows nothing about
functions, types, or any other language-specific concepts.  All comparison
logic lives on the snapshot types themselves via the
:class:`~snapshot.protocols.Comparable` protocol.

Every snapshot type **must** implement :class:`~snapshot.protocols.Comparable`.
"""

from __future__ import annotations

from typing import Any

from snapshot.protocols import Comparable, DiffResult


def diff_snapshots(old: Any, new: Any) -> DiffResult:
    """Compare two snapshots by delegating to ``old.diff_against(new)``.

    Both *old* and *new* must implement :class:`~snapshot.protocols.Comparable`.
    """
    if not isinstance(old, Comparable):
        raise TypeError(
            f"{type(old).__name__} does not implement Comparable "
            "(add a diff_against method)"
        )
    return old.diff_against(new)


def compare_snapshots(old: Any, new: Any) -> DiffResult:
    """Convenience alias for :func:`diff_snapshots`."""
    return diff_snapshots(old, new)


def compare_snapshot_files(old_path: str, new_path: str) -> DiffResult:
    """Compare two snapshot files."""
    from semverdredd import load_snapshot

    old = load_snapshot(old_path)
    new = load_snapshot(new_path)
    return diff_snapshots(old, new)


# ---------------------------------------------------------------------------
# DefaultDiffScorer — convenience wrapper around diff_snapshots
# ---------------------------------------------------------------------------


class DefaultDiffScorer:
    """Convenience wrapper that calls ``old.diff_against(new)``.

    Kept for backward compatibility with code that holds a scorer reference.
    Snapshot types must implement :class:`~snapshot.protocols.Comparable`.
    """

    def diff(self, old: Any, new: Any) -> DiffResult:
        return diff_snapshots(old, new)

    def compare(self, old: Any, new: Any) -> DiffResult:
        """Convenience alias for :meth:`diff`."""
        return self.diff(old, new)
