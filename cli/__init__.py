"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import sys

from cli.commands import (
    cmd_bake,
    cmd_bump,
    cmd_compare,
    cmd_init,
    cmd_patch,
    cmd_plugin_info,
    cmd_plugin_install,
    cmd_plugin_list,
    cmd_plugin_remove,
    cmd_snapshot,
    cmd_status,
    cmd_template,
)
from cli.config import apply_config_defaults, load_config
from cli.utils import EXIT_ERROR, EXIT_OK, _print_level


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="semver-dredd",
        description="Automatically increment semver based on API changes",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize semver-dredd for a project",
    )
    init_parser.add_argument(
        "module",
        help="Module name (Python) or source path (Go/Java)",
    )
    init_parser.add_argument(
        "--plugin",
        help="Language plugin to use (default: python)",
    )
    init_parser.add_argument(
        "--version",
        "-v",
        help="Initial version (default: 0.1.YYYYMMDD001)",
    )
    init_parser.add_argument(
        "--baked",
        default=None,
        help="Path to baked.yaml file (default: baked.yaml)",
    )
    init_parser.add_argument(
        "--version-file",
        default=None,
        help="Path to VERSION file (default: VERSION)",
    )
    init_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    init_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    init_parser.set_defaults(func=cmd_init)
    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show current API status compared to baked baseline",
    )
    status_parser.add_argument(
        "module",
        help="Module name (Python) or source path (Go/Java)",
    )
    status_parser.add_argument(
        "--plugin",
        help="Language plugin to use (default: python)",
    )
    status_parser.add_argument(
        "--date",
        help="Date to use for patch version (YYYY-MM-DD, default: today)",
    )
    status_parser.add_argument(
        "--baked",
        default=None,
        help="Path to baked.yaml file (default: baked.yaml)",
    )
    status_parser.add_argument(
        "--current-file",
        default=None,
        help="Path to current.yaml file (default: current.yaml)",
    )
    status_parser.add_argument(
        "--version-file",
        default=None,
        help="Path to VERSION file (default: VERSION)",
    )
    status_parser.add_argument(
        "--details",
        action="store_true",
        help="List breaking and added API items",
    )
    status_parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="Allow breaking changes without failing",
    )
    status_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    status_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    status_parser.set_defaults(func=cmd_status)
    # Bake command
    bake_parser = subparsers.add_parser(
        "bake",
        help="Bake current API state as the new baseline",
    )
    bake_parser.add_argument(
        "module",
        help="Module name (Python) or source path (Go/Java)",
    )
    bake_parser.add_argument(
        "--plugin",
        help="Language plugin to use (default: python)",
    )
    bake_parser.add_argument(
        "--version",
        help="Explicit version to bake (default: auto-computed)",
    )
    bake_parser.add_argument(
        "--baked",
        default=None,
        help="Path to baked.yaml file (default: baked.yaml)",
    )
    bake_parser.add_argument(
        "--version-file",
        default=None,
        help="Path to VERSION file (default: VERSION)",
    )
    bake_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    bake_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    bake_parser.set_defaults(func=cmd_bake)
    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two modules and detect change type",
    )
    compare_parser.add_argument(
        "--plugin",
        help="Language plugin to use (default: python)",
    )
    compare_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    compare_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    compare_parser.add_argument(
        "old_module",
        help="Path or name of the old module version",
    )
    compare_parser.add_argument(
        "new_module",
        help="Path or name of the new module version",
    )
    compare_parser.add_argument(
        "--current",
        "-c",
        help="Current version string to suggest new version",
    )
    compare_parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="Allow breaking changes (MAJOR) without failing the command",
    )
    compare_parser.add_argument(
        "--disallow-breaking",
        action="store_true",
        help="Explicitly disallow breaking changes (MAJOR) and fail the command",
    )
    compare_parser.add_argument(
        "--details",
        action="store_true",
        help="List breaking and added API items detected during comparison",
    )
    compare_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Explain what parts of the API are being inspected",
    )
    compare_parser.set_defaults(func=cmd_compare)
    # Bump command
    bump_parser = subparsers.add_parser(
        "bump",
        help="Bump version based on change type",
    )
    bump_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    bump_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    bump_parser.add_argument(
        "--current",
        "-c",
        required=True,
        help="Current version string",
    )
    bump_parser.add_argument(
        "--change",
        "-t",
        required=True,
        choices=["major", "minor", "patch", "none"],
        help="Type of change",
    )
    bump_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output the new version",
    )
    bump_parser.set_defaults(func=cmd_bump)
    # Patch command
    patch_parser = subparsers.add_parser(
        "patch",
        help="Generate a new patch version number",
    )
    patch_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    patch_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    patch_parser.add_argument(
        "--current",
        "-c",
        help="Current patch version (to increment if same day)",
    )
    patch_parser.set_defaults(func=cmd_patch)
    # Template command
    template_parser = subparsers.add_parser(
        "template",
        help="Generate a comprehensive .semver.yaml configuration template",
    )
    template_parser.add_argument(
        "--out",
        "-o",
        default="",
        help="Output file path (default: stdout)",
    )
    template_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    template_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    template_parser.set_defaults(func=cmd_template)
    # Snapshot command
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Generate an API snapshot (baked.yaml-like) using language plugins",
    )
    snapshot_parser.add_argument(
        "--plugin",
        required=True,
        help="Language plugin to use (e.g. python, go, java)",
    )
    snapshot_parser.add_argument(
        "--path",
        required=True,
        help="Path to the source directory/package",
    )
    snapshot_parser.add_argument(
        "--version",
        required=True,
        help="Version string to embed in the snapshot",
    )
    snapshot_parser.add_argument(
        "--out",
        default="",
        help="Output YAML file (default: stdout)",
    )
    snapshot_parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="Force colored log output",
    )
    snapshot_parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="Disable colored log output",
    )
    snapshot_parser.set_defaults(func=cmd_snapshot)
    # Plugin management
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage semver-dredd language plugins",
    )
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_cmd")
    plugin_list = plugin_sub.add_parser(
        "list",
        help="List discovered plugins",
    )
    plugin_list.set_defaults(func=cmd_plugin_list)
    plugin_install = plugin_sub.add_parser(
        "install",
        help="Install a plugin distribution into the user plugin directory",
    )
    plugin_install.add_argument(
        "source",
        help="Anything pip install accepts (path, wheel, sdist, or package spec)",
    )
    plugin_install.set_defaults(func=cmd_plugin_install)
    plugin_remove = plugin_sub.add_parser(
        "remove",
        help="Remove a plugin from the user plugin directory (best-effort)",
    )
    plugin_remove.add_argument(
        "name",
        help="Plugin name to remove (e.g. 'go', 'java', 'python' or vendor plugin name)",
    )
    plugin_remove.set_defaults(func=cmd_plugin_remove)
    plugin_info = plugin_sub.add_parser(
        "info",
        help="Show details about a discovered plugin",
    )
    plugin_info.add_argument(
        "name",
        help="Plugin name to inspect",
    )
    plugin_info.set_defaults(func=cmd_plugin_info)
    args = parser.parse_args(argv)
    # Load config with priority: .semver.yaml < .env < env vars < CLI args
    config = load_config()
    # Check for mutually exclusive flags before applying config
    if getattr(args, "command", None) in ("compare", "status"):
        allow = getattr(args, "allow_breaking", False)
        disallow = getattr(args, "disallow_breaking", False)
        if allow and disallow:
            _print_level(
                "error",
                "--allow-breaking and --disallow-breaking are mutually exclusive",
            )
            return EXIT_ERROR
    # Apply config defaults (respects CLI args as highest priority)
    apply_config_defaults(args, config)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
