"""Backward-compatibility shim — canonical home is semverdredd.registry."""
from semverdredd.registry import (
    SnapshotRegistry,
    default_registry,
    load_snapshot,
    load_snapshot_yaml,
)

__all__ = [
    "SnapshotRegistry",
    "default_registry",
    "load_snapshot",
    "load_snapshot_yaml",
]
