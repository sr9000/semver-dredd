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

from snapshot.protocols import SnapshotFormat


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

    @property
    def metadata(self) -> dict[str, Any]:
        """Optional structured metadata for inventory/automation.

        Third-party plugins may override this to describe scope syntax,
        plugin-specific options, external runtime requirements, feature flags,
        or other inventory details. The core treats the contents as optional
        and best-effort.
        """
        return {}

    def have(self, feature: str) -> bool:
        """Best-effort optional feature discovery.

        The default implementation is backward-compatible: plugins that do not
        override it simply report ``False`` for every feature. Plugins may
        instead advertise features through ``metadata["features"]``.
        """
        metadata = self.metadata
        if not isinstance(metadata, dict):
            return False
        features = metadata.get("features", [])
        if isinstance(features, str):
            return features == feature
        if isinstance(features, (list, tuple, set, frozenset)):
            return feature in features
        return False

    def validate_path(self, path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        return True, ""

    @abstractmethod
    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate a YAML snapshot string."""

    # ------------------------------------------------------------------
    # Optional hook for pluggable snapshot format
    # ------------------------------------------------------------------

    @property
    def snapshot_format_class(self) -> type[SnapshotFormat] | None:
        """Return a custom snapshot class, or ``None`` to use the default.

        The returned class must satisfy the :class:`SnapshotFormat` protocol
        (``to_yaml``, ``from_yaml_str``, ``from_file``, ``to_dict``) and the
        :class:`~snapshot.protocols.Comparable` protocol
        (``diff_against``).
        """
        return None
