"""
CLI tool for semver-dredd that compares modules and manages versions.
"""

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any
import subprocess

from semverdredd import ChangeType, Version, detect_change, generate_patch, ModuleAPI, compare_modules
from semverdredd.diff import diff_module_objects, diff_modules
from semverdredd.snapshot import APISnapshot, save_version_file


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BREAKING_CHANGES_DETECTED = 10

DEFAULT_CONFIG_FILE = ".semver.yaml"
DEFAULT_BAKED_FILE = "baked.yaml"
DEFAULT_CURRENT_FILE = "current.yaml"
DEFAULT_VERSION_FILE = "VERSION"


def _load_config() -> dict[str, Any]:
    """Load configuration from .semver.yaml if it exists in the current directory."""
    config_path = Path(DEFAULT_CONFIG_FILE)
    if not config_path.exists():
        return {}

    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config or {}
    except ImportError:
        # yaml not available, skip
        return {}
    except Exception:
        # Invalid yaml or other error, skip
        return {}


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
        module_path: Either a dotted module name (e.g., 'example.gogeometry1')
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

    if getattr(args, "verbose", False):
        _print_level(
            "info",
            "Inspecting public module API: exported functions/classes from dir(module) excluding '_' names; "
            "for classes: methods from dir(class) excluding '_' names (except __init__) and comparing call signatures.",
            use_color=use_color,
        )

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

    # Adjust severity for MAJOR changes when breaking changes are allowed
    if change == ChangeType.MAJOR and args.allow_breaking:
        severity = "warn"

    # Keep existing human-friendly output, but route severity summary to stderr.
    _print_level(severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color)
    print(f"Change type: {change.name}")
    print(f"Description: {change_descriptions[change]}")

    if getattr(args, "details", False):
        diff = diff_module_objects(old_module, new_module)
        if diff.breaking:
            print("Breaking changes:")
            for item in diff.breaking:
                print(f"- {item}")
        if diff.added:
            print("Added changes:")
            for item in diff.added:
                print(f"- {item}")
        if not diff.breaking and not diff.added:
            print("No API additions or breaking changes detected.")

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


def cmd_status(args: argparse.Namespace) -> int:
    """Show current API status compared to baked baseline."""
    use_color = _should_use_color(getattr(args, "color", None))

    # If lang is not python, delegate to xl logic
    if hasattr(args, "lang") and args.lang != "python":
        args.path = args.module
        return cmd_xl_status(args)

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

    baked_path = Path(getattr(args, "baked", DEFAULT_BAKED_FILE))
    current_path = Path(getattr(args, "current_file", DEFAULT_CURRENT_FILE))
    version_path = Path(getattr(args, "version_file", DEFAULT_VERSION_FILE))

    # Check if baked.yaml exists
    if not baked_path.exists():
        _print_level("warn", f"No {baked_path} found. Run 'init' or 'bake' first.", use_color=use_color)
        return EXIT_ERROR

    # Load module
    try:
        module = import_module_from_path(args.module)
    except ImportError as e:
        _print_level("error", f"Error importing module: {e}", use_color=use_color)
        return EXIT_ERROR
    except ValueError as e:
        _print_level("error", f"Error: {e}", use_color=use_color)
        return EXIT_ERROR

    # Load baked API
    baked = APISnapshot.load(baked_path)
    baked_api = baked.to_module_api()
    current_api = ModuleAPI.from_module(module)

    # Compare
    change = compare_modules(baked_api, current_api)
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

    try:
        suggested_version = current_version.increment(change, today=target_date)
    except ValueError as e:
        _print_level("error", str(e), use_color=use_color)
        return EXIT_ERROR

    change_descriptions = {
        ChangeType.NONE: "No API changes detected (patch bump)",
        ChangeType.PATCH: "Implementation changes only (patch bump)",
        ChangeType.MINOR: "New features added (minor bump)",
        ChangeType.MAJOR: "Breaking changes detected (major bump)",
    }

    severity = _severity_for_change(change)
    if change == ChangeType.MAJOR and args.allow_breaking:
        severity = "warn"

    _print_level(severity, f"{change.name}: {change_descriptions[change]}", use_color=use_color)
    print(f"Baked version: {baked.version}")
    print(f"Suggested version: {suggested_version}")

    if getattr(args, "details", False):
        diff = diff_modules(baked_api, current_api)
        if diff.breaking:
            print("Breaking changes:")
            for item in diff.breaking:
                print(f"- {item}")
        if diff.added:
            print("Added changes:")
            for item in diff.added:
                print(f"- {item}")
        if not diff.breaking and not diff.added:
            print("No API additions or breaking changes detected.")

    # Update current.yaml
    current_snapshot = APISnapshot.from_module_api(current_api, str(suggested_version))
    current_snapshot.save(current_path)
    _print_level("info", f"Updated {current_path}", use_color=use_color)

    # Policy gate
    if change == ChangeType.MAJOR and not args.allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK


