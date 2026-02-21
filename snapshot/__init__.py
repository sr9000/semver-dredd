"""snapshot — pluggable API snapshot format for semver-dredd.

This package provides the data model, diff engine, UUID-based type
registry, and the protocol definitions that custom snapshot formats
must satisfy.

Quick start
-----------
::

    from snapshot import (
        ChangeKind,
        NormalizedSnapshot,
        SnapshotDiff,
        DiffResult,
        DiffScorer,
        SnapshotFormat,
        default_registry,
        load_snapshot,
    )

See ``snapshot/README.md`` for the full API contract documentation.
"""

# Unified change severity enum
from snapshot.change_kind import ChangeKind

# Backward-compat alias
ChangeType = ChangeKind

# Protocols / ABCs
from snapshot.protocols import DiffResult, DiffScorer, SnapshotFormat

# Concrete data models
from snapshot.models import (
    NORMALIZED_SNAPSHOT_TYPE_ID,
    Field,
    FunctionSignature,
    NormalizedSnapshot,
    Parameter,
    SnapshotDiff,
    TypeDefinition,
)

# Registry
from snapshot.registry import (
    SnapshotRegistry,
    default_registry,
    load_snapshot,
    load_snapshot_yaml,
)

__all__ = [
    # Enum
    "ChangeKind",
    "ChangeType",
    # Protocols
    "DiffResult",
    "DiffScorer",
    "SnapshotFormat",
    # Models
    "NORMALIZED_SNAPSHOT_TYPE_ID",
    "Field",
    "FunctionSignature",
    "NormalizedSnapshot",
    "Parameter",
    "SnapshotDiff",
    "TypeDefinition",
    # Registry
    "SnapshotRegistry",
    "default_registry",
    "load_snapshot",
    "load_snapshot_yaml",
]
