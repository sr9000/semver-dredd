"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import sys
from pathlib import Path
import subprocess

from semverdredd import Version, generate_patch
from semverdredd.snapshot import save_version_file
from semverdredd.snapshot_io import NormalizedSnapshot
from semverdredd.xldiff import ChangeType, DefaultDiffScorer, change_kind_to_type
from semverdredd.plugin_base import LanguagePlugin
from cli.config import load_config, apply_config_defaults, Config


def _resolve_snapshot_class(plugin: LanguagePlugin | None) -> type:
    """Return the snapshot class to use — the plugin's custom one or the default.

    The returned class satisfies the :class:`SnapshotFormat` protocol.
    """
    if plugin is not None:
        cls = plugin.snapshot_format_class
        if cls is not None:
            return cls
    return NormalizedSnapshot


def _resolve_diff_scorer(plugin: LanguagePlugin | None):
    """Return the diff scorer to use — the plugin's custom one or the default."""
    if plugin is not None:
        scorer = plugin.diff_scorer
        if scorer is not None:
            return scorer
    return DefaultDiffScorer()


def _diff_result_to_change_and_snapshot_diff(diff_result):
    """Convert a DiffResult to (ChangeType, SnapshotDiff) for backward compat."""
    from semverdredd.xldiff import SnapshotDiff
    change = change_kind_to_type(diff_result.change_kind)
    diff = SnapshotDiff(breaking=diff_result.breaking, added=diff_result.added)
    return change, diff


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BREAKING_CHANGES_DETECTED = 10

DEFAULT_CONFIG_FILE = ".semver.yaml"
DEFAULT_BAKED_FILE = "baked.yaml"
DEFAULT_CURRENT_FILE = "current.yaml"
DEFAULT_VERSION_FILE = "VERSION"



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
        "info": "\x1b[32m",   # green
        "warn": "\x1b[33m",   # yellow
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


def _severity_for_change(change: ChangeType) -> str:
    """Map change type to log severity level."""
    if change in (ChangeType.NONE, ChangeType.PATCH):
        return "info"
    if change == ChangeType.MINOR:
        return "warn"
    return "error"


def _get_change_descriptions() -> dict[ChangeType, str]:
    """Get human-readable descriptions for change types."""
    return {
        ChangeType.NONE: "No API changes detected (patch bump)",
        ChangeType.PATCH: "Implementation changes only (patch bump)",
        ChangeType.MINOR: "New features added (minor bump)",
        ChangeType.MAJOR: "Breaking changes detected (major bump)",
    }


def _get_language_plugin(plugin_name: str, use_color: bool) -> tuple[int, LanguagePlugin | None]:
    """Resolve a language plugin by name. Returns (exit_code, plugin)."""
    from semverdredd.plugin_manager import get_plugin

    plugin = get_plugin(plugin_name)
    if not plugin:
        _print_level("error", f"Unsupported language/plugin: {plugin_name}", use_color=use_color)
        return EXIT_ERROR, None
    return EXIT_OK, plugin


