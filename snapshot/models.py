"""Backward-compatibility shim — canonical home is semverdredd.models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from snapshot.protocols import DiffResult

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
                    params.append(
                        Parameter(
                            name=p.get("name", ""),
                            type=p.get("type", "unknown"),
                            optional=p.get("optional", False),
                        )
                    )
            else:
                defaults_count = data.get("defaults_count", 0)
                total = len(params_data)
                for i, p in enumerate(params_data):
                    params.append(
                        Parameter(
                            name=p,
                            type="unknown",
                            optional=i >= total - defaults_count,
                        )
                    )

        returns_data = data.get("returns", [])
        returns: list[Parameter] = []
        for r in returns_data:
            if isinstance(r, dict):
                returns.append(
                    Parameter(
                        name=r.get("name", ""),
                        type=r.get("type", "unknown"),
                        optional=r.get("optional", False),
                    )
                )

        return cls(name=name, parameters=tuple(params), returns=tuple(returns))

    def diff_against(self, other: "FunctionSignature") -> "DiffResult":
        """Compare this signature against *other* and return a relative DiffResult."""
        from snapshot.change_kind import ChangeKind
        from snapshot.protocols import DiffResult

        breaking: list[str] = []
        added: list[str] = []

        old_params = self.parameters
        new_params = other.parameters

        old_required = sum(1 for p in old_params if not p.optional)
        new_required = sum(1 for p in new_params if not p.optional)

        is_breaking = False

        # More required params → breaking
        if new_required > old_required:
            breaking.append(
                f"requires more parameters ({old_required} -> {new_required})"
            )
            is_breaking = True

        # Fewer total params (removed) → breaking
        if len(new_params) < len(old_params):
            breaking.append(
                f"parameters removed ({len(old_params)} -> {len(new_params)})"
            )
            is_breaking = True

        # More total params with same or fewer required → additive
        if len(new_params) > len(old_params) and new_required <= old_required:
            added.append(
                f"new optional parameters added ({len(old_params)} -> {len(new_params)})"
            )

        # Fewer required (more defaults) → additive
        if new_required < old_required and not is_breaking:
            added.append(
                f"fewer required parameters ({old_required} -> {new_required})"
            )

        # Check parameter type / optionality changes
        min_params = min(len(old_params), len(new_params))
        for i in range(min_params):
            old_p = old_params[i]
            new_p = new_params[i]

            if (
                old_p.type != new_p.type
                and old_p.type != "unknown"
                and new_p.type != "unknown"
            ):
                breaking.append(
                    f"parameter '{old_p.name}' type changed: {old_p.type} -> {new_p.type}"
                )
                is_breaking = True

            if old_p.optional and not new_p.optional:
                breaking.append(
                    f"parameter '{old_p.name}' changed from optional to required"
                )
                is_breaking = True

        # Check return type changes
        if self.returns and other.returns:
            old_ret = self.returns[0]
            new_ret = other.returns[0]
            if (
                old_ret.type != new_ret.type
                and old_ret.type != "unknown"
                and new_ret.type != "unknown"
            ):
                breaking.append(
                    f"return type changed: {old_ret.type} -> {new_ret.type}"
                )
                is_breaking = True
        elif self.returns and not other.returns:
            breaking.append("return value removed")
            is_breaking = True

        if breaking:
            change = ChangeKind.BREAKING
        elif added:
            change = ChangeKind.MINOR
        else:
            change = ChangeKind.NONE

        return DiffResult(
            change_kind=change,
            breaking=tuple(breaking),
            added=tuple(added),
        )


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
                    fields.append(
                        Field(
                            name=f.get("name", ""),
                            type=f.get("type", "unknown"),
                            optional=f.get("optional", False),
                        )
                    )
            else:
                for f in fields_data:
                    fields.append(Field(name=f, type="unknown"))

        methods_data = data.get("methods", {})
        methods = {
            mn: FunctionSignature.from_dict(mn, md) for mn, md in methods_data.items()
        }

        return cls(
            name=name,
            fields=tuple(sorted(fields, key=lambda f: f.name)),
            methods=methods,
        )

    def diff_against(self, other: "TypeDefinition") -> "DiffResult":
        """Compare this type definition against *other* and return a relative DiffResult."""
        from snapshot.change_kind import ChangeKind
        from snapshot.protocols import DiffResult

        breaking: list[str] = []
        added: list[str] = []

        # --- Fields ---
        old_fields = {f.name: f for f in self.fields}
        new_fields = {f.name: f for f in other.fields}

        for field_name in sorted(set(old_fields) - set(new_fields)):
            breaking.append(f"field removed: {field_name}")

        for field_name in sorted(set(new_fields) - set(old_fields)):
            added.append(f"field added: {field_name}")

        for field_name in sorted(set(old_fields) & set(new_fields)):
            if old_fields[field_name].type != new_fields[field_name].type:
                breaking.append(
                    f"field {field_name} type changed: "
                    f"{old_fields[field_name].type} -> {new_fields[field_name].type}"
                )

        # --- Methods ---
        old_methods = self.methods
        new_methods = other.methods

        for method_name in sorted(set(old_methods) - set(new_methods)):
            breaking.append(f"method removed: {method_name}")

        for method_name in sorted(set(new_methods) - set(old_methods)):
            added.append(f"method added: {method_name}")

        for method_name in sorted(set(old_methods) & set(new_methods)):
            result = old_methods[method_name].diff_against(new_methods[method_name])
            breaking.extend(f"method {method_name}: {b}" for b in result.breaking)
            added.extend(f"method {method_name}: {a}" for a in result.added)

        if breaking:
            change = ChangeKind.BREAKING
        elif added:
            change = ChangeKind.MINOR
        else:
            change = ChangeKind.NONE

        return DiffResult(
            change_kind=change,
            breaking=tuple(breaking),
            added=tuple(added),
        )


# ---------------------------------------------------------------------------
# Generator provenance block
# ---------------------------------------------------------------------------


@dataclass
class GeneratorInfo:
    """Stable snapshot provenance block written into new snapshots.

    Keys are deliberately minimal. Absent keys are represented as empty string
    so older snapshots that pre-date the block can be loaded without error.

    ``plugin_name``    — plugin.name property value, e.g. "python".
    ``plugin_version`` — plugin.version property value when discoverable.
    ``plugin_source``  — PluginInfo.origin: "entry_point" | "builtin" | "user_dir" | "manual".
    ``config_path``    — selected config file path, empty when absent.
    ``candidate_index``— candidate document index (int) selected from a
                        multi-document config; -1 for single-document configs.
    """

    plugin_name: str = ""
    plugin_version: str = ""
    plugin_source: str = ""
    config_path: str = ""
    candidate_index: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "plugin_source": self.plugin_source,
            "config_path": self.config_path,
            "candidate_index": self.candidate_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratorInfo":
        return cls(
            plugin_name=str(data.get("plugin_name", "")),
            plugin_version=str(data.get("plugin_version", "")),
            plugin_source=str(data.get("plugin_source", "")),
            config_path=str(data.get("config_path", "")),
            candidate_index=int(data.get("candidate_index", -1)),
        )


# ---------------------------------------------------------------------------
# NormalizedSnapshot
# ---------------------------------------------------------------------------
@dataclass
class NormalizedSnapshot:
    """Language-agnostic normalized API snapshot.

    This is the **default** snapshot format bundled with semver-dredd.
    Plugins may provide their own format by implementing the
    :class:`~semverdredd.protocols.SnapshotFormat` protocol and registering
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
    # Provenance block — absent in older snapshots; default=None for back-compat.
    generator: GeneratorInfo | None = None

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
            n: FunctionSignature.from_dict(n, d) for n, d in functions_data.items()
        }

        types_data = api.get("types", api.get("classes", {}))
        types = {n: TypeDefinition.from_dict(n, d) for n, d in types_data.items()}

        # Deserialize generator block — absent in older snapshots (back-compat).
        generator_data = data.get("generator")
        generator: GeneratorInfo | None = None
        if isinstance(generator_data, dict):
            generator = GeneratorInfo.from_dict(generator_data)

        return cls(
            schema_version=schema_version,
            version=data.get("version", ""),
            language=language,
            source_kind=source_kind,
            source_path=source_path,
            functions=functions,
            types=types,
            generator=generator,
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
        # Include generator block when present (omit for older serialized snapshots).
        if self.generator is not None:
            result["generator"] = self.generator.to_dict()
        return result

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.to_yaml())

    def diff_against(self, other: "NormalizedSnapshot") -> "DiffResult":
        """Compare this snapshot against *other* and return a DiffResult.

        Implements :class:`~snapshot.protocols.Comparable`.  All knowledge of
        the internal collections (functions / types) lives here so the diff
        engine stays language-agnostic.
        """
        from snapshot.change_kind import ChangeKind
        from snapshot.protocols import DiffResult

        breaking: list[str] = []
        added: list[str] = []

        # --- Functions ---
        old_fns, new_fns = self.functions, other.functions

        for name in sorted(set(old_fns) - set(new_fns)):
            breaking.append(f"function removed: {name}")

        for name in sorted(set(new_fns) - set(old_fns)):
            added.append(f"function added: {name}")

        for name in sorted(set(old_fns) & set(new_fns)):
            result = old_fns[name].diff_against(new_fns[name])
            breaking.extend(f"function {name}: {b}" for b in result.breaking)
            added.extend(f"function {name}: {a}" for a in result.added)

        # --- Types ---
        old_types, new_types = self.types, other.types

        for name in sorted(set(old_types) - set(new_types)):
            breaking.append(f"type removed: {name}")

        for name in sorted(set(new_types) - set(old_types)):
            added.append(f"type added: {name}")

        for name in sorted(set(old_types) & set(new_types)):
            result = old_types[name].diff_against(new_types[name])
            breaking.extend(f"type {name}: {b}" for b in result.breaking)
            added.extend(f"type {name}: {a}" for a in result.added)

        if breaking:
            change = ChangeKind.BREAKING
        elif added:
            change = ChangeKind.MINOR
        else:
            change = ChangeKind.NONE

        return DiffResult(
            change_kind=change,
            breaking=tuple(breaking),
            added=tuple(added),
        )
