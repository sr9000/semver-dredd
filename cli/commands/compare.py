"""compare command — compare two modules/paths and report change type."""

from __future__ import annotations

import argparse

from cli.utils import (
    EXIT_BREAKING_CHANGES_DETECTED,
    EXIT_OK,
    _generate_snapshot_yaml,
    _get_change_descriptions,
    _get_language_plugin,
    _print_level,
    _resolve_snapshot_class,
    _run_diff,
    _severity_for_change,
    _should_use_color,
)
from semverdredd import Version
from snapshot import ChangeKind


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two modules/paths and report change type.

    This is the unified compare command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    if getattr(args, "verbose", False):
        _print_level(
            "info",
            f"Using plugin '{plugin_name}' to compare modules/paths.",
            use_color=use_color,
        )

    exit_code, old_yaml = _generate_snapshot_yaml(
        plugin_name, args.old_module, "0.0.0", use_color
    )
    if exit_code != EXIT_OK:
        return exit_code

    exit_code, new_yaml = _generate_snapshot_yaml(
        plugin_name, args.new_module, "0.0.0", use_color
    )
    if exit_code != EXIT_OK:
        return exit_code

    exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
    snap_cls = _resolve_snapshot_class(lang_plugin)

    old_snapshot = snap_cls.from_yaml_str(old_yaml)
    new_snapshot = snap_cls.from_yaml_str(new_yaml)

    diff_result = _run_diff(old_snapshot, new_snapshot, lang_plugin)
    change = diff_result.change_kind

    change_descriptions = _get_change_descriptions()

    severity = _severity_for_change(change)

    allow_breaking = getattr(args, "allow_breaking", False)
    if change == ChangeKind.BREAKING and allow_breaking:
        severity = "warn"

    # Output results
    _print_level(
        severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color
    )
    print(f"Change type: {change.name}")
    print(f"Description: {change_descriptions[change]}")

    if getattr(args, "details", False):
        if diff_result.breaking:
            print("Breaking changes:")
            for item in diff_result.breaking:
                print(f"  - {item}")
        if diff_result.added:
            print("Added changes:")
            for item in diff_result.added:
                print(f"  - {item}")
        if not diff_result.breaking and not diff_result.added:
            print("No API additions or breaking changes detected.")

    if getattr(args, "current", None):
        try:
            current = Version.parse(args.current)
            new_version = current.increment(change)
            print(f"Current version: {current}")
            print(f"Suggested version: {new_version}")
        except ValueError as e:
            _print_level(
                "warn", f"Could not parse current version: {e}", use_color=use_color
            )

    if change == ChangeKind.BREAKING and not allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK
