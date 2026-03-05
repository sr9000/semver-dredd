"""plugin commands — list, install, remove, and inspect language plugins."""

from __future__ import annotations

import argparse
import subprocess
import sys

from cli.utils import EXIT_ERROR, EXIT_OK, _print_level, _should_use_color


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

    _print_level(
        "info",
        f"Installing plugin into {target_dir}: {args.source}",
        use_color=use_color,
    )
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
        _print_level(
            "error",
            f"Plugin directory does not exist: {target_dir}",
            use_color=use_color,
        )
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

    _print_level(
        "info", f"Removed plugin '{plugin_name}' from {target_dir}", use_color=use_color
    )
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
