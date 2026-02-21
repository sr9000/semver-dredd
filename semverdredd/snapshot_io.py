"""Cross-language snapshot I/O for semver-dredd — backward-compatibility shim.

All concrete implementations now live in the ``snapshot`` package.
This module re-exports them so existing ``from semverdredd.snapshot_io import …``
statements keep working.
"""

from snapshot.models import (
    NormalizedSnapshot,
    FunctionSignature,
    TypeDefinition,
    Parameter,
    Field,
    SnapshotDiff,
)
from snapshot.registry import load_snapshot

__all__ = [
    "NormalizedSnapshot",
    "FunctionSignature",
    "TypeDefinition",
    "Parameter",
    "Field",
    "SnapshotDiff",
    "load_snapshot",
]
