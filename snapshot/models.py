"""Snapshot data models for semver-dredd.

This module contains the language-agnostic data classes used to represent
API snapshots, as well as the ``SnapshotDiff`` result type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Well-known UUID for the built-in NormalizedSnapshot format.
# Generated via uuid5(NAMESPACE_URL, "semver-dredd:NormalizedSnapshot")
NORMALIZED_SNAPSHOT_TYPE_ID = "d4e5f6a7-1234-5678-9abc-def012345678"


# ---------------------------------------------------------------------------
# Primitive value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Parameter:
    """A function/method parameter."""

    name: str
    type: str
    optional: bool = False


@dataclass(frozen=True)
class Field:
    """A struct/class field."""

    name: str
    type: str
    optional: bool = False


# ---------------------------------------------------------------------------
# Composite value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionSignature:
    """A function or method signature."""

    name: str
    parameters: tuple[Parameter, ...]
    returns: tuple[Parameter, ...] = ()

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> FunctionSignature:
        """Create from YAML dict (supports v1 and v2 formats)."""
        params_data = data.get("parameters", [])
        params: list[Parameter] = []

        if params_data:
            if isinstance(params_data[0], dict):
                for p in params_data:
                    params.append(Parameter(
                        name=p.get("name", ""),
                        type=p.get("type", "unknown"),
                        optional=p.get("optional", False),
                    ))
            else:
                defaults_count = data.get("defaults_count", 0)
                total = len(params_data)
                for i, p in enumerate(params_data):
                    params.append(Parameter(
                        name=p,
                        type="unknown",
                        optional=i >= total - defaults_count,
                    ))

        returns_data = data.get("returns", [])
        returns: list[Parameter] = []
        for r in returns_data:
            if isinstance(r, dict):
                returns.append(Parameter(
                    name=r.get("name", ""),
                    type=r.get("type", "unknown"),
                    optional=r.get("optional", False),
                ))

        return cls(name=name, parameters=tuple(params), returns=tuple(returns))


@dataclass(frozen=True)
class TypeDefinition:
    """A type (class/struct/interface/record) definition."""

    name: str
    fields: tuple[Field, ...]
    methods: dict[str, FunctionSignature]

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> TypeDefinition:
        """Create from YAML dict (supports v1 and v2 formats)."""
        fields_data = data.get("fields", [])
        fields: list[Field] = []
        if fields_data:
            if isinstance(fields_data[0], dict):
                for f in fields_data:
                    fields.append(Field(
                        name=f.get("name", ""),
                        type=f.get("type", "unknown"),
                        optional=f.get("optional", False),
                    ))
            else:
                for f in fields_data:
                    fields.append(Field(name=f, type="unknown"))

        methods_data = data.get("methods", {})
        methods = {
            mn: FunctionSignature.from_dict(mn, md)
            for mn, md in methods_data.items()
        }

        return cls(
            name=name,
            fields=tuple(sorted(fields, key=lambda f: f.name)),
            methods=methods,
        )


# ---------------------------------------------------------------------------
# SnapshotDiff
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SnapshotDiff:
    """Detailed diff between two snapshots."""

    breaking: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.breaking or self.added)


# ---------------------------------------------------------------------------
# NormalizedSnapshot
# ---------------------------------------------------------------------------

@dataclass
class NormalizedSnapshot:
    """Language-agnostic normalized API snapshot.

    This is the **default** snapshot format shipped with semver-dredd.
    Plugins may provide their own format by implementing the
    :class:`~snapshot.protocols.SnapshotFormat` protocol and registering
    it with a unique UUID.
    """

    SNAPSHOT_TYPE_ID: str = NORMALIZED_SNAPSHOT_TYPE_ID

    schema_version: int = 2
    version: str = ""
    language: str = ""
    source_kind: str = ""
    source_path: str = ""
    functions: dict[str, FunctionSignature] = field(default_factory=dict)
    types: dict[str, TypeDefinition] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> NormalizedSnapshot:
        """Parse YAML string into normalized snapshot."""
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> NormalizedSnapshot:
        """Load snapshot from file."""
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> NormalizedSnapshot:
        schema_version = data.get("schema_version", 1)
        language = data.get("language", "python")

        source = data.get("source", {})
        source_kind = source.get("kind", "")
        source_path = source.get("path", "")

        api = data.get("api", {})

        functions_data = api.get("functions", {})
        functions = {
            n: FunctionSignature.from_dict(n, d)
            for n, d in functions_data.items()
        }

        types_data = api.get("types", api.get("classes", {}))
        types = {
            n: TypeDefinition.from_dict(n, d)
            for n, d in types_data.items()
        }

        return cls(
            schema_version=schema_version,
            version=data.get("version", ""),
            language=language,
            source_kind=source_kind,
            source_path=source_path,
            functions=functions,
            types=types,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
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

        result: dict[str, Any] = {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
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
        return result

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.to_yaml())
