"""bump command — bump version based on change type."""

from __future__ import annotations

import argparse

from cli.utils import EXIT_ERROR, EXIT_OK, _print_level, _should_use_color
from semverdredd import Version
from snapshot import ChangeKind


def cmd_bump(args: argparse.Namespace) -> int:
    """Bump version based on change type."""
    use_color = _should_use_color(getattr(args, "color", None))

    try:
        current = Version.parse(args.current)
    except ValueError as e:
        _print_level("error", f"Error parsing version: {e}", use_color=use_color)
        return EXIT_ERROR

    change_map = {
        "major": ChangeKind.BREAKING,
        "minor": ChangeKind.MINOR,
        "patch": ChangeKind.PATCH,
        "none": ChangeKind.NONE,
    }

    change = change_map.get(args.change.lower())
    if change is None:
        _print_level(
            "error", f"Invalid change type '{args.change}'", use_color=use_color
        )
        _print_level(
            "error", f"Valid types: {', '.join(change_map.keys())}", use_color=use_color
        )
        return EXIT_ERROR

    new_version = current.increment(change)

    if args.quiet:
        print(new_version)
    else:
        print(f"Current: {current}")
        print(f"Change: {change.name}")
        print(f"New: {new_version}")

    return EXIT_OK