def _generate_snapshot_yaml(plugin_name: str, path: str, version: str, use_color: bool) -> tuple[int, str]:
    """Generate snapshot YAML using language-specific parser. Returns (exit_code, yaml_str)."""

    exit_code, plugin = _get_language_plugin(plugin_name, use_color)
    if exit_code != EXIT_OK or plugin is None:
        return EXIT_ERROR, ""

    ok, msg = plugin.validate_path(path)
    if not ok:
        _print_level("error", msg, use_color=use_color)
        return EXIT_ERROR, ""

    result = plugin.generate_snapshot(path, version, options={"use_color": use_color})

    if not result.success:
        _print_level("error", result.error_message or "Snapshot generation failed", use_color=use_color)
        return EXIT_ERROR, ""

    return EXIT_OK, result.yaml_content


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two modules/paths and report change type.

    This is the unified compare command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))

    # Handle default plugin
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    if getattr(args, "verbose", False):
        _print_level(
            "info",
            f"Using plugin '{plugin_name}' to compare modules/paths.",
            use_color=use_color,
        )

    # Generate snapshots for both old and new modules
    exit_code, old_yaml = _generate_snapshot_yaml(plugin_name, args.old_module, "0.0.0", use_color)
    if exit_code != EXIT_OK:
        return exit_code

    exit_code, new_yaml = _generate_snapshot_yaml(plugin_name, args.new_module, "0.0.0", use_color)
    if exit_code != EXIT_OK:
        return exit_code

    # Resolve plugin-specific snapshot class and diff scorer
    exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
    snap_cls = _resolve_snapshot_class(lang_plugin)
    scorer = _resolve_diff_scorer(lang_plugin)

    old_snapshot = snap_cls.from_yaml_str(old_yaml)
    new_snapshot = snap_cls.from_yaml_str(new_yaml)

    # Compare snapshots
    diff_result = scorer.diff(old_snapshot, new_snapshot)
    change, diff = _diff_result_to_change_and_snapshot_diff(diff_result)

    change_descriptions = _get_change_descriptions()

    severity = _severity_for_change(change)

    # Adjust severity for MAJOR changes when breaking changes are allowed
    allow_breaking = getattr(args, "allow_breaking", False)
    if change == ChangeType.MAJOR and allow_breaking:
        severity = "warn"

    # Output results
    _print_level(severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color)
    print(f"Change type: {change.name}")
    print(f"Description: {change_descriptions[change]}")

    if getattr(args, "details", False):
        if diff.breaking:
            print("Breaking changes:")
            for item in diff.breaking:
                print(f"  - {item}")
        if diff.added:
            print("Added changes:")
            for item in diff.added:
                print(f"  - {item}")
        if not diff.breaking and not diff.added:
            print("No API additions or breaking changes detected.")

    if getattr(args, "current", None):
        try:
            current = Version.parse(args.current)
            new_version = current.increment(change)
            print(f"Current version: {current}")
            print(f"Suggested version: {new_version}")
        except ValueError as e:
            _print_level("warn", f"Could not parse current version: {e}", use_color=use_color)

    # Policy gate: fail if breaking changes are detected and not allowed.
    if change == ChangeType.MAJOR and not allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    """Show current API status compared to baked baseline.

    This is the unified status command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))

    # Handle default plugin
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    # Parse --date if provided
    from datetime import date as date_type
    if getattr(args, "date", None):
        try:
            target_date = date_type.fromisoformat(args.date)
        except ValueError:
            _print_level("error", f"Invalid date format: {args.date}. Use YYYY-MM-DD.", use_color=use_color)
            return EXIT_ERROR
    else:
        target_date = date_type.today()

    baked_path = Path(getattr(args, "baked", None) or DEFAULT_BAKED_FILE)
    current_path = Path(getattr(args, "current_file", None) or DEFAULT_CURRENT_FILE)

    # Check if baked.yaml exists
    if not baked_path.exists():
        _print_level("warn", f"No {baked_path} found. Run 'init' or 'bake' first.", use_color=use_color)
        return EXIT_ERROR

    # Load baked snapshot
    exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
    snap_cls = _resolve_snapshot_class(lang_plugin)
    scorer = _resolve_diff_scorer(lang_plugin)

    baked = snap_cls.from_file(baked_path)

    # Generate current snapshot (use "0.0.0" placeholder, we'll compute suggested version)
    exit_code, yaml_str = _generate_snapshot_yaml(plugin_name, args.module, "0.0.0", use_color)
    if exit_code != EXIT_OK:
        return exit_code

    current = snap_cls.from_yaml_str(yaml_str)

    # Compare
    diff_result = scorer.diff(baked, current)
    change, diff = _diff_result_to_change_and_snapshot_diff(diff_result)

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
        suggested_version = current_version.increment(change, today=target_date)
    except ValueError as e:
        _print_level("error", str(e), use_color=use_color)
        return EXIT_ERROR

    severity = _severity_for_change(change)
    allow_breaking = getattr(args, "allow_breaking", False)
    if change == ChangeType.MAJOR and allow_breaking:
        severity = "warn"

    _print_level(severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color)
    print(f"Baked version: {baked.version}")
    print(f"Suggested version: {suggested_version}")

    if getattr(args, "details", False):
        if diff.breaking:
            print("Breaking changes:")
            for item in diff.breaking:
                print(f"  - {item}")
        if diff.added:
            print("Added changes:")
            for item in diff.added:
                print(f"  - {item}")
        if not diff.breaking and not diff.added:
            print("No API additions or breaking changes detected.")

    # Update current.yaml with suggested version
    import yaml
    current_dict = current.to_dict()
    current_dict["version"] = str(suggested_version)
    current_path.write_text(yaml.dump(current_dict, default_flow_style=False, sort_keys=False))
    _print_level("info", f"Updated {current_path}", use_color=use_color)

    # Policy gate
    if change == ChangeType.MAJOR and not allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK


def cmd_bake(args: argparse.Namespace) -> int:
    """Bake current API state as the new baseline.

    This is the unified bake command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))

    # Handle default plugin
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    baked_path = Path(getattr(args, "baked", None) or DEFAULT_BAKED_FILE)
    version_path = Path(getattr(args, "version_file", None) or DEFAULT_VERSION_FILE)

    # Determine version
    if getattr(args, "version", None):
        version = args.version
    elif baked_path.exists():
        # Load existing and compute next version
        exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
        snap_cls = _resolve_snapshot_class(lang_plugin)
        scorer = _resolve_diff_scorer(lang_plugin)

        baked = snap_cls.from_file(baked_path)

        # Generate current snapshot
        exit_code, yaml_str = _generate_snapshot_yaml(plugin_name, args.module, "0.0.0", use_color)
        if exit_code != EXIT_OK:
            return exit_code

        current = snap_cls.from_yaml_str(yaml_str)
        diff_result = scorer.diff(baked, current)
        change, _ = _diff_result_to_change_and_snapshot_diff(diff_result)

        current_version = Version.parse(baked.version)
        version = str(current_version.increment(change))
    else:
        # Default initial version
        version = f"0.1.{generate_patch()}"

    # Generate and save snapshot with final version
    exit_code, yaml_str = _generate_snapshot_yaml(plugin_name, args.module, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level("info", f"Baked API to {baked_path} with version {version}", use_color=use_color)

    # Update VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Updated {version_path}", use_color=use_color)

    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize semver-dredd for a project.

    This is the unified init command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))

    # Handle default plugin
    plugin_name = (getattr(args, "plugin", None) or "python").lower()

    config_path = Path(DEFAULT_CONFIG_FILE)
    baked_path = Path(getattr(args, "baked", None) or DEFAULT_BAKED_FILE)
    version_path = Path(getattr(args, "version_file", None) or DEFAULT_VERSION_FILE)

    version = getattr(args, "version", None) or f"0.1.{generate_patch()}"

    # Create config if not exists
    if not config_path.exists():
        default_config = f"""# semver-dredd configuration
schema_version: 1
plugin: {plugin_name}

policies:
  allow_breaking_changes: false

output:
  severity_by_change:
    none: info
    patch: info
    minor: warn
    major: error
"""
        config_path.write_text(default_config)
        _print_level("info", f"Created {config_path}", use_color=use_color)
    else:
        _print_level("info", f"{config_path} already exists", use_color=use_color)

    # Generate snapshot using plugin
    exit_code, yaml_str = _generate_snapshot_yaml(plugin_name, args.module, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level("info", f"Created {baked_path} with version {version}", use_color=use_color)

    # Create VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Created {version_path}", use_color=use_color)

    return EXIT_OK


def cmd_bump(args: argparse.Namespace) -> int:
    """Bump version based on change type."""
    use_color = _should_use_color(getattr(args, "color", None))

    try:
        current = Version.parse(args.current)
    except ValueError as e:
        _print_level("error", f"Error parsing version: {e}", use_color=use_color)
        return EXIT_ERROR

    change_map = {
        "major": ChangeType.MAJOR,
        "minor": ChangeType.MINOR,
        "patch": ChangeType.PATCH,
        "none": ChangeType.NONE,
    }

    change = change_map.get(args.change.lower())
    if change is None:
        _print_level("error", f"Invalid change type '{args.change}'", use_color=use_color)
        _print_level("error", f"Valid types: {', '.join(change_map.keys())}", use_color=use_color)
        return EXIT_ERROR

    new_version = current.increment(change)

    if args.quiet:
        print(new_version)
    else:
        print(f"Current: {current}")
        print(f"Change: {change.name}")
        print(f"New: {new_version}")

    return EXIT_OK


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



def cmd_snapshot(args: argparse.Namespace) -> int:
    """Generate a baked.yaml-like snapshot using language-specific parsers."""
    use_color = _should_use_color(getattr(args, "color", None))

    plugin_name = args.plugin.lower()
    version = args.version
    out_path = args.out

    exit_code, yaml_str = _generate_snapshot_yaml(plugin_name, args.path, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    if out_path:
        Path(out_path).write_text(yaml_str)
        _print_level("info", f"Wrote snapshot to {out_path}", use_color=use_color)
    else:
        print(yaml_str, end="")

    return EXIT_OK


def cmd_plugin_list(args: argparse.Namespace) -> int:
    """List discovered plugins."""
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import list_plugins

    plugins = list_plugins()
    if not plugins:
        _print_level("info", "No plugins found", use_color=use_color)
        return EXIT_OK

    for info in sorted(plugins, key=lambda i: i.name):
        p = info.plugin
        line = f"{info.name}\t{p.version}\t{p.description}"
        if info.origin:
            line += f"\t[{info.origin}]"
        _print_level("info", line, use_color=use_color)

    return EXIT_OK


def cmd_plugin_install(args: argparse.Namespace) -> int:
    """Install a plugin distribution into the user plugin directory."""
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    target_dir = mgr.ensure_plugin_dir()

    pip = [str(sys.executable), "-m", "pip"]

    cmd = pip + [
        "install",
        "--upgrade",
        "--target",
        str(target_dir),
        args.source,
    ]

    _print_level("info", f"Installing plugin into {target_dir}: {args.source}", use_color=use_color)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        _print_level("error", "Plugin installation failed", use_color=use_color)
        return EXIT_ERROR

    mgr.load_plugins(force=True)
    _print_level("info", "Plugin installed", use_color=use_color)
    return EXIT_OK


def cmd_plugin_remove(args: argparse.Namespace) -> int:
    """Remove a plugin installed in the user plugin directory."""
    use_color = _should_use_color(getattr(args, "color", None))

    import shutil

    from semverdredd.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    plugin_name = args.name.lower()

    target_dir = mgr.user_plugin_dir
    if not target_dir.exists():
        _print_level("error", f"Plugin directory does not exist: {target_dir}", use_color=use_color)
        return EXIT_ERROR

    # Best-effort removal by deleting matching package directories and dist-info.
    removed_any = False

    candidates = [
        target_dir / plugin_name,
        target_dir / f"semver_dredd_{plugin_name}",
        target_dir / f"semverdredd_{plugin_name}",
    ]

    for c in candidates:
        if c.exists() and c.is_dir():
            shutil.rmtree(c)
            removed_any = True

    # dist-info dirs
    patterns = [
        f"{plugin_name}-*.dist-info",
        f"semver_dredd_{plugin_name}-*.dist-info",
        f"semverdredd_{plugin_name}-*.dist-info",
        f"semver-dredd-{plugin_name}-*.dist-info",
    ]
    for pat in patterns:
        for dist in target_dir.glob(pat):
            if dist.is_dir():
                shutil.rmtree(dist)
                removed_any = True

    if not removed_any:
        _print_level(
            "error",
            f"Plugin '{plugin_name}' not found in {target_dir} (note: system-installed plugins can't be removed here)",
            use_color=use_color,
        )
        return EXIT_ERROR

    mgr.unregister(plugin_name)
    mgr.load_plugins(force=True)

    _print_level("info", f"Removed plugin '{plugin_name}' from {target_dir}", use_color=use_color)
    return EXIT_OK


def cmd_plugin_info(args: argparse.Namespace) -> int:
    """Show details about a discovered plugin."""
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    mgr.load_plugins()

    name = args.name.lower()
    info = next((i for i in mgr.list_plugins() if i.name == name), None)
    if info is None:
        _print_level("error", f"Plugin '{args.name}' not found", use_color=use_color)
        return EXIT_ERROR

    p = info.plugin
    print(f"Name: {info.name}")
    print(f"Display: {p.display_name}")
    print(f"Version: {p.version}")
    print(f"Origin: {info.origin}")
    if info.entry_point:
        print(f"Entry point: {info.entry_point}")
    print(f"Description: {p.description}")

    # Optional: parser assets location
    parser_path = getattr(p, "get_parser_resource_path", lambda: None)()
    if parser_path:
        print(f"Parser path: {parser_path}")

    return EXIT_OK



def cmd_template(args: argparse.Namespace) -> int:
    """Generate a comprehensive .semver.yaml template with all options and comments"""
    use_color = _should_use_color(getattr(args, "color", None))

    config_path = Path(DEFAULT_CONFIG_FILE)

    # Comprehensive template content with all options and comments
    template = """# semver-dredd configuration file
# This file configures semver-dredd behavior for your project.
# Place this file in your project root as '.semver.yaml'
#
# Configuration Priority (lowest to highest):
# 1. .semver.yaml (this file) - lowest priority
# 2. .env file - overrides .semver.yaml
# 3. Environment variables - override .env
# 4. CLI arguments - highest priority (always win)
#
# Note: This priority system only applies to CLI usage.
# Programmatic API calls ignore all config files.

# Schema version for this configuration file
# Currently supported: 1
schema_version: 1

# Project plugin (optional, defaults to 'python')
# Supported: python, go, java (or any installed plugin)
# Can be overridden by SEMVER_DREDD_PLUGIN env var or --plugin CLI arg
# plugin: python

# Policies section controls semver-dredd behavior
policies:
  # Whether to allow breaking changes (MAJOR version bumps)
  # If false, semver-dredd will exit with error code 10 when breaking changes are detected
  # If true, breaking changes are allowed but logged as warnings
  # Can be overridden by SEMVER_DREDD_ALLOW_BREAKING env var or --allow-breaking CLI flag
  allow_breaking_changes: false

# Output configuration
output:
  # Color mode for log output
  # true: always use ANSI colors
  # false: never use colors
  # null/omit: auto-detect (color if stderr is a TTY)
  # Can be overridden by SEMVER_DREDD_COLOR env var or --color/--no-color CLI flags
  # color: null

  # Severity levels for different change types
  # Controls the log level (info/warn/error) for each change type
  severity_by_change:
    # NONE: No API changes detected (but patch bump still occurs)
    none: info
    # PATCH: Implementation changes only
    patch: info
    # MINOR: New features added (backward compatible)
    minor: warn
    # MAJOR: Breaking changes detected
    major: error

# File paths configuration
# Can be overridden by environment variables or CLI arguments
files:
  # Baked API snapshot file
  # Env var: SEMVER_DREDD_BAKED_FILE
  # CLI: --baked
  baked: baked.yaml

  # Current API snapshot file (generated during status command)
  # Env var: SEMVER_DREDD_CURRENT_FILE
  # CLI: --current-file
  current: current.yaml

  # Version file
  # Env var: SEMVER_DREDD_VERSION_FILE
  # CLI: --version-file
  version: VERSION

# Module paths for Python projects (optional)
# Specify additional module paths to include in API analysis
# module_paths:
#   - mypackage
#   - ../anotherpackage

# Go-specific configuration (optional)
# go:
#   # Go module name (from go.mod)
#   module: mymodule
#   # Output directory for generated files
#   output: ./gen

# Java-specific configuration (optional)
# java:
#   # Source directory for Java files
#   source: ./src/main/java
#   # Output directory for generated files
#   output: ./gen

# Advanced options (experimental)
# advanced:
#   # Whether to include private API in snapshots (default: false)
#   include_private: false
#   # Custom ignore patterns for API elements
#   ignore_patterns:
#     - "test_*"
#     - "*_internal"

# Environment Variables Reference:
# ================================
# SEMVER_DREDD_ALLOW_BREAKING - Set to 'true' or 'false'
# SEMVER_DREDD_COLOR - Set to 'true' or 'false'
# SEMVER_DREDD_PLUGIN - Set to 'python', 'go', or 'java' (or plugin name)
# SEMVER_DREDD_BAKED_FILE - Path to baked.yaml
# SEMVER_DREDD_CURRENT_FILE - Path to current.yaml
# SEMVER_DREDD_VERSION_FILE - Path to VERSION file
#
# .env file example:
# ------------------
# SEMVER_DREDD_ALLOW_BREAKING=true
# SEMVER_DREDD_COLOR=false
# SEMVER_DREDD_BAKED_FILE=api/baked.yaml
"""

    # Write to file or print to stdout
    if args.out:
        Path(args.out).write_text(template)
        _print_level("info", f"Wrote template to {args.out}", use_color=use_color)
    else:
        print(template)

    return EXIT_OK


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
        "--version", "-v",
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
        "--current", "-c",
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
        "--current", "-c",
        required=True,
        help="Current version string",
    )
    bump_parser.add_argument(
        "--change", "-t",
        required=True,
        choices=["major", "minor", "patch", "none"],
        help="Type of change",
    )
    bump_parser.add_argument(
        "--quiet", "-q",
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
        "--current", "-c",
        help="Current patch version (to increment if same day)",
    )
    patch_parser.set_defaults(func=cmd_patch)

    # Template command
    template_parser = subparsers.add_parser(
        "template",
        help="Generate a comprehensive .semver.yaml configuration template",
    )
    template_parser.add_argument(
        "--out", "-o",
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
            _print_level("error", "--allow-breaking and --disallow-breaking are mutually exclusive")
            return EXIT_ERROR

    # Apply config defaults (respects CLI args as highest priority)
    apply_config_defaults(args, config)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
