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
from pathlib import Path
from typing import Optional

from importlib.metadata import entry_points

from semverdredd.plugin_base import LanguagePlugin


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

        # Register built-ins immediately so the core CLI works in editable/dev installs
        # even when entry point metadata isn't available.
        try:
            from semverdredd.plugins.builtin import register_builtin_plugins

            register_builtin_plugins(self)
        except Exception:
            # Never make plugin discovery fatal.
            pass

    def ensure_plugin_dir(self) -> Path:
        self.user_plugin_dir.mkdir(parents=True, exist_ok=True)
        return self.user_plugin_dir

    def load_plugins(self, force: bool = False) -> None:
        if self._loaded and not force:
            return

        # Reset on force reload
        if force:
            self._registry = {k: v for k, v in self._registry.items() if v.origin in ("manual", "builtin")}

        # Add user plugin dir to sys.path for import resolution (if present)
        try:
            if self.user_plugin_dir.exists():
                plugin_dir_str = str(self.user_plugin_dir)
                if plugin_dir_str not in sys.path:
                    sys.path.insert(0, plugin_dir_str)
        except Exception:
            # Don't break core operation if home dir isn't accessible
            pass

        # Discover via entry points
        try:
            discovered = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Very old importlib.metadata fallback; not expected with py>=3.10.
            discovered = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]

        for ep in discovered:
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls()
                self.register(plugin, origin="entry_point", entry_point=f"{ep.module}:{ep.attr}")
            except Exception as e:
                logger.warning("Failed to load plugin '%s': %s", getattr(ep, "name", "<unknown>"), e)

        self._loaded = True

    def register(self, plugin: LanguagePlugin, *, origin: str = "manual", entry_point: str | None = None) -> None:
        name = plugin.name.lower()
        if name in self._registry:
            logger.info("Replacing existing plugin: %s", name)
        self._registry[name] = PluginInfo(name=name, plugin=plugin, origin=origin, entry_point=entry_point)

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
