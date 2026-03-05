"""Cross-language API diff engine for semver-dredd.

The engine is intentionally structure-agnostic: it knows nothing about
functions, types, or any other language-specific concepts.  All comparison
logic lives on the snapshot types themselves via the
:class:`~snapshot.protocols.Comparable` protocol.

For snapshot types that do not yet implement :class:`~snapshot.protocols.Comparable`
the engine falls back to the plugin-supplied :class:`~snapshot.protocols.DiffScorer`.
"""

from __future__ import annotations

from typing import Any

from snapshot.protocols import Comparable, DiffResult, DiffScorer


def diff_snapshots(old: Any, new: Any) -> DiffResult:
    """Compare two snapshots by delegating to ``old.diff_against(new)``.

    Both *old* and *new* must implement :class:`~snapshot.protocols.Comparable`.
    """
    if not isinstance(old, Comparable):
        raise TypeError(
            f"{type(old).__name__} does not implement Comparable "
            "(add a diff_against method or provide a DiffScorer via the plugin)"
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
# Default diff scorer
# ---------------------------------------------------------------------------


class DefaultDiffScorer(DiffScorer):
    """Default diff scorer: delegates to the snapshot's own ``diff_against``.

    Requires the snapshot to implement :class:`~snapshot.protocols.Comparable`.
    """

    def diff(self, old: Any, new: Any) -> DiffResult:
        return diff_snapshots(old, new)
