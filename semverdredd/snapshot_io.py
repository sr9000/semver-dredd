"""Cross-language snapshot I/O for semver-dredd — backward-compatibility shim.

All concrete implementations live in the ``semverdredd`` package.
This module re-exports them so existing ``from semverdredd.snapshot_io import …``
statements keep working.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semverdredd import default_registry
from semverdredd.registry import _ensure_builtins_registered


def load_snapshot(path: Path | str) -> Any:
    """Load and deserialize a snapshot file using the default registry.

    This is the primary entry point for loading snapshot YAML files.
    """
    _ensure_builtins_registered()
    return default_registry.load_file(path)


def load_snapshot_yaml(yaml_str: str) -> Any:
    """Deserialize a snapshot YAML string using the default registry."""
    _ensure_builtins_registered()
    return default_registry.load_yaml_str(yaml_str)
