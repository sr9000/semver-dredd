"""Cross-language snapshot I/O for semver-dredd — backward-compatibility shim.

All concrete implementations now live in the ``semverdredd`` package.
This module re-exports them so existing ``from semverdredd.snapshot_io import …``
statements keep working.
"""

from semverdredd.models import (
    NormalizedSnapshot,
    FunctionSignature,
    TypeDefinition,
    Parameter,
    Field,
)
from semverdredd.registry import load_snapshot

__all__ = [
    "NormalizedSnapshot",
    "FunctionSignature",
    "TypeDefinition",
    "Parameter",
    "Field",
    "load_snapshot",
]
