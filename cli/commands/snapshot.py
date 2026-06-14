"""snapshot command — generate an API snapshot using language plugins."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.utils import EXIT_OK, _generate_snapshot_yaml, _print_level, _should_use_color


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Generate a baked.yaml-like snapshot using language-specific parsers."""
    use_color = _should_use_color(getattr(args, "color", None))

    if not getattr(args, "plugin", None):
        _print_level(
            "error",
            "No plugin provided. Pass --plugin or configure plugin in config.",
            use_color=use_color,
        )
        return 1
    if not getattr(args, "path", None):
        _print_level(
            "error",
            "No source path provided. Pass --path or configure source.path.",
            use_color=use_color,
        )
        return 1
    if not getattr(args, "version", None):
        _print_level(
            "error",
            "No version provided and no readable version file resolved.",
            use_color=use_color,
        )
        return 1

    plugin_name = args.plugin.lower()
    version = args.version
    out_path = args.out

    exit_code, yaml_str = _generate_snapshot_yaml(
        plugin_name,
        args.path,
        version,
        use_color,
        extra_options=getattr(args, "snapshot_options", None),
    )
    if exit_code != EXIT_OK:
        return exit_code

    if out_path:
        Path(out_path).write_text(yaml_str)
        _print_level("info", f"Wrote snapshot to {out_path}", use_color=use_color)
    else:
        print(yaml_str, end="")

    return EXIT_OK
