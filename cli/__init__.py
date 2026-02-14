"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import importlib
import sys
from pathlib import Path

from semverdredd import ChangeType, Version, detect_change, generate_patch


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BREAKING_CHANGES_DETECTED = 10


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
    # Default mapping (can be expanded later via meta.yaml/config)
    if change in (ChangeType.NONE, ChangeType.PATCH):
        return "info"
    if change == ChangeType.MINOR:
        return "warn"
    return "error"


def import_module_from_path(module_path: str):
    """
    Import a module from a file path or module name.

    Args:
        module_path: Either a dotted module name (e.g., 'example.pygeometry1')
                     or a file path (e.g., './mymodule/__init__.py')

    Returns:
        Imported module object
    """
    path = Path(module_path)

    if path.exists():
        # It's a file path
        if path.is_dir():
            # Directory with __init__.py
            init_file = path / "__init__.py"
            if not init_file.exists():
                raise ValueError(f"Directory {path} is not a package (no __init__.py)")
            module_name = path.name
            sys.path.insert(0, str(path.parent))
        else:
            # Single file
            module_name = path.stem
            sys.path.insert(0, str(path.parent))

        try:
            return importlib.import_module(module_name)
        finally:
            sys.path.pop(0)
    else:
        # Try as a dotted module name
        return importlib.import_module(module_path)


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two modules and report change type."""
    use_color = _should_use_color(getattr(args, "color", None))

    try:
        old_module = import_module_from_path(args.old_module)
        new_module = import_module_from_path(args.new_module)
    except ImportError as e:
        _print_level("error", f"Error importing module: {e}", use_color=use_color)
        return EXIT_ERROR
    except ValueError as e:
        _print_level("error", f"Error: {e}", use_color=use_color)
        return EXIT_ERROR

    change = detect_change(old_module, new_module)

    change_descriptions = {
        ChangeType.NONE: "No API changes detected",
        ChangeType.PATCH: "Implementation changes only (patch bump)",
        ChangeType.MINOR: "New features added (minor bump)",
        ChangeType.MAJOR: "Breaking changes detected (major bump)",
    }

    severity = _severity_for_change(change)

    # Keep existing human-friendly output, but route severity summary to stderr.
    _print_level(severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color)
    print(f"Change type: {change.name}")
    print(f"Description: {change_descriptions[change]}")

    if args.current:
        try:
            current = Version.parse(args.current)
            new_version = current.increment(change)
            print(f"Current version: {current}")
            print(f"Suggested version: {new_version}")
        except ValueError as e:
            _print_level("warn", f"Could not parse current version: {e}", use_color=use_color)

    # Policy gate: fail if breaking changes are detected and not allowed.
    if change == ChangeType.MAJOR and not args.allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

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


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="semver-dredd",
        description="Automatically increment semver based on API changes",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two modules and detect change type",
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

    args = parser.parse_args(argv)

    # For compare: by default breaking changes are disallowed.
    if getattr(args, "command", None) == "compare":
        if args.allow_breaking and args.disallow_breaking:
            _print_level("error", "--allow-breaking and --disallow-breaking are mutually exclusive")
            return EXIT_ERROR
        args.allow_breaking = bool(args.allow_breaking) and not bool(args.disallow_breaking)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
