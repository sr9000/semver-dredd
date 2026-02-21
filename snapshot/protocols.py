"""Backward-compatibility shim — canonical home is semverdredd.protocols."""
from semverdredd.protocols import DiffResult, DiffScorer, SnapshotFormat

__all__ = ["DiffResult", "DiffScorer", "SnapshotFormat"]
