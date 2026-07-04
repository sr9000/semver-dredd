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
from copy import deepcopy
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
    "SEMVER_DREDD_PATH": ("source", "path"),
}


@dataclass(frozen=True)
class RawConfigDocument:
    """A raw YAML document with stable origin metadata."""

    index: int
    source: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class CandidateAttempt:
    """One candidate-selection attempt and the outcome."""

    index: int
    plugin: str | None
    path: str | None
    ok: bool
    reason: str


@dataclass
class LoadedConfig:
    """Configuration load result with document and provenance metadata."""

    config_path: Path
    selected_explicitly: bool
    config_exists: bool
    raw_documents: list[RawConfigDocument] = field(default_factory=list)
    candidate_documents: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    env_overrides: dict[str, Any] = field(default_factory=dict)
    env_sources: dict[tuple[str, ...], str] = field(default_factory=dict)


@dataclass
class Config:
    """Configuration container for semver-dredd CLI."""

    # Policies
    allow_breaking_changes: bool = False

    # Output
    color: bool | None = None  # None means auto-detect

    # Plugin
    plugin: str = "python"

    # Source
    source_path: str | None = None

    # Files
    baked_file: str = "baked.yaml"
    current_file: str = "current.yaml"
    version_file: str = "VERSION"

    # Versioning
    patch_scheme: str = "date"  # "date" (YYYYMMDDZZZ) or "integer"

    # Analysis scope (opaque items interpreted by the plugin)
    include: list[Any] = field(default_factory=list)
    exclude: list[Any] = field(default_factory=list)

    # Free-form plugin options (never validated by the framework)
    plugin_options: dict[str, Any] = field(default_factory=dict)

    # Raw config dict for advanced options
    _raw: dict[str, Any] = field(default_factory=dict)

    # Source metadata for precedence/traceability
    _sources: dict[tuple[str, ...], str] = field(default_factory=dict)

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


def _load_yaml_documents(path: Path) -> list[RawConfigDocument]:
    """Load raw YAML documents preserving order and index metadata."""
    if not path.exists():
        return []

    try:
        import yaml
    except ImportError:
        print(
            f"[WARN] PyYAML is not installed; ignoring config file: {path}",
            file=sys.stderr,
        )
        return []

    try:
        with open(path, "r") as f:
            loaded_docs = list(yaml.safe_load_all(f))
    except yaml.YAMLError as e:
        print(
            f"[WARN] Failed to parse config file {path}: {e}",
            file=sys.stderr,
        )
        return []
    except OSError as e:
        print(
            f"[WARN] Failed to read config file {path}: {e}",
            file=sys.stderr,
        )
        return []

    result: list[RawConfigDocument] = []
    for idx, doc in enumerate(loaded_docs):
        if doc is None:
            doc = {}
        if not isinstance(doc, dict):
            print(
                f"[WARN] Config file {path} must contain a YAML mapping; "
                f"document #{idx} is {type(doc).__name__}, ignoring it",
                file=sys.stderr,
            )
            continue
        result.append(RawConfigDocument(index=idx, source=path, data=doc))

    return result


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Parse errors are reported on stderr (instead of being silently
    swallowed) so users notice malformed config files.
    """
    docs = _load_yaml_documents(path)
    if not docs:
        return {}
    return dict(docs[0].data)


def _set_nested(d: dict, path: tuple[str, ...], value: Any) -> None:
    """Set a nested dictionary value by path."""
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def _parse_any_list(value: Any, *, key: str) -> list[Any]:
    """Validate include/exclude as arrays while preserving item shapes."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    raise ValueError(f"Config key '{key}' must be an array, got {type(value).__name__}")


