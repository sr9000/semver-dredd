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
from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin

# Snapshot registry is owned by the semverdredd main module.
from semverdredd.registry import default_registry

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "semver_dredd.plugins"
DEFAULT_USER_PLUGIN_DIR = Path.home() / ".semver-dredd" / "plugins"

# Fallback import specs for the plugins bundled with this repository.
# Used ONLY when entry-point discovery did not find them (editable/dev
# installs without dist metadata). (module, class, plugin name)
_BUILTIN_FALLBACK_SPECS: list[tuple[str, str, str]] = [
    ("semver_dredd_python.plugin", "PythonPlugin", "python"),
    ("semver_dredd_go.plugin", "GoPlugin", "go"),
    ("semver_dredd_java.plugin", "JavaPlugin", "java"),
]


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
        # Discover via entry points (preferred mechanism)
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
                    ep.value.split(":")[1]
                    if hasattr(ep, "value") and ":" in ep.value
                    else None
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
        # Built-in fallback (editable/dev installs without entry points)
        # ------------------------------------------------------------------
        # When the bundled plugins are pip-installed, entry-point discovery
        # above already registered them and this list is never consulted.
        # It only matters for editable/dev checkouts where the plugin
        # packages are importable but their dist metadata is not installed.
        #
        # Guard against circular imports: if a plugin module is already in
        # sys.modules but still being initialized (the class attribute won't
        # exist yet), skip it here — a later load_plugins(force=True) call
        # will pick it up.
        for _mod_name, _cls_name, _plugin_name in _BUILTIN_FALLBACK_SPECS:
            if _plugin_name in self._registry:
                continue  # already discovered via entry points
            try:
                # Check if the submodule is mid-import (circular dependency).
                _partial = sys.modules.get(_mod_name)
                if _partial is not None and not hasattr(_partial, _cls_name):
                    logger.debug(
                        "Skipping partially-loaded builtin plugin '%s'", _plugin_name
                    )
                    continue
                _mod = __import__(_mod_name, fromlist=[_cls_name])
                cls = getattr(_mod, _cls_name)
            except Exception:
                continue  # plugin package not importable — not installed

            try:
                self.register(cls(), origin="builtin")
            except Exception as e:
                logger.warning(
                    "Failed to init builtin plugin '%s': %s",
                    getattr(cls, "__name__", "<unknown>"),
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
            except ValueError as e:
                # Duplicate SNAPSHOT_TYPE_ID across plugins — this means two
                # plugins claim the same snapshot format UUID. Snapshots may
                # deserialize with the wrong class; make it loud.
                logger.warning(
                    "Snapshot type conflict for plugin '%s': %s",
                    info.name,
                    e,
                )
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
        existing = self._registry.get(name)
        if existing is not None:
            if type(existing.plugin) is type(plugin):
                # Same plugin class rediscovered (e.g. builtin + entry point);
                # benign, keep it quiet.
                logger.debug("Re-registering plugin: %s", name)
            else:
                logger.warning(
                    "Plugin name conflict: '%s' (%s from %s) is being replaced "
                    "by %s from %s",
                    name,
                    type(existing.plugin).__qualname__,
                    existing.origin,
                    type(plugin).__qualname__,
                    origin,
                )
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

    def describe_plugin(self, name: str) -> dict[str, Any] | None:
        self.load_plugins()
        info = self._registry.get(name.lower())
        if info is None:
            return None
        return self._build_plugin_metadata(info)

    def list_plugin_metadata(self) -> list[dict[str, Any]]:
        self.load_plugins()
        return [self._build_plugin_metadata(info) for info in self._registry.values()]

    def list_names(self) -> list[str]:
        self.load_plugins()
        return list(self._registry.keys())

    def is_loaded(self) -> bool:
        return self._loaded

    def _build_plugin_metadata(self, info: PluginInfo) -> dict[str, Any]:
        plugin = info.plugin
        raw_metadata = getattr(plugin, "metadata", {})
        if callable(raw_metadata):
            raw_metadata = raw_metadata()
        if raw_metadata is None:
            raw_metadata = {}
        if not isinstance(raw_metadata, dict):
            logger.warning(
                "Plugin '%s' returned non-dict metadata of type %s; ignoring it",
                info.name,
                type(raw_metadata).__name__,
            )
            raw_metadata = {}

        metadata = dict(raw_metadata)
        features = metadata.get("features", [])
        normalized_features = self._normalize_features(plugin, features)

        snapshot_cls = plugin.snapshot_format_class
        snapshot_type_id = getattr(snapshot_cls, "SNAPSHOT_TYPE_ID", None)

        metadata["name"] = info.name
        metadata["display_name"] = plugin.display_name
        metadata["version"] = plugin.version
        metadata["description"] = plugin.description
        metadata["origin"] = info.origin
        metadata["entry_point"] = info.entry_point
        metadata["features"] = normalized_features
        metadata["snapshot_format"] = {
            "class": snapshot_cls.__name__ if snapshot_cls is not None else None,
            "snapshot_type_id": snapshot_type_id,
        }
        return metadata

    def _normalize_features(
        self, plugin: LanguagePlugin, features: Any
    ) -> list[str]:
        feature_candidates = [
            "metadata",
            "machine_readable_inventory",
        ]
        declared = [feature for feature in feature_candidates if plugin.have(feature)]

        if isinstance(features, str):
            return sorted(set([features, *declared]))
        if isinstance(features, (list, tuple, set, frozenset)):
            return sorted({*(str(feature) for feature in features), *declared})
        if features not in (None, {}):
            logger.warning(
                "Plugin '%s' exposed unsupported features metadata of type %s; "
                "falling back to have()",
                plugin.name,
                type(features).__name__,
            )
        return declared


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
