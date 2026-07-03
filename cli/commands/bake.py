"""bake command — bake current API state as the new baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.utils import (DEFAULT_BAKED_FILE, DEFAULT_VERSION_FILE, EXIT_ERROR,
                       EXIT_OK, _generate_snapshot_yaml, _get_language_plugin,
                       _print_level, _resolve_snapshot_class, _run_diff,
                       _should_use_color)
from semverdredd import Version, generate_patch
from semverdredd.version import save_version_file


def cmd_bake(args: argparse.Namespace) -> int:
    """Bake current API state as the new baseline.

    This is the unified bake command that works with any plugin.
    The plugin is responsible for extracting meta information and API state.
    """
    use_color = _should_use_color(getattr(args, "color", None))
    plugin_name = (getattr(args, "plugin", None) or "python").lower()
    if not getattr(args, "module", None):
        _print_level(
            "error",
            "No source path/module provided. Pass positional module/--path or configure source.path.",
            use_color=use_color,
        )
        return EXIT_ERROR

    baked_path = Path(getattr(args, "baked", None) or DEFAULT_BAKED_FILE)
    version_path = Path(getattr(args, "version_file", None) or DEFAULT_VERSION_FILE)

    # Determine version
    if getattr(args, "version", None):
        version = args.version
    elif baked_path.exists():
        # Load existing and compute next version
        exit_code, lang_plugin = _get_language_plugin(plugin_name, use_color)
        snap_cls = _resolve_snapshot_class(lang_plugin)

        baked = snap_cls.from_file(baked_path)

        # Generate current snapshot
        exit_code, yaml_str = _generate_snapshot_yaml(
            plugin_name,
            args.module,
            "0.0.0",
            use_color,
            extra_options=getattr(args, "snapshot_options", None),
            generator=getattr(args, "generator_info", None),
        )
        if exit_code != EXIT_OK:
            return exit_code

        current = snap_cls.from_yaml_str(yaml_str)
        diff_result = _run_diff(baked, current, lang_plugin)
        change = diff_result.change_kind

        current_version = Version.parse(baked.version)
        scheme = getattr(args, "patch_scheme", None) or "date"
        version = str(current_version.increment(change, scheme=scheme))
    else:
        # Default initial version
        scheme = getattr(args, "patch_scheme", None) or "date"
        version = f"0.1.{generate_patch(scheme=scheme)}"

    # Generate and save snapshot with final version
    exit_code, yaml_str = _generate_snapshot_yaml(
        plugin_name,
        args.module,
        version,
        use_color,
        extra_options=getattr(args, "snapshot_options", None),
        generator=getattr(args, "generator_info", None),
    )
    if exit_code != EXIT_OK:
        return exit_code

    baked_path.write_text(yaml_str)
    _print_level(
        "info", f"Baked API to {baked_path} with version {version}", use_color=use_color
    )

    # Update VERSION file
    save_version_file(version, version_path)
    _print_level("info", f"Updated {version_path}", use_color=use_color)

    return EXIT_OK
