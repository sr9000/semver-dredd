"""
Configuration loading for semver-dredd CLI.

Priority order (lowest to highest):
1. .semver.yaml file
2. .env file
3. Environment variables
4. CLI arguments
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILE = ".semver.yaml"
DEFAULT_ENV_FILE = ".env"

# Mapping of environment variable names to config keys
ENV_VAR_PREFIX = "SEMVER_DREDD_"
ENV_VAR_MAPPING = {
    "SEMVER_DREDD_ALLOW_BREAKING": ("policies", "allow_breaking_changes"),
    "SEMVER_DREDD_COLOR": ("output", "color"),
    "SEMVER_DREDD_PLUGIN": ("plugin",),
    "SEMVER_DREDD_BAKED_FILE": ("files", "baked"),
    "SEMVER_DREDD_CURRENT_FILE": ("files", "current"),
    "SEMVER_DREDD_VERSION_FILE": ("files", "version"),
}


@dataclass
class Config:
    """Configuration container for semver-dredd CLI."""

    # Policies
    allow_breaking_changes: bool = False

    # Output
    color: bool | None = None  # None means auto-detect

    # Plugin
    plugin: str = "python"

    # Files
    baked_file: str = "baked.yaml"
    current_file: str = "current.yaml"
    version_file: str = "VERSION"

    # Versioning
    patch_scheme: str = "date"  # "date" (YYYYMMDDZZZ) or "integer"

    # Analysis scope (opaque strings, interpreted by the plugin)
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    # Free-form plugin options (never validated by the framework)
    plugin_options: dict[str, Any] = field(default_factory=dict)

    # Raw config dict for advanced options
    _raw: dict[str, Any] = field(default_factory=dict)

    def get(self, *path: str, default: Any = None) -> Any:
        """Get a nested config value by path."""
        current = self._raw
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def snapshot_options(self) -> dict[str, Any]:
        """Build the options dict forwarded to LanguagePlugin.generate_snapshot.

        Keys are only present when configured, so plugins that ignore them
        behave exactly as before.
        """
        options: dict[str, Any] = {}
        if self.include:
            options["include"] = list(self.include)
        if self.exclude:
            options["exclude"] = list(self.exclude)
        if self.plugin_options:
            options["plugin_options"] = dict(self.plugin_options)
        return options


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary.

    Simple format: KEY=VALUE per line, supports # comments.
    Does not support quoting or escape sequences for simplicity.
    """
    env_vars = {}
    if not path.exists():
        return env_vars

    try:
        with open(path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove surrounding quotes if present
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]

                env_vars[key] = value
    except (IOError, OSError):
        pass

    return env_vars


def _parse_bool(value: str | bool | None) -> bool | None:
    """Parse a boolean value from string."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower()
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
    return None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Parse errors are reported on stderr (instead of being silently
    swallowed) so users notice malformed config files.
    """
    if not path.exists():
        return {}

    try:
        import yaml
    except ImportError:
        print(
            f"[WARN] PyYAML is not installed; ignoring config file: {path}",
            file=sys.stderr,
        )
        return {}

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(
            f"[WARN] Failed to parse config file {path}: {e}",
            file=sys.stderr,
        )
        return {}
    except OSError as e:
        print(
            f"[WARN] Failed to read config file {path}: {e}",
            file=sys.stderr,
        )
        return {}

    if config is not None and not isinstance(config, dict):
        print(
            f"[WARN] Config file {path} must contain a YAML mapping; ignoring it",
            file=sys.stderr,
        )
        return {}

    return config or {}


