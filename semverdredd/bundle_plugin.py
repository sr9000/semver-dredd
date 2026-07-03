"""Built-in bundle plugin.

This registration slice only establishes builtin discovery and metadata.
Snapshot generation/diff semantics land in follow-up patches.
"""

from __future__ import annotations

from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult


class BundlePlugin(LanguagePlugin):
    """Built-in aggregate plugin for VERSION-file bundles."""

    @property
    def name(self) -> str:
        return "bundle"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Analyzes bundles of VERSION files without a language-specific parser"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "scope": {
                "syntax": "paths to VERSION files in include[]",
                "include_mode": "explicit dependency list",
                "exclude_mode": "not used",
                "empty_include": "invalid for bundle snapshots",
            },
            "plugin_options": [],
            "runtime_requirements": {
                "python": ">=3.10",
                "external_tools": [],
            },
            "features": ["metadata", "machine_readable_inventory"],
        }

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Bundle uses config include paths rather than validating a source tree."""
        return True, ""

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        return SnapshotResult(
            False,
            "",
            "Bundle snapshot generation is not implemented yet",
        )