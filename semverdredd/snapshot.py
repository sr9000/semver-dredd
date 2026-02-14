"""API snapshot serialization for semver-dredd.

This module handles reading/writing API snapshots to YAML files:
- baked.yaml: locked API state with version
- current.yaml: current API state with suggested next version
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from semverdredd import ModuleAPI, APISignature, ClassAPI
# Version is not imported here to avoid circular imports; version strings are used directly


@dataclass
class APISnapshot:
    """Serializable representation of a module's public API."""

    version: str
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    classes: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_module_api(cls, api: ModuleAPI, version: str) -> "APISnapshot":
        """Create a snapshot from a ModuleAPI object."""
        functions = {}
        for name, sig in api.functions.items():
            functions[name] = {
                "parameters": sig.parameters,
                "defaults_count": sig.defaults_count,
            }

        classes = {}
        for name, class_api in api.classes.items():
            methods = {}
            for method_name, method_sig in class_api.methods.items():
                methods[method_name] = {
                    "parameters": method_sig.parameters,
                    "defaults_count": method_sig.defaults_count,
                }
            classes[name] = {"methods": methods}

        return cls(version=version, functions=functions, classes=classes)

    @classmethod
    def from_module(cls, module: ModuleType, version: str) -> "APISnapshot":
        """Create a snapshot directly from a module object."""
        api = ModuleAPI.from_module(module)
        return cls.from_module_api(api, version)

    def to_module_api(self) -> ModuleAPI:
        """Convert snapshot back to ModuleAPI for comparison."""
        functions = {}
        for name, data in self.functions.items():
            functions[name] = APISignature(
                name=name,
                parameters=data["parameters"],
                defaults_count=data["defaults_count"],
            )

        classes = {}
        for name, data in self.classes.items():
            methods = {}
            for method_name, method_data in data["methods"].items():
                methods[method_name] = APISignature(
                    name=method_name,
                    parameters=method_data["parameters"],
                    defaults_count=method_data["defaults_count"],
                )
            classes[name] = ClassAPI(name=name, methods=methods)

        return ModuleAPI(functions=functions, classes=classes)

    def to_yaml(self) -> str:
        """Serialize snapshot to YAML string."""
        data = {
            "version": self.version,
            "api": {
                "functions": self.functions,
                "classes": self.classes,
            },
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "APISnapshot":
        """Deserialize snapshot from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(
            version=data["version"],
            functions=data.get("api", {}).get("functions", {}),
            classes=data.get("api", {}).get("classes", {}),
        )

    def save(self, path: Path | str) -> None:
        """Save snapshot to a YAML file."""
        path = Path(path)
        path.write_text(self.to_yaml())

    @classmethod
    def load(cls, path: Path | str) -> "APISnapshot":
        """Load snapshot from a YAML file."""
        path = Path(path)
        return cls.from_yaml(path.read_text())


def save_version_file(version: str, path: Path | str = "VERSION") -> None:
    """Save version string to a plain text file."""
    path = Path(path)
    path.write_text(f"{version}\n")


def load_version_file(path: Path | str = "VERSION") -> str:
    """Load version string from a plain text file."""
    path = Path(path)
    return path.read_text().strip()
