"""Plugin base types for semver-dredd.

This defines the stable interface that all language plugins (including Python)
must implement.

Plugins are discovered via Python entry points under the group
`semver_dredd.plugins`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable


class ChangeKind(Enum):
    """Severity of an API change, used for semver classification.

    Plugins use this to communicate change severity to the core engine.
    """
    NONE = 0
    PATCH = 1
    MINOR = 2
    BREAKING = 3


@dataclass(frozen=True)
class DiffResult:
    """Universal diff result returned by DiffScorer.

    Plugins may subclass to add richer information, but the core engine
    only inspects ``change_kind`` and the two description tuples.
    """
    change_kind: ChangeKind
    breaking: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return self.change_kind is not ChangeKind.NONE


@runtime_checkable
class SnapshotFormat(Protocol):
    """Protocol that any pluggable snapshot class must satisfy.

    The core engine calls these methods for marshalling/unmarshalling
    and never touches the internal structure of the snapshot.
    """

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


class DiffScorer(ABC):
    """Abstract base class for diff/scoring logic.

    Plugins that need custom comparison semantics should subclass this
    and return an instance from ``LanguagePlugin.diff_scorer``.
    """

    @abstractmethod
    def diff(self, old: Any, new: Any) -> DiffResult:
        """Compare *old* and *new* snapshots and return a :class:`DiffResult`.

        The snapshot objects are whatever the plugin's
        ``snapshot_format_class`` produces (or ``NormalizedSnapshot`` by
        default).
        """

    def compare(self, old: Any, new: Any) -> DiffResult:
        """Convenience wrapper — same as :meth:`diff`."""
        return self.diff(old, new)


@dataclass(frozen=True)
class SnapshotResult:
    """Result of snapshot generation."""

    success: bool
    yaml_content: str
    error_message: Optional[str] = None


class LanguagePlugin(ABC):
    """Abstract base class for language plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique language identifier (e.g. 'python', 'go', 'java')."""

    @property
    def display_name(self) -> str:
        return self.name.capitalize()

    @property
    def version(self) -> str:
        return "0.0.0"

    @property
    def description(self) -> str:
        return f"{self.display_name} language support for semver-dredd"

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        return True, ""

    @abstractmethod
    def generate_snapshot(self, path: str, version: str, options: Optional[dict[str, Any]] = None) -> SnapshotResult:
        """Generate a YAML snapshot string."""

    # ------------------------------------------------------------------
    # Optional hooks for pluggable snapshot format & diff scoring
    # ------------------------------------------------------------------

    @property
    def snapshot_format_class(self) -> type[SnapshotFormat] | None:
        """Return a custom snapshot class, or ``None`` to use the default.

        The returned class must satisfy the :class:`SnapshotFormat` protocol
        (``to_yaml``, ``from_yaml_str``, ``from_file``, ``to_dict``).
        """
        return None

    @property
    def diff_scorer(self) -> DiffScorer | None:
        """Return a custom diff scorer, or ``None`` to use the default.

        The scorer receives snapshots produced by :attr:`snapshot_format_class`
        (or ``NormalizedSnapshot`` when that is ``None``).
        """
        return None
