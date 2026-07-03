"""plugin commands — list, install, remove, and inspect language plugins."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from cli.utils import EXIT_ERROR, EXIT_OK, _print_level, _should_use_color

# Manifest of plugins installed via `semver-dredd plugin install`.
# Maps manifest key (plugin name or source spec) → {"source", "paths"}.
MANIFEST_FILENAME = "installed_plugins.json"


def _manifest_path(plugin_dir: Path) -> Path:
    return plugin_dir / MANIFEST_FILENAME


def _load_manifest(plugin_dir: Path) -> dict:
    """Load the installed-plugin manifest (empty dict when absent/corrupt)."""
    path = _manifest_path(plugin_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[WARN] Could not read plugin manifest {path}: {e}",
            file=sys.stderr,
        )
        return {}


def _save_manifest(plugin_dir: Path, manifest: dict) -> None:
    _manifest_path(plugin_dir).write_text(json.dumps(manifest, indent=2, sort_keys=True))


def _record_installation(
    plugin_dir: Path,
    keys: list[str],
    source: str,
    new_paths: list[str],
) -> None:
    """Record an installation in the manifest under each plugin-name key."""
    manifest = _load_manifest(plugin_dir)
    entry = {"source": source, "paths": sorted(new_paths)}
    for key in keys or [source]:
        manifest[key.lower()] = entry
    _save_manifest(plugin_dir, manifest)


def _emit_plugin_inventory(payload: object, args: argparse.Namespace) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if getattr(args, "yaml", False):
        print(yaml.safe_dump(payload, sort_keys=True), end="")
        return


def cmd_plugin_list(args: argparse.Namespace) -> int:
    """List discovered plugins."""
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import get_plugin_manager, list_plugins

    plugins = list_plugins()
    if not plugins:
        _print_level("info", "No plugins found", use_color=use_color)
        return EXIT_OK

    if getattr(args, "json", False) or getattr(args, "yaml", False):
        payload = get_plugin_manager().list_plugin_metadata()
        payload.sort(key=lambda item: item["name"])
        _emit_plugin_inventory(payload, args)
        return EXIT_OK

    for info in sorted(plugins, key=lambda i: i.name):
        p = info.plugin
        line = f"{info.name}\t{p.version}\t{p.description}"
        if info.origin:
            line += f"\t[{info.origin}]"
        _print_level("info", line, use_color=use_color)

    return EXIT_OK


def cmd_plugin_install(args: argparse.Namespace) -> int:
    """Install a plugin distribution into the user plugin directory.

    The installation is recorded in a manifest file so `plugin remove`
    can delete exactly what was installed.
    """
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    target_dir = mgr.ensure_plugin_dir()

    entries_before = {p.name for p in target_dir.iterdir()}
    names_before = set(mgr.list_names())

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

    # Record exactly what this installation created.
    entries_after = {p.name for p in target_dir.iterdir()}
    new_paths = sorted(entries_after - entries_before - {MANIFEST_FILENAME})
    new_plugin_names = sorted(set(mgr.list_names()) - names_before)
    _record_installation(target_dir, new_plugin_names, args.source, new_paths)

    _print_level("info", "Plugin installed", use_color=use_color)
    if new_plugin_names:
        _print_level(
            "info",
            f"New plugins available: {', '.join(new_plugin_names)}",
            use_color=use_color,
        )
    return EXIT_OK


def _remove_paths(target_dir: Path, names: list[str]) -> list[str]:
    """Delete the given entries inside target_dir. Returns what was removed."""
    import shutil

    removed = []
    for name in names:
        p = target_dir / name
        if p.is_dir():
            shutil.rmtree(p)
            removed.append(name)
        elif p.exists():
            p.unlink()
            removed.append(name)
    return removed


def _legacy_glob_removal(target_dir: Path, plugin_name: str) -> list[str]:
    """Best-effort removal for plugins not tracked in the manifest."""
    import shutil

    removed = []

    candidates = [
        target_dir / plugin_name,
        target_dir / f"semver_dredd_{plugin_name}",
        target_dir / f"semverdredd_{plugin_name}",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            shutil.rmtree(c)
            removed.append(c.name)

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
                removed.append(dist.name)

    return removed


def cmd_plugin_remove(args: argparse.Namespace) -> int:
    """Remove a plugin installed in the user plugin directory.

    Uses the installed-plugin manifest when available; falls back to
    best-effort name matching for untracked installs.
    """
    use_color = _should_use_color(getattr(args, "color", None))

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

    manifest = _load_manifest(target_dir)
    removed: list[str] = []
    tracked = plugin_name in manifest

    if tracked:
        entry = manifest[plugin_name]
        removed = _remove_paths(target_dir, entry.get("paths", []))

        # Drop every manifest key that points at this installation
        # (one install may provide several plugins).
        manifest = {
            k: v for k, v in manifest.items() if v.get("paths") != entry.get("paths")
        }
        _save_manifest(target_dir, manifest)

        if not removed:
            _print_level(
                "warn",
                f"Manifest entry for '{plugin_name}' found, but its files were "
                f"already gone from {target_dir}",
                use_color=use_color,
            )
    else:
        _print_level(
            "warn",
            f"Plugin '{plugin_name}' is not tracked in the install manifest; "
            "attempting best-effort removal by name",
            use_color=use_color,
        )
        removed = _legacy_glob_removal(target_dir, plugin_name)

    if not removed and not tracked:
        _print_level(
            "error",
            f"Nothing removable for plugin '{plugin_name}' in {target_dir} "
            "(note: system-installed plugins can't be removed here)",
            use_color=use_color,
        )
        return EXIT_ERROR

    mgr.unregister(plugin_name)
    mgr.load_plugins(force=True)

    _print_level(
        "info",
        f"Removed plugin '{plugin_name}' from {target_dir} "
        f"({len(removed)} entr{'y' if len(removed) == 1 else 'ies'})",
        use_color=use_color,
    )
    return EXIT_OK


def cmd_plugin_info(args: argparse.Namespace) -> int:
    """Show details about a discovered plugin."""
    use_color = _should_use_color(getattr(args, "color", None))

    from semverdredd.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    mgr.load_plugins()

    name = args.name.lower()
    info = mgr.describe_plugin(name)
    if info is None:
        _print_level("error", f"Plugin '{args.name}' not found", use_color=use_color)
        return EXIT_ERROR

    if getattr(args, "json", False) or getattr(args, "yaml", False):
        _emit_plugin_inventory(info, args)
        return EXIT_OK

    plugin_info = next((i for i in mgr.list_plugins() if i.name == name), None)
    if plugin_info is None:
        _print_level("error", f"Plugin '{args.name}' not found", use_color=use_color)
        return EXIT_ERROR

    p = plugin_info.plugin
    print(f"Name: {plugin_info.name}")
    print(f"Display: {p.display_name}")
    print(f"Version: {p.version}")
    print(f"Origin: {plugin_info.origin}")
    if plugin_info.entry_point:
        print(f"Entry point: {plugin_info.entry_point}")
    print(f"Description: {p.description}")

    # Optional: parser assets location
    parser_path = getattr(p, "get_parser_resource_path", lambda: None)()
    if parser_path:
        print(f"Parser path: {parser_path}")

    return EXIT_OK