def _set_nested(d: dict, path: tuple[str, ...], value: Any) -> None:
    """Set a nested dictionary value by path."""
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def _parse_str_list(value: Any) -> list[str]:
    """Coerce a config value into a flat list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def load_config(
    config_file: str | Path | None = None,
    env_file: str | Path | None = None,
    cwd: Path | None = None,
) -> Config:
    """Load configuration from all sources in priority order.

    Args:
        config_file: Path to .semver.yaml (default: .semver.yaml in cwd)
        env_file: Path to .env file (default: .env in cwd)
        cwd: Working directory (default: current directory)

    Returns:
        Config object with merged configuration
    """
    if cwd is None:
        cwd = Path.cwd()

    # Layer 1: Load .semver.yaml (lowest priority)
    yaml_path = Path(config_file) if config_file else cwd / DEFAULT_CONFIG_FILE
    merged = _load_yaml_config(yaml_path)

    # Layer 2: Load .env file
    dotenv_path = Path(env_file) if env_file else cwd / DEFAULT_ENV_FILE
    env_from_file = _parse_env_file(dotenv_path)

    # Apply .env values to merged config
    for env_key, config_path in ENV_VAR_MAPPING.items():
        if env_key in env_from_file:
            _set_nested(merged, config_path, env_from_file[env_key])

    # Layer 3: Load real environment variables (override .env)
    for env_key, config_path in ENV_VAR_MAPPING.items():
        if env_key in os.environ:
            _set_nested(merged, config_path, os.environ[env_key])

    # Build Config object from merged dict
    policies = merged.get("policies", {})
    output = merged.get("output", {})
    files = merged.get("files", {})

    # Parse allow_breaking_changes
    allow_breaking_raw = policies.get("allow_breaking_changes", False)
    allow_breaking = _parse_bool(allow_breaking_raw)
    if allow_breaking is None:
        allow_breaking = False

    # Parse color
    color_raw = output.get("color")
    color = _parse_bool(color_raw)  # None means auto-detect

    # Parse plugin
    plugin = str(merged.get("plugin", "python"))

    # Parse files
    baked_file = str(files.get("baked", "baked.yaml"))
    current_file = str(files.get("current", "current.yaml"))
    version_file = str(files.get("version", "VERSION"))

    # Parse versioning options
    versioning = merged.get("versioning", {})
    patch_scheme = str(versioning.get("patch_scheme", "date")).lower()
    if patch_scheme not in ("date", "integer"):
        print(
            f"[WARN] Unknown versioning.patch_scheme {patch_scheme!r}; "
            'falling back to "date"',
            file=sys.stderr,
        )
        patch_scheme = "date"

    # Parse analysis scope and free-form plugin options
    include = _parse_str_list(merged.get("include"))
    exclude = _parse_str_list(merged.get("exclude"))
    plugin_options_raw = merged.get("plugin_options")
    plugin_options = (
        dict(plugin_options_raw) if isinstance(plugin_options_raw, dict) else {}
    )

    return Config(
        allow_breaking_changes=allow_breaking,
        color=color,
        plugin=plugin,
        baked_file=baked_file,
        current_file=current_file,
        version_file=version_file,
        patch_scheme=patch_scheme,
        include=include,
        exclude=exclude,
        plugin_options=plugin_options,
        _raw=merged,
    )


def apply_config_defaults(args: Any, config: Config) -> None:
    """Apply config defaults to argparse namespace.

    CLI arguments have highest priority, so we only set values
    that weren't explicitly provided.

    Args:
        args: argparse.Namespace to update
        config: Config object with merged configuration
    """
    # allow_breaking: only set if not explicitly set via CLI
    if hasattr(args, "allow_breaking"):
        allow = getattr(args, "allow_breaking", False)
        disallow = getattr(args, "disallow_breaking", False)
        if not allow and not disallow:
            # Neither flag was set, use config default
            args.allow_breaking = config.allow_breaking_changes

    # color: only set if CLI didn't set it (None means auto-detect)
    if hasattr(args, "color") and args.color is None:
        args.color = config.color

    # plugin: only set if not explicitly set via CLI
    if hasattr(args, "plugin") and args.plugin is None:
        args.plugin = config.plugin

    # File paths: apply config defaults
    if hasattr(args, "baked"):
        if getattr(args, "baked", None) is None:
            args.baked = config.baked_file

    if hasattr(args, "current_file"):
        if getattr(args, "current_file", None) is None:
            args.current_file = config.current_file

    if hasattr(args, "version_file"):
        if getattr(args, "version_file", None) is None:
            args.version_file = config.version_file

    # Scope/options forwarded to LanguagePlugin.generate_snapshot.
    # There is no CLI flag for these yet, so config is the only source.
    if getattr(args, "snapshot_options", None) is None:
        args.snapshot_options = config.snapshot_options()

    # Patch scheme used when incrementing/generating patch numbers.
    if getattr(args, "patch_scheme", None) is None:
        args.patch_scheme = config.patch_scheme
