"""Structured result types for semver-dredd.

This module is intentionally pure-data (no logging/printing) so it can be used
from CI systems and other tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from semverdredd.version import Version

if TYPE_CHECKING:  # pragma: no cover
    from semverdredd import ChangeType


@dataclass(frozen=True, slots=True)
class APIDiff:
    """Detailed diff of API changes between two modules."""

    breaking: tuple[str, ...] = field(default_factory=tuple)
    added: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_changes(self) -> bool:
        return bool(self.breaking or self.added)


@dataclass(frozen=True, slots=True)
class CompareResult:
    """Outcome of comparing two modules."""

    change_type: "ChangeType"
    description: str
    severity: str  # info|warn|error
    diff: APIDiff = field(default_factory=APIDiff)


@dataclass(frozen=True, slots=True)
class SuggestVersionResult:
    """CompareResult + suggested next version."""

    change_type: "ChangeType"
    description: str
    severity: str
    current_version: Version
    suggested_version: Version
    diff: APIDiff = field(default_factory=APIDiff)
