"""snapshot — backward-compatibility shim.

All canonical implementations live in the ``semverdredd`` package.
This package re-exports them so existing ``from snapshot import …``
statements keep working.

See ``snapshot/README.md`` for the full API contract documentation.
"""

# Registry
from semverdredd.registry import (
    SnapshotRegistry,
    default_registry,
    load_snapshot,
    load_snapshot_yaml,
)

# Unified change severity enum
from snapshot.change_kind import ChangeKind

# Concrete data models
from snapshot.models import (
    NORMALIZED_SNAPSHOT_TYPE_ID,
    Field,
    FunctionSignature,
    NormalizedSnapshot,
    Parameter,
    TypeDefinition,
)

# Protocols / ABCs
from snapshot.protocols import Comparable, DiffResult, SnapshotFormat

__all__ = [
    # Enum
    "ChangeKind",
    # Protocols
    "Comparable",
    "DiffResult",
    "SnapshotFormat",
    # Models
    "NORMALIZED_SNAPSHOT_TYPE_ID",
    "Field",
    "FunctionSignature",
    "NormalizedSnapshot",
    "Parameter",
    "TypeDefinition",
    # Registry
    "SnapshotRegistry",
    "default_registry",
    "load_snapshot",
    "load_snapshot_yaml",
]
