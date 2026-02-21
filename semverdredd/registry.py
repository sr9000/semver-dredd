"""UUID-based snapshot type registry.

Every snapshot format is identified by a **UUID string** stored in its
``SNAPSHOT_TYPE_ID`` class attribute and serialized as the
``snapshot_type_id`` top-level YAML field.

When loading YAML that contains a ``snapshot_type_id``, the registry is
consulted to find the correct class for deserialization.  If the field is
absent the built-in :class:`~semverdredd.models.NormalizedSnapshot` is used
as a fallback (backward compatibility with schema v2 files).

Typical usage::

    from semverdredd.registry import default_registry, load_snapshot

    # Register at startup (plugins do this automatically)
    default_registry.register(MyCustomSnapshot)

    # Load — the registry picks the right class
    snap = load_snapshot("baked.yaml")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class SnapshotRegistry:
    """Maps UUID strings → snapshot classes that can deserialize YAML."""

    def __init__(self) -> None:
        self._types: dict[str, type] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, cls: type, *, force: bool = False) -> None:
        """Register a snapshot format class.

        The class **must** have a ``SNAPSHOT_TYPE_ID`` class attribute
        (a ``str`` UUID).

        Raises:
            ValueError: if the UUID is already registered (unless *force*).
            TypeError:  if the class has no ``SNAPSHOT_TYPE_ID``.
        """
        uid = getattr(cls, "SNAPSHOT_TYPE_ID", None)
        if uid is None:
            raise TypeError(
                f"{cls.__qualname__} does not have a SNAPSHOT_TYPE_ID attribute"
            )
        uid = str(uid)
        if uid in self._types and not force:
            existing = self._types[uid]
            if existing is not cls:
                raise ValueError(
                    f"UUID {uid!r} is already registered to "
                    f"{existing.__qualname__}; pass force=True to override"
                )
        self._types[uid] = cls
        logger.debug("Registered snapshot type %s → %s", uid, cls.__qualname__)

    def unregister(self, uid: str) -> bool:
        """Remove a snapshot type by UUID.  Returns True if it was present."""
        return self._types.pop(str(uid), None) is not None

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, uid: str) -> type | None:
        """Return the snapshot class for *uid*, or ``None``."""
        return self._types.get(str(uid))

    def __contains__(self, uid: str) -> bool:
        return str(uid) in self._types

    def registered_ids(self) -> list[str]:
        """Return all registered UUIDs."""
        return list(self._types.keys())

    # ------------------------------------------------------------------
    # Deserialization helpers
    # ------------------------------------------------------------------

    def load_yaml_str(self, yaml_str: str) -> Any:
        """Deserialize YAML to the appropriate snapshot object.

        1. Parse the YAML to extract ``snapshot_type_id``.
        2. Look up the class in the registry.
        3. Delegate to ``cls.from_yaml_str(yaml_str)``.

        If ``snapshot_type_id`` is missing, falls back to
        :class:`~semverdredd.models.NormalizedSnapshot`.
        """
        data = yaml.safe_load(yaml_str)
        uid = data.get("snapshot_type_id") if isinstance(data, dict) else None
        cls = self._resolve(uid)
        return cls.from_yaml_str(yaml_str)

    def load_file(self, path: Path | str) -> Any:
        """Load a snapshot from *path* using the registry."""
        text = Path(path).read_text()
        return self.load_yaml_str(text)

    def _resolve(self, uid: str | None) -> type:
        """Resolve a UUID to a class, falling back to NormalizedSnapshot."""
        from snapshot import NormalizedSnapshot

        if uid is None:
            return NormalizedSnapshot

        cls = self.get(uid)
        if cls is None:
            logger.warning(
                "Unknown snapshot_type_id %r — falling back to NormalizedSnapshot",
                uid,
            )
            return NormalizedSnapshot
        return cls


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

default_registry = SnapshotRegistry()


def _ensure_builtins_registered() -> None:
    """Register the built-in NormalizedSnapshot (idempotent)."""
    from snapshot import NormalizedSnapshot
    from snapshot import NORMALIZED_SNAPSHOT_TYPE_ID

    if NORMALIZED_SNAPSHOT_TYPE_ID not in default_registry:
        default_registry.register(NormalizedSnapshot)


def load_snapshot(path: Path | str) -> Any:
    """Load and deserialize a snapshot file using the default registry.

    This is the primary entry point for loading snapshot YAML files.
    """
    _ensure_builtins_registered()
    return default_registry.load_file(path)


def load_snapshot_yaml(yaml_str: str) -> Any:
    """Deserialize a snapshot YAML string using the default registry."""
    _ensure_builtins_registered()
    return default_registry.load_yaml_str(yaml_str)
