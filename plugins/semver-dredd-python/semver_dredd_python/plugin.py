"""Python plugin implementation for semver-dredd."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Optional

from semverdredd.plugin_base import LanguagePlugin, SnapshotResult
from semverdredd.snapshot import APISnapshot


class PythonPlugin(LanguagePlugin):
    """Python language support plugin for semver-dredd.

    Analyzes Python modules using introspection (inspect module).
    """

    @property
    def name(self) -> str:
        return "python"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Analyzes Python modules using introspection"

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Validate that the path is a valid Python module."""
        p = Path(path)
        if p.exists():
            if p.is_dir():
                if not (p / "__init__.py").exists():
                    return False, f"Directory '{path}' is not a Python package (no __init__.py)"
                return True, ""
            if p.is_file() and p.suffix == ".py":
                return True, ""

        # Allow importable module names
        if path and ("." in path or path.isidentifier()):
            return True, ""

        return False, f"'{path}' is not a valid Python module path or name"

    def generate_snapshot(
        self, path: str, version: str, options: Optional[dict[str, Any]] = None
    ) -> SnapshotResult:
        """Generate snapshot by importing and introspecting Python module."""
        try:
            module = self._import_module(path)
        except Exception as e:
            return SnapshotResult(False, "", f"Failed to import module: {e}")

        try:
            snapshot = APISnapshot.from_module(module, version)
            yaml_content = snapshot.to_yaml()
            return SnapshotResult(True, yaml_content)
        except Exception as e:
            return SnapshotResult(False, "", f"Failed to generate snapshot: {e}")

    def _import_module(self, module_path: str):
        """Import a module from path or name."""
        module_fs_path = Path(module_path)
        if module_fs_path.exists():
            if module_fs_path.is_dir():
                module_name = module_fs_path.name
                parent = str(module_fs_path.parent)
            else:
                module_name = module_fs_path.stem
                parent = str(module_fs_path.parent)

            sys.path.insert(0, parent)
            try:
                return importlib.import_module(module_name)
            finally:
                if sys.path and sys.path[0] == parent:
                    sys.path.pop(0)

        return importlib.import_module(module_path)