def cmd_bake(args: argparse.Namespace) -> int:
    """Bake current API state as the new baseline."""
    use_color = _should_use_color(getattr(args, "color", None))

    # If lang is not python, delegate to xl logic
    if hasattr(args, "lang") and args.lang != "python":
        args.path = args.module
        return cmd_xl_bake(args)

    baked_path = Path(getattr(args, "baked", DEFAULT_BAKED_FILE))
    version_path = Path(getattr(args, "version_file", DEFAULT_VERSION_FILE))

    # Load module
    try:
        module = import_module_from_path(args.module)
    except ImportError as e:
        _print_level("error", f"Error importing module: {e}", use_color=use_color)
        return EXIT_ERROR
    except ValueError as e:
        _print_level("error", f"Error: {e}", use_color=use_color)
        return EXIT_ERROR

    # Determine version
    if args.version:
        version = args.version
    elif baked_path.exists():
        # Load existing and compute next version
        baked = APISnapshot.load(baked_path)
        baked_api = baked.to_module_api()
        current_api = ModuleAPI.from_module(module)
        change = compare_modules(baked_api, current_api)
        current_version = Version.parse(baked.version)
        version = str(current_version.increment(change))
    else:
        # Default initial version
        version = f"0.1.{generate_patch()}"

    # Create and save snapshot
    snapshot = APISnapshot.from_module(module, version)
    snapshot.save(baked_path)
    _print_level("info", f"Baked API to {baked_path} with version {version}", use_color=use_color)

    # Update VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Updated {version_path}", use_color=use_color)

    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize semver-dredd for a project."""
    use_color = _should_use_color(getattr(args, "color", None))

    # If lang is not python, delegate to xl logic
    if hasattr(args, "lang") and args.lang != "python":
        # Remap args for delegation
        args.path = args.module
        return cmd_xl_init(args)

    config_path = Path(DEFAULT_CONFIG_FILE)
    baked_path = Path(getattr(args, "baked", DEFAULT_BAKED_FILE))
    version_path = Path(getattr(args, "version_file", DEFAULT_VERSION_FILE))

    # Create config if not exists
    if not config_path.exists():
        default_config = """# semver-dredd configuration
schema_version: 1

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

    # Load module and create initial baked.yaml
    try:
        module = import_module_from_path(args.module)
    except ImportError as e:
        _print_level("error", f"Error importing module: {e}", use_color=use_color)
        return EXIT_ERROR
    except ValueError as e:
        _print_level("error", f"Error: {e}", use_color=use_color)
        return EXIT_ERROR

    version = args.version or f"0.1.{generate_patch()}"

    snapshot = APISnapshot.from_module(module, version)
    snapshot.save(baked_path)
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


