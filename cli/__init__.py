"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import ast
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

__all__ = [
    "CLI_SURFACE",
    "RichHelpFormatter",
    "main",
]


def _string_args(call: ast.Call) -> tuple[str, ...]:
    return tuple(
        arg.value
        for arg in call.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    )


def _call_receiver(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return call.func.value.id
    return None


def _call_method(call: ast.Call) -> str | None:
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def _extract_cli_surface() -> tuple[str, ...]:
    """Extract public command/argument surface from this active parser source.

    This is deliberately inside the real ``cli`` package so semver tracking sees
    behavior exported by the package itself, not a separate compatibility mirror.
    """
    tree = ast.parse(Path(__file__).read_text(), filename=__file__)
    main_func = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )

    parser_vars: dict[str, tuple[str, ...]] = {"parser": ()}
    subparser_vars: dict[str, tuple[str, ...]] = {}
    group_vars: dict[str, tuple[str, ...]] = {}
    entries: set[str] = {"prog:semver-dredd", "global:--config", "global:-v"}

    for stmt in main_func.body:
        call: ast.Call | None = None
        target: str | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            target = stmt.targets[0].id
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
        if call is None:
            continue

        receiver = _call_receiver(call)
        method = _call_method(call)
        args = _string_args(call)

        if target and method == "add_subparsers" and receiver in parser_vars:
            subparser_vars[target] = parser_vars[receiver]
            continue
        if target and method == "add_parser" and receiver in subparser_vars and args:
            path = subparser_vars[receiver] + (args[0],)
            parser_vars[target] = path
            entries.add("command:" + " ".join(path))
            continue
        if target and method == "add_mutually_exclusive_group" and receiver in parser_vars:
            group_vars[target] = parser_vars[receiver]
            continue
        if method != "add_argument" or not args:
            continue
        if receiver in parser_vars:
            path = parser_vars[receiver]
        elif receiver in group_vars:
            path = group_vars[receiver]
        else:
            continue
        prefix = "global" if not path else "command:" + " ".join(path)
        entries.add(prefix + ":" + "|".join(args))

    return tuple(sorted(entries))


CLI_SURFACE = _extract_cli_surface()


class RichHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """Help formatter that preserves paragraphs/examples and shows defaults."""


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="semver-dredd",
        formatter_class=RichHelpFormatter,
        description=(
            "Automatically increment semantic versions based on public API changes.\n\n"
            "Typical workflow:\n"
            "  1. semver-dredd init <source> --plugin <name> --version 1.0.0\n"
            "  2. semver-dredd status --details\n"
            "  3. semver-dredd bake\n\n"
            "Configuration precedence (lowest to highest):\n"
            "  .semver.yaml / --config file < .env < environment < CLI arguments\n\n"
            "Use the command-specific --help pages for examples and config-driven behavior."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin list\n"
            "  semver-dredd init example.py.pygeometry1 --plugin python --version 1.0.0\n"
            "  semver-dredd status --details\n"
            "  semver-dredd snapshot --version 1.0.0 --out baked.yaml\n"
            "  semver-dredd template --out .semver.yaml"
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Initialize semver-dredd for a source tree or module.\n\n"
            "This command writes an initial config, generates a baked baseline\n"
            "snapshot, and writes the chosen starting version to the VERSION file."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd init example.py.pygeometry1 --plugin python --version 1.0.0\n"
            "  semver-dredd init ./pkg/api --plugin go --version 1.0.0\n"
            "  semver-dredd init ./src/main/java --plugin java --version 1.0.0\n\n"
            "Notes:\n"
            "  - --plugin is required.\n"
            "  - The generated config records plugin, source.path, and VERSION path\n"
            "    so later status/bake/snapshot commands can often omit them."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Compare the current API surface against the baked baseline and write\n"
            "a current snapshot with the suggested next version."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd status mymodule --plugin python\n"
            "  semver-dredd status --details\n"
            "  semver-dredd status --path ./pkg/api --plugin go --details\n"
            "  semver-dredd status --allow-breaking\n\n"
            "Config-driven behavior:\n"
            "  If source.path and plugin are present in config, the positional path\n"
            "  may be omitted. CLI --path/--plugin still win and produce warnings\n"
            "  when they override config values."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Promote the current API surface to the new baked baseline and update\n"
            "the VERSION file."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd bake mymodule --plugin python\n"
            "  semver-dredd bake --version 2.0.0\n"
            "  semver-dredd bake --path ./pkg/api --plugin go\n\n"
            "Config-driven behavior:\n"
            "  If source.path is configured, bake can usually run without a\n"
            "  positional path. When an existing baked snapshot is present, the\n"
            "  new version is auto-computed from the detected change kind unless\n"
            "  --version is supplied explicitly."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Compare two source trees/modules directly without using baked.yaml.\n"
            "Useful for CI checks, review flows, and exploratory diffs."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd compare old_module new_module\n"
            "  semver-dredd compare ./v1/pkg ./v2/pkg --plugin go\n"
            "  semver-dredd compare old_module new_module --details --current 1.0.0\n"
            "  semver-dredd compare old_module new_module --verbose\n\n"
            "Notes:\n"
            "  - compare does not read source.path from config because it always\n"
            "    requires both old and new inputs explicitly."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Compute a new semantic version from a current version and a change\n"
            "kind (major/minor/patch/none)."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd bump --current 1.0.0 --change minor\n"
            "  semver-dredd bump --current 1.2.7 --change patch --quiet\n\n"
            "Notes:\n"
            "  - patch numbering uses the effective patch_scheme (config/env/CLI)."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Generate the next patch component according to the effective patch\n"
            "numbering scheme."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd patch\n"
            "  semver-dredd patch --current 20260305001\n\n"
            "Notes:\n"
            "  - With the default date scheme this yields YYYYMMDDZZZ.\n"
            "  - With integer scheme it yields the next integer patch value."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Generate a commented configuration template that documents the\n"
            "supported config surface."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd template\n"
            "  semver-dredd template --out .semver.yaml\n\n"
            "See also:\n"
            "  example/semver_showcase.yaml for a fuller copy-pasteable reference."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Generate a standalone API snapshot without comparing or baking it.\n"
            "This is useful for inspection, fixtures, and integration workflows."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd snapshot --plugin python --path mymodule --version 1.0.0\n"
            "  semver-dredd snapshot --out snapshot.yaml\n"
            "  semver-dredd snapshot --include api.v1 --exclude api.v1.internal\n\n"
            "Config-driven behavior:\n"
            "  plugin/path default from config when available. If --version is\n"
            "  omitted, semver-dredd reads the resolved VERSION file. CLI include\n"
            "  and exclude append to config arrays unless --override is used."
        ),
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
        formatter_class=RichHelpFormatter,
        description=(
            "Inspect installed/discoverable plugins and manage user-installed\n"
            "plugin distributions."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin list\n"
            "  semver-dredd plugin list --json\n"
            "  semver-dredd plugin info python\n"
            "  semver-dredd plugin install ./dist/vendor-plugin.whl\n"
            "  semver-dredd plugin remove vendor-plugin"
        ),
    )
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_cmd")
    plugin_list = plugin_sub.add_parser(
        "list",
        help="List discovered plugins",
        formatter_class=RichHelpFormatter,
        description=(
            "List discovered plugins from entry points, built-ins, and the user\n"
            "plugin directory."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin list\n"
            "  semver-dredd plugin list --json\n"
            "  semver-dredd plugin list --yaml"
        ),
    )
    plugin_list_format = plugin_list.add_mutually_exclusive_group()
    plugin_list_format.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
    plugin_list_format.add_argument(
        "--yaml",
        action="store_true",
        help="Emit machine-readable YAML output",
    )
    plugin_list.set_defaults(func=cmd_plugin_list)
    plugin_install = plugin_sub.add_parser(
        "install",
        help="Install a plugin distribution into the user plugin directory",
        formatter_class=RichHelpFormatter,
        description=(
            "Install a plugin distribution into semver-dredd's user plugin\n"
            "directory using pip semantics."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin install vendor-plugin\n"
            "  semver-dredd plugin install ./dist/vendor_plugin-1.0.0-py3-none-any.whl"
        ),
    )
    plugin_install.add_argument(
        "source",
        help="Anything pip install accepts (path, wheel, sdist, or package spec)",
    )
    plugin_install.set_defaults(func=cmd_plugin_install)
    plugin_remove = plugin_sub.add_parser(
        "remove",
        help="Remove a plugin from the user plugin directory (manifest-tracked)",
        formatter_class=RichHelpFormatter,
        description=(
            "Remove a plugin that was installed into semver-dredd's user plugin\n"
            "directory."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin remove go\n"
            "  semver-dredd plugin remove vendor-plugin"
        ),
    )
    plugin_remove.add_argument(
        "name",
        help="Plugin name to remove (e.g. 'go', 'java', 'python' or vendor plugin name)",
    )
    plugin_remove.set_defaults(func=cmd_plugin_remove)
    plugin_info = plugin_sub.add_parser(
        "info",
        help="Show details about a discovered plugin",
        formatter_class=RichHelpFormatter,
        description=(
            "Show metadata, provenance, scope information, and machine-readable\n"
            "details for a discovered plugin."
        ),
        epilog=(
            "Examples:\n"
            "  semver-dredd plugin info python\n"
            "  semver-dredd plugin info bundle --json\n"
            "  semver-dredd plugin info java --yaml"
        ),
    )
    plugin_info.add_argument(
        "name",
        help="Plugin name to inspect",
    )
    plugin_info_format = plugin_info.add_mutually_exclusive_group()
    plugin_info_format.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
    plugin_info_format.add_argument(
        "--yaml",
        action="store_true",
        help="Emit machine-readable YAML output",
    )
    plugin_info.set_defaults(func=cmd_plugin_info)

    def _plugin_help(_args: argparse.Namespace) -> int:
        plugin_parser.print_help()
        return EXIT_OK

    plugin_parser.set_defaults(func=_plugin_help)
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

    # Resolve command-scoped plugin/path/version/include/exclude context before
    # applying generic defaults. This is important for multi-document configs:
    # load_config() materializes only the first merged candidate, so pre-filling
    # args.plugin from Config here would incorrectly turn a config default into
    # an explicit override and break candidate fallback.
    try:
        resolved = resolve_command_context(args, loaded, cwd=Path.cwd())
    except ValueError as e:
        _print_level("error", str(e), use_color=False)
        return EXIT_ERROR

    # Apply generic defaults after command-scoped resolution so only genuinely
    # unset flags (allow_breaking, color, patch_scheme, etc.) are filled from
    # config without interfering with candidate selection.
    apply_config_defaults(args, config)

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
    _config_path = ""
    if loaded.config_exists:
        try:
            _config_path = (
                loaded.config_path.resolve()
                .relative_to(Path.cwd().resolve())
                .as_posix()
            )
        except ValueError:
            _config_path = str(loaded.config_path)

    args.generator_info = GeneratorInfo(
        plugin_name=resolved.plugin or "",
        plugin_version=_gen_plugin_version,
        plugin_source=_gen_plugin_source,
        config_path=_config_path,
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
