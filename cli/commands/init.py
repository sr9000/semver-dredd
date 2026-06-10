"""init command — initialize semver-dredd for a project."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.utils import (
    DEFAULT_BAKED_FILE,
    DEFAULT_CONFIG_FILE,
    DEFAULT_VERSION_FILE,
    EXIT_OK,
    _generate_snapshot_yaml,
    _print_level,
    _should_use_color,
)
from semverdredd import generate_patch
from semverdredd.version import save_version_file


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

    scheme = getattr(args, "patch_scheme", None) or "date"
    version = getattr(args, "version", None) or f"0.1.{generate_patch(scheme=scheme)}"

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
    exit_code, yaml_str = _generate_snapshot_yaml(
        plugin_name,
        args.module,
        version,
        use_color,
        extra_options=getattr(args, "snapshot_options", None),
    )
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level(
        "info", f"Created {baked_path} with version {version}", use_color=use_color
    )

    # Create VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Created {version_path}", use_color=use_color)

    return EXIT_OK