def _generate_snapshot_yaml(lang: str, path: str, version: str, use_color: bool) -> tuple[int, str]:
    """Generate snapshot YAML using language-specific parser. Returns (exit_code, yaml_str)."""
    import tempfile

    if lang == "go":
        parser_dir = Path(__file__).parent.parent / "parser" / "golang"
        cmd = [
            "go", "run", ".",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]
        cwd = str(parser_dir)
    elif lang == "java":
        java_dir = Path(__file__).parent.parent / "parser" / "java"
        jar = java_dir / "lib" / "snakeyaml-2.2.jar"
        src = java_dir / "main.java"

        if not jar.exists():
            _print_level(
                "error",
                f"Missing {jar}. Install snakeyaml jar or use Maven build.",
                use_color=use_color,
            )
            return EXIT_ERROR, ""

        # Compile
        compile_cmd = ["javac", "-cp", str(jar), str(src)]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            _print_level("error", f"javac failed: {e.stderr or e}", use_color=use_color)
            return EXIT_ERROR, ""

        cmd = [
            "java", "-cp", f"{jar}:{java_dir}", "main",
            "--dir", str(Path(path).absolute()),
            "--version", version,
        ]
        cwd = None
    else:
        _print_level("error", f"Unsupported language: {lang}", use_color=use_color)
        return EXIT_ERROR, ""

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=cwd)
        return EXIT_OK, result.stdout
    except FileNotFoundError as e:
        _print_level("error", f"Missing tool: {e}", use_color=use_color)
        return EXIT_ERROR, ""
    except subprocess.CalledProcessError as e:
        _print_level("error", f"Parser failed: {e.stderr or e}", use_color=use_color)
        return e.returncode or EXIT_ERROR, ""


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Generate a baked.yaml-like snapshot using language-specific parsers."""
    use_color = _should_use_color(getattr(args, "color", None))

    lang = args.lang.lower()
    version = args.version
    out_path = args.out

    exit_code, yaml_str = _generate_snapshot_yaml(lang, args.path, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    if out_path:
        Path(out_path).write_text(yaml_str)
        _print_level("info", f"Wrote snapshot to {out_path}", use_color=use_color)
    else:
        print(yaml_str, end="")

    return EXIT_OK


def cmd_xl_init(args: argparse.Namespace) -> int:
    """Initialize semver-dredd for a Go/Java project."""
    use_color = _should_use_color(getattr(args, "color", None))

    config_path = Path(DEFAULT_CONFIG_FILE)
    baked_path = Path(DEFAULT_BAKED_FILE)
    version_path = Path(DEFAULT_VERSION_FILE)

    lang = args.lang.lower()
    version = args.version or f"0.1.{generate_patch()}"

    # Create config if not exists
    if not config_path.exists():
        default_config = f"""# semver-dredd configuration
