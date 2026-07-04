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

import warnings

from semverdredd.diff import DefaultDiffScorer, compare_snapshots
from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semverdredd.plugin_manager import (
    PluginManager,
    get_plugin,
    get_plugin_manager,
    list_plugins,
)
from semverdredd.registry import SnapshotRegistry, default_registry
from semverdredd.snapshot_io import load_snapshot, load_snapshot_yaml

# ---------------------------------------------------------------------------
# Import-time initialization
# ---------------------------------------------------------------------------
# The CLI and many users expect that importing `semverdredd` is sufficient to:
# 1) register the built-in snapshot format in the UUID registry
# 2) discover/register language plugins (so `get_plugin()` works immediately)
#
# Both operations are designed to be idempotent and safe to call multiple times.
try:
    from semverdredd.registry import _ensure_builtins_registered as _sd__ensure

    _sd__ensure()
except Exception as e:
    # Keep import side-effects best-effort; callers can still explicitly load.
    warnings.warn(f"Failed to register built-in snapshot formats: {e}", UserWarning)

# NOTE: Plugin loading is intentionally NOT done at import time.
# PluginManager.get() and PluginManager.list_plugins() already call
# load_plugins() lazily on first use.  Calling it eagerly here caused
# circular-import failures: a plugin's module imports from semverdredd,
# which triggers this __init__.py, which tries to load the very plugin
# that is still being imported — resulting in a partially-initialized
# module and missing class attributes.

# Structured result types (pure data)
from semverdredd.result import CompareResult, SuggestVersionResult

# Re-export Version and generate_patch from version module
from semverdredd.version import Version, generate_patch

# Change severity enum (canonical home)
from snapshot.change_kind import ChangeKind

# Snapshot data models
from snapshot.models import NormalizedSnapshot

# Protocols and diff types
from snapshot.protocols import DiffResult, SnapshotFormat

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


def compare(
    old_path: str,
    new_path: str,
    plugin: str = "python",
    options: dict | None = None,
    old_version: str = "0.0.0",
    new_version: str = "0.0.0",
) -> CompareResult:
    """Programmatic compare that returns structured data (no printing).

    Works with any language via the plugin system.

    Args:
        old_path: Path to old module/package (or module name for Python)
        new_path: Path to new module/package (or module name for Python)
        plugin: Language plugin to use (default: "python")
        options: Optional dict forwarded to LanguagePlugin.generate_snapshot
            (e.g. include/exclude/plugin_options)
        old_version: Version string embedded in the old snapshot
            (default "0.0.0" when unknown)
        new_version: Version string embedded in the new snapshot
            (default "0.0.0" when unknown)

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
    old_result = lang_plugin.generate_snapshot(old_path, old_version, options=options)
    if not old_result.success:
        raise RuntimeError(
            f"Failed to generate snapshot for old: {old_result.error_message}"
        )

    new_result = lang_plugin.generate_snapshot(new_path, new_version, options=options)
    if not new_result.success:
        raise RuntimeError(
            f"Failed to generate snapshot for new: {new_result.error_message}"
        )

    # Use plugin-provided snapshot class; resolve the diff path
    snap_cls = _resolve_snapshot_class(lang_plugin)

    old_snapshot = snap_cls.from_yaml_str(old_result.yaml_content)
    new_snapshot = snap_cls.from_yaml_str(new_result.yaml_content)

    # All snapshot types must implement Comparable (diff_against).
    from snapshot.protocols import Comparable

    if not isinstance(old_snapshot, Comparable):
        raise TypeError(
            f"{type(old_snapshot).__name__} does not implement Comparable "
            "(add a diff_against method)"
        )
    diff_result = old_snapshot.diff_against(new_snapshot)
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
    options: dict | None = None,
) -> SuggestVersionResult:
    """Compare two modules/packages and compute a suggested next version.

    This is the recommended pure-data entry point for other tools.
    Works with any language via the plugin system.

    Args:
        old_path: Path to old module/package (or module name for Python)
        new_path: Path to new module/package (or module name for Python)
        current_version: Version or version string
        plugin: Language plugin to use (default: "python")
        options: Optional dict forwarded to LanguagePlugin.generate_snapshot

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
    # The old snapshot describes the API at the current (known) version.
    # The new snapshot's version isn't known until the diff is scored, so the
    # current version is the most meaningful value available for both.
    base = compare(
        old_path,
        new_path,
        plugin=plugin,
        options=options,
        old_version=str(current),
        new_version=str(current),
    )
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
    "ChangeKind",
    "NormalizedSnapshot",
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
    "DiffResult",
    "DefaultDiffScorer",
    "PluginManager",
    "get_plugin_manager",
    "get_plugin",
    "list_plugins",
    "SnapshotRegistry",
    "default_registry",
]
