"""Structured result types for semver-dredd.

This module is intentionally pure-data (no logging/printing) so it can be used
from CI systems and other tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from semverdredd.version import Version

if TYPE_CHECKING:  # pragma: no cover
    from semverdredd import ChangeType


@dataclass(frozen=True, slots=True)
class CompareResult:
    """Outcome of comparing two modules."""

    change_type: "ChangeType"
    description: str
    severity: str  # info|warn|error


@dataclass(frozen=True, slots=True)
class SuggestVersionResult(CompareResult):
    """CompareResult + suggested next version."""

    current_version: Version
    suggested_version: Version