schema_version: 1
language: {lang}

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

    # Generate snapshot
    exit_code, yaml_str = _generate_snapshot_yaml(lang, args.path, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level("info", f"Created {baked_path} with version {version}", use_color=use_color)

    # Create VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Created {version_path}", use_color=use_color)

    return EXIT_OK


def cmd_xl_status(args: argparse.Namespace) -> int:
    """Show current API status for Go/Java project compared to baked baseline"""
    use_color = _should_use_color(getattr(args, "color", None))

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

    baked_path = Path(DEFAULT_BAKED_FILE)
    current_path = Path(DEFAULT_CURRENT_FILE)

    if not baked_path.exists():
        _print_level("warn", f"No {baked_path} found. Run 'init' first.", use_color=use_color)
        return EXIT_ERROR

    lang = args.lang.lower()

    # Load baked snapshot
    from semverdredd.snapshot_io import load_snapshot
    from semverdredd.xldiff import compare_snapshots, ChangeType as XLChangeType

    baked = load_snapshot(baked_path)

    # Generate current snapshot (use "0.0.0" placeholder, we'll compute suggested version)
    exit_code, yaml_str = _generate_snapshot_yaml(lang, args.path, "0.0.0", use_color)
    if exit_code != EXIT_OK:
        return exit_code

    from semverdredd.snapshot_io import NormalizedSnapshot
    current = NormalizedSnapshot.from_yaml_str(yaml_str)

    # Compare
    change, diff = compare_snapshots(baked, current)

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

    # Map XLChangeType to semverdredd.ChangeType for version increment
    change_map = {
        XLChangeType.NONE: ChangeType.NONE,
        XLChangeType.PATCH: ChangeType.PATCH,
        XLChangeType.MINOR: ChangeType.MINOR,
        XLChangeType.MAJOR: ChangeType.MAJOR,
    }

    try:
        suggested_version = current_version.increment(change_map[change], today=target_date)
    except ValueError as e:
        _print_level("error", str(e), use_color=use_color)
        return EXIT_ERROR

    change_descriptions = {
        XLChangeType.NONE: "No API changes detected (patch bump)",
        XLChangeType.PATCH: "Implementation changes only (patch bump)",
        XLChangeType.MINOR: "New features added (minor bump)",
        XLChangeType.MAJOR: "Breaking changes detected (major bump)",
    }

    severity = _severity_for_change(change_map[change])
    allow_breaking = getattr(args, "allow_breaking", False)
    if change == XLChangeType.MAJOR and allow_breaking:
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
    current_dict = current.to_dict()
    current_dict["version"] = str(suggested_version)
    import yaml
    current_path.write_text(yaml.dump(current_dict, default_flow_style=False, sort_keys=False))
    _print_level("info", f"Updated {current_path}", use_color=use_color)

    # Policy gate
    if change == XLChangeType.MAJOR and not allow_breaking:
        _print_level(
            "error",
            "Breaking changes are not allowed (use --allow-breaking to override)",
            use_color=use_color,
        )
        return EXIT_BREAKING_CHANGES_DETECTED

    return EXIT_OK


def cmd_xl_bake(args: argparse.Namespace) -> int:
    """Bake current API state as the new baseline for Go/Java project."""
    use_color = _should_use_color(getattr(args, "color", None))

    baked_path = Path(DEFAULT_BAKED_FILE)
    version_path = Path(DEFAULT_VERSION_FILE)

    lang = args.lang.lower()

    # Determine version
    if args.version:
        version = args.version
    elif baked_path.exists():
        # Load existing and compute next version
        from semverdredd.snapshot_io import load_snapshot, NormalizedSnapshot
        from semverdredd.xldiff import compare_snapshots, ChangeType as XLChangeType

        baked = load_snapshot(baked_path)

        # Generate current snapshot
        exit_code, yaml_str = _generate_snapshot_yaml(lang, args.path, "0.0.0", use_color)
        if exit_code != EXIT_OK:
            return exit_code

        current = NormalizedSnapshot.from_yaml_str(yaml_str)
        change, _ = compare_snapshots(baked, current)

        current_version = Version.parse(baked.version)
        change_map = {
            XLChangeType.NONE: ChangeType.NONE,
            XLChangeType.PATCH: ChangeType.PATCH,
            XLChangeType.MINOR: ChangeType.MINOR,
            XLChangeType.MAJOR: ChangeType.MAJOR,
        }
        version = str(current_version.increment(change_map[change]))
    else:
        version = f"0.1.{generate_patch()}"

    # Generate and save snapshot with final version
    exit_code, yaml_str = _generate_snapshot_yaml(lang, args.path, version, use_color)
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level("info", f"Baked API to {baked_path} with version {version}", use_color=use_color)

    # Update VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Updated {version_path}", use_color=use_color)

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
        "--lang",
        choices=["python", "go", "java"],
        default="python",
        help="Project language (default: python)",
    )
    init_parser.add_argument(
        "--version", "-v",
        help="Initial version (default: 0.1.YYYYMMDD001)",
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
        "--lang",
        choices=["python", "go", "java"],
        default="python",
        help="Project language (default: python)",
    )
    status_parser.add_argument(
        "--date",
        help="Date to use for patch version (YYYY-MM-DD, default: today)",
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
        "--lang",
        choices=["python", "go", "java"],
        default="python",
        help="Project language (default: python)",
    )
    bake_parser.add_argument(
        "--version",
        help="Explicit version to bake (default: auto-computed)",
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

    # Snapshot command
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Generate an API snapshot for a Go/Java project (baked.yaml-like)",
    )
    snapshot_parser.add_argument(
        "--lang",
        required=True,
        choices=["go", "java"],
        help="Language parser to use",
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


    args = parser.parse_args(argv)

    # Load config and apply defaults
    config = _load_config()
    policies = config.get("policies", {})

    # For compare/status: set default allow_breaking from config if not explicitly set
    if getattr(args, "command", None) in ("compare", "status"):
        allow = getattr(args, "allow_breaking", False)
        disallow = getattr(args, "disallow_breaking", False)
        if not allow and not disallow:
            default_allow = policies.get("allow_breaking_changes", False)
            args.allow_breaking = bool(default_allow)
        elif allow and disallow:
            _print_level("error", "--allow-breaking and --disallow-breaking are mutually exclusive")
            return EXIT_ERROR
        else:
            args.allow_breaking = bool(allow) and not bool(disallow)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
