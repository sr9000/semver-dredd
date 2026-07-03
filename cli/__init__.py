"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import logging
import sys
from pathlib import Path

from cli.commands import (cmd_bake, cmd_bump, cmd_compare, cmd_init, cmd_patch,
                          cmd_plugin_info, cmd_plugin_install, cmd_plugin_list,
                          cmd_plugin_remove, cmd_snapshot, cmd_status,
                          cmd_template)
from cli.config import (apply_config_defaults, load_config,
                        load_config_with_meta, resolve_command_context)
from cli.utils import (EXIT_ERROR, EXIT_OK, _log_candidate_attempt,
                       _log_config_selected, _log_event, _log_plugin_selected,
                       _print_level)
from semverdredd.version import load_version_file
from snapshot.models import GeneratorInfo

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="semver-dredd",
        description="Automatically increment semver based on API changes",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config file (default: .semver.yaml)",
    )
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help=(
            "Increase verbosity: -v info (once per call), "
            "-vv debug (per candidate/plugin), -vvv debug + arg dump"
        ),
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
        required=True,
        help="Language plugin to use",
    )
    init_parser.add_argument(
        "--version",
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
        nargs="?",
        help="Module name (Python) or source path (Go/Java)",
    )
    status_parser.add_argument(
        "--path",
        default=None,
        help="Explicit source path/module override",
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
    status_parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Additional include item (repeatable)",
    )
    status_parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Additional exclude item (repeatable)",
    )
    status_parser.add_argument(
        "--override",
        action="store_true",
        help="Replace config include/exclude with CLI include/exclude",
    )
    status_parser.set_defaults(func=cmd_status)
    # Bake command
    bake_parser = subparsers.add_parser(
        "bake",
        help="Bake current API state as the new baseline",
    )
    bake_parser.add_argument(
        "module",
        nargs="?",
        help="Module name (Python) or source path (Go/Java)",
    )
    bake_parser.add_argument(
        "--path",
        default=None,
        help="Explicit source path/module override",
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
    bake_parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Additional include item (repeatable)",
    )
    bake_parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Additional exclude item (repeatable)",
    )
    bake_parser.add_argument(
        "--override",
        action="store_true",
        help="Replace config include/exclude with CLI include/exclude",
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
        default=None,
        help="Language plugin to use (e.g. python, go, java)",
    )
    snapshot_parser.add_argument(
        "--path",
        default=None,
        help="Path to the source directory/package",
    )
    snapshot_parser.add_argument(
        "--version",
        default=None,
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
    snapshot_parser.add_argument(
        "--version-file",
        default=None,
        help="Path to VERSION file used when --version is omitted",
    )
    snapshot_parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Additional include item (repeatable)",
    )
    snapshot_parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Additional exclude item (repeatable)",
    )
    snapshot_parser.add_argument(
        "--override",
        action="store_true",
        help="Replace config include/exclude with CLI include/exclude",
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
        help="Remove a plugin from the user plugin directory (manifest-tracked)",
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

    # Configure stdlib logging based on -v count.
    # default (0): WARNING only — semver-dredd internal logs stay silent.
    # -v  (1): INFO  — O(1) config/plugin selection events per call.
    # -vv (2): DEBUG — O(n) candidate/plugin/include/API-member events.
    # -vvv(3): DEBUG — same as -vv; arg dump emitted separately below.
    _verbosity_to_level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    _log_level = _verbosity_to_level.get(args.verbosity, logging.DEBUG)
    logging.basicConfig(
        level=_log_level,
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Load config with priority: .semver.yaml < .env < env vars < CLI args
    allow_missing_explicit = getattr(args, "command", None) == "init"
    try:
        loaded = load_config_with_meta(
            config_file=getattr(args, "config", None),
            allow_missing_explicit=allow_missing_explicit,
        )
    except FileNotFoundError as e:
        _print_level("error", str(e))
        return EXIT_ERROR

    # Emit config selection event (-v and above).
    if loaded.selected_explicitly:
        _config_how = "explicit"
    elif loaded.config_exists:
        _config_how = "default"
    else:
        _config_how = "absent"
    _log_config_selected(str(loaded.config_path), _config_how)

    try:
        config = load_config(
            config_file=getattr(args, "config", None),
            allow_missing_explicit=allow_missing_explicit,
        )
    except ValueError as e:
        _print_level("error", str(e))
        return EXIT_ERROR

    # Apply generic defaults first (allow_breaking, color, etc.)
    apply_config_defaults(args, config)

    # Resolve command-scoped plugin/path/version/include/exclude context.
    try:
        resolved = resolve_command_context(args, loaded, cwd=Path.cwd())
    except ValueError as e:
        _print_level("error", str(e), use_color=False)
        return EXIT_ERROR

    # Emit candidate attempt events (-vv and above).
    for attempt in resolved.candidate_attempts:
        _log_candidate_attempt(
            attempt.index,
            attempt.plugin or "(none)",
            None if attempt.ok else attempt.reason,
        )

    # Emit plugin selection event (-v and above).
    if resolved.plugin:
        _log_plugin_selected(resolved.plugin, resolved.plugin_layer)

    # -vvv: dump resolved args/context for deep debugging.
    if args.verbosity >= 3:
        _log_event(
            "args.dump",
            f"command={args.command!r} plugin={resolved.plugin!r} "
            f"source_path={resolved.source_path!r} "
            f"version_file={resolved.version_file!r} "
            f"include={list(resolved.include)!r} "
            f"exclude={list(resolved.exclude)!r}",
            level=logging.DEBUG,
        )

    for warning in resolved.warnings:
        _print_level("warn", warning, use_color=False)

    if hasattr(args, "plugin"):
        args.plugin = resolved.plugin
    if hasattr(args, "version_file") and getattr(args, "version_file", None) is None:
        args.version_file = resolved.version_file

    if getattr(args, "command", None) in ("init", "status", "bake"):
        args.module = resolved.source_path
    if getattr(args, "command", None) == "snapshot":
        args.path = resolved.source_path
        if not getattr(args, "version", None):
            try:
                args.version = load_version_file(args.version_file)
            except OSError as e:
                _print_level(
                    "error", f"Failed to read version file {args.version_file}: {e}"
                )
                return EXIT_ERROR

    snapshot_options: dict[str, object] = {}
    if resolved.include:
        snapshot_options["include"] = list(resolved.include)
    if resolved.exclude:
        snapshot_options["exclude"] = list(resolved.exclude)
    if resolved.plugin_options:
        snapshot_options["plugin_options"] = dict(resolved.plugin_options)
    args.snapshot_options = snapshot_options

    args._resolved_context = resolved

    # Build generator provenance from resolved plugin context.
    # Commands that write snapshots should pass args.generator_info to
    # _generate_snapshot_yaml so new snapshots carry stable provenance.
    _gen_plugin_version = ""
    _gen_plugin_source = ""
    if resolved.plugin:
        from semverdredd.plugin_manager import get_plugin_manager

        _pm = get_plugin_manager()
        _pinfo = _pm._registry.get(resolved.plugin.lower())
        if _pinfo is not None:
            _gen_plugin_source = _pinfo.origin
            try:
                _gen_plugin_version = str(_pinfo.plugin.version)
            except Exception:
                _gen_plugin_version = ""
    args.generator_info = GeneratorInfo(
        plugin_name=resolved.plugin or "",
        plugin_version=_gen_plugin_version,
        plugin_source=_gen_plugin_source,
        config_path=str(loaded.config_path) if loaded.config_exists else "",
        candidate_index=(
            resolved.candidate_index if resolved.candidate_index is not None else -1
        ),
    )

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
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
