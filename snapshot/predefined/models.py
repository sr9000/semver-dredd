"""Predefined snapshot component models for semver-dredd.

These dataclasses represent the building blocks of a public API snapshot.
Each leaf type carries a ``SNAPSHOT_TYPE_ID`` UUID so it can be stored and
retrieved via the :class:`~semverdredd.registry.SnapshotRegistry`.

UUIDs are generated via::

    uuid.uuid5(uuid.NAMESPACE_URL, "semver-dredd:predefined:<ClassName>")

Hierarchy
---------
* :class:`Variable`    -- a named value (field, constant, parameter with default)
* :class:`Argument`    -- a function argument (same shape as Variable)
* :class:`Function`    -- a callable: name + return type + args
* :class:`ClassField`  -- a class/struct field (same shape as Variable)
* :class:`ClassMethod` -- a class method (same shape as Function)

Language-specific argument types (e.g. ``PythonArgument``) live in their
respective language plugins.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# UUID helpers
# ---------------------------------------------------------------------------
_NS = uuid.NAMESPACE_URL


def _uid(name: str) -> str:
    return str(uuid.uuid5(_NS, f"semver-dredd:predefined:{name}"))


# ---------------------------------------------------------------------------
# Variable
# ---------------------------------------------------------------------------
VARIABLE_TYPE_ID = _uid("Variable")


@dataclass(frozen=True)
class Variable:
    """A named variable / constant with an optional default value."""

    SNAPSHOT_TYPE_ID: str = VARIABLE_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Variable":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "Variable":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Variable":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# Argument
# ---------------------------------------------------------------------------
ARGUMENT_TYPE_ID = _uid("Argument")


@dataclass(frozen=True)
class Argument:
    """A function argument -- same attributes as Variable."""

    SNAPSHOT_TYPE_ID: str = ARGUMENT_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Argument":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "Argument":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Argument":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# Function
# ---------------------------------------------------------------------------
FUNCTION_TYPE_ID = _uid("Function")


@dataclass(frozen=True)
class Function:
    """A standalone function or static method.

    ``args`` holds :class:`Argument` instances.  Language plugins that need
    richer argument metadata (e.g. ``PythonArgument``) may pass their own
    argument subtype here -- Python duck typing ensures runtime compatibility.
    """

    SNAPSHOT_TYPE_ID: str = FUNCTION_TYPE_ID

    name: str = ""
    result_type: str = "void"
    args: tuple[Argument, ...] = ()

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "result_type": self.result_type,
            "args": [_arg_to_dict(a) for a in self.args],
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "Function":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "Function":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Function":
        return cls(
            name=data.get("name", ""),
            result_type=data.get("result_type", "void"),
            args=tuple(_arg_from_dict(a) for a in data.get("args", [])),
        )


# ---------------------------------------------------------------------------
# ClassField
# ---------------------------------------------------------------------------
CLASS_FIELD_TYPE_ID = _uid("ClassField")


@dataclass(frozen=True)
class ClassField:
    """A public field of a class or struct -- same shape as Variable."""

    SNAPSHOT_TYPE_ID: str = CLASS_FIELD_TYPE_ID

    name: str = ""
    type: str = "unknown"
    default: str | None = None

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "type": self.type,
            "default": self.default,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "ClassField":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "ClassField":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassField":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "unknown"),
            default=data.get("default"),
        )


# ---------------------------------------------------------------------------
# ClassMethod
# ---------------------------------------------------------------------------
CLASS_METHOD_TYPE_ID = _uid("ClassMethod")


@dataclass(frozen=True)
class ClassMethod:
    """A public method of a class -- same shape as Function."""

    SNAPSHOT_TYPE_ID: str = CLASS_METHOD_TYPE_ID

    name: str = ""
    result_type: str = "void"
    args: tuple[Argument, ...] = ()

    @property
    def version(self) -> str:
        return "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_type_id": self.SNAPSHOT_TYPE_ID,
            "name": self.name,
            "result_type": self.result_type,
            "args": [_arg_to_dict(a) for a in self.args],
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "ClassMethod":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "ClassMethod":
        return cls.from_yaml_str(Path(path).read_text())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassMethod":
        return cls(
            name=data.get("name", ""),
            result_type=data.get("result_type", "void"),
            args=tuple(_arg_from_dict(a) for a in data.get("args", [])),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _arg_to_dict(arg: Argument) -> dict[str, Any]:
    """Serialize an argument to a plain dict (strips snapshot_type_id)."""
    d = arg.to_dict()
    d.pop("snapshot_type_id", None)
    return d


def _arg_from_dict(data: dict[str, Any]) -> Argument:
    """Deserialize an argument dict into an Argument."""
    return Argument.from_dict(data)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

ALL_TYPE_IDS: dict[str, str] = {
    "Variable": VARIABLE_TYPE_ID,
    "Argument": ARGUMENT_TYPE_ID,
    "Function": FUNCTION_TYPE_ID,
    "ClassField": CLASS_FIELD_TYPE_ID,
    "ClassMethod": CLASS_METHOD_TYPE_ID,
}

ALL_CLASSES: list[type] = [
    Variable,
    Argument,
    Function,
    ClassField,
    ClassMethod,
]
