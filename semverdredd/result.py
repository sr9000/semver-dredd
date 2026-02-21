"""Structured result types for semver-dredd.

This module is intentionally pure-data (no logging/printing) so it can be used
from CI systems and other tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from semverdredd.version import Version

if TYPE_CHECKING:  # pragma: no cover
    from snapshot.change_kind import ChangeKind
    from snapshot.protocols import DiffResult


@dataclass(frozen=True, slots=True)
class CompareResult:
    """Outcome of comparing two modules."""

    change_kind: "ChangeKind"
    description: str
    severity: str  # info|warn|error
    diff: "DiffResult | None" = None


@dataclass(frozen=True, slots=True)
class SuggestVersionResult:
    """CompareResult + suggested next version."""

    change_kind: "ChangeKind"
    description: str
    severity: str
    current_version: Version
    suggested_version: Version
    diff: "DiffResult | None" = None
