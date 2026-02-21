"""
Automatically increments semver number based on interface changes.

semver consists of three numbers: major, minor, and patch.

Major version is incremented when there are breaking changes to the public API.
Minor version is incremented when there are new features added to the public API, but no breaking changes.
Patch version is equal YYYYMMDDZZZ.
- YYYY is the current year.
- MM is the current month.
- DD is the current day.
- ZZZ is a zero-padded incremental number that starts at 001 for each day and increments with each patch release on the same day.
"""

# Diff engine
from semverdredd.diff import DefaultDiffScorer, compare_snapshots

# Plugin system (programmatic API)
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semverdredd.plugin_manager import (
    PluginManager,
    get_plugin,
    get_plugin_manager,
    list_plugins,
)

# Registry (canonical home)
from semverdredd.registry import (
    SnapshotRegistry,
    default_registry,
)
from semverdredd.snapshot_io import load_snapshot, load_snapshot_yaml

# Structured result types (pure data)
from semverdredd.result import CompareResult, SuggestVersionResult

# Re-export Version and generate_patch from version module
from semverdredd.version import Version, generate_patch

# Change severity enum (canonical home)
from snapshot.change_kind import ChangeKind

# Snapshot data models
from snapshot.models import NormalizedSnapshot

# Protocols and diff types
from snapshot.protocols import DiffResult, DiffScorer, SnapshotFormat


def _description_for_change(change: ChangeKind) -> str:
    return {
        ChangeKind.NONE: "No API changes detected",
        ChangeKind.PATCH: "Implementation changes only (patch bump)",
        ChangeKind.MINOR: "New features added (minor bump)",
        ChangeKind.BREAKING: "Breaking changes detected (major bump)",
    }[change]


def _severity_for_change(change: ChangeKind) -> str:
    if change in (ChangeKind.NONE, ChangeKind.PATCH):
        return "info"
    if change == ChangeKind.MINOR:
        return "warn"
    return "error"


def _resolve_snapshot_class(plugin: LanguagePlugin | None) -> type:
    """Return the snapshot class to use — the plugin's custom one or the default."""
    if plugin is not None:
        cls = plugin.snapshot_format_class
        if cls is not None:
            return cls
    return NormalizedSnapshot


def _resolve_diff_scorer(plugin: LanguagePlugin | None) -> DiffScorer:
    """Return the diff scorer to use — the plugin's custom one or the default."""
    if plugin is not None:
        scorer = plugin.diff_scorer
        if scorer is not None:
            return scorer
    return DefaultDiffScorer()


def compare(
    old_path: str,
    new_path: str,
    plugin: str = "python",
) -> CompareResult:
    """Programmatic compare that returns structured data (no printing).

    Works with any language via the plugin system.

    Args:
        old_path: Path to old module/package (or module name for Python)
        new_path: Path to new module/package (or module name for Python)
        plugin: Language plugin to use (default: "python")

    Returns:
        CompareResult with change_kind/description/severity/diff

    Raises:
        RuntimeError: if plugin not found or snapshot generation fails
    """
    from semverdredd.plugin_manager import get_plugin as _get_plugin

    lang_plugin = _get_plugin(plugin)
    if not lang_plugin:
        raise RuntimeError(f"Plugin '{plugin}' not found")

    # Validate paths
    ok, msg = lang_plugin.validate_path(old_path)
    if not ok:
        raise RuntimeError(f"Invalid old path: {msg}")
    ok, msg = lang_plugin.validate_path(new_path)
    if not ok:
        raise RuntimeError(f"Invalid new path: {msg}")

    # Generate snapshots
    old_result = lang_plugin.generate_snapshot(old_path, "0.0.0")
    if not old_result.success:
        raise RuntimeError(
            f"Failed to generate snapshot for old: {old_result.error_message}"
        )

    new_result = lang_plugin.generate_snapshot(new_path, "0.0.0")
    if not new_result.success:
        raise RuntimeError(
            f"Failed to generate snapshot for new: {new_result.error_message}"
        )

    # Use plugin-provided snapshot class and diff scorer
    snap_cls = _resolve_snapshot_class(lang_plugin)
    scorer = _resolve_diff_scorer(lang_plugin)

    old_snapshot = snap_cls.from_yaml_str(old_result.yaml_content)
    new_snapshot = snap_cls.from_yaml_str(new_result.yaml_content)

    diff_result = scorer.diff(old_snapshot, new_snapshot)
    change = diff_result.change_kind

    return CompareResult(
        change_kind=change,
        description=_description_for_change(change),
        severity=_severity_for_change(change),
        diff=diff_result,
    )


def compare_and_suggest(
    old_path: str,
    new_path: str,
    current_version: Version | str,
    plugin: str = "python",
) -> SuggestVersionResult:
    """Compare two modules/packages and compute a suggested next version.

    This is the recommended pure-data entry point for other tools.
    Works with any language via the plugin system.

    Args:
        old_path: Path to old module/package (or module name for Python)
        new_path: Path to new module/package (or module name for Python)
        current_version: Version or version string
        plugin: Language plugin to use (default: "python")

    Returns:
        SuggestVersionResult

    Raises:
        ValueError: if current_version cannot be parsed
        RuntimeError: if plugin not found or snapshot generation fails
    """
    current = (
        current_version
        if isinstance(current_version, Version)
        else Version.parse(str(current_version))
    )
    base = compare(old_path, new_path, plugin=plugin)
    suggested = current.increment(base.change_kind)
    return SuggestVersionResult(
        change_kind=base.change_kind,
        description=base.description,
        severity=base.severity,
        current_version=current,
        suggested_version=suggested,
        diff=base.diff,
    )


__all__ = [
    # Core types
    "Version",
    "generate_patch",
    # Result types
    "CompareResult",
    "SuggestVersionResult",
    # Programmatic API
    "compare",
    "compare_and_suggest",
    # Snapshot types
    "load_snapshot",
    "load_snapshot_yaml",
    "compare_snapshots",
    # Plugin system
    "LanguagePlugin",
    "SnapshotResult",
    "SnapshotFormat",
    "DiffScorer",
    "DiffResult",
    "DefaultDiffScorer",
    "PluginManager",
    "get_plugin_manager",
    "get_plugin",
    "list_plugins",
    "SnapshotRegistry",
    "default_registry",
]
