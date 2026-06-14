"""Shared utilities for CLI commands."""

from __future__ import annotations

import logging
import sys
from typing import Any

import yaml

from semverdredd.plugin_base import LanguagePlugin
from snapshot import ChangeKind, NormalizedSnapshot
from snapshot.models import GeneratorInfo

_cli_logger = logging.getLogger("cli")

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


# ---------------------------------------------------------------------------
# Structured log event helpers (verbosity-gated, stdlib logging)
# ---------------------------------------------------------------------------

# Event topics emitted through stdlib logging so verbosity level controls them.
# Use INFO for O(1) once-per-call events, DEBUG for O(n) per-item events.


def _log_event(topic: str, message: str, *, level: int = logging.INFO) -> None:
    """Emit a structured log event through the 'cli' logger.

    Callers should pass an INFO level for O(1) once-per-call events (config
    selection, plugin selection) and DEBUG for O(n) events (candidates,
    include/exclude items, API members).

    topic: short dot-separated label (e.g. "config.selected", "plugin.selected").
    """
    _cli_logger.log(level, "[%s] %s", topic, message)


def _log_config_selected(config_path: str, how: str) -> None:
    """Emit an info event when a config file is selected.

    how: 'explicit' | 'default' | 'absent'
    """
    _log_event("config.selected", f"{config_path!r} ({how})", level=logging.INFO)


def _log_plugin_selected(plugin_name: str, source: str) -> None:
    """Emit an info event when a plugin is selected.

    source: e.g. 'cli', 'env', 'config', 'default'
    """
    _log_event("plugin.selected", f"{plugin_name!r} from {source}", level=logging.INFO)


def _log_candidate_attempt(index: int, plugin: str, reason: str | None) -> None:
    """Emit a debug event for each candidate selection attempt."""
    if reason:
        _log_event(
            "candidate.attempt",
            f"[{index}] plugin={plugin!r} failed: {reason}",
            level=logging.DEBUG,
        )
    else:
        _log_event(
            "candidate.attempt",
            f"[{index}] plugin={plugin!r} accepted",
            level=logging.DEBUG,
        )


def _warn_snapshot_plugin_mismatch(
    baseline_plugin: str,
    current_plugin: str,
    use_color: bool = False,
) -> None:
    """Warn when baseline and current snapshots were produced by different plugins.

    Called before delegating diff logic so the user understands the
    compatibility assumption being made.  Does not block comparison —
    snapshot classes own compatibility.
    """
    _print_level(
        "warn",
        f"Snapshot plugin mismatch: baseline generated by {baseline_plugin!r}, "
        f"current generated by {current_plugin!r}. "
        "Diff proceeds with current plugin's snapshot class; results may be incomplete.",
        use_color=use_color,
    )


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


def _inject_generator_into_yaml(yaml_str: str, generator: GeneratorInfo) -> str:
    """Inject a generator provenance block into an existing snapshot YAML string.

    The block is inserted at the top level; any existing 'generator' key is
    replaced. Returns the modified YAML string.  Snapshots without a top-level
    mapping (unusual) are returned unchanged.
    """
    data: Any = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        return yaml_str
    data["generator"] = generator.to_dict()
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _generate_snapshot_yaml(
    plugin_name: str,
    path: str,
    version: str,
    use_color: bool,
    extra_options: dict | None = None,
    generator: GeneratorInfo | None = None,
) -> tuple[int, str]:
    """Generate snapshot YAML using language-specific parser. Returns (exit_code, yaml_str).

    extra_options (e.g. include/exclude/plugin_options from .semver.yaml) are
    merged into the options dict passed to the plugin.

    If ``generator`` is provided, inject its provenance block into the YAML
    output before returning.
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

    yaml_content = result.yaml_content
    if generator is not None:
        yaml_content = _inject_generator_into_yaml(yaml_content, generator)

    return EXIT_OK, yaml_content
