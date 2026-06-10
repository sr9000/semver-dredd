"""Shared utilities for CLI commands."""

from __future__ import annotations

import sys

from semverdredd.plugin_base import LanguagePlugin
from snapshot import ChangeKind, NormalizedSnapshot

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BREAKING_CHANGES_DETECTED = 10

# ---------------------------------------------------------------------------
# Default file paths
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_FILE = ".semver.yaml"
DEFAULT_BAKED_FILE = "baked.yaml"
DEFAULT_CURRENT_FILE = "current.yaml"
DEFAULT_VERSION_FILE = "VERSION"

# ---------------------------------------------------------------------------
# Snapshot / diff helpers
# ---------------------------------------------------------------------------


def _resolve_snapshot_class(plugin: LanguagePlugin | None) -> type:
    """Return the snapshot class to use — the plugin's custom one or the default."""
    if plugin is not None:
        cls = plugin.snapshot_format_class
        if cls is not None:
            return cls
    return NormalizedSnapshot


def _run_diff(old_snapshot, new_snapshot, plugin: LanguagePlugin | None):
    """Run a diff by calling old_snapshot.diff_against(new_snapshot).

    All snapshot types must implement the Comparable protocol.
    """
    from snapshot.protocols import Comparable

    if not isinstance(old_snapshot, Comparable):
        raise TypeError(
            f"{type(old_snapshot).__name__} does not implement Comparable "
            "(add a diff_against method)"
        )
    return old_snapshot.diff_against(new_snapshot)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _should_use_color(color_flag: bool | None) -> bool:
    """Decide whether to use ANSI colors for log lines.

    color_flag:
      - True: always color
      - False: never color
      - None: auto (only when stderr is a tty)
    """
    if color_flag is True:
        return True
    if color_flag is False:
        return False
    return bool(getattr(sys.stderr, "isatty", lambda: False)())


def _style_level(level: str, *, use_color: bool) -> str:
    if not use_color:
        return level.upper()

    # Basic ANSI colors (no external deps)
    colors = {
        "info": "\x1b[32m",  # green
        "warn": "\x1b[33m",  # yellow
        "error": "\x1b[31m",  # red
    }
    reset = "\x1b[0m"
    return f"{colors.get(level.lower(), '')}{level.upper()}{reset}"


def _print_level(level: str, message: str, *, use_color: bool = False) -> None:
    """Print a message with a log level prefix.

    NOTE: We deliberately keep this lightweight (no logging module) so tests can
    assert on stdout/stderr deterministically.
    """
    stream = sys.stdout if level.lower() == "info" else sys.stderr
    styled = _style_level(level, use_color=use_color)
    print(f"[{styled}] {message}", file=stream)


def _severity_for_change(change: ChangeKind) -> str:
    """Map change kind to log severity level."""
    if change in (ChangeKind.NONE, ChangeKind.PATCH):
        return "info"
    if change == ChangeKind.MINOR:
        return "warn"
    return "error"


def _get_change_descriptions() -> dict[ChangeKind, str]:
    """Get human-readable descriptions for change kinds."""
    return {
        ChangeKind.NONE: "No API changes detected (patch bump)",
        ChangeKind.PATCH: "Implementation changes only (patch bump)",
        ChangeKind.MINOR: "New features added (minor bump)",
        ChangeKind.BREAKING: "Breaking changes detected (major bump)",
    }


# ---------------------------------------------------------------------------
# Plugin helpers
# ---------------------------------------------------------------------------


def _get_language_plugin(
    plugin_name: str, use_color: bool
) -> tuple[int, LanguagePlugin | None]:
    """Resolve a language plugin by name. Returns (exit_code, plugin)."""
    from semverdredd.plugin_manager import get_plugin

    plugin = get_plugin(plugin_name)
    if not plugin:
        _print_level(
            "error", f"Unsupported language/plugin: {plugin_name}", use_color=use_color
        )
        return EXIT_ERROR, None
    return EXIT_OK, plugin


def _generate_snapshot_yaml(
    plugin_name: str,
    path: str,
    version: str,
    use_color: bool,
    extra_options: dict | None = None,
) -> tuple[int, str]:
    """Generate snapshot YAML using language-specific parser. Returns (exit_code, yaml_str).

    extra_options (e.g. include/exclude/plugin_options from .semver.yaml) are
    merged into the options dict passed to the plugin.
    """
    exit_code, plugin = _get_language_plugin(plugin_name, use_color)
    if exit_code != EXIT_OK or plugin is None:
        return EXIT_ERROR, ""

    ok, msg = plugin.validate_path(path)
    if not ok:
        _print_level("error", msg, use_color=use_color)
        return EXIT_ERROR, ""

    options: dict = {"use_color": use_color}
    if extra_options:
        options.update(extra_options)

    result = plugin.generate_snapshot(path, version, options=options)

    if not result.success:
        _print_level(
            "error",
            result.error_message or "Snapshot generation failed",
            use_color=use_color,
        )
        return EXIT_ERROR, ""

    return EXIT_OK, result.yaml_content
