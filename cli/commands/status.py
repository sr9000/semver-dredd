"""status command — show current API status compared to baked baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from cli.utils import (
    DEFAULT_BAKED_FILE,
    DEFAULT_CURRENT_FILE,
    EXIT_BREAKING_CHANGES_DETECTED,
    EXIT_ERROR,
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


def cmd_status(args: argparse.Namespace) -> int:
    """Show current API status compared to baked baseline.

    This is the unified status command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    # Parse --date if provided
    from datetime import date as date_type

    if getattr(args, "date", None):
        try:
            target_date = date_type.fromisoformat(args.date)
        except ValueError:
            _print_level(
                "error",
                f"Invalid date format: {args.date}. Use YYYY-MM-DD.",
                use_color=use_color,
            )
            return EXIT_ERROR
    else:
        target_date = date_type.today()

    baked_path = Path(getattr(args, "baked", None) or DEFAULT_BAKED_FILE)
    current_path = Path(getattr(args, "current_file", None) or DEFAULT_CURRENT_FILE)

    # Check if baked.yaml exists
    if not baked_path.exists():
        _print_level(
            "warn",
            f"No {baked_path} found. Run 'init' or 'bake' first.",
            use_color=use_color,
        )
        return EXIT_ERROR

    # Load baked snapshot
    exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
    snap_cls = _resolve_snapshot_class(lang_plugin)

    baked = snap_cls.from_file(baked_path)

    # Generate current snapshot (use "0.0.0" placeholder, we'll compute suggested version)
    exit_code, yaml_str = _generate_snapshot_yaml(
        plugin_name,
        args.module,
        "0.0.0",
        use_color,
        extra_options=getattr(args, "snapshot_options", None),
    )
    if exit_code != EXIT_OK:
        return exit_code

    current = snap_cls.from_yaml_str(yaml_str)

    # Compare
    diff_result = _run_diff(baked, current, lang_plugin)
    change = diff_result.change_kind

    # Compute suggested version
    current_version = Version.parse(baked.version)

    # Check for patch date warnings/errors
    baked_patch_date = current_version.patch_date
    if baked_patch_date and baked_patch_date > target_date:
        _print_level(
            "warn",
            f"Baked version patch date ({baked_patch_date}) is in the future compared to target date ({target_date}). "
            "This suggests clock skew or incorrect date override.",
            use_color=use_color,
        )
    elif baked_patch_date and baked_patch_date == target_date:
        # Check if we're about to overflow
        if current_version.patch_increment >= 999:
            _print_level(
                "error",
                f"Maximum daily releases (999) reached for {target_date}. Cannot increment patch.",
                use_color=use_color,
            )
            return EXIT_ERROR

    change_descriptions = _get_change_descriptions()

    try:
        scheme = getattr(args, "patch_scheme", None) or "date"
        suggested_version = current_version.increment(
            change, today=target_date, scheme=scheme
        )
    except ValueError as e:
        _print_level("error", str(e), use_color=use_color)
        return EXIT_ERROR

    severity = _severity_for_change(change)
    allow_breaking = getattr(args, "allow_breaking", False)
    if change == ChangeKind.BREAKING and allow_breaking:
        severity = "warn"

    _print_level(
        severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color
    )
    print(f"Baked version: {baked.version}")
    print(f"Suggested version: {suggested_version}")

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

    # Update current.yaml with suggested version
    current_dict = current.to_dict()
    current_dict["version"] = str(suggested_version)
    current_path.write_text(
        yaml.dump(current_dict, default_flow_style=False, sort_keys=False)
    )
    _print_level("info", f"Updated {current_path}", use_color=use_color)

    # Policy gate
    if change == ChangeKind.BREAKING and not allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK
