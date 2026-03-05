"""patch command — generate a new patch version number."""

from __future__ import annotations

import argparse

from cli.utils import EXIT_ERROR, EXIT_OK, _print_level, _should_use_color
from semverdredd import generate_patch


def cmd_patch(args: argparse.Namespace) -> int:
    """Generate a new patch version."""
    use_color = _should_use_color(getattr(args, "color", None))

    current = int(args.current) if args.current else None

    try:
        new_patch = generate_patch(current_patch=current)
        print(new_patch)
        return EXIT_OK
    except ValueError as e:
        _print_level("error", f"Error: {e}", use_color=use_color)
        return EXIT_ERROR
