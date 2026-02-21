"""snapshot — backward-compatibility shim.

All canonical implementations now live in the ``semverdredd`` package.
This package re-exports them so existing ``from snapshot import …``
statements keep working.

See ``snapshot/README.md`` for the full API contract documentation.
"""

# Unified change severity enum
from semverdredd.change_kind import ChangeKind

# Protocols / ABCs
from semverdredd.protocols import DiffResult, DiffScorer, SnapshotFormat

# Concrete data models
from semverdredd.models import (
    NORMALIZED_SNAPSHOT_TYPE_ID,
    Field,
    FunctionSignature,
    NormalizedSnapshot,
    Parameter,
    TypeDefinition,
)

# Registry
from semverdredd.registry import (
    SnapshotRegistry,
    default_registry,
    load_snapshot,
    load_snapshot_yaml,
)

__all__ = [
    # Enum
    "ChangeKind",
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
    "TypeDefinition",
    # Registry
    "SnapshotRegistry",
    "default_registry",
    "load_snapshot",
    "load_snapshot_yaml",
]
