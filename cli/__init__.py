"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import importlib
import sys
from pathlib import Path

from semverdredd import ChangeType, Version, detect_change, generate_patch


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
    try:
        old_module = import_module_from_path(args.old_module)
        new_module = import_module_from_path(args.new_module)
    except ImportError as e:
        print(f"Error importing module: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    change = detect_change(old_module, new_module)

    change_descriptions = {
        ChangeType.NONE: "No API changes detected",
        ChangeType.PATCH: "Implementation changes only (patch bump)",
        ChangeType.MINOR: "New features added (minor bump)",
        ChangeType.MAJOR: "Breaking changes detected (major bump)",
    }

    print(f"Change type: {change.name}")
    print(f"Description: {change_descriptions[change]}")

    if args.current:
        try:
            current = Version.parse(args.current)
            new_version = current.increment(change)
            print(f"Current version: {current}")
            print(f"Suggested version: {new_version}")
        except ValueError as e:
            print(f"Warning: Could not parse current version: {e}", file=sys.stderr)

    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    """Bump version based on change type."""
    try:
        current = Version.parse(args.current)
    except ValueError as e:
        print(f"Error parsing version: {e}", file=sys.stderr)
        return 1

    change_map = {
        "major": ChangeType.MAJOR,
        "minor": ChangeType.MINOR,
        "patch": ChangeType.PATCH,
        "none": ChangeType.NONE,
    }

    change = change_map.get(args.change.lower())
    if change is None:
        print(f"Error: Invalid change type '{args.change}'", file=sys.stderr)
        print(f"Valid types: {', '.join(change_map.keys())}", file=sys.stderr)
        return 1

    new_version = current.increment(change)

    if args.quiet:
        print(new_version)
    else:
        print(f"Current: {current}")
        print(f"Change: {change.name}")
        print(f"New: {new_version}")

    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    """Generate a new patch version."""
    current = int(args.current) if args.current else None

    try:
        new_patch = generate_patch(current_patch=current)
        print(new_patch)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


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
    compare_parser.set_defaults(func=cmd_compare)

    # Bump command
    bump_parser = subparsers.add_parser(
        "bump",
        help="Bump version based on change type",
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
        "--current", "-c",
        help="Current patch version (to increment if same day)",
    )
    patch_parser.set_defaults(func=cmd_patch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
