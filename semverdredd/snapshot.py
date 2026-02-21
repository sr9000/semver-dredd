"""API snapshot serialization for semver-dredd.

This module handles reading/writing API snapshots to YAML files:
- baked.yaml: locked API state with version
- current.yaml: current API state with suggested next version

Schema v2 adds cross-language support with explicit types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from semverdredd.python_api import ModuleAPI, APISignature, ClassAPI

# Current schema version
SCHEMA_VERSION = 2


@dataclass
class SourceInfo:
    """Information about what was analyzed."""

    kind: str = ""
    path: str = ""


@dataclass
class APISnapshot:
    """Serializable representation of a module's public API (Schema v2)."""

    version: str
    language: str = "python"
    source: SourceInfo = field(default_factory=SourceInfo)
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    classes: dict[str, dict[str, Any]] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_module_api(
        cls, api: ModuleAPI, version: str, source_path: str = ""
    ) -> "APISnapshot":
        """Create a snapshot from a ModuleAPI object."""
        functions = {}
        for name, sig in api.functions.items():
            functions[name] = {
                "parameters": [
                    {
                        "name": p,
                        "type": "unknown",
                        "optional": i >= len(sig.parameters) - sig.defaults_count,
                    }
                    for i, p in enumerate(sig.parameters)
                ],
                "defaults_count": sig.defaults_count,  # Keep for backward compat
            }

        classes = {}
        for name, class_api in api.classes.items():
            methods = {}
            for method_name, method_sig in class_api.methods.items():
                methods[method_name] = {
                    "parameters": [
                        {
                            "name": p,
                            "type": "unknown",
                            "optional": i
                            >= len(method_sig.parameters) - method_sig.defaults_count,
                        }
                        for i, p in enumerate(method_sig.parameters)
                    ],
                    "defaults_count": method_sig.defaults_count,
                }
            classes[name] = {
                "methods": methods,
                "fields": [
                    {"name": f, "type": "unknown"} for f in sorted(class_api.fields)
                ],
            }

        return cls(
            version=version,
            language="python",
            source=SourceInfo(kind="module", path=source_path),
            functions=functions,
            classes=classes,
            schema_version=SCHEMA_VERSION,
        )

    @classmethod
    def from_module(cls, module: ModuleType, version: str) -> "APISnapshot":
        """Create a snapshot directly from a module object."""
        api = ModuleAPI.from_module(module)
        source_path = getattr(module, "__name__", "")
        return cls.from_module_api(api, version, source_path)

    def to_module_api(self) -> ModuleAPI:
        """Convert snapshot back to ModuleAPI for comparison."""
        functions = {}
        for name, data in self.functions.items():
            # Handle both v1 and v2 formats
            if "parameters" in data and isinstance(data["parameters"], list):
                # v2 format: list of dicts
                if data["parameters"] and isinstance(data["parameters"][0], dict):
                    params = [p["name"] for p in data["parameters"]]
                    defaults_count = sum(
                        1 for p in data["parameters"] if p.get("optional", False)
                    )
                else:
                    # v1 format: list of strings
                    params = data["parameters"]
                    defaults_count = data.get("defaults_count", 0)
            else:
                params = data.get("parameters", [])
                defaults_count = data.get("defaults_count", 0)

            functions[name] = APISignature(
                name=name,
                parameters=params,
                defaults_count=defaults_count,
            )

        classes = {}
        for name, data in self.classes.items():
            methods = {}
            for method_name, method_data in data.get("methods", {}).items():
                # Handle both v1 and v2 formats
                if "parameters" in method_data and isinstance(
                    method_data["parameters"], list
                ):
                    if method_data["parameters"] and isinstance(
                        method_data["parameters"][0], dict
                    ):
                        params = [p["name"] for p in method_data["parameters"]]
                        defaults_count = sum(
                            1
                            for p in method_data["parameters"]
                            if p.get("optional", False)
                        )
                    else:
                        params = method_data["parameters"]
                        defaults_count = method_data.get("defaults_count", 0)
                else:
                    params = method_data.get("parameters", [])
                    defaults_count = method_data.get("defaults_count", 0)

                methods[method_name] = APISignature(
                    name=method_name,
                    parameters=params,
                    defaults_count=defaults_count,
                )

            # Handle fields - v2 is list of dicts, v1 was list of strings
            fields_data = data.get("fields", [])
            if fields_data and isinstance(fields_data[0], dict):
                fields = set(f["name"] for f in fields_data)
            else:
                fields = set(fields_data)

            classes[name] = ClassAPI(name=name, methods=methods, fields=fields)

        return ModuleAPI(functions=functions, classes=classes)

    def to_yaml(self) -> str:
        """Serialize snapshot to YAML string (Schema v2)."""
        data = {
            "schema_version": self.schema_version,
            "version": self.version,
            "language": self.language,
            "source": {
                "kind": self.source.kind,
                "path": self.source.path,
            },
            "api": {
                "functions": self.functions,
                "types": self.classes,  # Renamed to 'types' in v2 for cross-language
            },
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "APISnapshot":
        """Deserialize snapshot from YAML string (supports v1 and v2)."""
        data = yaml.safe_load(yaml_str)

        schema_version = data.get("schema_version", 1)
        language = data.get("language", "python")

        # Handle source field
        source_data = data.get("source", {})
        source = SourceInfo(
            kind=source_data.get("kind", ""),
            path=source_data.get("path", ""),
        )

        # v2 uses 'types', v1 uses 'classes'
        api = data.get("api", {})
        types_data = api.get("types", api.get("classes", {}))

        return cls(
            version=data["version"],
            language=language,
            source=source,
            functions=api.get("functions", {}),
            classes=types_data,
            schema_version=schema_version,
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
