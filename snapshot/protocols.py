"""Snapshot protocols — contracts that custom snapshot types must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from snapshot import ChangeKind

# ---------------------------------------------------------------------------
# DiffResult — universal return value of any diff scorer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffResult:
    """Universal diff result returned by a :class:`DiffScorer`.

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
# DiffScorer — pluggable comparison logic
# ---------------------------------------------------------------------------


class DiffScorer(ABC):
    """Abstract base class for diff / scoring logic.

    Plugins that need custom comparison semantics should subclass this and
    return an instance from ``LanguagePlugin.diff_scorer``.
    """

    @abstractmethod
    def diff(self, old: Any, new: Any) -> DiffResult:
        """Compare *old* and *new* snapshots and return a :class:`DiffResult`.

        The snapshot objects are whatever the plugin's
        ``snapshot_format_class`` produces (or ``NormalizedSnapshot`` by
        default).
        """

    def compare(self, old: Any, new: Any) -> DiffResult:
        """Convenience alias for :meth:`diff`."""
        return self.diff(old, new)
