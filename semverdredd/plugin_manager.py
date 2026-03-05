"""Plugin discovery and registry.

This is the new home for semver-dredd's language plugin system.

Discovery mechanisms:
- Python entry points: group `semver_dredd.plugins`
- Optional user plugin directory: `~/.semver-dredd/plugins/` (added to sys.path)

The CLI should use this module (not `cli.languages`) so that:
- Python is treated as just another plugin
- third-party plugins can be installed and discovered
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Optional

from semverdredd.plugin_base import LanguagePlugin

# Snapshot registry is owned by the semverdredd main module.
from semverdredd.registry import default_registry

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "semver_dredd.plugins"
DEFAULT_USER_PLUGIN_DIR = Path.home() / ".semver-dredd" / "plugins"


@dataclass(frozen=True)
class PluginInfo:
    name: str
    plugin: LanguagePlugin
    origin: str  # "entry_point" | "user_dir" | "builtin" | "manual"
    entry_point: str | None = None


class PluginManager:
    def __init__(self, user_plugin_dir: Optional[Path] = None):
        self.user_plugin_dir = user_plugin_dir or DEFAULT_USER_PLUGIN_DIR
        self._registry: dict[str, PluginInfo] = {}
        self._loaded = False

    def ensure_plugin_dir(self) -> Path:
        self.user_plugin_dir.mkdir(parents=True, exist_ok=True)
        return self.user_plugin_dir

    def load_plugins(self, force: bool = False) -> None:
        if self._loaded and not force:
            return

        # Reset on force reload
        if force:
            self._registry = {
                k: v
                for k, v in self._registry.items()
                if v.origin in ("manual", "builtin")
            }

        # Add user plugin dir to sys.path for import resolution (if present)
        try:
            if self.user_plugin_dir.exists():
                plugin_dir_str = str(self.user_plugin_dir)
                if plugin_dir_str not in sys.path:
                    sys.path.insert(0, plugin_dir_str)
        except Exception:
            # Don't break core operation if home dir isn't accessible
            pass

        # ------------------------------------------------------------------
        # Built-in plugins (available in this repository / distribution)
        # ------------------------------------------------------------------

        # NOTE: In some environments (e.g. tests, editable installs) entry
        # points may not be installed. We register built-ins by import.
        #
        # Guard against circular imports: if a plugin module is already in
        # sys.modules but still being initialized (the class attribute won't
        # exist yet), skip it here — the entry-point loader or a later
        # load_plugins(force=True) call will pick it up.
        builtins: list[type[LanguagePlugin]] = []
        _builtin_specs: list[tuple[str, str, str]] = [
            ("semver_dredd_python.plugin", "PythonPlugin", "Python"),
            ("semver_dredd_go.plugin", "GoPlugin", "Go"),
            ("semver_dredd_java.plugin", "JavaPlugin", "Java"),
        ]
        for _mod_name, _cls_name, _label in _builtin_specs:
            try:
                # Check if the submodule is mid-import (circular dependency).
                _partial = sys.modules.get(_mod_name)
                if _partial is not None and not hasattr(_partial, _cls_name):
                    logger.debug(
                        "Skipping partially-loaded builtin plugin '%s'", _label
                    )
                    continue
                _mod = __import__(_mod_name, fromlist=[_cls_name])
                builtins.append(getattr(_mod, _cls_name))
            except Exception:
                pass

        for cls in builtins:
            try:
                plugin = cls()
                self.register(plugin, origin="builtin")
            except Exception as e:
                logger.warning(
                    "Failed to init builtin plugin '%s': %s",
                    getattr(cls, "__name__", "<unknown>"),
                    e,
                )

        # ------------------------------------------------------------------
        # Discover via entry points
        # ------------------------------------------------------------------
        try:
            discovered = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Very old importlib.metadata fallback; not expected with py>=3.10.
            discovered = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]

        for ep in discovered:
            try:
                # Guard: if the entry-point's module is mid-import (circular
                # dependency), skip it — the plugin will be available on the
                # next call to load_plugins() or get().
                _ep_mod = getattr(ep, "module", None) or (
                    ep.value.split(":")[0] if hasattr(ep, "value") else None
                )
                _ep_attr = getattr(ep, "attr", None) or (
                    ep.value.split(":")[1] if hasattr(ep, "value") and ":" in ep.value else None
                )
                if _ep_mod and _ep_attr:
                    _partial_mod = sys.modules.get(_ep_mod)
                    if _partial_mod is not None and not hasattr(_partial_mod, _ep_attr):
                        logger.debug(
                            "Skipping partially-loaded entry-point plugin '%s'",
                            getattr(ep, "name", "<unknown>"),
                        )
                        continue
                plugin_cls = ep.load()
                plugin = plugin_cls()
                self.register(
                    plugin, origin="entry_point", entry_point=f"{ep.module}:{ep.attr}"
                )
            except Exception as e:
                logger.warning(
                    "Failed to load plugin '%s': %s",
                    getattr(ep, "name", "<unknown>"),
                    e,
                )

        # ------------------------------------------------------------------
        # Snapshot type registration
        # ------------------------------------------------------------------
        # Any plugin may provide a custom SnapshotFormat implementation.
        # Register those types so YAML unmarshalling can resolve them.
        for info in self._registry.values():
            try:
                snap_cls = getattr(info.plugin, "snapshot_format_class", None)
                if snap_cls is not None:
                    default_registry.register(snap_cls)
            except Exception as e:
                logger.debug(
                    "Failed to register snapshot type for plugin '%s': %s",
                    info.name,
                    e,
                )

        self._loaded = True

    def register(
        self,
        plugin: LanguagePlugin,
        *,
        origin: str = "manual",
        entry_point: str | None = None,
    ) -> None:
        name = plugin.name.lower()
        if name in self._registry:
            logger.info("Replacing existing plugin: %s", name)
        self._registry[name] = PluginInfo(
            name=name, plugin=plugin, origin=origin, entry_point=entry_point
        )

    def unregister(self, name: str) -> bool:
        name = name.lower()
        if name in self._registry:
            del self._registry[name]
            return True
        return False

    def get(self, name: str) -> LanguagePlugin | None:
        self.load_plugins()
        info = self._registry.get(name.lower())
        return info.plugin if info else None

    def list_plugins(self) -> list[PluginInfo]:
        self.load_plugins()
        return list(self._registry.values())

    def list_names(self) -> list[str]:
        self.load_plugins()
        return list(self._registry.keys())

    def is_loaded(self) -> bool:
        return self._loaded


_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager


def get_plugin(name: str) -> LanguagePlugin | None:
    return get_plugin_manager().get(name)


def list_plugins() -> list[PluginInfo]:
    return get_plugin_manager().list_plugins()
