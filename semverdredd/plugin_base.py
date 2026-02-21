"""Plugin base types for semver-dredd.

This defines the stable interface that all language plugins (including Python)
must implement.

Plugins are discovered via Python entry points under the group
`semver_dredd.plugins`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Re-export from the snapshot package for backward compatibility
from snapshot.change_kind import ChangeKind
from snapshot.protocols import DiffResult, DiffScorer, SnapshotFormat

# Backward-compat alias
ChangeType = ChangeKind


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
