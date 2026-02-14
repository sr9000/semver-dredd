"""Cross-language snapshot I/O for semver-dredd.

This module provides a unified interface for loading and normalizing
API snapshots from any supported language (Python, Go, Java).

The NormalizedSnapshot is the common in-memory structure used by the
diff and classification engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Parameter:
    """A function/method parameter."""
    name: str
    type: str
    optional: bool = False


@dataclass(frozen=True)
class FunctionSignature:
    """A function or method signature."""
    name: str
    parameters: tuple[Parameter, ...]
    returns: tuple[Parameter, ...] = ()

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "FunctionSignature":
        """Create from YAML dict (supports v1 and v2 formats)."""
        params_data = data.get("parameters", [])
        params = []

        if params_data:
            if isinstance(params_data[0], dict):
                # v2 format: list of dicts with name/type/optional
                for p in params_data:
                    params.append(Parameter(
                        name=p.get("name", ""),
                        type=p.get("type", "unknown"),
                        optional=p.get("optional", False),
                    ))
            else:
                # v1 format: list of strings (param names only)
                defaults_count = data.get("defaults_count", 0)
                total = len(params_data)
                for i, p in enumerate(params_data):
                    params.append(Parameter(
                        name=p,
                        type="unknown",
                        optional=i >= total - defaults_count,
                    ))

        returns_data = data.get("returns", [])
        returns = []
        for r in returns_data:
            if isinstance(r, dict):
                returns.append(Parameter(
                    name=r.get("name", ""),
                    type=r.get("type", "unknown"),
                    optional=r.get("optional", False),
                ))

        return cls(
            name=name,
            parameters=tuple(params),
            returns=tuple(returns),
        )


@dataclass(frozen=True)
class Field:
    """A struct/class field."""
    name: str
    type: str
    optional: bool = False


@dataclass(frozen=True)
class TypeDefinition:
    """A type (class/struct/interface/record) definition."""
    name: str
    fields: tuple[Field, ...]
    methods: dict[str, FunctionSignature]

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "TypeDefinition":
        """Create from YAML dict (supports v1 and v2 formats)."""
        # Parse fields
        fields_data = data.get("fields", [])
        fields = []
        if fields_data:
            if isinstance(fields_data[0], dict):
                # v2: list of dicts
                for f in fields_data:
                    fields.append(Field(
                        name=f.get("name", ""),
                        type=f.get("type", "unknown"),
                        optional=f.get("optional", False),
                    ))
            else:
                # v1: list of strings
                for f in fields_data:
                    fields.append(Field(name=f, type="unknown"))

        # Parse methods
        methods_data = data.get("methods", {})
        methods = {}
        for method_name, method_data in methods_data.items():
            methods[method_name] = FunctionSignature.from_dict(method_name, method_data)

        return cls(
            name=name,
            fields=tuple(sorted(fields, key=lambda f: f.name)),
            methods=methods,
        )


@dataclass
class NormalizedSnapshot:
    """Language-agnostic normalized API snapshot."""
    schema_version: int
    version: str
    language: str
    source_kind: str
    source_path: str
    functions: dict[str, FunctionSignature]
    types: dict[str, TypeDefinition]

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "NormalizedSnapshot":
        """Parse YAML string into normalized snapshot."""
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "NormalizedSnapshot":
        """Load snapshot from file."""
        path = Path(path)
        return cls.from_yaml_str(path.read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "NormalizedSnapshot":
        """Convert raw dict to normalized snapshot."""
        schema_version = data.get("schema_version", 1)
        language = data.get("language", "python")

        source = data.get("source", {})
        source_kind = source.get("kind", "")
        source_path = source.get("path", "")

        api = data.get("api", {})

        # Functions
        functions_data = api.get("functions", {})
        functions = {}
        for name, func_data in functions_data.items():
            functions[name] = FunctionSignature.from_dict(name, func_data)

        # Types (v2) or classes (v1)
        types_data = api.get("types", api.get("classes", {}))
        types = {}
        for name, type_data in types_data.items():
            types[name] = TypeDefinition.from_dict(name, type_data)

        return cls(
            schema_version=schema_version,
            version=data.get("version", ""),
            language=language,
            source_kind=source_kind,
            source_path=source_path,
            functions=functions,
            types=types,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        functions = {}
        for name, sig in self.functions.items():
            functions[name] = {
                "parameters": [
                    {"name": p.name, "type": p.type, "optional": p.optional}
                    for p in sig.parameters
                ],
                "returns": [
                    {"name": r.name, "type": r.type, "optional": r.optional}
                    for r in sig.returns
                ],
            }

        types = {}
        for name, typedef in self.types.items():
            methods = {}
            for method_name, method_sig in typedef.methods.items():
                methods[method_name] = {
                    "parameters": [
                        {"name": p.name, "type": p.type, "optional": p.optional}
                        for p in method_sig.parameters
                    ],
                    "returns": [
                        {"name": r.name, "type": r.type, "optional": r.optional}
                        for r in method_sig.returns
                    ],
                }
            types[name] = {
                "fields": [
                    {"name": f.name, "type": f.type, "optional": f.optional}
                    for f in typedef.fields
                ],
                "methods": methods,
            }

        return {
            "schema_version": self.schema_version,
            "version": self.version,
            "language": self.language,
            "source": {
                "kind": self.source_kind,
                "path": self.source_path,
            },
            "api": {
                "functions": functions,
                "types": types,
            },
        }

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def save(self, path: Path | str) -> None:
        """Save to file."""
        path = Path(path)
        path.write_text(self.to_yaml())


def load_snapshot(path: Path | str) -> NormalizedSnapshot:
    """Load and normalize a snapshot from any supported format."""
    return NormalizedSnapshot.from_file(path)