def _merge_values(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        return _deep_merge_dicts(base, override)
    if isinstance(base, list) and isinstance(override, list):
        return list(base) + list(override)
    return deepcopy(override)


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge semantics: deep objects, concat arrays, replace scalars, null removes."""
    merged = deepcopy(base)
    for key, override_value in override.items():
        if override_value is None:
            merged.pop(key, None)
            continue
        if key not in merged:
            merged[key] = deepcopy(override_value)
            continue
        merged[key] = _merge_values(merged[key], override_value)
    return merged


def _build_candidate_documents(raw_documents: list[RawConfigDocument]) -> list[tuple[int, dict[str, Any]]]:
    if not raw_documents:
        return []
    if len(raw_documents) == 1:
        return [(raw_documents[0].index, deepcopy(raw_documents[0].data))]

    shared_defaults = raw_documents[0].data
    candidates: list[tuple[int, dict[str, Any]]] = []
    for doc in raw_documents[1:]:
        candidates.append((doc.index, _deep_merge_dicts(shared_defaults, doc.data)))
    return candidates


def _collect_sources(d: dict[str, Any], prefix: tuple[str, ...], source: str, out: dict[tuple[str, ...], str]) -> None:
    for k, v in d.items():
        path = prefix + (k,)
        out[path] = source
        if isinstance(v, dict):
            _collect_sources(v, path, source, out)


def _get_nested(d: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _build_config(merged: dict[str, Any], sources: dict[tuple[str, ...], str]) -> Config:
    policies = merged.get("policies", {})
    output = merged.get("output", {})
    files = merged.get("files", {})
    source = merged.get("source", {})

    allow_breaking_raw = policies.get("allow_breaking_changes", False)
    allow_breaking = _parse_bool(allow_breaking_raw)
    if allow_breaking is None:
        allow_breaking = False

    color_raw = output.get("color")
    color = _parse_bool(color_raw)

    plugin_raw = merged.get("plugin")
    plugin = str(plugin_raw if plugin_raw is not None else "python")
    source_path_raw = source.get("path") if isinstance(source, dict) else None
    source_path = str(source_path_raw) if source_path_raw is not None else None

    baked_file = str(files.get("baked", "baked.yaml"))
    current_file = str(files.get("current", "current.yaml"))
    version_file = str(files.get("version", "VERSION"))

    versioning = merged.get("versioning", {})
    patch_scheme = str(versioning.get("patch_scheme", "date")).lower()
    if patch_scheme not in ("date", "integer"):
        print(
            f"[WARN] Unknown versioning.patch_scheme {patch_scheme!r}; "
            'falling back to "date"',
            file=sys.stderr,
        )
        patch_scheme = "date"

    include = _parse_any_list(merged.get("include"), key="include")
    exclude = _parse_any_list(merged.get("exclude"), key="exclude")
    plugin_options_raw = merged.get("plugin_options")
    plugin_options = (
        dict(plugin_options_raw) if isinstance(plugin_options_raw, dict) else {}
    )

    return Config(
        allow_breaking_changes=allow_breaking,
        color=color,
        plugin=plugin,
        source_path=source_path,
        baked_file=baked_file,
        current_file=current_file,
        version_file=version_file,
        patch_scheme=patch_scheme,
        include=include,
        exclude=exclude,
        plugin_options=plugin_options,
        _raw=merged,
        _sources=sources,
    )


def load_config_with_meta(
    config_file: str | Path | None = None,
    env_file: str | Path | None = None,
    cwd: Path | None = None,
    *,
    allow_missing_explicit: bool = False,
) -> LoadedConfig:
    if cwd is None:
        cwd = Path.cwd()

    selected_explicitly = config_file is not None
    config_path = Path(config_file) if config_file else cwd / DEFAULT_CONFIG_FILE
    config_exists = config_path.exists()
    if selected_explicitly and not config_exists and not allow_missing_explicit:
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw_documents = _load_yaml_documents(config_path)
    candidate_documents = _build_candidate_documents(raw_documents)

    env_overrides: dict[str, Any] = {}
    env_sources: dict[tuple[str, ...], str] = {}
    dotenv_path = Path(env_file) if env_file else cwd / DEFAULT_ENV_FILE
    env_from_file = _parse_env_file(dotenv_path)
    for env_key, config_path_tuple in ENV_VAR_MAPPING.items():
        if env_key in env_from_file:
            _set_nested(env_overrides, config_path_tuple, env_from_file[env_key])
            env_sources[config_path_tuple] = ".env"
    for env_key, config_path_tuple in ENV_VAR_MAPPING.items():
        if env_key in os.environ:
            _set_nested(env_overrides, config_path_tuple, os.environ[env_key])
            env_sources[config_path_tuple] = "env"

    return LoadedConfig(
        config_path=config_path,
        selected_explicitly=selected_explicitly,
        config_exists=config_exists,
        raw_documents=raw_documents,
        candidate_documents=candidate_documents,
        env_overrides=env_overrides,
        env_sources=env_sources,
    )


def load_config(
    config_file: str | Path | None = None,
    env_file: str | Path | None = None,
    cwd: Path | None = None,
    *,
    allow_missing_explicit: bool = False,
) -> Config:
    """Load configuration from all sources in priority order.

    Args:
        config_file: Path to .semver.yaml (default: .semver.yaml in cwd)
        env_file: Path to .env file (default: .env in cwd)
        cwd: Working directory (default: current directory)

    Returns:
        Config object with merged configuration
    """
    loaded = load_config_with_meta(
        config_file=config_file,
        env_file=env_file,
        cwd=cwd,
        allow_missing_explicit=allow_missing_explicit,
    )
    if loaded.candidate_documents:
        _, merged = loaded.candidate_documents[0]
    elif loaded.raw_documents:
        merged = dict(loaded.raw_documents[0].data)
    else:
        merged = {}

    sources: dict[tuple[str, ...], str] = {}
    _collect_sources(merged, (), "config", sources)
    merged = _deep_merge_dicts(merged, loaded.env_overrides)
    sources.update(loaded.env_sources)
    return _build_config(merged, sources)


@dataclass
class ResolvedCommandContext:
    config_path: Path
    config_selected_explicitly: bool
    config_status: str
    source_path: str | None
    source_layer: str
    plugin: str
    plugin_layer: str
    version_file: str
    version_file_layer: str
    include: list[Any]
    exclude: list[Any]
    plugin_options: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    candidate_attempts: list[CandidateAttempt] = field(default_factory=list)
    candidate_index: int | None = None


def _dedupe_warnings_for_lists(base: list[Any], extra: list[Any], key: str) -> list[str]:
    warnings: list[str] = []
    seen = set()
    for item in base:
        seen.add(repr(item))
    for item in extra:
        r = repr(item)
        if r in seen:
            warnings.append(f"Duplicate {key} item in CLI and config: {item!r}")
        seen.add(r)
    return warnings


def resolve_command_context(args: Any, loaded: LoadedConfig, cwd: Path | None = None) -> ResolvedCommandContext:
    if cwd is None:
        cwd = Path.cwd()

    command = getattr(args, "command", "")
    command_uses_source = command in {"init", "status", "bake", "snapshot"}

    explicit_plugin = getattr(args, "plugin", None)
    explicit_path = getattr(args, "path", None)
    positional_path = getattr(args, "module", None)
    explicit_source = explicit_path if explicit_path is not None else positional_path

    env_plugin_override = _get_nested(loaded.env_overrides, ("plugin",))
    override_plugin = explicit_plugin if explicit_plugin is not None else env_plugin_override

    candidate_attempts: list[CandidateAttempt] = []
    selected_candidate_index: int | None = None
    selected_candidate: dict[str, Any] = {}

    candidates = loaded.candidate_documents or [(-1, {})]
    from semverdredd.plugin_manager import get_plugin_manager

    plugin_manager = get_plugin_manager()
    plugin_manager.load_plugins()

    for doc_index, candidate in candidates:
        candidate_plugin = str(candidate.get("plugin", "python"))
        if override_plugin is not None and candidate_plugin != str(override_plugin):
            candidate_attempts.append(
                CandidateAttempt(
                    index=doc_index,
                    plugin=candidate_plugin,
                    path=str(candidate.get("source", {}).get("path")) if isinstance(candidate.get("source"), dict) and candidate.get("source", {}).get("path") is not None else None,
                    ok=False,
                    reason=(
                        f"candidate plugin {candidate_plugin!r} does not match override {str(override_plugin)!r}"
                    ),
                )
            )
            continue

        chosen_plugin = str(override_plugin) if override_plugin is not None else candidate_plugin
        plugin = plugin_manager.get(chosen_plugin)
        if plugin is None:
            candidate_attempts.append(
                CandidateAttempt(
                    index=doc_index,
                    plugin=chosen_plugin,
                    path=None,
                    ok=False,
                    reason=f"plugin {chosen_plugin!r} is not installed",
                )
            )
            continue

        source_cfg = candidate.get("source", {}) if isinstance(candidate.get("source"), dict) else {}
        candidate_path = source_cfg.get("path")
        resolved_path = explicit_source or _get_nested(loaded.env_overrides, ("source", "path")) or candidate_path

        if command_uses_source and resolved_path in (None, ""):
            candidate_attempts.append(
                CandidateAttempt(
                    index=doc_index,
                    plugin=chosen_plugin,
                    path=None,
                    ok=False,
                    reason="no source path resolved from CLI/env/config",
                )
            )
            continue

        if command_uses_source and resolved_path not in (None, ""):
            ok, reason = plugin.validate_path(str(resolved_path))
            if not ok:
                candidate_attempts.append(
                    CandidateAttempt(
                        index=doc_index,
                        plugin=chosen_plugin,
                        path=str(resolved_path),
                        ok=False,
                        reason=reason,
                    )
                )
                continue

        selected_candidate_index = doc_index
        selected_candidate = deepcopy(candidate)
        candidate_attempts.append(
            CandidateAttempt(
                index=doc_index,
                plugin=chosen_plugin,
                path=str(resolved_path) if resolved_path is not None else None,
                ok=True,
                reason="selected",
            )
        )
        break

    if command_uses_source and selected_candidate_index is None:
        if override_plugin is not None and not any(
            str(cand.get("plugin", "python")) == str(override_plugin) for _, cand in candidates
        ):
            raise ValueError(
                f"Requested plugin override {str(override_plugin)!r} is not present in any config candidate"
            )
        details = "; ".join(
            f"doc#{attempt.index}:{attempt.reason}" for attempt in candidate_attempts
        )
        raise ValueError(f"No valid config candidate found ({details})")

    merged_for_command = _deep_merge_dicts(selected_candidate, loaded.env_overrides)
    sources: dict[tuple[str, ...], str] = {}
    _collect_sources(selected_candidate, (), "config", sources)
    sources.update(loaded.env_sources)
    config = _build_config(merged_for_command, sources)

    warnings: list[str] = []
    plugin_layer = "cmdarg" if explicit_plugin is not None else config._sources.get(("plugin",), "default")
    resolved_plugin = str(explicit_plugin) if explicit_plugin is not None else config.plugin

    if explicit_plugin is not None and config._raw.get("plugin") and str(config._raw.get("plugin")) != str(explicit_plugin):
        warnings.append(
            f"CLI --plugin={explicit_plugin!r} overrides config plugin {config._raw.get('plugin')!r}"
        )

    source_layer = "none"
    resolved_source_path = None
    if explicit_path is not None:
        resolved_source_path = explicit_path
        source_layer = "cmdarg"
    elif positional_path is not None:
        resolved_source_path = positional_path
        source_layer = "cmdarg"
    elif _get_nested(loaded.env_overrides, ("source", "path")) is not None:
        resolved_source_path = str(_get_nested(loaded.env_overrides, ("source", "path")))
        source_layer = loaded.env_sources.get(("source", "path"), "env")
    elif config.source_path is not None:
        resolved_source_path = config.source_path
        source_layer = config._sources.get(("source", "path"), "config")

    config_source_path = None
    if isinstance(config._raw.get("source"), dict):
        cfg_sp = config._raw["source"].get("path")
        if cfg_sp is not None:
            config_source_path = str(cfg_sp)
    if explicit_source is not None and config_source_path and str(explicit_source) != config_source_path:
        warnings.append(
            f"Explicit source path {str(explicit_source)!r} overrides config source.path {config_source_path!r}"
        )

    version_file_layer = "cmdarg" if getattr(args, "version_file", None) is not None else config._sources.get(("files", "version"), "default")
    version_file = str(getattr(args, "version_file", None) or config.version_file)

    cli_include = list(getattr(args, "include", None) or [])
    cli_exclude = list(getattr(args, "exclude", None) or [])
    override_scope = bool(getattr(args, "override", False))

    # Scope from config belongs to commands that operate on the configured
    # source.path.  Direct two-input comparisons intentionally do not inherit
    # root-config include/exclude items: a repository self-config such as
    # include: [cli, semverdredd, snapshot] must not filter unrelated explicit
    # module comparisons like ``semver-dredd compare old_module new_module``.
    command_uses_configured_scope = command in {"init", "status", "bake", "snapshot"}
    if override_scope or not command_uses_configured_scope:
        include = cli_include
        exclude = cli_exclude
    else:
        include = list(config.include) + cli_include
        exclude = list(config.exclude) + cli_exclude
        warnings.extend(_dedupe_warnings_for_lists(list(config.include), cli_include, "include"))
        warnings.extend(_dedupe_warnings_for_lists(list(config.exclude), cli_exclude, "exclude"))

    config_status = "explicit-selected" if loaded.selected_explicitly else "default-selected"
    if not loaded.config_exists:
        config_status = "absent"

    return ResolvedCommandContext(
        config_path=loaded.config_path,
        config_selected_explicitly=loaded.selected_explicitly,
        config_status=config_status,
        source_path=resolved_source_path,
        source_layer=source_layer,
        plugin=resolved_plugin,
        plugin_layer=plugin_layer,
        version_file=version_file,
        version_file_layer=version_file_layer,
        include=include,
        exclude=exclude,
        plugin_options=config.plugin_options,
        warnings=warnings,
        candidate_attempts=candidate_attempts,
        candidate_index=selected_candidate_index,
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
