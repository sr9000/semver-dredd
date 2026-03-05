"""Snapshot protocols — contracts that custom snapshot types must implement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from snapshot import ChangeKind

# ---------------------------------------------------------------------------
# DiffResult — universal return value of any diff operation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffResult:
    """Universal diff result returned by a snapshot's :meth:`diff_against`.

    Plugins may subclass to carry richer information, but the core engine
    only inspects ``change_kind`` and the two description tuples.
    """

    change_kind: ChangeKind
    breaking: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return self.change_kind is not ChangeKind.NONE


# ---------------------------------------------------------------------------
# SnapshotFormat — what every snapshot class must look like
# ---------------------------------------------------------------------------


@runtime_checkable
class SnapshotFormat(Protocol):
    """Protocol that any pluggable snapshot class must satisfy.

    The core engine calls these methods for marshalling / unmarshalling
    and never touches the internal structure of the snapshot.

    Every conforming class **must** also embed a ``SNAPSHOT_TYPE_ID``
    class attribute (a ``str`` UUID) so the registry can identify the
    correct deserializer when loading YAML.
    """

    SNAPSHOT_TYPE_ID: str
    """UUID (as string) that uniquely identifies this snapshot format."""

    @property
    def version(self) -> str:
        """The version string stored in the snapshot."""
        ...

    def to_yaml(self) -> str:
        """Serialize the snapshot to a YAML string."""
        ...

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "SnapshotFormat":
        """Deserialize a snapshot from a YAML string."""
        ...

    @classmethod
    def from_file(cls, path: Path | str) -> "SnapshotFormat":
        """Load a snapshot from a file path."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict (for inspection / further serialization)."""
        ...


# ---------------------------------------------------------------------------
# Comparable — snapshot types that know how to diff themselves
# ---------------------------------------------------------------------------


@runtime_checkable
class Comparable(Protocol):
    """Protocol for snapshot types that can compare themselves against another.

    **All** snapshot types must implement this protocol.  The core engine
    calls ``old_snapshot.diff_against(new_snapshot)`` exclusively; there
    is no fallback scorer interface.

    Implementations may raise :class:`TypeError` when *other* is not the
    same concrete type as *self*.
    """

    def diff_against(self, other: "Comparable") -> DiffResult:
        """Compare *self* against *other* and return a :class:`DiffResult`."""
        ...
